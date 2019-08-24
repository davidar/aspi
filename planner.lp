#include <incmode>.

#program base.
% Define
state(F,0) :- init(F).

% Generate
{ apply(A,T) : action(A) } = 1 :- T = 1..now.

% Define
state(F,T) :- apply(A,T), adds(A,F).
del  (F,T) :- apply(A,T), deletes(A,F).
state(F,T) :- state(F,T-1), not del(F,T), T = 1..now.
holds(F,T) :- state(F,T).

#program step(t).
% Generate
{ apply(A, now+t) : action(A) } = 1.

% Test
:- apply(A, now+t), demands(A,F, true), not holds(F, now+t-1).
:- apply(A, now+t), demands(A,F, false),    holds(F, now+t-1).

% Define
state(F, now+t) :- apply(A, now+t), adds(A,F).
del  (F, now+t) :- apply(A, now+t), deletes(A,F).
state(F, now+t) :- state(F, now+t-1), not del(F, now+t).
holds(F, now+t) :- state(F, now+t).

% Display
retract(moves(now)).
assert(moves(now+t)) :- query(t).
assert(apply(A, now+t)) :- apply(A, now+t).
show(ok).
#show assert/1.
#show retract/1.
#show show/1.

#program check(t).
% Test
:- query(t), goal(F, true), not holds(F, now+t).
:- query(t), goal(F, false),    holds(F, now+t).
