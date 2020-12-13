#program base.
#show what/1.
#show history/2.
history(counter, goal(F)) :- goal(F).
history(counter, what(X)) :- what(X).

now(now).

that(X,N) :- history(counter-N, what(X)).
that(X) :- that(X,1).

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
