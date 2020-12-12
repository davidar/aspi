#!/usr/bin/env python3
import lark
import string
import sys
from typing import cast, Callable, Dict, Iterable, List, \
        Literal, Optional, Protocol, Tuple, TypeVar

# https://arxiv.org/abs/1309.4408

ebnf = r'''
%import common.CNAME
%import common.INT
%import common.LCASE_LETTER
%import common.UCASE_LETTER
%import common.WS
%ignore WS

BIN_OP: "<=" | ">=" | "<" | ">"
      | "+" | "-" | "*" | "/"
      | "\\" | "**" | "&" | "?" | "^" | ".."
AGG_OP: "count" | "sum" | "any"
SUP_OP: "most" | "each"
VARIABLE: UCASE_LETTER
NAME: LCASE_LETTER CNAME

?start: command
command: pred "."
       | define "."
       | ldcs "?"
       | "#" "any" "(" ldcs ")" "!" -> goal_any
       | ldcs "!" -> goal_all
pred: atom "(" ldcs ("," ldcs)* ")"
    | atom "$" pred
    | bracketed BIN_OP bracketed -> binop
define: lam ":=" ldcs
?bracketed: "(" ldcs ")"
          | constant -> ldcs
          | join -> ldcs
atom: NAME
ldcs: disj
disjs: disj ("," disj)*
disj: conj ("|" conj)*
conj: lam lam*
constant: INT
        | VARIABLE
?lam: unary
    | constant
    | join
    | neg
    | hof
    | unify
?unary: func
?binary: func
func: atom
    | "(" BIN_OP ")" -> func_binop
    | atom "$" func -> compose
    | func "'" -> flip
join: binary "." lam
    | binary "[" disj "]"
    | func "[" disjs [";" disjs] "]" -> multijoin
neg: "~" lam
hof: "#" AGG_OP "(" disj ")" -> aggregation
   | "#" SUP_OP "(" binary "," disj ")" -> superlative
unify: pred
'''

Sym = str
CSym = Tuple[Sym, Optional[str]]
Unary = Callable[[Sym], str]
Binary = Callable[[Sym, Sym], str]
T = TypeVar('T')
S = TypeVar('S')


class Variadic(Protocol):
    def __call__(self, *args: Sym) -> str: ...


parser = lark.Lark(ebnf)


def unzip(pairs: Iterable[Tuple[S, T]]) -> Tuple[List[S], List[T]]:
    a, b = zip(*pairs)
    return cast(List[S], a), cast(List[T], b)


def commas(*args: Optional[str]) -> str:
    return ', '.join(arg for arg in args if arg)


@lark.v_args(inline=True)
class LDCS(lark.Transformer[str]):
    def __init__(self) -> None:
        self.count: int = 0
        self.counts: Dict[str, int] = {}
        self.rules: List[str] = []
        self.macros: Dict[str, Tuple[List[Sym], lark.Tree]] = {}

    def gensym(self) -> Sym:
        sym = string.ascii_uppercase[self.count]
        self.count += 1
        return sym

    def genpred(self, prefix: str) -> Unary:
        if prefix not in self.counts:
            self.counts[prefix] = 0
        self.counts[prefix] += 1
        return lambda x: prefix + str(self.counts[prefix]) + '(' + x + ')'

    def lift(self, lam: Unary, prefix: str = 'lifted') -> Unary:
        f = self.genpred(prefix)
        z = self.gensym()
        self.rules.append(f(z) + ' :- ' + lam(z) + '.')
        return f

    def expand_macro(self, name: str, *args: Sym) -> str:
        params, tree = self.macros[name]
        subst = dict(zip(params, args))
        return RuleBody(subst, self.gensym).transform(tree)

    def command(self, vb: CSym) -> str:
        value, body = vb
        if len(value) == 1:
            value = 'what(' + value + ')'
        if body:
            value += ' :- ' + body
        value += '.'
        self.rules.insert(0, value)
        return '\n'.join(self.rules).replace(';,', ';')

    def goal_any(self, vb: CSym) -> str:
        value, body = vb
        assert body is not None
        if ';' in body:
            f = self.genpred('goal')
            self.rules.append(f(value) + ' :- ' + body + '.')
            value = self.gensym()
            body = f(value)
        self.rules.insert(0, '{ goal(' + value + ') : ' + body + ' } = 1.')
        return '\n'.join(self.rules).replace(';,', ';')

    def goal_all(self, vb: CSym) -> str:
        value, body = vb
        assert body is not None
        self.rules.insert(0, 'goal(' + value + ') :- ' + body + '.')
        return '\n'.join(self.rules).replace(';,', ';')

    def pred(self, name: str, *args: CSym) -> CSym:
        vals, bodies = unzip(args)
        if not vals:
            return name, None
        return name + '(' + ','.join(vals) + ')', commas(*bodies)

    def binop(self, a: CSym, op: str, b: CSym) -> CSym:
        arg1, body1 = a
        arg2, body2 = b
        return arg1 + op + arg2, commas(body1, body2)

    def define(self, head: Unary, vb: CSym) -> CSym:
        result, body = vb
        lhs = head(result).split(', ')
        if len(lhs) > 1:
            body = commas(*lhs[1:], body)
        return lhs[0], body

    def atom(self, name: str) -> str:
        return name

    def ldcs(self, lam: Unary) -> CSym:
        x = self.gensym()
        return x, lam(x)

    def disjs(self, *args: str) -> List[str]:
        return list(args)

    def disj(self, *lams: Unary) -> Unary:
        if len(lams) == 1:
            return lams[0]
        f = self.genpred('disjunction')
        x = self.gensym()
        self.rules.extend(f(x) + ' :- ' + lam(x) + '.' for lam in lams)
        return f

    def conj(self, *lams: Unary) -> Unary:
        return lambda x: ', '.join(lam(x) for lam in lams)

    def constant(self, c: str) -> Unary:
        if c in string.ascii_uppercase:
            c = 'Mu' + c
        return lambda x: x + ' = ' + c

    def func(self, name: str) -> Variadic:
        if name in self.macros:
            return lambda *args: self.expand_macro(name, *args)
        return lambda *args: name + '(' + ','.join(args) + ')'

    def func_binop(self, op: str) -> Binary:
        return lambda x, y: x + op + y

    def compose(self, name: str, lam: Variadic) -> Variadic:
        return lambda *args: name + '(' + lam(*args) + ')'

    def flip(self, lam: Variadic) -> Variadic:
        return lambda *args: lam(*reversed(args))

    def join(self, rel: Binary, lam: Unary) -> Unary:
        y = self.gensym()
        return lambda x: rel(x, y) + ', ' + lam(y)

    def neg(self, lam: Unary) -> Unary:
        if ' ' in lam('_'):
            lam = self.lift(lam)
        return lambda x: 'not ' + lam(x)

    def aggregation(self, op: Literal['count', 'sum', 'any'],
                    lam: Unary) -> Unary:
        y = self.gensym()
        if ';' in lam(y):
            lam = self.lift(lam, 'aggregation')
        if op == 'count' or op == 'sum':
            return lambda x: f'{x} = #{op} {{ {y} : {lam(y)} }}'
        elif op == 'any':
            f = self.genpred('any')
            self.rules.append(f('true') + ' :- ' + lam(y) + '.')
            self.rules.append(f('false') + ' :- not ' + f('true') + '.')
            return f
        else:
            assert False

    def superlative(self, op: Literal['most', 'each'],
                    rel: Binary, lam: Unary) -> Unary:
        y = self.gensym()
        if ' ' in lam(y):
            lam = self.lift(lam, 'superlative')
        if op == 'most':
            return lambda x: f'{rel(x, y)} : {lam(y)}, {x} != {y}; {lam(x)}'
        elif op == 'each':
            return lambda x: f'{rel(x, y)} : {lam(y)};'
        else:
            assert False

    def unify(self, vb: CSym) -> Unary:
        pred, body = vb
        return lambda x: commas(body, x + ' = ' + pred)

    def multijoin(self, rel: Variadic, lams_tail: List[Unary],
                  lams_head: List[Unary] = []) -> Unary:
        lams_head.reverse()
        xs = [self.gensym() for lam in lams_head]
        zs = [self.gensym() for lam in lams_tail]
        lams = zip(lams_head + lams_tail, xs + zs)
        body = ', '.join(lam(x) for lam, x in lams)
        return lambda y: rel(*xs, y, *zs) + ', ' + body

    def toASP(self, s: str) -> Optional[str]:
        try:
            tree = parser.parse(s)
            return self.transform(tree)
        except lark.exceptions.UnexpectedInput as e:
            print('Syntax error:', e, file=sys.stderr)
            return None
        except lark.exceptions.UnexpectedEOF as e:
            print('Syntax error:', e, file=sys.stderr)
            return None
        finally:
            self.count = 0
            self.counts = {}
            self.rules = []

    def add_macro(self, s: str) -> None:
        tree = rule_parser.parse(s)
        name, args = RuleHead().transform(tree)
        self.macros[name] = args, tree


rule_ebnf = r'''
%import common.DIGIT
%import common.INT
%import common.LETTER
%import common.LCASE_LETTER
%import common.UCASE_LETTER
%import common.WS
%ignore WS

ATOM: ["@"] LCASE_LETTER ("_"|LETTER|DIGIT)*
VARIABLE: UCASE_LETTER ("_"|LETTER|DIGIT)*
OPERATOR: "=" | "!=" | "<=" | ">=" | "<" | ">"
        | "+" | "-" | "*" | "/"
        | "\\" | "**" | "&" | "?" | "^" | ".."

?start: rule
rule: head ":-" pred ("," pred)* "."
pred: ATOM [ "(" value ("," value)* ")" ]
    | value OPERATOR value -> predop
?value: pred
      | var
      | INT
var: VARIABLE
head: ATOM "(" var ("," var)* ")"
'''

rule_parser = lark.Lark(rule_ebnf)


@lark.v_args(inline=True)
class RuleHead(lark.Transformer[Tuple[str, List[str]]]):
    def rule(self, head: str, *body: str) -> str:
        return head

    def var(self, name: str) -> str:
        return name

    def head(self, name: str, *args: str) -> Tuple[str, List[str]]:
        return str(name), [str(arg) for arg in args]


@lark.v_args(inline=True)
class RuleBody(lark.Transformer[str]):
    def __init__(self, subst: Dict[Sym, Sym], gensym: Callable[[], Sym]):
        self.subst = subst
        self.gensym = gensym

    def rule(self, head: str, *body: str) -> str:
        return ', '.join(body)

    def pred(self, name: str, *args: str) -> str:
        if not args:
            name
        return name + '(' + ','.join(args) + ')'

    def predop(self, *args: str) -> str:
        return ' '.join(args)

    def var(self, name: Sym) -> Sym:
        if name not in self.subst:
            self.subst[name] = self.gensym()
        return self.subst[name]


if __name__ == '__main__':
    print(LDCS().toASP(input()))
