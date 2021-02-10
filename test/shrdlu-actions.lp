#program base.
action(pickup(X)) :- object(X).
action(put_on(X,Y)) :- object(X), location(Y), X != Y.

costs(pickup(X), 1) :- object(X).
costs(put_on(X,Y), 1) :- object(X), location(Y), X != Y.

pickup(apply(pickup(X),T), X)   :- apply(pickup(X),T).
put_on(apply(put_on(X,Y),T), X,Y) :- apply(put_on(X,Y),T).

demands_not(pickup(X), on(A,X)) :- object(X), object(A).
demands_not(pickup(X), holding(Y)) :- object(X), object(Y).
demands(put_on(X,Y), holding(X)) :- object(X), location(Y).
%demands_not(put_on(X,Y), on(B,Y)) :- object(X), location(Y), object(B), not table(Y), Y != box.
demands_not(put_on(X,Y), on(B,Y)) :- object(X), small(Y), object(B).
demands_not(put_on(X,Y), on(B,Y)) :- large(X), large(Y), object(B).
demands_not(put_on(X,Y), many_on(Y)) :- object(X), large(Y).
demands_not(put_on(X,Y), many_on(Y)) :- object(X), table(Y).
demands_not(put_on(X, box), many_on(box)) :- object(X).

adds(pickup(X), holding(X)) :- object(X).
adds(put_on(X,Y), on(X,Y)) :- object(X), location(Y).

deletes(pickup(X), on(X,Z)) :- object(X), location(Z).
deletes(put_on(X,Y), holding(X)) :- object(X), location(Y).
