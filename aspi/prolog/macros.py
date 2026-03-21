"""Macro expansion — _MacroExpander and _to_pterm."""

import lark

from aspi.prolog.ast import (
    PTerm, PVar, PAtom, PNum, PStr, PCompound, PArith, PGoal,
    GCall, GUnify, GIs, GCompare, GBetween, GNot, GFindAll, GBagOf, GWhen, GRaw,
)
from aspi.prolog.render import render_term


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


@lark.v_args(inline=True)
class _MacroExpander(lark.Transformer):
    """Transform a macro rule tree into PGoals with PTerm substitutions."""

    def __init__(self, subst: dict, gensym, params: list, ldcs_instance=None):
        self.subst = subst
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
        if hasattr(self, '_ldcs') and f'{n}/{len(args)}' in self._ldcs.macros:
            expanded = self._ldcs.expand_macro(n, *args)
            if isinstance(expanded, list):
                return expanded
            if isinstance(expanded, PTerm):
                return expanded
        return compound

    def predop(self, *args):
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
                if isinstance(right, PCompound) and right.functor.startswith('@'):
                    return self._expand_at_function(left, right)
                return GUnify(left, right)
            if op in ('<', '>', '<=', '>='):
                return GCompare(op, left, right)
            if op == '!=':
                return GCompare('\\=', left, right)
            if op == '..':
                return PCompound('..', (left, right))
            return PArith(op, left, right)
        if len(parts) == 2:
            return GNot([parts[1]] if isinstance(parts[1], PGoal) else [GCall(parts[1])])
        return GRaw(' '.join(str(a) for a in parts))

    def var(self, name):
        name = str(name)
        if name not in self.subst:
            self.subst[name] = PVar(self.gensym())
        return self.subst[name]

    def _expand_at_function(self, target, compound):
        """Expand X = @fn(args) into appropriate PGoal(s)."""
        fn = compound.functor[1:]
        args = compound.args
        if fn == 'concatenate':
            if len(args) == 2:
                return GCall(PCompound('string_concat', (args[0], args[1], target)))
            elif len(args) == 3:
                tmp = PVar(self.gensym())
                return [GCall(PCompound('string_concat', (args[1], args[2], tmp))),
                        GCall(PCompound('string_concat', (args[0], tmp, target)))]
        if fn == 'substring':
            if len(args) == 3:
                s1 = PVar(self.gensym())
                return [GIs(s1, PArith('-', args[1], PNum(1))),
                        GCall(PCompound('sub_string', (args[0], s1, args[2], PVar('_'), target)))]
        if fn == 'length':
            return GCall(PCompound('string_length', (args[0], target)))
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
        return GRaw(f'{render_term(target)} = {render_term(compound)}')

    def paren(self, val):
        return val

    def __default__(self, data, children, meta):
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
            return s
        if token.type == 'ATOM':
            return PAtom(s)
        if token.type == 'OPERATOR':
            return s
        return s
