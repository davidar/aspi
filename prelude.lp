#program base.
history(counter, goal(F)) :- goal(F).
history(counter, show(X)) :- show(X).
#show history/2.

it(X) :- history(counter-1, show(X)).
that(X) :- it(X).
holds(X) :- holds(X, now).
history(F) :- history(C,F).
plan_times(C,T) :- plan_interval(C, T1, T2), T = T1..T2.

pickup(apply(pickup(X),T), X) :- apply(pickup(X),T).
put_on(apply(put_on(X,Y),T), X,Y) :- apply(put_on(X,Y),T).
goal(history(C,goal(F)), F) :- history(C,goal(F)).
start_time(T1, history(C,G)) :- history(C,G), plan_interval(C, T1, T2).
  end_time(T2, history(C,G)) :- history(C,G), plan_interval(C, T1, T2).
start_time(T, apply(A,T)) :- apply(A,T).
  end_time(T, apply(A,T)) :- apply(A,T).
