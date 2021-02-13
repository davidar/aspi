#program base.
#show what/1.
#show yes/0.
#show no/0.
#show history/2.
#show describe/2.
#show describe/3.
#show describe/4.
#show describe/5.

true(true).
false(false).
now(now).

history(counter, goal(F)) :- goal(F).
history(counter, what(X)) :- what(X).
that(X,N) :- history(counter-N, what(X)).
that(X) :- that(X,1).

proof(@proof(csv(V,R,C)),csv(V,R,C)) :- csv(V,R,C).
proof(@proof(csv_cols(C,R)),csv_cols(C,R)) :- csv_cols(C,R).
proof(@proof(csv_rows(R)),csv_rows(R)) :- csv_rows(R).

gather(@gather(I,X)) :- gather(I,X).
setof_(I,X) :- gather(I), gather(I,Y), X = @setof(I).
setof(I,S) :- setof_(I,S), @countof(S) = #max { @countof(X) : setof_(I,X) }.
proof(@proof(setof(I,X)),setof(I,X)) :- setof(I,X).
bagof_(I,X) :- gather(I), gather(I,Y), X = @bagof(I).
bagof(I,S) :- bagof_(I,S), @countof(S) = #max { @countof(X) : bagof_(I,X) }.
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
def setof(i):
    if i not in gathered:
        return clingo.Function('empty')
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
def minof(a):
    return min(x.number for x in a.arguments)
def maxof(a):
    return max(x.number for x in a.arguments)
def memberof(a):
    return a.arguments
def enumerateof(a):
    return list((i+1,x) for i,x in enumerate(sorted(a.arguments)))

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
