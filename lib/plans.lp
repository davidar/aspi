#program base.
state(F,0) :- init(F).
action(nop).
costs(nop, 0).
tmax(now + 20).

state(F,T) :- apply(A,T), adds(A,F).
del  (F,T) :- apply(A,T), deletes(A,F).
state(F,T) :- state(F,T-1), not del(F,T), T = 1..M, tmax(M).
holds(F,T) :- state(F,T).

holds(X) :- holds(X, now).
history(F) :- history(C,F).
command(G) :- history(goal(G)).

plan_times(C,T) :- plan_interval(C, T1, T2), T = T1..T2.

goal(history(C,goal(F)), F) :- history(C,goal(F)).

event(history(C,G)) :- history(C,G).
event(apply(A,T)) :- apply(A,T).

start_time(T1, history(C,G)) :- history(C,G), plan_interval(C, T1, T2).
  end_time(T2, history(C,G)) :- history(C,G), plan_interval(C, T1, T2).
start_time(T, apply(A,T)) :- apply(A,T).
  end_time(T, apply(A,T)) :- apply(A,T).
start_time(T, holds(P,T)) :- holds(P,T).
  end_time(T, holds(P,T)) :- holds(P,T).

because(apply(X,S), apply(A,T)) :- adds(X,F),    plan_interval(C, T1, T2), T1 <= S, S <= T2, demands(A,F,true),  apply(A,T), S < T, T <= T2, S = 1..now.
because(apply(X,S), apply(A,T)) :- deletes(X,F), plan_interval(C, T1, T2), T1 <= S, S <= T2, demands(A,F,false), apply(A,T), S < T, T <= T2, S = 1..now, holds(F, S-1).
because(apply(A,T), history(C, goal(G))) :- plan_interval(C,S,T), history(C, goal(G)), action(A).
because(A,R) :- apply(A,T), because(apply(A,T), R).
because(A, nonexistent) :- action(A), not apply(A,T) : T = 1..now.
why(R,E) :- because(E,R).
