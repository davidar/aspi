#!/usr/bin/env python3
import lark
import string

# https://arxiv.org/abs/1309.4408

ebnf = r'''
%import common.CNAME
%import common.INT
%import common.UCASE_LETTER
%import common.WS
%ignore WS

AGG_OP: "count" | "any"
SUP_OP: "most" | "each"
VARIABLE: UCASE_LETTER

?start: command
command: pred "."
       | ldcs "?"
       | ldcs "!" -> goal
pred: atom "(" ldcs ("," ldcs)* ")"
    | atom "$" pred
atom: CNAME
ldcs: disj
disjs: disj ("," disj)*
disj: conj ("|" conj)*
conj: lam lam*
?lam: unary
    | INT -> constant
    | VARIABLE -> constant
    | join
    | neg
    | hof
    | unify
    | multijoin
?unary: func
?binary: func
func: atom
    | atom "$" func -> compose
    | func "'" -> flip
join: binary "." lam
    | binary "[" disj "]"
neg: "~" lam
hof: "#" AGG_OP "(" disj ")" -> aggregation
   | "#" SUP_OP "(" binary "," disj ")" -> superlative
unify: pred
multijoin: func "[" disjs [";" disjs] "]"
'''

parser = lark.Lark(ebnf)

@lark.v_args(inline=True)
class LDCS(lark.Transformer):
  def __init__(self):
    self.count = 0
    self.counts = {}
    self.body = ''
    self.rules = []
  def gensym(self):
    sym = string.ascii_uppercase[self.count]
    self.count += 1
    return sym
  def genpred(self, prefix):
    if prefix not in self.counts: self.counts[prefix] = 0
    self.counts[prefix] += 1
    return lambda x: prefix + str(self.counts[prefix]) + '(' + x + ')'
  def lift(self, lam, prefix='lifted'):
    f = self.genpred(prefix)
    z = self.gensym()
    self.rules.append(f(z) + ' :- ' + lam(z) + '.')
    return f
  def expand_macro(self, name, *args):
    params, tree = macros[name]
    subst = dict(zip(params,args))
    return RuleBody(subst, self.gensym).transform(tree)

  def command(self, value):
    if len(value) == 1: value = 'show(' + value + ')'
    if self.body: value += ' :- ' + self.body
    value += '.'
    self.rules.insert(0, value)
    return '\n'.join(self.rules).replace(';,', ';')
  def goal(self, value):
    body = self.body
    if ';' in self.body:
      f = self.genpred('goal')
      self.rules.append(f(value) + ' :- ' + body + '.')
      value = self.gensym()
      body = f(value)
    self.rules.insert(0, '{ goal(' + value + ') : ' + body + ' } = 1.')
    return '\n'.join(self.rules).replace(';,', ';')
  def pred(self, name, *args):
    if not args: return name
    return name + '(' + ','.join(args) + ')'
  def atom(self, name):
    return name
  def ldcs(self, lam):
    x = self.gensym()
    if self.body: self.body += ', '
    self.body += lam(x)
    return x
  def disjs(self, *args):
    return list(args)
  def disj(self, *lams):
    if len(lams) == 1: return lams[0]
    f = self.genpred('disjunction')
    x = self.gensym()
    self.rules.extend(f(x) + ' :- ' + lam(x) + '.' for lam in lams)
    return f
  def conj(self, *lams):
    return lambda x: ', '.join(lam(x) for lam in lams)
  def constant(self, c):
    if c in string.ascii_uppercase: c = 'Mu' + c
    return lambda x: x + ' = ' + c
  def func(self, name):
    if name in macros: return lambda *args: self.expand_macro(name,*args)
    return lambda *args: name + '(' + ','.join(args) + ')'
  def compose(self, name, lam):
    return lambda *args: name + '(' + lam(*args) + ')'
  def flip(self, lam):
    return lambda *args: lam(*reversed(args))
  def join(self, rel, lam):
    y = self.gensym()
    return lambda x: rel(x,y) + ', ' + lam(y)
  def neg(self, lam):
    if ' ' in lam('_'): lam = self.lift(lam)
    return lambda x: 'not ' + lam(x)
  def aggregation(self, op, lam):
    y = self.gensym()
    if ';' in lam(y): lam = self.lift(lam, 'aggregation')
    if op == 'count':
      return lambda x: x + ' = #count { ' + y + ' : ' + lam(y) + ' }'
    elif op == 'any':
      f = self.genpred('any')
      self.rules.append(f('true')  + ' :- ' + lam(y) + '.')
      self.rules.append(f('false') + ' :- not ' + f('true') + '.')
      return f
  def superlative(self, op, rel, lam):
    y = self.gensym()
    if ';' in lam(y): lam = self.lift(lam, 'superlative')
    if op == 'most':
      return lambda x: rel(x,y) + ' : ' + lam(y) + ', ' + x + ' != ' + y + '; ' + lam(x)
    elif op == 'each':
      return lambda x: rel(x,y) + ' : ' + lam(y) + ';'
  def unify(self, pred):
    return lambda x: x + ' = ' + pred
  def multijoin(self, rel, lams_tail, lams_head = []):
    lams_head.reverse()
    xs = [self.gensym() for lam in lams_head]
    zs = [self.gensym() for lam in lams_tail]
    lams = zip(lams_head + lams_tail, xs + zs)
    return lambda y: rel(*xs,y,*zs) + ', ' + ', '.join(lam(x) for lam,x in lams)

rule_ebnf = r'''
%import common.DIGIT
%import common.INT
%import common.LETTER
%import common.LCASE_LETTER
%import common.UCASE_LETTER
%import common.WS
%ignore WS

ATOM: LCASE_LETTER ("_"|LETTER|DIGIT)*
VARIABLE: UCASE_LETTER ("_"|LETTER|DIGIT)*
OPERATOR: "=" | "!=" | "<=" | ">=" | "<" | ">" | "+" | "-" | ".."

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
class RuleHead(lark.Transformer):
  def rule(self, head, *body):
    return head
  def var(self, name):
    return name
  def head(self, name, *args):
    return str(name), [str(arg) for arg in args]

@lark.v_args(inline=True)
class RuleBody(lark.Transformer):
  def __init__(self, subst, gensym):
    self.subst = subst
    self.gensym = gensym
  def rule(self, head, *body):
    return ', '.join(body)
  def pred(self, name, *args):
    if not args: name
    return name + '(' + ','.join(args) + ')'
  def predop(self, *args):
    return ' '.join(args)
  def var(self, name):
    if name not in self.subst:
      self.subst[name] = self.gensym()
    return self.subst[name]

def transform(s):
  prefix = ''
  if s.startswith(':def '):
    prefix = ':def '
    s = s[len(prefix):]
  tree = parser.parse(s)
  return prefix + LDCS().transform(tree)

macros = {}

def add_macro(s):
  tree = rule_parser.parse(s)
  name, args = RuleHead().transform(tree)
  macros[name] = args, tree

def main():
  print(transform(input()))
if __name__ == '__main__': main()
