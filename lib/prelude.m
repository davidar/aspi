:- module main.
:- interface.
:- import_module io.
:- pred main(io::di, io::uo) is det.
:- implementation.
:- import_module int, list, solutions, string.

sum(X + S, [X|L]) :- sum(S,L).
sum(0, []).

max(int.max(X,S), [X|L]) :- max(S,L).
max(X, [X]).

:- pred show(string, int).
show(S, X) :- format("%d", [i(X)], S).

:- pred reverse(string, string).
reverse(from_char_list(to_rev_char_list(S)), S).

:- pred sorted_solutions(pred(T), list(T)).
:- mode sorted_solutions(pred(out) is nondet, out) is det.
sorted_solutions(P, sort(S)) :-
    promise_equivalent_solutions[S] unsorted_solutions(P,S).
