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
        if len(args) == 0:
            return rel
        if len(args) == 1 and ' ' not in args[0]:
            return f"{rel}.{args[0]}"
        return f"{rel}[{','.join(args)}]"

    def flip(self, verb):
        return f"{verb}'"

    def neg(self, x):
        return f"~{x}"

    def flipjoin(self, noun, verb, *args):
        return self.join(self.flip(verb), noun, *args)

    def flipjoin2(self, verb, noun=None, *args):
        if not noun:
            return verb
        return self.join(self.flip(verb), noun, *args)

    def joint(self, rel, noun, time=None):
        if not time:
            return self.join(rel, noun)
        return f"{rel}[{noun}; {time}]"

    def rjoin(self, n, v):
        return self.join(v, n)

    def command(self, verb, noun):
        return f"{verb}({noun})!"

    def put(self, noun, prep, location):
        return f"{prep}({noun}, {location})!"

    def stack(self, n1, n2=None):
        if n2:
            return f"stack({n1}, {n1}, {n2})"
        else:
            return f"stack({n1}, {n1})"

    def build(self, noun):
        return f"{noun}!"

    def question(self, *args):
        return self.conj(*args) + '?'

    def count(self, *args):
        return f"#count({self.conj(*args)})"

    def statement(self, noun, adj):
        return f"{adj}({noun})."

    def verb(self, name):
        return name.replace(' ', '')

    def verbp(self, v, p=''):
        return v + p

    def np(self, *args):
        return self.conj(*args)

    def verbpthat(self, v, p):
        return self.join(self.verbp(v, p), 'that')

    def commanded(self, verb):
        return f"command${verb}"

    def put_on(self, n1, n2):
        return f"put_on({n1},{n2})"

    def that(self):
        return 'that'

    def most(self, adj, *args):
        return f"#most({adj},{self.conj(*args)})"

    def it(self):
        return '#it'

    def det(self, name):
        if name == 'that':
            return name
        return ''

    def each(self, adj, noun):
        return f"#each({adj},{noun})"

    def prep(self, name):
        if name.endswith('to'):
            name = name[:-2]
        if name == 'on top of':
            name = 'above'
        return name

    def time(self, name=''):
        return name

    def prept(self, name):
        return name.replace(' ', '_')

    def told(self, c):
        return self.join('goal', c[:-1])


def main():
    for line in open('test.txt', 'r'):
        if line[0] == '#':
            continue
        line = line.strip().lower()[:-1]
        print(line)
        tree = parser.parse(line)
        # print(tree.pretty())
        print(Sem().transform(tree))
        print()


if __name__ == '__main__':
    main()
