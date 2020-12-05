#program base.
action(pickup(X)) :- object(X).
action(put_on(X,Y)) :- object(X), location(Y), X != Y.

pickup(apply(pickup(X),T), X)   :- apply(pickup(X),T).
put_on(apply(put_on(X,Y),T), X,Y) :- apply(put_on(X,Y),T).

demands(pickup(X), on(A,X), false) :- object(X), object(A).
demands(pickup(X), holding(Y), false) :- object(X), object(Y).
demands(put_on(X,Y), holding(X), true) :- object(X), location(Y).
%demands(put_on(X,Y), on(B,Y), false) :- object(X), location(Y), object(B), not table(Y), Y != box.
demands(put_on(X,Y), on(B,Y), false) :- object(X), small(Y), object(B).
demands(put_on(X,Y), on(B,Y), false) :- large(X), large(Y), object(B).
demands(put_on(X,Y), many_on(Y), false) :- object(X), large(Y).
demands(put_on(X,Y), many_on(Y), false) :- object(X), table(Y).
demands(put_on(X, box), many_on(box), false) :- object(X).

adds(pickup(X), holding(X)) :- object(X).
adds(put_on(X,Y), on(X,Y)) :- object(X), location(Y).

deletes(pickup(X), on(X,Z)) :- object(X), location(Z).
deletes(put_on(X,Y), holding(X)) :- object(X), location(Y).
