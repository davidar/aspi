#!/usr/bin/env python3
"""Prolog backend for aspi — replaces clingo with SWI-Prolog + tabling."""

import lark
import os
import re
import string
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple, Union

import ldcs


# ── Prolog AST ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PVar:
    name: str

@dataclass(frozen=True)
class PAtom:
    name: str

@dataclass(frozen=True)
class PNum:
    value: int | float

@dataclass(frozen=True)
class PStr:
    value: str

@dataclass(frozen=True)
class PCompound:
    functor: str
    args: tuple  # of PTerm

@dataclass(frozen=True)
class PArith:
    op: str
    left: 'PTerm'
    right: 'PTerm'

PTerm = PVar | PAtom | PNum | PStr | PCompound | PArith

def _no_str(self):
    raise TypeError(f'{type(self).__name__} was converted to str — use render_term() instead.\n{self!r}')

for _cls in (PVar, PAtom, PNum, PStr, PCompound, PArith):
    _cls.__str__ = _no_str
    _cls.__format__ = lambda self, spec: _no_str(self)


@dataclass
class GCall:
    term: PTerm

@dataclass
class GUnify:
    left: PTerm
    right: PTerm

@dataclass
class GIs:
    target: PTerm
    expr: PTerm

@dataclass
class GCompare:
    op: str
    left: PTerm
    right: PTerm

@dataclass
class GBetween:
    lo: PTerm
    hi: PTerm
    var: PTerm

@dataclass
class GNot:
    goals: list

@dataclass
class GFindAll:
    template: PTerm
    goals: list
    result: PTerm

@dataclass
class GBagOf:
    template: PTerm
    goals: list
    result: PTerm

@dataclass
class GWhen:
    vars: set
    goal: 'PGoal'

@dataclass
class GRaw:
    text: str

PGoal = GCall | GUnify | GIs | GCompare | GBetween | GNot | GFindAll | GBagOf | GWhen | GRaw

# Internal types for PrologLDCS
PBody = List[PGoal]
PCSym = Tuple[PTerm, PBody]
PUnary = Callable[[PTerm], PBody]


# ── Render ────────────────────────────────────────────────────────────────────

_ARITH_PREC = {'+': 1, '-': 1, '*': 2, '//': 2, 'mod': 2, '^': 3}


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
            pre.append(render_goal(GIs(v, arg)))  # render_goal auto-wraps in when/2
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


def render_goal(g: PGoal) -> str:
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


def _render_goal_no_autowrap(g: PGoal) -> str:
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



# ── AST analysis ──────────────────────────────────────────────────────────────

def term_vars(t: PTerm) -> set:
    match t:
        case PVar(name): return {name}
        case PArith(_, l, r): return term_vars(l) | term_vars(r)
        case PCompound(_, args):
            return set().union(*(term_vars(a) for a in args)) if args else set()
        case _: return set()


def goal_vars(g: PGoal) -> set:
    match g:
        case GCall(term): return term_vars(term)
        case GUnify(l, r): return term_vars(l) | term_vars(r)
        case GIs(target, expr): return term_vars(target) | term_vars(expr)
        case GCompare(_, l, r): return term_vars(l) | term_vars(r)
        case GBetween(lo, hi, var): return term_vars(lo) | term_vars(hi) | term_vars(var)
        case GNot(goals): return set().union(*(goal_vars(g2) for g2 in goals))
        case GFindAll(t, gs, r):
            return term_vars(t) | set().union(*(goal_vars(g2) for g2 in gs)) | term_vars(r)
        case GBagOf(t, gs, r):
            return term_vars(t) | set().union(*(goal_vars(g2) for g2 in gs)) | term_vars(r)
        case GWhen(_, goal): return goal_vars(goal)
        case GRaw(text):
            return set(re.findall(r'\b([A-Z]\w*)\b', re.sub(r'"[^"]*"', '', text)))
    return set()


_DIRECTIONAL = {
    'between': ({0, 1}, {2}),
    'sort': ({0}, {1}), 'msort': ({0}, {1}),
    'sum_list': ({0}, {1}), 'min_list': ({0}, {1}), 'max_list': ({0}, {1}),
    'length': ({0}, {1}), 'product_of': ({0}, {1}),
    'atom_length': ({0}, {1}),
    'atom_concat': ({0, 1}, {2}),
    'char_code': ({0}, {1}), 'sub_atom': ({0}, {1, 2, 3, 4}),
    'member': (set(), {0}),
    'permutation': ({0}, {1}), 'reverse': ({0}, {1}),
}


def goal_needs_ground(g: PGoal) -> set:
    match g:
        case GIs(_, expr): return term_vars(expr)
        case GCompare(_, l, r): return term_vars(l) | term_vars(r)
        case GBetween(lo, hi, _): return term_vars(lo) | term_vars(hi)
        case GNot(goals): return set().union(*(goal_vars(g2) for g2 in goals))
        case GCall(PCompound(f, args)) if f in _DIRECTIONAL:
            input_idxs = _DIRECTIONAL[f][0]
            return set().union(*(term_vars(args[i]) for i in input_idxs if i < len(args)))
        case GCall(PCompound('forall', args)) if len(args) == 2:
            # forall(Generator, Test): needs free vars in Test that aren't bound by Generator
            gen_vars = goal_vars(GCall(args[0])) if isinstance(args[0], PTerm) else set()
            test_vars = goal_vars(GRaw(render_term(args[1]))) if isinstance(args[1], PTerm) else set()
            return test_vars - gen_vars
        case GFindAll(_, gs, _):
            inner = set().union(*(goal_vars(g2) for g2 in gs))
            return {v for v in inner if v.startswith('Mu')}
        case GWhen(_, _): return set()
        case GRaw(text):
            # Minimal fallback for raw strings
            m = re.match(r'(\w+) is (.+)', text)
            if m: return set(re.findall(r'\b([A-Z]\w*)\b', m.group(2)))
            if text.startswith('\\+ ') or text.startswith('\\+('):
                return set(re.findall(r'\b([A-Z]\w*)\b', text))
            for op in (' < ', ' > ', ' <= ', ' >= ', ' =:= ', ' =\\= '):
                if op in text:
                    return set(re.findall(r'\b([A-Z]\w*)\b', text))
            return set()
    return set()


def goal_binds(g: PGoal) -> set:
    match g:
        case GIs(PVar(name), _): return {name}
        case GBetween(_, _, PVar(name)): return {name}
        case GFindAll(_, _, PVar(name)): return {name}
        case GBagOf(_, _, PVar(name)): return {name}
        case GUnify(PVar(name), r): return {name} | term_vars(r)
        case GUnify(l, PVar(name)): return {name} | term_vars(l)
        case GCall(PCompound(f, args)) if f in _DIRECTIONAL:
            output_idxs = _DIRECTIONAL[f][1]
            return set().union(*(term_vars(args[i]) for i in output_idxs if i < len(args)))
        case GCall(PCompound(f, args)) if f not in _DIRECTIONAL:
            # User predicates: conservatively assume they ground their vars
            # but only if they have a single output-like variable
            return term_vars(PCompound(f, args))
        case GWhen(_, goal): return goal_binds(goal)
        case GRaw(text):
            m = re.match(r'(\w+) is ', text)
            if m and m.group(1)[0].isupper(): return {m.group(1)}
            m = re.match(r'(\w+)\(', text)
            if m and m.group(1) not in _DIRECTIONAL: return goal_vars(g)
            return set()
    return set()




# ── PrologLDCS ────────────────────────────────────────────────────────────────

def _to_pterm(s: str) -> PTerm:
    """Convert a string value to PTerm. Used at the macro/string boundary."""
    s = s.strip()
    if not s:
        return PAtom('')
    if s.startswith('"') and s.endswith('"'):
        return PStr(s[1:-1])
    if s == '_':
        return PVar('_')
    if s[0].isupper() or s.startswith('Mu'):
        return PVar(s)
    if s.lstrip('-').isdigit():
        return PNum(int(s))
    return PAtom(s)


_parse_counter = [0]
def _fresh_var() -> str:
    _parse_counter[0] += 1
    return f'G{chr(64 + (_parse_counter[0] % 26))}'


@lark.v_args(inline=True)
class _MacroExpander(lark.Transformer):
    """Transform a macro rule tree into PGoals with PTerm substitutions."""

    def __init__(self, subst: dict, gensym, params: list, ldcs_instance=None):
        self.subst = subst  # param_name -> PTerm
        self.gensym = gensym
        self.params = params
        self._ldcs = ldcs_instance

    def head(self, name, *args):
        body = []
        for param, arg in zip(self.params, args):
            if param.startswith('Head'):
                body.append(GUnify(self.var(param), arg))
        return body

    def rule(self, head, *body):
        goals = list(head)
        for b in body:
            if isinstance(b, list):
                goals.extend(b)
            elif isinstance(b, (GCall, GUnify, GIs, GCompare, GBetween, GNot, GFindAll, GBagOf, GWhen, GRaw)):
                goals.append(b)
            elif isinstance(b, PTerm):
                goals.append(GCall(b))
            else:
                raise TypeError(f'MacroExpander.rule: unexpected body item: {type(b).__name__}: {b!r}')
        return goals

    def pred(self, name, *args):
        n = name.name if isinstance(name, PAtom) else name if isinstance(name, str) else render_term(name)
        if not args:
            return PAtom(n)
        compound = PCompound(n, tuple(args))
        # Check if this is an @function assignment (handled by predop)
        # or a macro that needs further expansion
        if hasattr(self, '_ldcs') and f'{n}/{len(args)}' in self._ldcs.macros:
            expanded = self._ldcs.expand_macro(n, *args)
            if isinstance(expanded, list):
                return expanded  # list of PGoal
            if isinstance(expanded, PTerm):
                return expanded
        return compound

    def predop(self, *args):
        # Operator expression: value OP value
        # Filter None args
        parts = [a for a in args if a is not None]
        if len(parts) == 3:
            left, op, right = parts
            op = str(op)
            if op == '\\':
                op = 'mod'
            elif op == '/':
                op = '//'
            elif op == '**':
                op = '^'
            if op == '=':
                if isinstance(right, PArith):
                    return GIs(left, right)
                if isinstance(left, PArith):
                    return GIs(right, left)
                if isinstance(right, PCompound) and right.functor == '..':
                    return GBetween(right.args[0], right.args[1], left)
                # @function assignment: X = @fn(args) -> builtin call
                if isinstance(right, PCompound) and right.functor.startswith('@'):
                    return self._expand_at_function(left, right)
                return GUnify(left, right)
            if op in ('<', '>', '<=', '>='):
                return GCompare(op, left, right)
            if op == '!=':
                return GCompare('\\=', left, right)
            if op == '..':
                return PCompound('..', (left, right))
            # Arithmetic operator
            return PArith(op, left, right)
        if len(parts) == 2:
            # Unary prefix like "not"
            return GNot([parts[1]] if isinstance(parts[1], PGoal) else [GCall(parts[1])])
        return GRaw(' '.join(str(a) for a in parts))

    def var(self, name):
        name = str(name)
        if name not in self.subst:
            self.subst[name] = PVar(self.gensym())
        return self.subst[name]

    def _expand_at_function(self, target, compound):
        """Expand X = @fn(args) into appropriate PGoal(s)."""
        fn = compound.functor[1:]  # strip @
        args = compound.args
        if fn == 'concatenate':
            if len(args) == 2:
                return GCall(PCompound('atom_concat', (args[0], args[1], target)))
            elif len(args) == 3:
                tmp = PVar(self.gensym())
                return [GCall(PCompound('atom_concat', (args[1], args[2], tmp))),
                        GCall(PCompound('atom_concat', (args[0], tmp, target)))]
        if fn == 'substring':
            if len(args) == 3:
                s1 = PVar(self.gensym())
                return [GIs(s1, PArith('-', args[1], PNum(1))),
                        GCall(PCompound('sub_atom', (args[0], s1, args[2], PVar('_'), target)))]
        if fn == 'length':
            return GCall(PCompound('atom_length', (args[0], target)))
        if fn == 'show':
            return GCall(PCompound('term_to_atom', (args[0], target)))
        if fn == 'decimal':
            return GCall(PCompound('atom_number', (args[0], target)))
        if fn == 'codepoint':
            ch = PVar(self.gensym())
            return [GCall(PCompound('atom_chars', (args[0], PCompound('[', (ch,))))),
                    GCall(PCompound('char_code', (ch, target)))]
        if fn == 'reverse':
            c1, c2 = PVar(self.gensym()), PVar(self.gensym())
            return [GCall(PCompound('atom_chars', (args[0], c1))),
                    GCall(PCompound('reverse', (c1, c2))),
                    GCall(PCompound('atom_chars', (target, c2)))]
        if fn == 'productof':
            return GCall(PCompound('product_of', (args[0], target)))
        if fn == 'memberof':
            return GCall(PCompound('member', (target, args[0])))
        if fn == 'permutation':
            c1, c2 = PVar(self.gensym()), PVar(self.gensym())
            return [GCall(PCompound('atom_chars', (args[0], c1))),
                    GCall(PCompound('permutation', (c1, c2))),
                    GCall(PCompound('atom_chars', (target, c2)))]
        if fn == 'enumerateof':
            return GCall(PCompound('nth1', (target, args[0], PVar(self.gensym()))))
        # Unknown @function — keep as raw
        return GRaw(f'{render_term(target)} = {render_term(compound)}')

    def paren(self, val):
        return val

    def __default__(self, data, children, meta):
        # For INT, ESCAPED_STRING, etc.
        if len(children) == 1:
            return children[0]
        return children

    def __default_token__(self, token):
        s = str(token)
        if token.type == 'INT':
            return PNum(int(s))
        if token.type == 'ESCAPED_STRING':
            return PStr(s[1:-1])
        if token.type == 'VARIABLE':
            return s  # keep as string, var() rule will handle lookup
        if token.type == 'ATOM':
            return PAtom(s)
        if token.type == 'OPERATOR':
            return s
        return s


@lark.v_args(inline=True)
class PrologLDCS(ldcs.LDCS):
    """LDCS transformer that produces Prolog AST goals natively.

    Internal types:
      PCSym = (PTerm, PBody)  — a value and its computation goals
      PUnary = PTerm -> PBody — given a result variable, return goals
      Variadic: (*PTerm) -> str|PTerm — predicate call (string for macros)
    """

    def __init__(self) -> None:
        super().__init__()
        self._agg_counter = 0
        self._result_wrapper = None  # 'set' or 'bag' for bare {X}? / {{X}}? queries

    def _gensym_var(self) -> PVar:
        return PVar(self.gensym())

    # ── Atoms and constants ──

    def atom(self, name: str) -> str:
        return name

    def constant(self, c: str) -> PUnary:
        if c in string.ascii_uppercase:
            term = PVar('Mu' + c)
        elif c.startswith('"') and c.endswith('"'):
            term = PStr(c[1:-1])
        elif c.lstrip('-').isdigit():
            term = PNum(int(c))
        else:
            term = PAtom(c)
        return lambda x: [GUnify(x, term)]

    # Direct builtin mappings — replaces lib/macros.ldcs for Prolog backend
    _BUILTINS = {
        'show': lambda self, x, a: [GCall(PCompound('term_to_atom', (a, x)))],
        'concatenate': None,  # handled specially below
        'reverse': lambda self, x, a: (
            lambda c1, c2: [GCall(PCompound('atom_chars', (a, c1))),
                            GCall(PCompound('reverse', (c1, c2))),
                            GCall(PCompound('atom_chars', (x, c2)))]
        )(PVar(self.gensym()), PVar(self.gensym())),
        'length': lambda self, x, a: [GCall(PCompound('atom_length', (a, x)))],
        'decimal': lambda self, x, a: [GCall(PCompound('atom_number', (a, x)))],
        'codepoint': lambda self, x, a: (
            lambda ch: [GCall(PCompound('atom_chars', (a, PCompound('[', (ch,))))),
                        GCall(PCompound('char_code', (ch, x)))]
        )(PVar(self.gensym())),
        'product': lambda self, x, a: [GCall(PCompound('product_of', (a, x)))],
        'count': lambda self, x, a: [GCall(PCompound('length', (a, x)))],
        'sum': lambda self, x, a: [GCall(PCompound('sum_list', (a, x)))],
        'min': lambda self, x, a: [GCall(PCompound('min_list', (a, x)))],
        'max': lambda self, x, a: [GCall(PCompound('max_list', (a, x)))],
        'mean': None,  # handled specially
        'negate': lambda self, x, a: [GIs(x, PArith('-', PNum(0), a))],
        'permutation': lambda self, x, a: (
            lambda c1, c2: [GCall(PCompound('atom_chars', (a, c1))),
                            GCall(PCompound('permutation', (c1, c2))),
                            GCall(PCompound('atom_chars', (x, c2)))]
        )(PVar(self.gensym()), PVar(self.gensym())),
    }

    def func(self, name: str):
        """Returns a Variadic that takes PTerms and returns PTerm or list[PGoal]."""
        def variadic(*args):
            n = len(args)
            # Direct builtin handling (replaces macro indirection)
            if n >= 2 and name in self._BUILTINS and self._BUILTINS[name] is not None:
                return self._BUILTINS[name](self, *args)
            # Range shorthands: n1..n4, z1..z4, i1..i4
            for prefix, lo in [('n', 1), ('z', 0), ('i', None)]:
                for digits in range(1, 5):
                    rname = f'{prefix}{digits}'
                    if name == rname and n >= 1:
                        hi = 10**digits - 1
                        if prefix == 'i':
                            return [GBetween(PNum(-hi), PNum(hi), args[0])]
                        return [GBetween(PNum(lo), PNum(hi), args[0])]
            # Arithmetic predicates
            if name == 'multiple' and n == 2:
                x, y = args
                return [GCompare('=:=', PArith('mod', x, y), PNum(0))]
            if name == 'even' and n == 1:
                return [GCompare('=:=', PArith('mod', args[0], PNum(2)), PNum(0))]
            if name == 'odd' and n == 1:
                return [GCompare('=:=', PArith('mod', args[0], PNum(2)), PNum(1))]
            if name == 'exists' and n == 1:
                return []  # exists(X) is transparent
            # mean: sum/count
            if name == 'mean' and n == 2:
                x, a = args
                s = PVar(self.gensym())
                c = PVar(self.gensym())
                return [GCall(PCompound('sum_list', (a, s))),
                        GCall(PCompound('length', (a, c))),
                        GIs(x, PArith('//', s, c))]
            # concatenate: 2 or 3 source args + result
            if name == 'concatenate':
                if n == 3:
                    x, a, b = args
                    return [GCall(PCompound('atom_concat', (a, b, x)))]
                if n == 4:
                    x, a, b, c = args
                    tmp = PVar(self.gensym())
                    return [GCall(PCompound('atom_concat', (b, c, tmp))),
                            GCall(PCompound('atom_concat', (a, tmp, x)))]
            # substring: special case with 2-arg (iterate chars) and 4-arg forms
            if name == 'substring' and n == 2:
                x, a = args
                s = PVar(self.gensym())
                l = PVar(self.gensym())
                nn = PVar(self.gensym())
                s1 = PVar(self.gensym())
                return [GCall(PCompound('atom_length', (a, nn))),
                        GBetween(PNum(1), nn, s),
                        GIs(s1, PArith('-', s, PNum(1))),
                        GBetween(PNum(0), PArith('-', PArith('+', nn, PNum(1)), s), l),
                        GCall(PCompound('sub_atom', (a, s1, l, PVar('_'), x)))]
            if name == 'substring' and n == 4:
                x, a, s, l = args
                s1 = PVar(self.gensym())
                return [GIs(s1, PArith('-', s, PNum(1))),
                        GCall(PCompound('sub_atom', (a, s1, l, PVar('_'), x)))]
            # Macro expansion (for user-defined macros)
            if f'{name}/{n}' in self.macros:
                params, tree = self.macros[f'{name}/{n}']
                subst = dict(zip(params, args))
                return _MacroExpander(subst, self.gensym, params, ldcs_instance=self).transform(tree)
            elif n == 0:
                return PAtom(name)
            else:
                return PCompound(name, tuple(args))
        return variadic

    # ── Composition ──

    def join(self, rel, *var_bodies) -> PUnary:
        # Set/bag consumed by join — not a bare query
        self._result_wrapper = None
        if getattr(rel, '_prolog_needs_list', False):
            # Superlatives: strip member() and pass list directly
            new_var_bodies = []
            for var, goals in var_bodies:
                # Look for member(VAR, LIST) in goals
                found = False
                for i, g in enumerate(goals):
                    if isinstance(g, GCall) and isinstance(g.term, PCompound) \
                       and g.term.functor == 'member' and len(g.term.args) == 2 \
                       and g.term.args[0] == var:
                        list_var = g.term.args[1]
                        new_goals = goals[:i] + goals[i+1:]
                        new_var_bodies.append((list_var, new_goals))
                        found = True
                        break
                if not found:
                    new_var_bodies.append((var, goals))
            var_bodies = new_var_bodies

        ys = [vb[0] for vb in var_bodies]
        bs = [g for vb in var_bodies for g in vb[1]]
        def unary(x):
            call_result = rel(x, *ys)
            if isinstance(call_result, list):
                goals = call_result
            elif isinstance(call_result, PTerm):
                goals = [GCall(call_result)]
            else:
                raise TypeError(f'join: unexpected call result: {type(call_result).__name__}: {call_result!r}')
            return bs + goals
        return unary

    def reverse_join(self, rel, var_body) -> PUnary:
        return self.join(lambda x, y: rel(y, x), var_body)

    def conj(self, lams) -> PUnary:
        def unary(x):
            positive = []
            negative = []
            for lam in lams:
                result = lam(x)
                if isinstance(result, list):
                    for g in result:
                        (negative if isinstance(g, GNot) else positive).append(g)
                elif isinstance(result, PTerm):
                    positive.append(GCall(result))
                else:
                    raise TypeError(f'conj: unexpected lam result: {type(result).__name__}: {result!r}')
            return positive + negative  # generators before filters
        return unary

    def lams(self, *lams) -> list:
        return list(lams)

    def ldcs(self, lam, cond=None) -> PCSym:
        x = self._gensym_var()
        result = lam(x)
        if isinstance(result, list):
            goals = result
        elif isinstance(result, PTerm):
            goals = [GCall(result)]
        else:
            raise TypeError(f'ldcs: unexpected lam result: {type(result).__name__}: {result!r}')

        cond_goals = []
        if cond:
            cond_goals = cond if isinstance(cond, list) else [cond]

        # Try to simplify: if first goal is GUnify(x, value), extract value
        if goals and isinstance(goals[0], GUnify) and goals[0].left == x:
            value = goals[0].right
            remaining = goals[1:] + cond_goals

            # Don't extract if x appears in remaining goals (they need the binding)
            remaining_vars = set()
            for g in remaining:
                remaining_vars |= goal_vars(g)
            if x.name in remaining_vars:
                return (x, goals + cond_goals)

            # If value is a range, convert to GBetween
            if isinstance(value, PCompound) and value.functor == '..':
                lo, hi = value.args
                return (x, remaining + [GBetween(lo, hi, x)])

            return (value, remaining)

        return (x, goals + cond_goals)

    def disj(self, *lams) -> PUnary:
        if len(lams) == 0:
            return lambda x: []
        if len(lams) == 1:
            return lams[0]
        csyms = [self.ldcs(lam) for lam in lams]
        return self._lifts(csyms, 'disjunction')

    def short_disj(self, *args) -> PUnary:
        csyms = [self.ldcs(arg) for arg in args]
        # Each alternative after the first gets guards for prior alternatives
        guarded = []
        for i, (var, goals) in enumerate(csyms):
            guards = []
            for j in range(i):
                prev_var, prev_goals = csyms[j]
                guards.append(GNot(prev_goals + [GUnify(PVar('_'), prev_var)]))
            guarded.append((var, guards + goals))
        return self._lifts(guarded, 'disjunction')

    # ── Claims and queries ──

    def claim(self, head_body: PCSym, cond=None) -> str:
        value, goals = head_body
        if cond:
            goals = goals + (cond if isinstance(cond, list) else [cond])
        # Extract arithmetic from head: if value is PCompound with PArith args,
        # replace with fresh vars and add GIs goals
        value, extra_goals = self._extract_head_arith_ast(value)
        goals = goals + extra_goals
        head = render_term(value)
        if goals:
            return f'{head} :- {render_body(goals)}'
        return head

    def _extract_head_arith_ast(self, value: PTerm) -> tuple:
        """If value is a PCompound with PArith args, replace with fresh vars."""
        if not isinstance(value, PCompound):
            return value, []
        new_args = []
        extra = []
        for arg in value.args:
            if isinstance(arg, PArith):
                v = self._gensym_var()
                extra.append(GIs(v, arg))
                new_args.append(v)
            elif isinstance(arg, PCompound) and arg.functor == '..':
                v = self._gensym_var()
                extra.append(GBetween(arg.args[0], arg.args[1], v))
                new_args.append(v)
            else:
                new_args.append(arg)
        return PCompound(value.functor, tuple(new_args)), extra

    def reverse_claim(self, cond, head_body: PCSym) -> str:
        return self.claim(head_body, cond)

    def query(self, var_body: PCSym) -> str:
        var, goals = var_body
        # Extract arithmetic from query value
        if isinstance(var, PArith):
            v = self._gensym_var()
            goals = goals + [GIs(v, var)]
            var = v
        head = PCompound('what', (var,))
        if goals:
            return f'{render_term(head)} :- {render_body(goals)}'
        return render_term(head)

    def query_any(self, body) -> None:
        if isinstance(body, list):
            body_str = render_body(body)
        else:
            body_str = render_goal(body) if body else 'true'
        self.rules += [f'yes :- {body_str}.', 'no :- \\+ yes.']

    # ── Operators ──

    def binop(self, a: PCSym, op: str, b: PCSym) -> PCSym:
        val_a, goals_a = a
        val_b, goals_b = b
        if op == '..':
            return (PCompound('..', (val_a, val_b)), goals_a + goals_b)
        if op == '\\':
            op = 'mod'
        elif op == '/':
            op = '//'
        elif op == '**':
            op = '^'
        return (PArith(op, val_a, val_b), goals_a + goals_b)

    def binop_term(self, a: PCSym, op: str, b: PCSym) -> PBody:
        val_a, goals_a = a
        val_b, goals_b = b
        all_goals = goals_a + goals_b
        if op == '=':
            if isinstance(val_b, PCompound) and val_b.functor == '..':
                return all_goals + [GBetween(val_b.args[0], val_b.args[1], val_a)]
            if isinstance(val_b, PArith) and isinstance(val_a, PArith):
                return all_goals + [GCompare('=:=', val_a, val_b)]
            if isinstance(val_b, PArith):
                return all_goals + [GIs(val_a, val_b)]
            if isinstance(val_a, PArith):
                return all_goals + [GIs(val_b, val_a)]
            return all_goals + [GUnify(val_a, val_b)]
        if op == '!=':
            return all_goals + [GCompare('\\=', val_a, val_b)]
        if op in ('<', '>', '<=', '>='):
            return all_goals + [GCompare(op, val_a, val_b)]
        result = self.binop(a, op, b)
        return result[1] + [GRaw(render_term(result[0]))]

    def term(self, name: str, *args: PCSym) -> PBody:
        args = tuple(a for a in args if a is not None)
        if not args:
            return [GCall(PAtom(name))]
        vals = [a[0] for a in args]
        goals = [g for a in args for g in a[1]]
        new_vals = []
        extra = []
        for val in vals:
            if isinstance(val, PArith):
                v = self._gensym_var()
                extra.append(GIs(v, val))
                new_vals.append(v)
            elif isinstance(val, PCompound) and val.functor == '..':
                v = self._gensym_var()
                extra.append(GBetween(val.args[0], val.args[1], v))
                new_vals.append(v)
            else:
                new_vals.append(val)
        # Try macro expansion
        expanded = self.expand_macro(name, *new_vals)
        if isinstance(expanded, list):
            return goals + extra + expanded
        if isinstance(expanded, PTerm):
            return goals + extra + [GCall(expanded)]
        return goals + extra + [GCall(PCompound(name, tuple(new_vals)))]

    def clause(self, *args) -> PBody:
        goals = []
        for arg in args:
            if isinstance(arg, list):
                goals.extend(arg)
            elif isinstance(arg, PTerm):
                goals.append(GCall(arg))
            else:
                raise TypeError(f'clause: unexpected arg type: {type(arg).__name__}: {arg!r}')
        return goals

    def pred(self, name: str, *args) -> PCSym:
        args = tuple(a for a in args if a is not None)
        if not args:
            return (PAtom(name), [])
        vals = [a[0] for a in args]
        goals = [g for a in args for g in a[1]]
        # Extract arithmetic from predicate args
        new_vals = []
        extra_goals = []
        for val in vals:
            if isinstance(val, PArith):
                v = self._gensym_var()
                extra_goals.append(GIs(v, val))
                new_vals.append(v)
            elif isinstance(val, PCompound) and val.functor == '..':
                v = self._gensym_var()
                extra_goals.append(GBetween(val.args[0], val.args[1], v))
                new_vals.append(v)
            else:
                new_vals.append(val)
        return (PCompound(name, tuple(new_vals)), goals + extra_goals)

    def unify(self, pred_body: PCSym) -> PUnary:
        pred, goals = pred_body
        return lambda x: [GUnify(x, pred)] + goals

    def neg(self, var_body: PCSym) -> PUnary:
        lam = self._lift(var_body, 'negation', ground=True)
        return lambda x: [GNot(lam(x))]

    def ineq(self, op: str, var_body: PCSym) -> PUnary:
        var, goals = var_body
        return lambda x: goals + [GCompare(op, x, var)]

    def negative(self, var_body: PCSym) -> PUnary:
        var, goals = var_body
        return lambda x: goals + [GUnify(x, PArith('-', PNum(0), var))]

    def not_term(self, term, lift: bool = False) -> PBody:
        if isinstance(term, list):
            # Lift negation to a helper predicate to properly scope existential vars
            x = self._gensym_var()
            lam = self._lift((x, term), 'negation')
            # Use _ as the value arg since we only test existence
            result = lam(PVar('_'))
            if isinstance(result, list):
                return [GNot(result)]
            return [GNot([GCall(result)])]
        if isinstance(term, PTerm):
            return [GNot([GCall(term)])]
        raise TypeError(f'not_term: unexpected type: {type(term).__name__}: {term!r}')

    # ── Superlatives ──

    def superlative(self, rel, op: str):
        if op == "'":
            return lambda *args: rel(*reversed(args))
        elif op == "'each":
            y = self._gensym_var()
            def handler(x, z):
                inner = rel(x, y)
                if isinstance(inner, list):
                    inner_str = _render_body_no_autowrap(inner)
                elif isinstance(inner, (PCompound, PAtom)):
                    inner_str = render_term(inner)
                else:
                    inner_str = repr(inner)
                return PCompound('forall', (
                    PCompound('member', (y, z)),
                    PAtom(inner_str),
                ))
            handler._prolog_needs_list = True
            return handler
        elif op == "'est":
            y = self._gensym_var()
            y2 = PVar(y.name + '2_')
            def handler(x, z):
                inner = rel(x, y)
                if isinstance(inner, list):
                    inner_str = render_body(inner)
                else:
                    inner_str = str(inner)
                inner2 = inner_str.replace(render_term(y), render_term(y2))
                return PAtom(f'{inner_str}, member({render_term(y)}, {render_term(z)}), '
                             f'\\+ (member({render_term(y2)}, {render_term(z)}), '
                             f'{render_term(y2)} \\= {render_term(y)}, '
                             f'\\+ {inner2})')
            handler._prolog_needs_list = True
            return handler
        elif op == "'th":
            y = self._gensym_var()
            def handler(x, z):
                inner = rel(y)
                if isinstance(inner, list):
                    inner_goals = inner
                elif isinstance(inner, PTerm):
                    inner_goals = [GCall(inner)]
                else:
                    raise TypeError(f'superlative th: unexpected inner type: {type(inner).__name__}: {inner!r}')
                return inner_goals + [GCall(PCompound('nth1', (y, z, x)))]
            handler._prolog_needs_list = True
            return handler
        assert False, f'Unknown superlative: {op}'

    # ── Aggregation ──

    _agg_funcs = {
        'sum': 'sum_list', 'count': 'length', 'min': 'min_list',
        'max': 'max_list', 'product': 'product_of',
    }

    def _get_agg_name(self, a):
        """Check if a is a func wrapping an aggregation name (sum, count, etc.)."""
        if callable(a):
            try:
                result = a()
                name = result.name if isinstance(result, PAtom) else None
                if name and name in self._agg_funcs:
                    return name
            except Exception:
                pass
        return None

    def setof(self, a, b=None) -> PUnary:
        if a is None and b is not None:
            a = b
            b = None
        if b is not None:
            agg_name = self._get_agg_name(a)
            if agg_name and agg_name in self._agg_funcs:
                return self._make_agg(agg_name, b)
            return self.join(a, self.ldcs(self.setof(b)))
        var, goals = a
        self._agg_counter += 1
        tag = self._agg_counter
        list_var = PVar(f'Agg{tag}L_')
        sorted_var = PVar(f'Agg{tag}S_')
        self._result_wrapper = 'set'
        def f(x):
            return [GFindAll(var, goals, list_var),
                    GCall(PCompound('sort', (list_var, sorted_var))),
                    GCall(PCompound('member', (x, sorted_var)))]
        return f

    def bagof(self, a, b=None) -> PUnary:
        if a is None and b is not None:
            a = b
            b = None
        if b is not None:
            agg_name = self._get_agg_name(a)
            if agg_name and agg_name in self._agg_funcs:
                return self._make_agg(agg_name, b, dedup=False)
            return self.join(a, self.ldcs(self.bagof(b)))
        var, goals = a
        self._agg_counter += 1
        tag = self._agg_counter
        # Detect MuVars for grouped aggregation
        all_vars = term_vars(var)
        for g in goals:
            all_vars |= goal_vars(g)
        muvars = {v for v in all_vars if v.startswith('Mu')}
        result_var = PVar(f'Agg{tag}L_')
        self._result_wrapper = 'bag'
        def f(x):
            if muvars:
                return [GBagOf(var, goals, x)]
            return [GFindAll(var, goals, x)]
        return f

    def _make_agg(self, agg_name: str, inner: PCSym, dedup: bool = True) -> PUnary:
        var, goals = inner
        self._agg_counter += 1
        tag = self._agg_counter
        reduce_func = self._agg_funcs[agg_name]
        # Extract arithmetic from template var
        if isinstance(var, PArith):
            eval_var = PVar(f'AggV{tag}_')
            goals = goals + [GIs(eval_var, var)]
            var = eval_var
        list_var = PVar(f'Agg{tag}L_')
        if dedup:
            raw_var = PVar(f'Agg{tag}R_')
            def f(x):
                return [GFindAll(var, goals, raw_var),
                        GCall(PCompound('sort', (raw_var, list_var))),
                        GCall(PCompound(reduce_func, (list_var, x)))]
        else:
            def f(x):
                return [GFindAll(var, goals, list_var),
                        GCall(PCompound(reduce_func, (list_var, x)))]
        return f

    # ── Lift (helper predicates) ──

    def _lift(self, var_body: PCSym, prefix: str, ground: bool = False):
        return self._lifts([var_body], prefix, ground=ground)

    def _lifts(self, var_bodies: list, prefix: str, ground: bool = False):
        """Create helper predicate clauses, return a callable for the call."""
        i = self.counter(prefix)
        # Collect Mu vars for context closure
        all_text = []
        for var, goals in var_bodies:
            all_text.append(render_term(var))
            for g in goals:
                all_text.append(render_goal(g))
        muvars = sorted(set(re.findall(r'Mu[A-Z]', ' '.join(all_text))))
        closure = ','.join([str(i)] + muvars)

        def make_call(x):
            return PCompound(prefix, (PAtom(f'({closure})'), x))

        for var, goals in var_bodies:
            head = render_term(make_call(var))
            if goals:
                body = render_body(goals)
                self.rules.append(f'{head} :- {body}.')
            else:
                self.rules.append(f'{head}.')

        return lambda x: [GCall(make_call(x))]

    def lift(self, var_body, prefix: str, **kwargs):
        return self._lift(var_body, prefix, **kwargs)

    def lifts(self, var_bodies, prefix: str, **kwargs):
        return self._lifts(var_bodies, prefix, **kwargs)

    # ── Define and enum ──

    def define(self, heads, var_body: PCSym) -> None:
        var, goals = var_body
        for head in reversed(heads):
            result = head(var)
            if isinstance(result, list):
                # Find the head predicate call (last GCall — join puts call at end)
                head_term = None
                head_idx = None
                for i, g in enumerate(result):
                    if isinstance(g, GCall) and isinstance(g.term, PCompound):
                        head_term = g.term
                        head_idx = i
                body_goals = [g for i, g in enumerate(result) if i != head_idx]
                if head_term is None:
                    # Fallback: first goal is the head
                    if result and isinstance(result[0], GUnify):
                        head_term = PCompound('=', (result[0].left, result[0].right))
                        body_goals = result[1:]
                    else:
                        head_term = PAtom(render_body(result))
                body_goals = body_goals + goals
            elif isinstance(result, PTerm):
                head_term = result
                body_goals = goals
            head_term, extra = self._extract_head_arith_ast(head_term)
            body_goals = body_goals + extra
            head_str = render_term(head_term)
            if body_goals:
                self.rules.insert(0, f'{head_str} :- {render_body(body_goals)}.')
            else:
                self.rules.insert(0, f'{head_str}.')

    def enum(self, head: str, *args) -> None:
        for lams in args:
            i = self.counter(head)
            name_term = PCompound(head, (PNum(i),))
            name_str = render_term(name_term)
            describe_parts = []
            for lam in lams:
                result = lam(PAtom(''))
                if isinstance(result, list):
                    rendered = render_body(result).replace('()', '')
                    if ', ' not in rendered and ',)' not in rendered:
                        describe_parts.append(rendered)
                elif isinstance(result, PTerm):
                    rendered = render_term(result).replace('()', '')
                    if ', ' not in rendered and ',)' not in rendered:
                        describe_parts.append(rendered)
            if describe_parts:
                self.rules.append(f'describe({name_str}, {", ".join(describe_parts)}).')
            self.rules.append(f'{head}({name_str}).')
            self.rules.append(f'{head}({name_str},{i}).')
            for lam in lams:
                result = lam(PAtom(name_str))
                if isinstance(result, list):
                    all_goals = result
                    if all_goals and isinstance(all_goals[0], (GCall, GUnify)):
                        if isinstance(all_goals[0], GCall):
                            h = render_term(all_goals[0].term)
                        else:
                            h = render_goal(all_goals[0])
                        body = render_body(all_goals[1:]) if len(all_goals) > 1 else ''
                        if body:
                            self.rules.append(f'{h} :- {body}.')
                        else:
                            self.rules.append(f'{h}.')
                    else:
                        self.rules.append(render_body(all_goals).replace(', ', ' :- ', 1) + '.')
                elif isinstance(result, PTerm):
                    self.rules.append(f'{render_term(result)}.')

    # ── Expand macros ──

    def expand_macro(self, name: str, *args):
        """Expand a macro, returning list[PGoal] for macros or PTerm for plain calls."""
        if f'{name}/{len(args)}' in self.macros:
            params, tree = self.macros[f'{name}/{len(args)}']
            subst = dict(zip(params, args))
            return _MacroExpander(subst, self.gensym, params).transform(tree)
        elif len(args) == 0:
            return PAtom(name)
        else:
            return PCompound(name, tuple(args))

    # ── Start / toProlog ──

    def start(self, rule) -> str:
        if rule:
            if isinstance(rule, str):
                self.rules.insert(0, rule + '.')
            else:
                self.rules.insert(0, render_body([rule]) + '.' if isinstance(rule, (GCall, GUnify, GIs, GCompare, GBetween, GNot, GFindAll, GBagOf, GWhen, GRaw)) else render_term(rule) + '.' if isinstance(rule, PTerm) else repr(rule) + '.')
        return '\n'.join(self.rules) \
                   .replace(';,', ';') \
                   .replace(';.', '.') \
                   .replace(' :- .', '.')

    def toProlog(self, s: str) -> Optional[str]:
        self._result_wrapper = None
        try:
            tree = ldcs.parser.parse(s)
            return self.transform(tree)
        except lark.exceptions.UnexpectedInput as e:
            print('Syntax error:', e, file=sys.stderr)
            return None
        except lark.exceptions.UnexpectedEOF as e:
            print('Syntax error:', e, file=sys.stderr)
            return None
        finally:
            self.counts[''] = 0
            self.rules = []

    def add_macro(self, s: str) -> None:
        tree = ldcs.rule_parser.parse(s)
        name, args = ldcs.RuleHead().transform(tree)
        self.macros[f'{name}/{len(args)}'] = args, tree

    # ── Adverb (rarely used) ──

    def adverb(self, var_body: PCSym, adverb_body: PCSym) -> PUnary:
        var, goals = var_body
        avar, agoals = adverb_body
        if goals and isinstance(goals[0], GCall):
            head_term = goals[0].term
            body_goals = goals[1:]
        else:
            head_term = PAtom(render_body(goals))
            body_goals = []
        return lambda x: [GUnify(x, var),
                          GCall(PCompound('event', (avar, head_term)))] + body_goals + agoals


# ── PrologEngine ──────────────────────────────────────────────────────────────

class PrologEngine:
    """Runs SWI-Prolog queries via subprocess."""

    def __init__(self) -> None:
        self.clauses: List[str] = []
        self.predicates: Dict[Tuple[str, int], bool] = {}
        self._prelude = ''
        self._load_prelude()

    def _load_prelude(self) -> None:
        prelude_path = os.path.join(os.path.dirname(__file__), 'lib', 'prelude.pl')
        if os.path.exists(prelude_path):
            self._prelude = open(prelude_path).read()

    def add_clause(self, clause: str) -> None:
        clause = clause.strip()
        if not clause:
            return
        self.clauses.append(clause)
        pred_info = self._extract_pred(clause.rstrip('.'))
        if pred_info and pred_info not in self.predicates:
            self.predicates[pred_info] = False

    def retract_all(self, name: str, arity: int) -> None:
        prefix = f'{name}('
        self.clauses = [c for c in self.clauses if not c.startswith(prefix)]

    def _build_program(self, extra: str = '') -> str:
        all_clauses = '\n'.join(self.clauses)
        for (name, arity) in list(self.predicates.keys()):
            self.predicates[(name, arity)] = self._is_recursive(name, all_clauses)
        decls = []
        for (name, arity), recursive in self.predicates.items():
            decls.append(f':- discontiguous {name}/{arity}.')
            if recursive:
                decls.append(f':- table {name}/{arity}.')
        return '\n'.join([
            self._prelude, '',
            '\n'.join(decls), '',
            all_clauses, '', extra,
        ])

    def _is_recursive(self, name: str, program: str) -> bool:
        for line in program.split('\n'):
            line = line.strip()
            if not line or line.startswith('%'):
                continue
            if ' :- ' in line:
                head, body = line.split(' :- ', 1)
                head_pred = self._extract_pred(head.rstrip('.'))
                if head_pred and head_pred[0] == name and name + '(' in body:
                    return True
        return False

    def _run_query(self, program: str, goal: str, timeout: float = 30) -> List[Dict]:
        """Write program to temp file, run swipl, parse results."""
        import subprocess, tempfile
        # Build the query directive: findall + output each result
        query_directive = (
            f':- (findall(What, ({goal}), Results_) -> true ; Results_ = []),\n'
            f'   forall(member(R_, Results_), '
            f'(term_to_atom(R_, A_), format("result:~w~n", [A_]))),\n'
            f'   halt.\n'
        )
        full = program + '\n' + query_directive

        with tempfile.NamedTemporaryFile(mode='w', suffix='.pl', delete=False) as f:
            f.write(full)
            f.flush()
            tmppath = f.name

        try:
            proc = subprocess.run(
                ['swipl', '-q', tmppath],
                capture_output=True, text=True, timeout=timeout)
            results = []
            for line in proc.stdout.split('\n'):
                if line.startswith('result:'):
                    val = line[len('result:'):]
                    results.append({'What': val})
            if proc.stderr and 'DEBUG' in os.environ:
                print(proc.stderr, file=sys.stderr)
            return results
        except subprocess.TimeoutExpired:
            return []
        except Exception as e:
            if 'DEBUG' in os.environ:
                print(f'swipl error: {e}', file=sys.stderr)
            return []
        finally:
            os.unlink(tmppath)

    def query(self, goal: str, timeout: float = 30) -> List:
        program = self._build_program()
        return self._run_query(program, goal, timeout)

    def query_once(self, goal: str, timeout: float = 30):
        results = self.query(goal, timeout)
        return results[0] if results else None

    def query_with_extra(self, goal: str, extra_clauses: str, timeout: float = 30) -> List:
        program = self._build_program(extra=extra_clauses)
        return self._run_query(program, goal, timeout)

    def reset(self) -> None:
        self.clauses.clear()
        self.predicates.clear()

    def _extract_pred(self, clause: str) -> Optional[Tuple[str, int]]:
        head = clause.split(':-')[0].strip() if ':-' in clause else clause.strip()
        m = re.match(r'(\w+)\((.+)\)$', head)
        if m:
            return m.group(1), self._count_args(m.group(2))
        elif re.match(r'^\w+$', head):
            return head, 0
        return None

    def _count_args(self, args_str: str) -> int:
        depth = 0
        count = 1
        for ch in args_str:
            if ch in '([': depth += 1
            elif ch in ')]': depth -= 1
            elif ch == ',' and depth == 0: count += 1
        return count


# ── Output formatting ────────────────────────────────────────────────────────

def _quote_atoms_in_term(s: str) -> str:
    result = []
    i = 0
    while i < len(s):
        if s[i] == "'":
            j = i + 1
            while j < len(s) and s[j] != "'": j += 1
            result.append(f'"{s[i+1:j]}"')
            i = j + 1
            continue
        if s[i] == '"':
            j = i + 1
            while j < len(s) and s[j] != '"': j += 1
            result.append(s[i:j+1])
            i = j + 1
            continue
        m = re.match(r'-?\d+(\.\d+)?', s[i:])
        if m:
            result.append(m.group(0))
            i += len(m.group(0))
            continue
        m = re.match(r'[a-z_][a-zA-Z0-9_]*', s[i:])
        if m:
            word = m.group(0)
            end = i + len(word)
            if end < len(s) and s[end] == '(':
                result.append(word)
            else:
                result.append(f'"{word}"')
            i = end
            continue
        result.append(s[i])
        i += 1
    return ''.join(result)


def _parse_result_term(s: str) -> PTerm:
    """Parse a Prolog term string (from term_to_atom) into a PTerm for sorting."""
    s = s.strip()
    if not s:
        return PAtom('')
    if s.startswith('"') and s.endswith('"'):
        return PStr(s[1:-1])
    if s.lstrip('-').isdigit():
        return PNum(int(s))
    if s == '_' or (s[0].isupper() and '(' not in s):
        return PVar(s)
    # Compound: name(args)
    m = re.match(r'([a-z_]\w*)\((.+)\)$', s)
    if m:
        name = m.group(1)
        # Split args respecting nested parens
        args = []
        depth = 0
        cur = ''
        for ch in m.group(2):
            if ch in '([': depth += 1
            elif ch in ')]': depth -= 1
            if ch == ',' and depth == 0:
                args.append(_parse_result_term(cur))
                cur = ''
            else:
                cur += ch
        if cur:
            args.append(_parse_result_term(cur))
        return PCompound(name, tuple(args))
    return PAtom(s)


def _term_sort_key(s: str):
    """Sort key for Prolog result terms — structural comparison."""
    t = _parse_result_term(s)
    return _pterm_sort_key(t)


def _pterm_sort_key(t: PTerm):
    """Recursive sort key for PTerms."""
    match t:
        case PNum(v): return (0, v)
        case PStr(v): return (1, v)
        case PAtom(n): return (2, n)
        case PVar(n): return (3, n)
        case PCompound(f, args): return (4, f, tuple(_pterm_sort_key(a) for a in args))
        case PArith(op, l, r): return (5, op, _pterm_sort_key(l), _pterm_sort_key(r))
    return (6, repr(t))


def _parse_prolog_list(s: str) -> list:
    """Parse a Prolog list string like '[1,2,3]' into individual element strings."""
    s = s.strip()
    if not s.startswith('[') or not s.endswith(']'):
        return [s]
    inner = s[1:-1]
    if not inner:
        return []
    # Split respecting nested parens/brackets
    elements = []
    depth = 0
    cur = ''
    for ch in inner:
        if ch in '([': depth += 1
        elif ch in ')]': depth -= 1
        if ch == ',' and depth == 0:
            elements.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        elements.append(cur.strip())
    return elements


def _format_prolog_term(val) -> str:
    """Format a Prolog term (from term_to_atom output) for display."""
    if isinstance(val, str):
        if val.startswith('"'): return val
        if val.startswith("'") and val.endswith("'"): return f'"{val[1:-1]}"'
        # Try parsing as number
        try:
            n = int(val)
            return str(n)
        except ValueError:
            pass
        try:
            f = float(val)
            return str(int(f)) if f == int(f) else str(f)
        except ValueError:
            pass
        if '(' in val or "'" in val: return _quote_atoms_in_term(val)
        return f'"{val}"'
    return str(val)


# ── REPL ──────────────────────────────────────────────────────────────────────

class PrologASPI:
    def __init__(self, args: List[str] = []) -> None:
        self.counter = 1
        self.ldcs = PrologLDCS()
        self._asp_ldcs = ldcs.LDCS()
        self.engine = PrologEngine()
        self.proofs = False
        self.names: Dict[str, str] = {}  # enum id -> name mapping
        for arg in args:  # macros handled directly by PrologLDCS._BUILTINS
            self.include(arg)

    def include(self, arg: str) -> None:
        if arg.endswith('.lp'):
            return
        if arg.endswith('.ldcs'):
            with open(arg, 'r') as f:
                while True:
                    try:
                        line = next(f).strip()
                        if len(line) == 0 or line[0] == '%':
                            continue
                        while line[-1] not in '.?!':
                            line += next(f).strip()
                        if 'macros' in arg:
                            lp = self._asp_ldcs.toASP(line)
                            self.ldcs.add_macro(lp.split('\n')[0])
                        else:
                            pl = self.ldcs.toProlog(line)
                            if pl:
                                for clause in pl.split('\n'):
                                    if clause.strip():
                                        self.engine.add_clause(clause)
                    except StopIteration:
                        break
        elif arg.endswith('.csv'):
            with open(arg, 'r') as f:
                rows = 0
                for r, line in enumerate(f):
                    rows += 1
                    cols = 0
                    for c, v in enumerate(line.split(',')):
                        cols += 1
                        v = v.strip()
                        self.engine.add_clause(f'csv({v},{r+1},{c+1}).')
                    self.engine.add_clause(f'csv_cols({cols},{r+1}).')
                self.engine.add_clause(f'csv_rows({rows}).')
        elif arg.endswith('.txt'):
            name = os.path.basename(arg)[:-4]
            with open(arg, 'r') as f:
                for line in f:
                    k, v = line.split()
                    self.engine.add_clause(f'{name}({v},{k}).')

    def repl(self, cmd: str) -> None:
        if not cmd or cmd.startswith('%'):
            return
        if cmd.startswith('#undef '):
            name = cmd[len('#undef '):-1]
            self.engine.clauses = [c for c in self.engine.clauses if not c.startswith(name)]
            self.engine._dirty = True
            return
        if cmd.startswith('#include "'):
            return self.include(cmd[len('#include "'):-2])
        if cmd == 'thanks.':
            print("YOU'RE WELCOME!")
            sys.exit(0)
        if cmd == '#proof off.':
            self.proofs = False
            return
        if cmd.startswith('#macro '):
            cmd = cmd.replace('#macro ', '')
        res = self.eval(cmd)
        if res is not None:
            wrapper = self.ldcs._result_wrapper if cmd.endswith('?') else None
            self.print_results(res, wrapper=wrapper)
            self.counter += 1

    def eval(self, cmd: str) -> Optional[List]:
        pl = self.ldcs.toProlog(cmd)
        if pl is None:
            return None
        print('-->', '\n    '.join(line for line in pl.split('\n')))
        if cmd.endswith('.'):
            for clause in pl.split('\n'):
                clause = clause.strip()
                if clause:
                    self.engine.add_clause(clause)
                    # Collect describe(id, name) for enum name substitution
                    m = re.match(r'describe\((.+?),\s*(.+)\)\.$', clause)
                    if m:
                        self.names[m.group(1).strip()] = m.group(2).strip()
            print('understood.\n')
            return None
        if cmd.endswith('?'):
            lines = [l.strip() for l in pl.split('\n') if l.strip()]
            helpers = []
            query_clause = None
            for line in lines:
                if line.startswith('what('):
                    query_clause = line
                elif line.startswith('yes ') or line.startswith('no '):
                    helpers.append(line)
                else:
                    helpers.append(line)
            for h in helpers:
                self.engine.add_clause(h)
            if query_clause:
                if ' :- ' in query_clause:
                    return self.engine.query_with_extra('what(What)', extra_clauses=query_clause)
                else:
                    m = re.match(r'what\((.+)\)\.?', query_clause)
                    if m:
                        return [{'What': m.group(1)}]
            if any('yes' in h for h in helpers):
                return self.engine.query_with_extra(
                    '(yes -> What = yes ; no -> What = no ; What = unknown)',
                    extra_clauses='\n'.join(helpers))
        return None

    def _replace_names(self, s: str) -> str:
        """Replace enum identifiers with their names (from describe facts)."""
        for k, v in self.names.items():
            s = s.replace(k, v)
        return s

    def print_results(self, results: List, wrapper: str = None) -> None:
        if not results:
            print('impossible.\n')
            return
        # Extract raw values
        raw_values = [r['What'] for r in results if 'What' in r]
        # For bag wrapper, expand list-valued raw results into elements before formatting
        if wrapper == 'bag' and len(raw_values) == 1 and raw_values[0].startswith('['):
            raw_values = _parse_prolog_list(raw_values[0])
        values = [_format_prolog_term(v) for v in raw_values]
        if values == ['yes']:
            print('yes.\n')
            return
        if values == ['no']:
            print('no.\n')
            return
        if values:
            # Dedup and sort by underlying term structure (before name replacement)
            if wrapper == 'bag':
                # Bags preserve duplicates and order — just sort
                unique = sorted(values, key=_term_sort_key)
            else:
                seen = set()
                unique = []
                for v in values:
                    if v not in seen:
                        seen.add(v)
                        unique.append(v)
                unique.sort(key=_term_sort_key)
            # Replace enum identifiers with names (after sorting)
            if self.names:
                unique = [self._replace_names(v) for v in unique]
            self.engine.retract_all('that', 1)
            if wrapper in ('set', 'bag'):
                # Wrap results in set(...) or bag(...) compound term
                that = f'{wrapper}({",".join(unique)})'
                self.engine.add_clause(f'that({that}).')
            else:
                for v in unique:
                    self.engine.add_clause(f'that({v}).')
                that = ' | '.join(unique)
                if len(unique) > 1 and len(that) / len(unique) > 30:
                    that = that.replace(' | ', '\n    | ')
            print(f'that: {that}.')
        print()


if __name__ == '__main__':
    aspi = PrologASPI(sys.argv[1:])
    while True:
        try:
            cmd = input('>>> ')
        except EOFError:
            cmd = 'thanks.'
        except KeyboardInterrupt:
            print('^C')
            continue
        print(cmd)
        if len(cmd) == 0 or cmd[0] == '%':
            continue
        while cmd[-1] not in '.?!':
            cont = input('... ')
            print(cont)
            cmd += cont
        if cmd == '#reset.':
            aspi = PrologASPI(sys.argv[1:])
        else:
            aspi.repl(cmd)
