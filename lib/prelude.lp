#program base.
#show what/1.
#show yes/0.
#show no/0.
#show history/2.
#show describe/2.
#show describe/3.
#show describe/4.
#show describe/5.

history(counter, goal(F)) :- goal(F).
history(counter, what(X)) :- what(X).

true(true).
false(false).
now(now).

that(X,N) :- history(counter-N, what(X)).
that(X) :- that(X,1).

proof(@proof(csv(V,R,C)),csv(V,R,C)) :- csv(V,R,C).
proof(@proof(csv_cols(C,R)),csv_cols(C,R)) :- csv_cols(C,R).
proof(@proof(csv_rows(R)),csv_rows(R)) :- csv_rows(R).

n1(X) :- X = 1..9.
n2(X) :- X = 1..99.
n3(X) :- X = 1..999.
n4(X) :- X = 1..9999.
proof(@proof(n1(X)),n1(X)) :- n1(X).
proof(@proof(n2(X)),n2(X)) :- n2(X).
proof(@proof(n3(X)),n3(X)) :- n3(X).
proof(@proof(n4(X)),n4(X)) :- n4(X).

z1(X) :- X = 0..9.
z2(X) :- X = 0..99.
z3(X) :- X = 0..999.
z4(X) :- X = 0..9999.
proof(@proof(z1(X)),z1(X)) :- z1(X).
proof(@proof(z2(X)),z2(X)) :- z2(X).
proof(@proof(z3(X)),z3(X)) :- z3(X).
proof(@proof(z4(X)),z4(X)) :- z4(X).

i1(X) :- X = -9..9.
i2(X) :- X = -99..99.
i3(X) :- X = -999..999.
i4(X) :- X = -9999..9999.
proof(@proof(i1(X)),i1(X)) :- i1(X).
proof(@proof(i2(X)),i2(X)) :- i2(X).
proof(@proof(i3(X)),i3(X)) :- i3(X).
proof(@proof(i4(X)),i4(X)) :- i4(X).

gather(@gather(I,X)) :- gather(I,X).
enumerate(I,J,X) :- gather(I), (J-1,X) = @sort(I).
proof(@proof(enumerate(I,J,X)),enumerate(I,J,X)) :- enumerate(I,J,X).
setof(I,X) :- gather(I), X = @setof(I).
proof(@proof(setof(I,X)),setof(I,X)) :- setof(I,X).
bagof(I,X) :- gather(I), X = @bagof(I).
proof(@proof(bagof(I,X)),bagof(I,X)) :- bagof(I,X).

#script (python)
import clingo
import itertools
import math
import sys

def show(a):
    return clingo.String(str(a))
def concatenate(a, b):
    return a.string + b.string
def reverse(a):
    return clingo.String(a.string[::-1])
def substring(a, start, length):
    return a.string[start.number-1:start.number-1+length.number]
def length(a):
    return clingo.Number(len(a.string))
def decimal(a):
    try:
        return clingo.Number(int(a.string))
    except:
        return clingo.Function('error')
def permutation(a):
    return [clingo.String(''.join(t)) for t in itertools.permutations(a.string)]
def codepoint(a):
    try:
        return clingo.Number(ord(a.string))
    except TypeError:
        return clingo.Number(-1)

gathered = {}
def gather(i, a):
    if i not in gathered:
        gathered[i] = []
    gathered[i].append(a)
    return i
def sort(i):
    return list(enumerate(sorted(gathered[i]))) if i in gathered else []
def setof(i):
    return clingo.Function('set', sorted(gathered[i]))
def bagof(i):
    try:
        return clingo.Function('bag', sorted(a.arguments[0] for a in gathered[i]))
    except:
        return clingo.Function('error')

def countof(a):
    return len(a.arguments)
def sumof(a):
    return sum(x.number for x in a.arguments) % sys.maxsize
def productof(a):
    return math.prod(x.number for x in a.arguments) % sys.maxsize

def proof(head, *args):
    if len(args) == 0:
        return head
    body = set()
    proofs = set()
    for p in args:
        if p.type == clingo.SymbolType.Function and p.name == 'proof':
            for subproof in p.arguments:
                body.add(subproof.arguments[0])
                proofs.add(subproof)
        else:
            body.add(p)
    proofs.add(clingo.Tuple([head] + sorted(body)))
    return clingo.Function('proof', sorted(proofs))
#end.
