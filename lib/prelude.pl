%% aspi Prolog prelude
:- use_module(library(lists)).
:- use_module(library(apply)).
:- use_module(library(aggregate)).
:- set_prolog_flag(double_quotes, atom).

%% String operations
:- discontiguous concatenate/3.
concatenate(X, A, B) :- atom(A), atom(B), atom_concat(A, B, X).
:- discontiguous concatenate/4.
concatenate(X, A, B, C) :- atom(A), atom(B), atom(C),
    atom_concat(A, B, T), atom_concat(T, C, X).

:- discontiguous show/2.
show(X, A) :- term_to_atom(A, X).

:- discontiguous reverse_str/2.
reverse_str(X, A) :- atom_chars(A, Cs), reverse(Cs, Rs), atom_chars(X, Rs).

:- discontiguous length_str/2.
length_str(X, A) :- atom_length(A, X).

%% exists(X) is always true — transparent marker for existential queries
exists(_).

%% Null value (for LEFT JOIN / short_disj fallback)
:- discontiguous null/1.
null(null).

%% Arithmetic helpers
:- discontiguous multiple/2.
multiple(X, Y) :- 0 is X mod Y.

:- discontiguous even/1.
even(X) :- 0 is X mod 2.

:- discontiguous odd/1.
odd(X) :- 1 is X mod 2.

%% Aggregation helpers — use builtins from library(lists)
%% sum_list/2, min_list/2, max_list/2 are already available
count_of(L, N) :- length(L, N).
product_of([], 1).
product_of([H|T], P) :- product_of(T, P1), P is P1 * H.
