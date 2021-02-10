#program base.
% Generate
{ apply(A,T) : action(A) } = 1 :- T = 1..M, tmax(M).
{ finished(T) : T = 0..M, tmax(M) } = 1.

% Test
:- apply(A,T), demands(A,F), not holds(F,T-1), T = 1..M, tmax(M).
:- apply(A,T), demands_not(A,F), holds(F,T-1), T = 1..M, tmax(M).

success(F,T) :- holds(F,T).
success(A,T) :- apply(A,T).
:- finished(M), goal(G), not success(G,M).

:- finished(F), apply(nop, T), T <= F.
:- finished(F), apply(A,T), A != nop, T > F.

% Optimise
costs(A,C) :- rewards(A,-C).
:~ apply(A,T), costs(A,C), T = now+1..M, tmax(M). [C,T]

#show already/1.
already(F) :- goal(F), holds(F,now).

% Display
retract(moves(now)).
assert(moves(M)) :- finished(M).
assert(apply(A,T)) :- apply(A,T), T = now+1..M, finished(M).
assert(plan_interval(counter, now+1, M)) :- finished(M).
#show assert/1.
#show retract/1.
#show ok/0.
