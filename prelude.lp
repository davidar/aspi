#program base.
history(counter, goal(F)) :- goal(F,true).
history(counter, goal(F,B)) :- goal(F,B).
history(counter, show(X)) :- show(X).
#show history/2.

it(X) :- history(counter-1, show(X)).
holds(X) :- holds(X, now).
goal(F,true) :- goal(F).
history(F) :- history(C,F).
