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

pickup(apply(pickup(X),  T), X)   :- apply(pickup(X),  T).
put_on(apply(put_on(X,Y),T), X,Y) :- apply(put_on(X,Y),T).

      on(holds(      on(X,Y),T), X,Y) :- holds(      on(X,Y),T).
supports(holds(supports(X,Y),T), X,Y) :- holds(supports(X,Y),T).
 left_of(holds( left_of(X,Y),T), X,Y) :- holds( left_of(X,Y),T).
 holding(holds( holding(X),  T), X)   :- holds( holding(X),  T).

cleanoff_at(X,T) :- apply(pickup(Y), T), holds(on(Y,X), T-1).
cleanoff(cleanoff_at(X,T), X) :- cleanoff_at(X,T).
start_time(T, cleanoff_at(X,T)) :- cleanoff_at(X,T).

picked_up(X) :- apply(pickup(X),T).

goal(history(C,goal(F)), F) :- history(C,goal(F)).

event(history(C,G)) :- history(C,G).
event(apply(A,T)) :- apply(A,T).

start_time(T1, history(C,G)) :- history(C,G), plan_interval(C, T1, T2).
  end_time(T2, history(C,G)) :- history(C,G), plan_interval(C, T1, T2).
start_time(T, apply(A,T)) :- apply(A,T).
  end_time(T, apply(A,T)) :- apply(A,T).
start_time(T, holds(P,T)) :- holds(P,T).
  end_time(T, holds(P,T)) :- holds(P,T).
