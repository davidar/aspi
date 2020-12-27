#program base.
#show what/1.
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

#script (python)
import clingo
def show(a):
    return clingo.String(str(a))
def concatenate(a, b):
    return a.string + b.string
def reverse(a):
    return clingo.String(a.string[::-1])

gathered = {}
def gather(i, a):
    if i not in gathered:
        gathered[i] = []
    gathered[i].append(a)
    return i
def sort(i):
    return list(enumerate(sorted(gathered[i]))) if i in gathered else []
#end.
