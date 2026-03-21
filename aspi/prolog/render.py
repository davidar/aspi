"""Prolog term and goal rendering."""

from aspi.prolog.ast import (
    PTerm, PVar, PAtom, PNum, PStr, PCompound, PArith,
    GCall, GUnify, GIs, GCompare, GBetween, GNot, GFindAll, GBagOf, GWhen, GRaw,
)
from aspi.prolog.analysis import term_vars, goal_needs_ground


_ARITH_PREC = {'+': 1, '-': 1, '*': 2, '//': 2, 'mod': 2, '^': 3}

_parse_counter = [0]
def _fresh_var() -> str:
    _parse_counter[0] += 1
    return f'G{chr(64 + (_parse_counter[0] % 26))}'


def render_term(t: PTerm) -> str:
    match t:
        case PVar(name): return name
        case PAtom(name): return name
        case PNum(value): return str(value)
        case PStr(value): return f'"{value}"'
        case PCompound('[', args):
            return f'[{", ".join(render_term(a) for a in args)}]'
        case PCompound(f, args):
            return f'{f}({", ".join(render_term(a) for a in args)})'
        case PArith(op, left, right):
            ls = render_term(left)
            rs = render_term(right)
            lp = _ARITH_PREC.get(op, 0)
            if isinstance(left, PArith) and _ARITH_PREC.get(left.op, 0) < lp:
                ls = f'({ls})'
            if isinstance(right, PArith) and _ARITH_PREC.get(right.op, 0) <= lp:
                rs = f'({rs})'
            return f'{ls} {op} {rs}'
    return str(t)


def _render_call_extracting_arith(f: str, args: tuple) -> str:
    """Render a call, extracting PArith/range args into is/between right before the call."""
    new_args = []
    pre = []
    for arg in args:
        if isinstance(arg, PArith):
            v = PVar(_fresh_var())
            pre.append(render_goal(GIs(v, arg)))
            new_args.append(v)
        elif isinstance(arg, PCompound) and arg.functor == '..':
            v = PVar(_fresh_var())
            pre.append(render_goal(GBetween(arg.args[0], arg.args[1], v)))
            new_args.append(v)
        else:
            new_args.append(arg)
    call = render_term(PCompound(f, tuple(new_args)))
    if pre:
        return ', '.join(pre + [call])
    return call


def render_goal(g) -> str:
    # Bidirectional builtins: wrap with when(ground(A) ; ground(B), ...)
    _BIDIRECTIONAL = {'atom_chars', 'atom_number', 'term_to_atom'}
    match g:
        case GCall(PCompound(f, args)) if f in _BIDIRECTIONAL and len(args) == 2:
            a_vars = term_vars(args[0])
            b_vars = term_vars(args[1])
            if a_vars and b_vars:
                a_cond = ','.join(sorted(a_vars))
                b_cond = ','.join(sorted(b_vars))
                inner = _render_goal_no_autowrap(g)
                return f'when((ground(({a_cond})) ; ground(({b_cond}))), ({inner}))'
        case _: pass

    # Auto-wrap directional goals in when/2 if they have unground input vars
    needs = goal_needs_ground(g)
    if needs and not isinstance(g, (GNot, GWhen, GRaw)):
        return render_goal(GWhen(needs, g))

    match g:
        case GCall(PCompound(f, args)) if any(
            isinstance(a, PArith) or (isinstance(a, PCompound) and a.functor == '..')
            for a in args
        ):
            return _render_call_extracting_arith(f, args)
        case GCall(term): return render_term(term)
        case GUnify(l, PCompound('..', (lo, hi))):
            return render_goal(GBetween(lo, hi, l))
        case GUnify(PCompound('..', (lo, hi)), r):
            return render_goal(GBetween(lo, hi, r))
        case GUnify(l, r) if isinstance(r, PArith):
            return render_goal(GIs(l, r))
        case GUnify(l, r) if isinstance(l, PArith):
            return render_goal(GIs(r, l))
        case GUnify(l, r): return f'{render_term(l)} = {render_term(r)}'
        case GIs(target, expr): return f'{render_term(target)} is {render_term(expr)}'
        case GCompare(op, l, r): return f'{render_term(l)} {op} {render_term(r)}'
        case GBetween(lo, hi, var):
            pre = []
            if isinstance(lo, PArith):
                v = PVar(_fresh_var())
                pre.append(render_goal(GIs(v, lo)))
                lo = v
            if isinstance(hi, PArith):
                v = PVar(_fresh_var())
                pre.append(render_goal(GIs(v, hi)))
                hi = v
            bt = f'between({render_term(lo)}, {render_term(hi)}, {render_term(var)})'
            return ', '.join(pre + [bt]) if pre else bt
        case GNot(goals):
            inner = render_body(goals)
            return f'\\+ ({inner})' if len(goals) > 1 else f'\\+ {inner}'
        case GFindAll(t, gs, r):
            return f'findall({render_term(t)}, ({render_body(gs)}), {render_term(r)})'
        case GBagOf(t, gs, r):
            return f'bagof({render_term(t)}, ({render_body(gs)}), {render_term(r)})'
        case GWhen(vars, goal):
            inner = _render_goal_no_autowrap(goal)
            sv = sorted(vars)
            if len(sv) == 1:
                return f'when(ground({sv[0]}), ({inner}))'
            return f'when(ground(({",".join(sv)})), ({inner}))'
        case GRaw(text): return text
    raise TypeError(f'render_goal: unhandled goal type: {type(g).__name__}: {g!r}')


def _render_goal_no_autowrap(g) -> str:
    """Render without auto-wrapping (used inside GWhen)."""
    match g:
        case GCall(PCompound(f, args)) if any(
            isinstance(a, PArith) or (isinstance(a, PCompound) and a.functor == '..')
            for a in args
        ):
            return _render_call_extracting_arith(f, args)
        case GCall(term): return render_term(term)
        case GUnify(l, PCompound('..', (lo, hi))):
            return _render_goal_no_autowrap(GBetween(lo, hi, l))
        case GUnify(PCompound('..', (lo, hi)), r):
            return _render_goal_no_autowrap(GBetween(lo, hi, r))
        case GUnify(l, r): return f'{render_term(l)} = {render_term(r)}'
        case GIs(target, expr): return f'{render_term(target)} is {render_term(expr)}'
        case GCompare(op, l, r): return f'{render_term(l)} {op} {render_term(r)}'
        case GBetween(lo, hi, var):
            pre = []
            if isinstance(lo, PArith):
                v = PVar(_fresh_var())
                pre.append(render_goal(GIs(v, lo)))
                lo = v
            if isinstance(hi, PArith):
                v = PVar(_fresh_var())
                pre.append(render_goal(GIs(v, hi)))
                hi = v
            bt = f'between({render_term(lo)}, {render_term(hi)}, {render_term(var)})'
            return ', '.join(pre + [bt]) if pre else bt
        case GNot(goals):
            inner = render_body(goals)
            return f'\\+ ({inner})' if len(goals) > 1 else f'\\+ {inner}'
        case GFindAll(t, gs, r):
            return f'findall({render_term(t)}, ({render_body(gs)}), {render_term(r)})'
        case GBagOf(t, gs, r):
            return f'bagof({render_term(t)}, ({render_body(gs)}), {render_term(r)})'
        case GRaw(text): return text
    raise TypeError(f'_render_goal_no_autowrap: unhandled: {type(g).__name__}: {g!r}')


def _flatten_goals(goals: list) -> list:
    """Flatten nested goal lists."""
    result = []
    for g in goals:
        if isinstance(g, list):
            result.extend(_flatten_goals(g))
        else:
            result.append(g)
    return result


def render_body(goals: list) -> str:
    return ', '.join(render_goal(g) for g in _flatten_goals(goals))


def _render_body_no_autowrap(goals: list) -> str:
    """Render body goals without auto-wrapping (for inside findall/bagof)."""
    return ', '.join(_render_goal_no_autowrap(g) for g in _flatten_goals(goals))
