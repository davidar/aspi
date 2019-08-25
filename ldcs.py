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
ldcs: conj
conj: "[" lam lam* "]"
?lam: unary
    | join
    | neg
unary: atom
     | atom "$" unary -> compose
join: atom "." lam
    | atom conj
neg: "~" lam
'''

parser = lark.Lark(ebnf, start='command')

@lark.v_args(inline=True)
class LDCS(lark.Transformer):
  def __init__(self):
    self.count = 0
    self.body = ''
  def gensym(self):
    sym = string.ascii_uppercase[self.count]
    self.count += 1
    return sym
  def command(self, value):
    if len(value) == 1: value = 'show(' + value + ')'
    return value + ' :- ' + self.body + '.'
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
  def conj(self, *lams):
    return lambda x: ', '.join(lam(x) for lam in lams)
  def unary(self, name):
    return lambda x: name + '(' + x + ')'
  def compose(self, name, lam):
    return lambda x: name + '(' + lam(x) + ')'
  def join(self, rel, lam):
    y = self.gensym()
    return lambda x: rel + '(' + x + ',' + y + ')' + ', ' + lam(y)
  def neg(self, lam):
    return lambda x: 'not ' + lam(x)

def transform(s):
  tree = parser.parse(s)
  return LDCS().transform(tree)

def main():
  print(transform(input()))
if __name__ == '__main__': main()
