"""AST analysis — variable extraction and dependency tracking."""

import re

from aspi.prolog.ast import (
    PTerm, PVar, PAtom, PNum, PStr, PCompound, PArith,
    GCall, GUnify, GIs, GCompare, GBetween, GNot, GFindAll, GBagOf, GWhen, GRaw,
)


def term_vars(t: PTerm) -> set:
    match t:
        case PVar(name): return {name}
        case PArith(_, l, r): return term_vars(l) | term_vars(r)
        case PCompound(_, args):
            return set().union(*(term_vars(a) for a in args)) if args else set()
        case _: return set()


def goal_vars(g) -> set:
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
    'string_length': ({0}, {1}),
    'string_concat': ({0, 1}, {2}),
    'char_code': ({0}, {1}), 'sub_string': ({0}, {1, 2, 3, 4}),
    'member': (set(), {0}),
    'permutation': ({0}, {1}), 'reverse': ({0}, {1}),
}


def goal_needs_ground(g) -> set:
    match g:
        case GIs(_, expr): return term_vars(expr)
        case GCompare(_, l, r): return term_vars(l) | term_vars(r)
        case GBetween(lo, hi, _): return term_vars(lo) | term_vars(hi)
        case GNot(goals): return set().union(*(goal_vars(g2) for g2 in goals))
        case GCall(PCompound(f, args)) if f in _DIRECTIONAL:
            input_idxs = _DIRECTIONAL[f][0]
            return set().union(*(term_vars(args[i]) for i in input_idxs if i < len(args)))
        case GCall(PCompound('forall', args)) if len(args) == 2:
            gen_vars = goal_vars(GCall(args[0])) if isinstance(args[0], PTerm) else set()
            # Test arg is often a PAtom containing rendered Prolog text — extract vars via regex
            if isinstance(args[1], PAtom):
                test_vars = set(re.findall(r'\b([A-Z]\w*)\b', re.sub(r'"[^"]*"', '', args[1].name)))
            else:
                test_vars = term_vars(args[1])
            return test_vars - gen_vars
        case GFindAll(_, gs, _):
            inner = set().union(*(goal_vars(g2) for g2 in gs))
            return {v for v in inner if v.startswith('Mu')}
        case GWhen(_, _): return set()
        case GRaw(text):
            m = re.match(r'(\w+) is (.+)', text)
            if m: return set(re.findall(r'\b([A-Z]\w*)\b', m.group(2)))
            if text.startswith('\\+ ') or text.startswith('\\+('):
                return set(re.findall(r'\b([A-Z]\w*)\b', text))
            for op in (' < ', ' > ', ' <= ', ' >= ', ' =:= ', ' =\\= '):
                if op in text:
                    return set(re.findall(r'\b([A-Z]\w*)\b', text))
            return set()
    return set()


def goal_binds(g) -> set:
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
            return term_vars(PCompound(f, args))
        case GWhen(_, goal): return goal_binds(goal)
        case GRaw(text):
            m = re.match(r'(\w+) is ', text)
            if m and m.group(1)[0].isupper(): return {m.group(1)}
            m = re.match(r'(\w+)\(', text)
            if m and m.group(1) not in _DIRECTIONAL: return goal_vars(g)
            return set()
    return set()
