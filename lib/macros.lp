n1(X) :- X = 1..9.
n2(X) :- X = 1..99.
n3(X) :- X = 1..999.
n4(X) :- X = 1..9999.

z1(X) :- X = 0..9.
z2(X) :- X = 0..99.
z3(X) :- X = 0..999.
z4(X) :- X = 0..9999.

i1(X) :- X = -9..9.
i2(X) :- X = -99..99.
i3(X) :- X = -999..999.
i4(X) :- X = -9999..9999.

before(E,F) :- end_time(S,E), S = 0..T-1, start_time(T,F).
during(E,F) :- start_time(S1,E), end_time(S2,E), start_time(T1,F), end_time(T2,F), S1 = T1..T2, S2 = S1..T2, E != F.
just_before(E,F) :- end_time(T-1,E), start_time(T,F).

negate(X,Y) :- X = -Y.
multiple(X,Y) :- X \ Y = 0.
even(X) :- X \ 2 = 0.
odd(X) :- X \ 2 = 1.

show(X,A) :- X = @show(A).
concatenate(X,A,B) :- X = @concatenate(A,B).
concatenate(X,A,B,C) :- X = @concatenate(A,Y), Y = @concatenate(B,C).
reverse(X,A) :- X = @reverse(A).
substring(X,A,S,L) :- X = @substring(A,S,L).
substring(X,A) :- X = @substring(A,S,L), N = @length(A), S = 1..N, M = N-S+1, L = 0..M.
length(X,A) :- X = @length(A).
decimal(X,A) :- X = @decimal(A).
permutation(X,A) :- X = @permutation(A).
codepoint(X,A) :- X = @codepoint(A).

count(X,L) :- X = @countof(L).
sum(X,L) :- X = @sumof(L).
product(X,L) :- X = @productof(L).
min(X,L) :- X = @minof(L).
max(X,L) :- X = @maxof(L).
