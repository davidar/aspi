%% aspi Prolog prelude
:- use_module(library(lists)).
:- use_module(library(apply)).
:- use_module(library(aggregate)).
:- set_prolog_flag(double_quotes, string).

%% Declare planning predicates as dynamic so they don't error when undefined.
%% In ASP, undefined predicates are simply false; dynamic gives the same semantics.
:- dynamic apply/2, adds/2, deletes/2, adds_temporary/2, demands/2, demands_not/2.
:- dynamic init/1, action/1, costs/2, rewards/2, goal/1.

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

%% Lattice tabling helpers for recursive min/max aggregation.
%% Used with :- table pred(lattice(my_min/3), +).
%% SWI-Prolog calls my_min(New, Old, Keep) to merge answers.
my_min(New, Old, Min) :- Min is min(New, Old).
my_max(New, Old, Max) :- Max is max(New, Old).

%% Meta-interpreter for proof tracking
%% prove(+Goal, -ProofTree) — re-derives Goal, exploring all clause choices.
%% Only traces user-defined predicates; built-ins and library predicates are
%% called directly. Different derivation paths produce different proof trees,
%% which gives bag ({{X}}?) its duplicates.
:- meta_predicate prove(0, -).
prove(true, true) :- !.
prove((A, B), (PA, PB)) :- !, prove(A, PA), prove(B, PB).
prove(Goal, leaf) :-
    \+ user_defined(Goal), !, call(Goal).
prove(Goal, Proof) :-
    clause(Goal, Body),
    (Body == true ->
        Proof = fact(Goal)
    ;
        prove(Body, BodyProof),
        Proof = step(Goal, BodyProof)
    ).

user_defined(Goal) :-
    \+ predicate_property(Goal, built_in),
    \+ predicate_property(Goal, imported_from(_)).

%% proof(ProofTree, Goal) — wrapper matching LDCS join convention (result first)
proof(Tree, Goal) :- prove(Goal, Tree).
