#program base.
peg(a;b;c).
disk(1..4).
init(on(1..4,a)).

left(a).
middle(b).
right(c).

#show describe/3.
describe(a, left, peg).
describe(b, middle, peg).
describe(c, right, peg).

holds(on_same(D,E), T) :- holds(on(D,P), T), holds(on(E,P), T).
#program step(t).
holds(on_same(D,E), now+t) :- holds(on(D,P), now+t), holds(on(E,P), now+t).
#program base.

on(A,B) :- holds(on(A,B)).
