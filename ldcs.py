#!/usr/bin/env python3
import lark
import string

# https://arxiv.org/abs/1309.4408

ebnf = r'''
%import common.CNAME
%import common.WS
%ignore WS
command: value
?value: pred
      | ldcs
pred: atom [ "(" value ("," value)* ")" ]
    | atom ldcs
atom: CNAME
ldcs: disj
disj: "[" conj ("|" conj)* "]"
conj: lam lam*
?lam: unary
    | join
    | neg
unary: atom
     | atom "$" unary -> compose
     | "argmax" "(" atom "," conj ")" -> argmax
join: atom "." lam
    | atom disj
neg: "~" lam
'''

parser = lark.Lark(ebnf, start='command')

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
  def command(self, value):
    if len(value) == 1: value = 'show(' + value + ')'
    self.rules.insert(0, value + ' :- ' + self.body + '.')
    return '\n'.join(self.rules)
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
  def disj(self, *lams):
    if len(lams) == 1: return lams[0]
    f = self.genpred('disjunction')
    x = self.gensym()
    self.rules.extend(f(x) + ' :- ' + lam(x) + '.' for lam in lams)
    return f
  def conj(self, *lams):
    return lambda x: ', '.join(lam(x) for lam in lams)
  def unary(self, name):
    return lambda x: name + '(' + x + ')'
  def compose(self, name, lam):
    return lambda x: name + '(' + lam(x) + ')'
  def argmax(self, rel, lam):
    y = self.gensym()
    if ';' in lam(y): lam = self.lift(lam, 'superlative')
    return lambda x: 'not ' + rel + '(' + y + ',' + x + ')' + ' : ' + lam(y) + '; ' + lam(x)
  def join(self, rel, lam):
    y = self.gensym()
    return lambda x: rel + '(' + x + ',' + y + ')' + ', ' + lam(y)
  def neg(self, lam):
    if ' ' in lam('_'): lam = self.lift(lam)
    return lambda x: 'not ' + lam(x)

def transform(s):
  tree = parser.parse(s)
  return LDCS().transform(tree)

def main():
  print(transform(input()))
if __name__ == '__main__': main()
