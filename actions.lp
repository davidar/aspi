action(pickup(X)) :- object(X).
action(put_on(X,Y)) :- object(X), location(Y), X != Y.

demands(pickup(X), on(A,X), false) :- object(X), object(A).
demands(pickup(X), holding(Y), false) :- object(X), object(Y).
demands(put_on(X,Y), holding(X), true) :- object(X), location(Y).
demands(put_on(X,Y), on(B,Y), false) :- object(X), location(Y), object(B), Y != table, Y != box.

adds(pickup(X), holding(X)) :- object(X).
adds(put_on(X,Y), on(X,Y)) :- object(X), location(Y).

deletes(pickup(X), on(X,Z)) :- object(X), location(Z).
deletes(put_on(X,Y), holding(X)) :- object(X), location(Y).
