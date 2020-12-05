#!/usr/bin/env python3
import lark

parser = lark.Lark(open('english.ebnf', 'r'), ambiguity='explicit')

@lark.v_args(inline=True)
class Sem(lark.Transformer):
  def conj(self, *args):
    return ' '.join(arg for arg in args if arg)
  def disj(self, *args):
    return ' | '.join(args)
  def join(self, rel, *args):
    if len(args) == 1 and ' ' not in args[0]:
      return f"{rel}.{args[0]}"
    return f"{rel}[{','.join(args)}]"
  def flip(self, verb):
    return f"{verb}'"
  def neg(self, adj):
    return f"~{adj}"
  def flipjoin(self, noun, verb, *args):
    return self.join(self.flip(verb), noun, *args)
  def flipjoin2(self, verb, noun, *args):
    return self.join(self.flip(verb), noun, *args)
  def joint(self, rel, noun, time=None):
    if not time: return self.join(rel, noun)
    return f"{rel}[{noun}; {time}]"

  def _ambig(self, args):
    args = set(args)
    if len(args) > 1: return args
    return args.pop()
  def command(self, verb, noun):
    return f"{verb}({noun})!"
  def put(self, noun, prep, location):
    return f"{prep}({noun}, {location})!"
  def stack(self, n1, n2=None):
    if n2: return f"stack({n1}, {n1}, {n2})"
    else:  return f"stack({n1}, {n1})"
  def build(self, noun):
    return f"{noun}!"
  def question(self, *args):
    return self.conj(*args) + '?'
  def passive(self, noun, verb):
    return self.join(verb, noun)
  def count(self, *args):
    return f"#count({self.conj(*args)})"
  def count2(self, noun, verb, time):
    return f"#count({self.conj(self.join(verb, noun), time)})"
  def qwhen(self, verb, noun, time):
    return self.conj(self.join(verb, noun), time)
  def statement(self, noun, adj):
    return f"{adj}({noun})."
  def but(self, v1, n1, v2, n2):
    if v1 == v2:
      return v1 + '(' + self.conj(n1, self.neg(n2)) + ')'
  def define(self, noun, adj):
    return f"{noun}({adj})."
  def verb(self, name):
    return name.replace(' ','')
  def noun(self, *args):
    return self.conj(*args)
  def holding(self):
    return 'holding'
  def commanded(self, verb):
    return f"command${verb}"
  def that(self):
    return 'that'
  def most(self, adj, *args):
    return f"#most({adj},{self.conj(*args)})"
  def support(self, noun):
    return self.join('support', noun)
  def it(self):
    return '#it'
  def det(self, name):
    if name == 'that': return name
    return ''
  def adj(self, name):
    return name
  def each(self, adj, noun):
    return f"#each({adj},{noun})"
  def prep(self, name):
    if name.endswith('to'): name = name[:-2]
    if name == 'on top of': name = 'above'
    return name
  def time(self):
    return ''
  def told_put(self, n1, p, n2):
    return f"goal.{p}({n1},{n2})"
  def cleanoff(self, noun):
    return self.join('cleanoff', noun)

def main():
  tests = [
    'pick up a big red block',
    'pick up that pyramid',
    'find a block which is taller than the one you are holding',
    'put that into the box',
    'what does the box contain',
    'what is that pyramid supported by',
    'how many blocks are not in the box',
    'is at least one of those narrower than the one which I told you to pick up',
    'is that supported',
    'stack up two pyramids',
    'the blue pyramid is mine',
    'I own blocks which are not red but I don\'t own anything which supports a pyramid',
    'do I own the box',
    'do I own anything in the box',
    'will you please stack up both of the red blocks and either a green cube or a pyramid',
    'which cube is sitting on the table',
    'is there a large block behind a pyramid',
    'put a small block onto the green cube which supports a pyramid',
    'put the smallest pyramid on top of the small block',
    'does the shortest thing the tallest pyramid\'s support supports support anything green',
    'which green thing does the shortest thing the tallest pyramid\'s support supports support',
    'what colour is that',
    'how many things are on top of green cubes',
    'had you touched any pyramid before I told you to put the green pyramid on the little cube',
    'how many objects did you touch while you were doing that',
    'what did the red cube support before you started to clean the red cube off',
    'which blocks were to the left of the box before you started to clean the red cube off',
    'put the blue pyramid on the block in the box',
    'is there anything which is big-er than every pyramid but is not as wide as the thing that supports it',
    'a "steeple" is a stack which contains two green cubes and a pyramid',
    'build a steeple',
    'call the big-est block "superblock"',
    'have you picked superblock up since we began',
    'is there anything to the right of the red pyramid',
  ]
  for test in tests:
    print(test)
    tree = parser.parse(test)
    #print(tree.pretty())
    print(Sem().transform(tree))
    print()
if __name__ == '__main__': main()
