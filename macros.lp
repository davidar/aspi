before(E,F) :- end_time(S,E), S < T, start_time(T,F).
during(E,F) :- start_time(S1,E), end_time(S2,E), start_time(T1,F), end_time(T2,F), T1 <= S1, S2 <= T2, E != F.
just_before(E,F) :- end_time(T-1,E), start_time(T,F).
