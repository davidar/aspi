#!/usr/bin/env python3
import lark
import re
import string
import sys
from typing import cast, Callable, Dict, Iterable, List, \
        Optional, Protocol, Tuple, TypeVar

# https://arxiv.org/abs/1309.4408

ebnf = r'''
%import common.DIGIT
%import common.ESCAPED_STRING
%import common.INT
%import common.LCASE_LETTER
%import common.UCASE_LETTER
%import common.LETTER
%import common.WS
%ignore WS

CMP_OP: "=" | "!=" | "<=" | ">=" | "<" | ">"
BIN_OP: ".." | "**" | "+" | "-" | "*" | "/" | "\\" | "&" | "?" | "^"
AGG_OP: "count" | "sum" | "min" | "max" | "product" | "set" | "bag"
SUP_OP: "most" | "each" | "argmin" | "argmax"
VARIABLE: UCASE_LETTER
NAME: LCASE_LETTER ("_"|LETTER|DIGIT)*

start: cmd
?cmd: "#" "fluent" pred [":" clause] "." -> fluent
    | lams ":" "#" "some" lams ("|" lams)* "." -> enum
    | "#" "some" lams ("|" lams)* "." -> exist
    | "#" "relation" atom "(" rparam ("," rparam)* ")" "." -> relation
    | "#" "any" (ldcs | cmpop) "." -> constraint_any
    | "#" "any" ldcs "?" -> query_any
    | "#" "any" ldcs "!" -> goal_any
    | (func | join) ":" ldcs [":" clause] "." -> define
    | term [":" clause] "." -> claim
    | ldcs [":" clause] "?" -> query
    | ldcs "!" -> goal
clause: term ("," term)*
?term: pred
     | cmpop
pred: atom "(" ldcs ("," ldcs)* ")"
    | atom "$" pred
cmpop: bracketed CMP_OP bracketed -> binop
binop: bracketed BIN_OP bracketed
     | "(" "-" bracketed ")" -> negative
?bracketed: "(" ldcs ")"
          | lam -> ldcs
rparam: INT ldcs
atom: NAME
ldcs: disj
disjs: disj ("," disj)*
disj: conj ("|" conj)*
lams: lam lam*
conj: lams
constant: INT
        | VARIABLE
        | ESCAPED_STRING
?lam: func
    | constant
    | join
    | neg
    | hof
    | unify
func: atom
    | "(" CMP_OP ")" -> func_binop
    | atom "$" func -> compose
    | func "'" -> flip
join: func "." lam
    | func "[" disj "]"
    | func "[" disjs [";" disjs] "]" -> multijoin
neg: "~" lam
hof: "#" AGG_OP "(" disj ")" -> aggregation
   | "#" SUP_OP "(" func "," disj ")" -> superlative
   | "#" "enumerate" "(" disj "," disj ")" -> enumerate
unify: pred
     | binop
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
        self.counts: Dict[str, int] = {}
        self.rules: List[str] = []
        self.macros: Dict[str, Tuple[List[Sym], lark.Tree]] = {}

    def counter(self, prefix: str = '') -> int:
        if prefix not in self.counts:
            self.counts[prefix] = 0
        self.counts[prefix] += 1
        return self.counts[prefix]

    def gensym(self) -> Sym:
        return string.ascii_uppercase[self.counter()-1]

    def lift(self, lam: Unary, prefix: str, context: bool = True) -> Unary:
        # TODO: only suppress context for vars not used in the parent context
        i = self.counter(prefix)
        z = self.gensym()
        vars = sorted(set(re.findall('Mu[A-Z]', lam(z))))
        if not context:
            vars = []

        def f(x: str) -> str:
            closure = ','.join([str(i)] + vars)
            return f'{prefix}(({closure}),{x})'
        if len(vars) > 0:
            self.rules.append(f'{f(z)} :- {lam(z)}, @context({f("_")}).')
        else:
            self.rules.append(f'{f(z)} :- {lam(z)}.')
        return f

    def expand_macro(self, name: str, *args: Sym) -> str:
        params, tree = self.macros[name]
        subst = dict(zip(params, args))
        return RuleBody(subst, self.gensym).transform(tree)

    def start(self, rule: Optional[str]) -> str:
        if rule:
            self.rules.insert(0, rule + '.')
        for rule in self.rules[:]:
            if ' :- ' in rule and '{' not in rule:
                self.rules.append(self.proof(rule))
        return '\n'.join(self.rules).replace(';,', ';').replace(';.', '.')

    def define(self, head: Unary, var_body: CSym,
               cond: Optional[str] = None) -> str:
        var, body = var_body
        lhs = head(var).split(', ')
        return f'{lhs[0]} :- {commas(*lhs[1:], body, cond)}'

    def fluent(self, head_body: CSym, cond: Optional[str] = None) -> str:
        head, body = head_body
        if cond:
            terms = []
            for term in commas(body, cond).split(', '):
                if ' ' in term:
                    terms.append(term)
                else:
                    terms.append(f'holds({term}, Time)')
            rule = f'holds({head}, Time) :- {commas(*terms)}.'
            self.rules += [
                rule,
                '#program step(t).',
                rule.replace('Time', 'now+t'),
                '#program base.',
                ]
        return f'{head} :- holds({head})'

    def proof(self, rule: str) -> str:
        head, body = rule[:-1].split(' :- ')
        terms = []
        pvars = []
        for term in body.split(', '):
            if ' ' in term:
                terms.append(term)
            else:
                var = 'P' + str(self.counter('proof'))
                terms.append(f'proof({var},{term})')
                pvars.append(var)
        prf = ','.join([head] + pvars)
        return f'proof(@proof({prf}),{head}) :- {commas(*terms)}.'

    def enum(self, heads: List[Unary], *args: List[Unary]) -> None:
        for lams in args:
            name = 'object' + str(self.counter('object'))
            describe = ', '.join(lam('').replace('()', '')
                                 for lam in lams if ', ' not in lam(''))
            self.rules.append(f'describe({name}, {describe}).')
            for lam in heads + lams:
                self.rules.append(lam(name).replace(', ', ' :- ', 1) + '.')

    def exist(self, *args: List[Unary]) -> None:
        self.enum([], *args)

    def relation(self, name: str, *params: Tuple[str, CSym]) -> None:
        bounds = [x for x, _ in params]
        symbol = [x for _, (x, _) in params]
        bodies = [x for _, (_, x) in params]
        for i in range(len(params)):
            bound = bounds[i]
            body = bodies[i]
            args = commas(*symbol)
            cond = commas(*bodies[:i], *bodies[i+1:])
            self.rules.append(
                f'{{ {name}({args}) : {cond} }} = {bound} :- {body}.')

    def claim(self, head_body: CSym, cond: Optional[str] = None) -> str:
        head, body = head_body
        return f'{head} :- {commas(body, cond)}'

    def constraint_any(self, var_body: CSym) -> None:
        var, body = var_body
        if len(var) > 1:
            body = commas(var, body)
        name = 'constraint' + str(self.counter('constraint'))
        self.rules += [f'{name} :- {body}.', f':- not {name}.']

    def query(self, var_body: CSym, cond: Optional[str] = None) -> str:
        var, body = var_body
        return f'what({var}) :- {commas(body, cond)}'

    def query_any(self, var_body: CSym) -> None:
        var, body = var_body
        self.rules += [f'yes :- {body}.', 'no :- not yes.']

    def clause(self, *args: CSym) -> Optional[str]:
        body = None
        for v, b in args:
            body = commas(body, v, b)
        return body

    def goal_any(self, var_body: CSym) -> str:
        var, body = var_body
        assert body is not None
        if ';' in body:
            i = self.counter('goal')
            self.rules.append(f'goal{i}({var}) :- {body}.')
            var = self.gensym()
            body = f'goal{i}({var})'
        return f'{{ goal({var}) : {body} }} = 1'

    def goal(self, var_body: CSym) -> str:
        var, body = var_body
        assert body is not None
        return f'goal({var}) :- {body}'

    def pred(self, name: str, *args: CSym) -> CSym:
        vals, bodies = unzip(args)
        if not vals:
            return name, None
        return f"{name}({','.join(vals)})", commas(*bodies)

    def rparam(self, bound: str, param: CSym) -> Tuple[str, CSym]:
        return bound, param

    def binop(self, a: CSym, op: str, b: CSym) -> CSym:
        arg1, body1 = a
        arg2, body2 = b
        return f'{arg1} {op} {arg2}', commas(body1, body2)

    def negative(self, a: CSym) -> CSym:
        arg, body = a
        return '-' + arg, body

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
        i = self.counter('disjunction')
        x = self.gensym()
        self.rules.extend(f'disjunction{i}({x}) :- {lam(x)}.' for lam in lams)
        return lambda x: f'disjunction{i}({x})'

    def lams(self, *lams: Unary) -> List[Unary]:
        return list(lams)

    def conj(self, lams: List[Unary]) -> Unary:
        return lambda x: ', '.join(lam(x) for lam in lams)

    def constant(self, c: str) -> Unary:
        if c in string.ascii_uppercase:
            c = 'Mu' + c
        return lambda x: f'{x} = {c}'

    def func(self, name: str) -> Variadic:
        if name in self.macros:
            return lambda *args: self.expand_macro(name, *args)
        return lambda *args: f"{name}({','.join(args)})"

    def func_binop(self, op: str) -> Binary:
        return lambda x, y: f'{x} {op} {y}'

    def compose(self, name: str, lam: Variadic) -> Variadic:
        return lambda *args: f'{name}({lam(*args)})'

    def flip(self, lam: Variadic) -> Variadic:
        return lambda *args: lam(*reversed(args))

    def join(self, rel: Binary, lam: Unary) -> Unary:
        y = self.gensym()
        return lambda x: commas(rel(x, y), lam(y))

    def neg(self, lam: Unary) -> Unary:
        if ' ' in lam('_'):
            lam = self.lift(lam, 'negation')
        return lambda x: 'not ' + lam(x)

    def aggregation(self, op: str, lam: Unary) -> Unary:
        y = self.gensym()
        if ' ' in lam(y):
            lam = self.lift(lam, 'aggregation')
        if op in ('count', 'sum', 'min', 'max'):
            return lambda x: f'{x} = #{op} {{ {y} : {lam(y)} }}'
        elif op in ('product', 'set'):
            i = self.counter('gather')
            vars = sorted(set(re.findall('Mu[A-Z]', lam(y))))
            closure = ','.join([str(i)] + vars)

            def f(x: str) -> str:
                return f'{op}of(({closure}),{x})'
            context = ''
            if len(vars) > 0:
                context = f', @context({f("_")})'
            self.rules.append(f'gather(({closure}),{y}) :- {lam(y)}{context}.')
            return f
        elif op == 'bag':
            i = self.counter('gather')
            self.rules.append(f'gather({i},({y},P0)) :- proof(P0,{lam(y)}).')
            return lambda x: f'bagof({i},{x})'
        else:
            assert False

    def superlative(self, op: str, rel: Binary, lam: Unary) -> Unary:
        y = self.gensym()
        if ' ' in lam(y):
            lam = self.lift(lam, 'superlative', False)
        if op == 'most':
            return lambda x: f'{rel(x, y)} : {lam(y)}, {x} != {y}; {lam(x)}'
        elif op == 'each':
            return lambda x: f'{rel(x, y)} : {lam(y)};'
        elif op in ('argmin', 'argmax'):
            agg = self.aggregation(op[3:], self.join(rel, lam))
            return lambda x: commas(agg(y), rel(y, x), lam(x))
        else:
            assert False

    def enumerate(self, idx: Unary, lam: Unary) -> Unary:
        i = self.counter('gather')
        y = self.gensym()
        self.rules.append(f'gather({i},{y}) :- {lam(y)}.')
        return lambda x: f'enumerate({i},{y},{x}), {idx(y)}'

    def unify(self, pred_body: CSym) -> Unary:
        pred, body = pred_body
        return lambda x: commas(body, f'{x} = {pred}')

    def multijoin(self, rel: Variadic, lams_tail: List[Unary],
                  lams_head: List[Unary] = []) -> Unary:
        lams_head.reverse()
        xs = [self.gensym() for lam in lams_head]
        zs = [self.gensym() for lam in lams_tail]
        lams = zip(lams_head + lams_tail, xs + zs)
        body = ', '.join(lam(x) for lam, x in lams)
        return lambda y: commas(rel(*xs, y, *zs), body)

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
            self.counts[''] = 0
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
        return f"{name}({','.join(args)})"

    def predop(self, *args: str) -> str:
        return ' '.join(args)

    def var(self, name: Sym) -> Sym:
        if name not in self.subst:
            self.subst[name] = self.gensym()
        return self.subst[name]


if __name__ == '__main__':
    print(LDCS().toASP(input()))
