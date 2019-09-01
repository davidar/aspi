#program base.
because(apply(X,S), apply(A,T)) :- adds(X,F),    plan_interval(C, T1, T2), T1 <= S, S <= T2, demands(A,F,true),  apply(A,T), S < T, T <= T2, S = 1..now.
because(apply(X,S), apply(A,T)) :- deletes(X,F), plan_interval(C, T1, T2), T1 <= S, S <= T2, demands(A,F,false), apply(A,T), S < T, T <= T2, S = 1..now, holds(F, S-1).
because(apply(A,T), history(C, goal(G))) :- plan_interval(C,S,T), history(C, goal(G)), action(A).
because(A,R) :- apply(A,T), because(apply(A,T), R).
because(A, nonexistent) :- action(A), not apply(A,T) : T = 1..now.
why(R,E) :- because(E,R).
