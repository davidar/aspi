before(E,F) :- end_time(S,E), S = 0..T-1, start_time(T,F).
during(E,F) :- start_time(S1,E), end_time(S2,E), start_time(T1,F), end_time(T2,F), S1 = T1..T2, S2 = S1..T2, E != F.
just_before(E,F) :- end_time(T-1,E), start_time(T,F).

multiple(X,Y) :- X \ Y = 0.
even(X) :- X \ 2 = 0.

show(X,A) :- X = @show(A).
concatenate(X,A,B) :- X = @concatenate(A,B).
reverse(X,A) :- X = @reverse(A).
