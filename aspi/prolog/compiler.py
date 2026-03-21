"""PrologLDCS — LDCS transformer producing Prolog AST."""

import lark
import re
import string
from typing import Optional

from aspi import ldcs
from aspi.prolog.ast import (
    PTerm, PVar, PAtom, PNum, PStr, PCompound, PArith,
    PBody, PCSym, PUnary,
    GCall, GUnify, GIs, GCompare, GBetween, GNot, GFindAll, GBagOf, GWhen, GRaw,
)
from aspi.prolog.render import render_term, render_goal, render_body, _render_body_no_autowrap
from aspi.prolog.analysis import term_vars, goal_vars
from aspi.prolog.macros import _MacroExpander


@lark.v_args(inline=True)
class PrologLDCS(ldcs.LDCS):
    """LDCS transformer that produces Prolog AST goals natively."""

    def __init__(self) -> None:
        super().__init__()
        self._agg_counter = 0
        self._result_wrapper = None
        self._proofs = True
        self._pending_lattice = None
        self._fluent_preds = set()

    def _gensym_var(self) -> PVar:
        return PVar(self.gensym())

    def atom(self, name: str) -> str:
        return name

    def constant(self, c: str) -> PUnary:
        if c[0] in string.ascii_uppercase:
            term = PVar('Mu' + c)
        elif c.startswith('"') and c.endswith('"'):
            term = PStr(c[1:-1])
        elif c.lstrip('-').isdigit():
            term = PNum(int(c))
        else:
            term = PAtom(c)
        return lambda x: [GUnify(x, term)]

    _BUILTINS = {
        'show': lambda self, x, a: [GCall(PCompound('term_to_atom', (a, x)))],
        'concatenate': None,
        'reverse': lambda self, x, a: (
            lambda c1, c2: [GCall(PCompound('atom_chars', (a, c1))),
                            GCall(PCompound('reverse', (c1, c2))),
                            GCall(PCompound('atom_chars', (x, c2)))]
        )(PVar(self.gensym()), PVar(self.gensym())),
        'length': lambda self, x, a: [GCall(PCompound('string_length', (a, x)))],
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
        'mean': None,
        'negate': lambda self, x, a: [GIs(x, PArith('-', PNum(0), a))],
        'permutation': lambda self, x, a: (
            lambda c1, c2: [GCall(PCompound('atom_chars', (a, c1))),
                            GCall(PCompound('permutation', (c1, c2))),
                            GCall(PCompound('atom_chars', (x, c2)))]
        )(PVar(self.gensym()), PVar(self.gensym())),
    }

    def func(self, name: str):
        def variadic(*args):
            n = len(args)
            if n >= 2 and name in self._BUILTINS and self._BUILTINS[name] is not None:
                return self._BUILTINS[name](self, *args)
            for prefix, lo in [('n', 1), ('z', 0), ('i', None)]:
                for digits in range(1, 5):
                    rname = f'{prefix}{digits}'
                    if name == rname and n >= 1:
                        hi = 10**digits - 1
                        if prefix == 'i':
                            return [GBetween(PNum(-hi), PNum(hi), args[0])]
                        return [GBetween(PNum(lo), PNum(hi), args[0])]
            if name == 'multiple' and n == 2:
                x, y = args
                return [GCompare('=:=', PArith('mod', x, y), PNum(0))]
            if name == 'even' and n == 1:
                return [GCompare('=:=', PArith('mod', args[0], PNum(2)), PNum(0))]
            if name == 'odd' and n == 1:
                return [GCompare('=:=', PArith('mod', args[0], PNum(2)), PNum(1))]
            if name == 'exists' and n == 1:
                return []
            if name == 'mean' and n == 2:
                x, a = args
                s = PVar(self.gensym())
                c = PVar(self.gensym())
                return [GCall(PCompound('sum_list', (a, s))),
                        GCall(PCompound('length', (a, c))),
                        GIs(x, PArith('//', s, c))]
            if name == 'concatenate':
                if n == 3:
                    x, a, b = args
                    return [GCall(PCompound('string_concat', (a, b, x)))]
                if n == 4:
                    x, a, b, c = args
                    tmp = PVar(self.gensym())
                    return [GCall(PCompound('string_concat', (b, c, tmp))),
                            GCall(PCompound('string_concat', (a, tmp, x)))]
            if name == 'substring' and n == 2:
                x, a = args
                s = PVar(self.gensym())
                l = PVar(self.gensym())
                nn = PVar(self.gensym())
                s1 = PVar(self.gensym())
                return [GCall(PCompound('string_length', (a, nn))),
                        GBetween(PNum(1), nn, s),
                        GIs(s1, PArith('-', s, PNum(1))),
                        GBetween(PNum(0), PArith('-', PArith('+', nn, PNum(1)), s), l),
                        GCall(PCompound('sub_string', (a, s1, l, PVar('_'), x)))]
            if name == 'substring' and n == 4:
                x, a, s, l = args
                s1 = PVar(self.gensym())
                return [GIs(s1, PArith('-', s, PNum(1))),
                        GCall(PCompound('sub_string', (a, s1, l, PVar('_'), x)))]
            if f'{name}/{n}' in self.macros:
                params, tree = self.macros[f'{name}/{n}']
                subst = dict(zip(params, args))
                return _MacroExpander(subst, self.gensym, params, ldcs_instance=self).transform(tree)
            elif n == 0:
                return PAtom(name)
            else:
                return PCompound(name, tuple(args))
        return variadic

    def join(self, rel, *var_bodies) -> PUnary:
        self._result_wrapper = None
        if getattr(rel, '_prolog_needs_list', False):
            new_var_bodies = []
            for var, goals in var_bodies:
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
            return positive + negative
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

        if goals and isinstance(goals[0], GUnify) and goals[0].left == x:
            value = goals[0].right
            remaining = goals[1:] + cond_goals

            remaining_vars = set()
            for g in remaining:
                remaining_vars |= goal_vars(g)
            if x.name in remaining_vars:
                return (x, goals + cond_goals)

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
        guarded = []
        for i, (var, goals) in enumerate(csyms):
            guards = []
            for j in range(i):
                prev_var, prev_goals = csyms[j]
                guards.append(GNot(prev_goals + [GUnify(PVar('_'), prev_var)]))
            guarded.append((var, guards + goals))
        return self._lifts(guarded, 'disjunction')

    def fluent(self, head_body, *args):
        head, head_goals = head_body
        body_preds = [vb for vb in args if vb is not None]
        if body_preds:
            all_goals = list(head_goals)
            for pred, pred_goals in body_preds:
                all_goals.extend(pred_goals)
                if isinstance(pred, PTerm):
                    all_goals.append(GCall(pred))
            head_str = render_term(head)
            body_str = render_body(all_goals)
            self.rules.append(f'{head_str} :- {body_str}.')
        head_str = render_term(head)
        self.rules.append(f'{head_str} :- holds({head_str}).')
        if isinstance(head, PCompound):
            self._fluent_preds.add(head.functor)
        return None

    def claim(self, head_body: PCSym, cond=None) -> str:
        value, goals = head_body
        if cond:
            goals = goals + (cond if isinstance(cond, list) else [cond])
        value, extra_goals = self._extract_head_arith_ast(value)
        goals = goals + extra_goals
        head = render_term(value)
        if goals:
            return f'{head} :- {render_body(goals)}'
        return head

    def _extract_head_arith_ast(self, value: PTerm) -> tuple:
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
            op = self._ineq_ops.get(op, op)
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

    _ineq_ops = {'<=': '=<', '!=': '\\='}

    def ineq(self, op: str, var_body: PCSym) -> PUnary:
        var, goals = var_body
        op = self._ineq_ops.get(op, op)
        return lambda x: goals + [GCompare(op, x, var)]

    def negative(self, var_body: PCSym) -> PUnary:
        var, goals = var_body
        return lambda x: goals + [GUnify(x, PArith('-', PNum(0), var))]

    def not_term(self, term, lift: bool = False) -> PBody:
        if isinstance(term, list):
            x = self._gensym_var()
            lam = self._lift((x, term), 'negation')
            result = lam(PVar('_'))
            if isinstance(result, list):
                return [GNot(result)]
            return [GNot([GCall(result)])]
        if isinstance(term, PTerm):
            return [GNot([GCall(term)])]
        raise TypeError(f'not_term: unexpected type: {type(term).__name__}: {term!r}')

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
                    inner_str = _render_body_no_autowrap(inner)
                elif isinstance(inner, (PCompound, PAtom)):
                    inner_str = render_term(inner)
                else:
                    inner_str = repr(inner)
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

    _agg_funcs = {
        'sum': 'sum_list', 'count': 'length', 'min': 'min_list',
        'max': 'max_list', 'product': 'product_of',
    }

    def _get_agg_name(self, a):
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
        all_vars = term_vars(var)
        for g in goals:
            all_vars |= goal_vars(g)
        muvars = {v for v in all_vars if v.startswith('Mu')}
        result_var = PVar(f'Agg{tag}L_')
        self._result_wrapper = 'bag'
        proofs = self._proofs
        def f(x):
            if muvars:
                return [GBagOf(var, goals, x)]
            if proofs:
                body_str = _render_body_no_autowrap(goals)
                prove_goals = [GRaw(f'prove(({body_str}), _)')]
                return [GFindAll(var, prove_goals, x)]
            return [GFindAll(var, goals, x)]
        return f

    def _make_agg(self, agg_name: str, inner: PCSym, dedup: bool = True) -> PUnary:
        var, goals = inner
        self._agg_counter += 1
        tag = self._agg_counter
        reduce_func = self._agg_funcs[agg_name]
        if isinstance(var, PArith):
            eval_var = PVar(f'AggV{tag}_')
            goals = goals + [GIs(eval_var, var)]
            var = eval_var
        if agg_name in ('min', 'max'):
            self._pending_lattice = (agg_name, var, goals)
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

    def _lift(self, var_body: PCSym, prefix: str, ground: bool = False):
        return self._lifts([var_body], prefix, ground=ground)

    def _lifts(self, var_bodies: list, prefix: str, ground: bool = False):
        i = self.counter(prefix)
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

    def define(self, heads, var_body: PCSym) -> None:
        lattice_info = self._pending_lattice
        self._pending_lattice = None

        var, goals = var_body

        if lattice_info:
            agg_name, inner_var, inner_goals = lattice_info
            _reduce_funcs = set(self._agg_funcs.values())
            cleaned = []
            for g in goals:
                if isinstance(g, GFindAll):
                    continue
                if isinstance(g, GCall) and isinstance(g.term, PCompound) \
                        and g.term.functor in ('sort', *_reduce_funcs):
                    continue
                cleaned.append(g)
            goals = cleaned + inner_goals
            var = inner_var

        for head in reversed(heads):
            result = head(var)
            if isinstance(result, list):
                head_term = None
                head_idx = None
                for i, g in enumerate(result):
                    if isinstance(g, GCall) and isinstance(g.term, PCompound):
                        head_term = g.term
                        head_idx = i
                body_goals = [g for i, g in enumerate(result) if i != head_idx]
                if head_term is None:
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
            if lattice_info and isinstance(head_term, PCompound):
                agg_name = lattice_info[0]
                arity = len(head_term.args)
                tabling_args = [f'lattice(my_{agg_name}/3)'] + ['+'] * (arity - 1)
                self.rules.append(f':- table {head_term.functor}({", ".join(tabling_args)}).')

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

    def expand_macro(self, name: str, *args):
        if f'{name}/{len(args)}' in self.macros:
            params, tree = self.macros[f'{name}/{len(args)}']
            subst = dict(zip(params, args))
            return _MacroExpander(subst, self.gensym, params).transform(tree)
        elif len(args) == 0:
            return PAtom(name)
        else:
            return PCompound(name, tuple(args))

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
        self._pending_lattice = None
        try:
            tree = ldcs.parser.parse(s)
            return self.transform(tree)
        except lark.exceptions.UnexpectedInput as e:
            import sys
            print('Syntax error:', e, file=sys.stderr)
            return None
        except lark.exceptions.UnexpectedEOF as e:
            import sys
            print('Syntax error:', e, file=sys.stderr)
            return None
        finally:
            self.counts[''] = 0
            self.rules = []

    def add_macro(self, s: str) -> None:
        tree = ldcs.rule_parser.parse(s)
        name, args = ldcs.RuleHead().transform(tree)
        self.macros[f'{name}/{len(args)}'] = args, tree

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
