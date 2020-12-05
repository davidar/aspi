#program base.
action(move(D,P)) :- disk(D), peg(P).

demands(move(D,P), on(E,P), false) :- disk(D), disk(E), peg(P), E < D.
demands(move(D,P), on_same(D,E), false) :- disk(D), disk(E), peg(P), E < D.

adds(move(D,P), on(D,P)) :- disk(D), peg(P).

deletes(move(D,P), on(D,Q)) :- disk(D), peg(P), peg(Q).
