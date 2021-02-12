#!/usr/bin/env python3
import lark
import re
import string
import sys
from typing import Callable, Dict, Iterable, List, \
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
SUP_SUFFIX: "'est" | "'each" | "'th" | "'"
VARIABLE: UCASE_LETTER
NAME: LCASE_LETTER ("_"|LETTER|DIGIT)*

start: cmd
?cmd: "#" "fluent" pred [":" clause] "." -> fluent
    | "#" "enum" atom ":" lams ("|" lams)* "." -> enum
    | "#" "relation" atom "(" rparam ("," rparam)* ")" "." -> relation
    | "#" "any" (ldcs | cmpop) "." -> constraint_any
    | "#" "any" ldcs "?" -> query_any
    | "#" "any" [ldcs] "!" -> goal_any
    | ["#" "macro"] define_heads ":" ldcs "." -> define
    | ldcs "::" define_heads "." -> reverse_define
    | term [":" clause] "." -> claim
    | clause "::" term "." -> reverse_claim
    | ldcs "?" -> query
    | ldcs "!" -> goal
define_heads: (func | join)+
clause: term ("," term)*
?term: pred
     | cmpop
     | "#" "each" "(" term "," term ")" -> foreach
pred: atom "(" [ldcs ("," ldcs)*] ")"
    | atom "$" pred
cmpop: ldcs CMP_OP ldcs -> binop
binop: bracketed BIN_OP bracketed
?bracketed: "(" ldcs ")"
          | arg -> ldcs
rparam: INT ldcs
atom: NAME
ldcs: disj [":" clause]
disjs: disj ("," disj)*
disj: conj ("|" conj)*
    | "_"
conj: lams
lams: lam+
?lam: arg
    | binop -> unify
constant: INT
        | VARIABLE
        | ESCAPED_STRING
?arg: func
    | constant
    | join
    | "~" bracketed -> neg
    | CMP_OP bracketed -> ineq
    | pred -> unify
    | "(" "-" bracketed ")" -> negative
    | [func] "{{" ldcs "}}" -> bagof
    | [func] "{" ldcs "}" -> setof
func: atom
    | atom "$" func -> compose
    | (func | constant) SUP_SUFFIX -> superlative
join: func "." arg
    | func "[" disj "]"
    | func "[" disjs [";" disjs] "]" -> multijoin
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
    xs = []
    ys = []
    for x, y in pairs:
        xs.append(x)
        ys.append(y)
    return xs, ys


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
        i = self.counter() - 1
        if i < len(string.ascii_uppercase):
            return string.ascii_uppercase[i]
        else:
            i -= len(string.ascii_uppercase)
            return f'X{i}'

    def lift(self, var_body: CSym, prefix: str,
             context: bool = True, ground: bool = False,
             gather: bool = False) -> Unary:
        # TODO: only suppress context for vars not used in the parent context
        #       this has functional effects for aggregations
        var, body = var_body
        prefix_gather = 'gather' if gather else prefix
        i = self.counter(prefix_gather)
        vars = []
        if context:
            vars = sorted(set(re.findall('Mu[A-Z]', commas(var, body))))
        if var[0] not in string.ascii_uppercase:
            ground = False

        def f(x: str, name: str = prefix) -> str:
            closure = ','.join([str(i)] + vars)
            return f'{name}(({closure}),{x})'
        if len(vars) > 0 or ground:
            args = f('_')
            if ground:
                args = f'{var},{args}'
            body = commas(body, f'@context({args})')
        if body:
            self.rules.append(f'{f(var, prefix_gather)} :- {body}.')
        else:
            self.rules.append(f'{f(var, prefix_gather)}.')
        return f

    def expand_macro(self, name: str, *args: Sym) -> str:
        params, tree = self.macros[f'{name}/{len(args)}']
        subst = dict(zip(params, args))
        return RuleBody(subst, self.gensym).transform(tree)

    def expand_contexts(self) -> None:
        updated = False
        for i, rule in enumerate(self.rules):
            if (match := re.search(r'@context\((.*)\)', rule)):
                pred = match.group(1)
                groundvar = None
                if pred[1] == ',':
                    groundvar = pred[0]
                    pred = pred[2:]
                template = re.escape(pred).replace('_', '([A-Z])')
                for rule2 in self.rules:
                    if ' :- ' in rule2:
                        body = rule2[:-1].split(' :- ')[1].split(', ')
                        for j, term in enumerate(body):
                            if (match2 := re.search(template, term)):
                                headvar = match2.group(1)
                                context = []
                                for t in body[:j] + body[j+1:]:
                                    if not re.search(fr'\b{headvar}\b', t) \
                                            and 'Mu' in pred:
                                        context.append(t)
                                    elif groundvar and '..' in t and \
                                            t.startswith(f'{headvar} = '):
                                        context.append(groundvar + t[1:])
                                    elif groundvar and \
                                            t.endswith(f'({headvar})'):
                                        context.append(
                                            t.replace(headvar, groundvar))
                                rule = rule.replace(
                                    match.group(0), commas(*context))
                                rule = rule.replace(', .', '.')
                                self.rules[i] = rule
                                updated = True
        if updated:
            self.expand_contexts()

    def start(self, rule: Optional[str]) -> str:
        if rule:
            self.rules.insert(0, rule + '.')
        self.expand_contexts()
        for rule in self.rules[:]:
            if ' :- ' in rule and '{' not in rule:
                self.rules.append(self.proof(rule))
        return '\n'.join(self.rules) \
                   .replace(';,', ';') \
                   .replace(';.', '.') \
                   .replace(' :- .', '.')

    def define(self, heads: List[Unary], var_body: CSym) -> None:
        var, body = var_body
        for head in reversed(heads):
            lhs = head(var).split(', ')
            self.rules.insert(0, f'{lhs[0]} :- {commas(*lhs[1:], body)}.')

    def reverse_define(self, var_body: CSym, heads: List[Unary]) -> None:
        return self.define(heads, var_body)

    def fluent(self, head_body: CSym, cond: Optional[str] = None) -> str:
        head, body = head_body
        if cond:
            terms = []
            for term in commas(body, cond).split(', '):
                if ' ' in term:
                    terms.append(term)
                else:
                    terms.append(f'holds({term}, Time)')
            self.rules.append(f'holds({head}, Time) :- {commas(*terms)}.')
        return f'{head} :- holds({head})'

    def proof(self, rule: str) -> str:
        head, body = rule[:-1].split(' :- ')
        terms = []
        pvars = []
        for term in body.split(', '):
            if ' = @' in term and ':' not in term and ';' not in term:
                terms.append(term)
                var = 'P' + str(self.counter('proof'))
                eq = term.replace(' = @', ',')
                terms.append(f'{var} = eq({eq})')
                pvars.append(var)
            elif ' ' in term:
                terms.append(term)
            elif term.strip():
                var = 'P' + str(self.counter('proof'))
                terms.append(f'proof({var},{term})')
                pvars.append(var)
        prf = ','.join([head] + pvars)
        return f'proof(@proof({prf}),{head}) :- {commas(*terms)}.'

    def enum(self, head: str, *args: List[Unary]) -> None:
        for lams in args:
            i = self.counter(head)
            name = f'{head}({i})'
            describe = ', '.join(lam('').replace('()', '')
                                 for lam in lams if ', ' not in lam(''))
            self.rules.append(f'describe({name}, {describe}).')
            self.rules.append(f'{head}({name}).')
            self.rules.append(f'{head}({name},{i}).')
            for lam in lams:
                self.rules.append(lam(name).replace(', ', ' :- ', 1) + '.')

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

    def reverse_claim(self, cond: Optional[str], head_body: CSym) -> str:
        head, body = head_body
        return f'{head} :- {commas(body, cond)}'

    def constraint_any(self, var_body: CSym) -> None:
        var, body = var_body
        if len(var) > 1:
            body = commas(var, body)
        name = 'constraint' + str(self.counter('constraint'))
        self.rules += [f'{name} :- {body}.', f':- not {name}.']

    def query(self, var_body: CSym) -> str:
        var, body = var_body
        if body:
            return f'what({var}) :- {body}'
        else:
            return f'what({var})'

    def query_any(self, var_body: CSym) -> None:
        var, body = var_body
        self.rules += [f'yes :- {body}.', 'no :- not yes.']

    def clause(self, *args: CSym) -> Optional[str]:
        body = None
        for v, b in args:
            body = commas(body, v, b)
        return body

    def goal_any(self, var_body: Optional[CSym] = None) -> Optional[str]:
        if var_body is None:
            return None
        var, body = var_body
        if body is None:
            return f'{{ goal({var}) }} = 1'
        if ';' in body:
            i = self.counter('goal')
            self.rules.append(f'goal{i}({var}) :- {body}.')
            var = self.gensym()
            body = f'goal{i}({var})'
        return f'{{ goal({var}) : {body} }} = 1'

    def goal(self, var_body: CSym) -> str:
        var, body = var_body
        if body is None:
            return f'goal({var})'
        else:
            return f'goal({var}) :- {body}'

    def define_heads(self, *args: Unary) -> List[Unary]:
        return list(args)

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
        if not arg1.isalnum():
            arg1 = f'({arg1})'
        if not arg2.isalnum():
            arg2 = f'({arg2})'
        return f'{arg1} {op} {arg2}', commas(body1, body2)

    def foreach(self, lit: CSym, cond: CSym) -> CSym:
        return f'{commas(*lit)} : {commas(*cond)};', None

    def negative(self, var_body: CSym) -> Unary:
        var, body = var_body
        return lambda x: commas(body, f'{x} = -{var}')

    def atom(self, name: str) -> str:
        return name

    def ldcs(self, lam: Unary, cond: Optional[str] = None) -> CSym:
        lam_ = lam('_')
        if lam_.startswith('_ = ') and \
                ', ' not in lam_ and \
                '{' not in lam_ and \
                '..' not in lam_:
            x = lam_[len('_ = '):]
            if x[0] != '"':
                x = x.replace(' ', '')
            return x, cond
        else:
            x = self.gensym()
            return x, commas(lam(x), cond)

    def disjs(self, *args: str) -> List[str]:
        return list(args)

    def disj(self, *lams: Unary) -> Unary:
        if len(lams) == 0:
            return lambda x: ''
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
        def f(*args: Sym) -> str:
            if f'{name}/{len(args)}' in self.macros:
                return self.expand_macro(name, *args)
            else:
                return f"{name}({','.join(args)})"
        return f

    def compose(self, name: str, lam: Variadic) -> Variadic:
        return lambda *args: f'{name}({lam(*args)})'

    def superlative(self, rel: Variadic, op: str) -> Variadic:
        if op == "'":
            return lambda *args: rel(*reversed(args))
        elif op == "'each":
            y = self.gensym()
            return lambda x, z: f'{rel(x, y)} : {y} = @memberof({z});'
        elif op == "'est":
            y = self.gensym()
            return lambda x, z: f'{rel(x, y)} : {y} = @memberof({z}), {x} != {y}; {x} = @memberof({z})'
        elif op == "'th":
            y = self.gensym()
            return lambda x, z: f'{rel(y)}, ({y},{x}) = @enumerateof({z})'
        assert False

    def join(self, rel: Binary, lam: Unary) -> Unary:
        y, body = self.ldcs(lam)
        return lambda x: commas(rel(x, y), body)

    def neg(self, var_body: CSym) -> Unary:
        lam = self.lift(var_body, 'negation', True, True)
        return lambda x: 'not ' + lam(x)

    def ineq(self, op: str, var_body: CSym) -> Unary:
        var, body = var_body
        return lambda x: commas(f'{x} {op} {var}', body)

    def setof(self, a, b=None) -> Unary:
        if b is not None:
            return self.join(a, self.setof(b))
        return self.lift(a, 'setof', gather=True)

    def bagof(self, a, b=None) -> Unary:
        if b is not None:
            return self.join(a, self.bagof(b))
        var, body = a
        if body is not None and ' ' in body:
            var, body = self.ldcs(self.lift((var, body), 'aggregation'))
        var = f'({var},P0)'
        body = f'proof(P0,{body})'
        return self.lift((var, body), 'bagof', gather=True)

    def unify(self, pred_body: CSym) -> Unary:
        pred, body = pred_body
        return lambda x: commas(body, f'{x} = {pred}')

    def multijoin(self, rel: Variadic, lams_tail: List[Unary],
                  lams_head: List[Unary] = []) -> Unary:
        lams_head.reverse()
        xs, b1 = unzip(self.ldcs(lam) for lam in lams_head)
        zs, b2 = unzip(self.ldcs(lam) for lam in lams_tail)
        return lambda y: commas(rel(*xs, y, *zs), commas(*b1, *b2))

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
        self.macros[f'{name}/{len(args)}'] = args, tree


rule_ebnf = r'''
%import common.DIGIT
%import common.ESCAPED_STRING
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
    | [value] OPERATOR value -> predop
?value: pred
      | var
      | INT
      | ESCAPED_STRING
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


def unparen(s: str) -> str:
    if s[0] == '(' and s[-1] == ')':
        return s[1:-1]
    else:
        return s


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
        return f"{name}({','.join(unparen(arg) for arg in args)})"

    def predop(self, *args: str) -> str:
        return ' '.join(args)

    def var(self, name: Sym) -> Sym:
        if name not in self.subst:
            self.subst[name] = self.gensym()
        expr = self.subst[name]
        if not expr.isalnum():
            expr = f'({expr})'
        return expr


if __name__ == '__main__':
    print(LDCS().toASP(input()))
