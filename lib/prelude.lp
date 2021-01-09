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

n1(X) :- X = 1..9.
n2(X) :- X = 1..99.
n3(X) :- X = 1..999.
n4(X) :- X = 1..9999.

z1(X) :- X = 0..9.
z2(X) :- X = 0..99.
z3(X) :- X = 0..999.
z4(X) :- X = 0..9999.

i1(X) :- X = -9..9.
i2(X) :- X = -99..99.
i3(X) :- X = -999..999.
i4(X) :- X = -9999..9999.

gather(@gather(I,X)) :- gather(I,X).
enumerate(I,J,X) :- gather(I), (J-1,X) = @sort(I).
productof(I,X) :- gather(I), X = @productof(I).
setof(I,X) :- gather(I), X = @setof(I).
bagof(I,X) :- gather(I), X = @bagof(I).

#script (python)
import clingo
import math
import sys

def show(a):
    return clingo.String(str(a))
def concatenate(a, b):
    return a.string + b.string
def reverse(a):
    return clingo.String(a.string[::-1])
def substring(a):
    s = a.string
    n = len(s)
    for start in range(0,n+1):
        for end in range(start,n+1):
            yield s[start:end]
def length(a):
    return clingo.Number(len(a.string))

gathered = {}
def gather(i, a):
    if i not in gathered:
        gathered[i] = []
    gathered[i].append(a)
    return i
def sort(i):
    return list(enumerate(sorted(gathered[i]))) if i in gathered else []
def productof(i):
    try:
        return math.prod(x.number for x in gathered[i]) % sys.maxsize
    except:
        return clingo.Function('nan')
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
