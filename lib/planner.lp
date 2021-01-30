#program base.
% Define
state(F,0) :- init(F).
action(nop).
costs(nop, 0).
tmax(20).

% Generate
{ apply(A,T) : action(A) } = 1 :- T = 1..M, tmax(M).
{ finished(T) : T = 0..M, tmax(M) } = 1.

% Test
:- apply(A,T), demands(A,F), not holds(F,T-1), T = 1..M, tmax(M).
:- apply(A,T), demands_not(A,F), holds(F,T-1), T = 1..M, tmax(M).

success(F,T) :- holds(F,T).
success(A,T) :- apply(A,T).
:- tmax(M), goal(G), not success(G,M).

:- finished(F), apply(nop, T), T <= F.
:- finished(F), apply(A,T), A != nop, T > F.

% Optimise
:~ apply(A,T), costs(A,C), T = 1..M, tmax(M). [C,T]

% Define
state(F,T) :- apply(A,T), adds(A,F).
del  (F,T) :- apply(A,T), deletes(A,F).
state(F,T) :- state(F,T-1), not del(F,T), T = 1..M, tmax(M).
holds(F,T) :- state(F,T).

#show already/1.
already(F) :- goal(F), holds(F,now).

% Display
ok :- tmax(M), goal(G), success(G,M).
retract(moves(now)) :- ok.
assert(moves(M)) :- ok, finished(M).
assert(apply(A,T)) :- ok, apply(A,T), T = 1..M, finished(M).
assert(plan_interval(counter, now+1, M)) :- ok, finished(M).
#show assert/1.
#show retract/1.
#show ok/0.
