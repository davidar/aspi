:- module main.
:- interface.
:- import_module io.
:- pred main(io::di, io::uo) is det.
:- implementation.
:- import_module int, list, solutions, string.

sum([X|L], X+S) :- sum(L,S).
sum([], 0).

max([X|L], int.max(X,S)) :- max(L,S).
max([X], X).

min([X|L], int.min(X,S)) :- min(L,S).
min([X], X).

:- pred show(int, string).
show(X,S) :- format("%d", [i(X)], S).

:- pred reverse(string, string).
reverse(S, from_char_list(to_rev_char_list(S))).

:- pred sorted_solutions(pred(T), list(T)).
:- mode sorted_solutions(pred(out) is nondet, out) is det.
sorted_solutions(P, sort(S)) :-
    promise_equivalent_solutions[S] unsorted_solutions(P,S).
