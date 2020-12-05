#program base.
#show what/1.
#show history/2.
history(counter, goal(F)) :- goal(F).
history(counter, what(X)) :- what(X).

now(now).

that(X,N) :- history(counter-N, what(X)).
that(X) :- that(X,1).

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
