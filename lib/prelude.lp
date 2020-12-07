#program base.
#show what/1.
#show history/2.
history(counter, goal(F)) :- goal(F).
history(counter, what(X)) :- what(X).

now(now).

that(X,N) :- history(counter-N, what(X)).
that(X) :- that(X,1).

#script (python)
import clingo
def show(a):
    return clingo.String(str(a))
def concatenate(a, b):
    return a.string + b.string
def reverse(a):
    return clingo.String(a.string[::-1])
#end.
