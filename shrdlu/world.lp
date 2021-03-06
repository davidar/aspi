#program base.
% https://www.uv.es/ivorra/Filosofia/TC/cubos.png
init(on(
  green_cube_1,big_red; big_red,table_front_left;
  green_pyramid,red_cube; red_cube,table_front_left;
  red_pyramid,green_cube_2; green_cube_2,table_front_right;
  blue_pyramid,box; box,table_back_right;
  blue_block,table_back_left)).

init( behind((table_back_left;table_back_right), (table_front_left;table_front_right))).
init(left_of((table_front_left;table_back_left), (table_front_right;table_back_right))).

pyramid(red_pyramid; green_pyramid; blue_pyramid).
cube(red_cube; green_cube_1; green_cube_2).
block(big_red; blue_block).
block(X) :- cube(X).

object(X) :- block(X).
object(X) :- pyramid(X).

table(table_front_left; table_front_right; table_back_left; table_back_right).
box(box).

describe(big_red, large, red, block).
describe(red_cube, red, cube).
describe(blue_block, blue, block).
describe(P, C, pyramid) :- pyramid(P), colour(C,P).
describe(T, table) :- table(T).
describe(C, green, cube) :- green(C), cube(C).

#show describe_extra/3.
describe_extra(T, C, holding) :-
  green(C), cube(C), holds(holding(C), T).
describe_extra(T, C, supports(X)) :-
  green(C), cube(C), holds(supports(C,X), T).
describe_extra(T, C, not_supports(X)) :-
  green(C), cube(C), not holds(supporter(C), T),
  green(G), cube(G),    holds(supports(G,X), T), C != G, C != X.
describe_extra(T, C, on(X)) :-
  green(C), cube(C), not holds(supporter(C), T),
  green(G), cube(G), not holds(supporter(G), T), C != G,
  holds(on(C,X), T), not table(X).

location(box).
location(X) :- table(X), not init(on(box, X)).
location(X) :- block(X).

red(big_red; red_cube; red_pyramid).
green(green_cube_1; green_cube_2; green_pyramid).
blue(blue_block; blue_pyramid).
colour(red, X) :- red(X).
colour(green, X) :- green(X).
colour(blue, X) :- blue(X).

big(X) :- large(X).
large(big_red; green_cube_1; green_cube_2; blue_block).
small(red_cube).
little(X) :- small(X).

taller_than(blue_block,big_red; red_pyramid,blue_pyramid; blue_pyramid,green_pyramid; red_pyramid,red_cube).
taller_than(A,C) :- taller_than(A,B), taller_than(B,C).
tall(A,B) :- taller_than(A,B).
shorter_than(A,B) :- taller_than(B,A).
short(A,B) :- shorter_than(A,B).

bigger_than(blue_block,P) :- pyramid(P).
bigger_than(L,green_pyramid) :- large(L).
bigger_than(
  blue_block,big_red; big_red,green_cube_1; big_red,green_cube_2; green_cube_1,red_cube; green_cube_2,red_cube;
  blue_pyramid,red_pyramid; red_pyramid,green_pyramid).
bigger_than(A,C) :- bigger_than(A,B), bigger_than(B,C).
big(A,B) :- bigger_than(A,B).
smaller_than(A,B) :- bigger_than(B,A).
small(A,B) :- smaller_than(A,B).
little(A,B) :- small(A,B).

wider_than(box, X) :- object(X).
wider_than(T,X) :- table(T), object(X).
wider_than(big_red,red_cube).
wide(A,B) :- wider_than(A,B).
narrower_than(A,B) :- wider_than(B,A).
narrow(A,B) :- narrower_than(A,B).

holds(num_on(N,X), T) :- location(X), T = 0..now, #count { Y : object(Y), holds(on(Y,X), T) } = N.
holds(many_on(X), T) :- holds(num_on(N,X), T), N > 1.
holds(stack(A,B; B,A), T) :- holds(on(A,B), T), not table(B), B != box.
holds(stack(A,B,C; A,C,B; B,A,C; B,C,A; C,A,B; C,B,A), T) :- holds(on(A,B), T), holds(on(B,C), T), not table(C), C != box.
holds(above(A,B), T) :- holds(on(A,B), T).
holds(above(A,C), T) :- holds(above(A,B), T), holds(above(B,C), T).
holds(in(A,B), T) :- holds(above(A,B), T).
holds(contains(A,B), T) :- holds(in(B,A), T).
holds(supports(A,B), T) :- holds(on(B,A), T).
holds(supporter(X), T) :- holds(supports(X,Y), T).
holds(behind(B,A), T) :- holds(above(B,X), T), holds(above(A,Y), T), table(X), table(Y), holds(behind(X,Y), T).
holds(left_of(B,A), T) :- holds(above(B,X), T), holds(above(A,Y), T), table(X), table(Y), holds(left_of(X,Y), T).
holds(right_of(A,B), T) :- holds(left_of(B,A), T).

holding(X) :- holds(holding(X)).
on(A,B) :- holds(on(A,B)).
above(A,B) :- holds(above(A,B)).
in(A,B) :- holds(in(A,B)).
contains(A,B) :- holds(contains(A,B)).
supports(A,B) :- holds(supports(A,B)).
behind(B,A) :- holds(behind(B,A)).
left_of(A,B) :- holds(left_of(A,B)).
right_of(A,B) :- holds(right_of(A,B)).

on(holds(on(X,Y),T), X,Y) :- holds(on(X,Y),T).
supports(holds(supports(X,Y),T), X,Y) :- holds(supports(X,Y),T).
left_of(holds(left_of(X,Y),T), X,Y) :- holds(left_of(X,Y),T).
holding(holds(holding(X),T), X) :- holds(holding(X),T).

cleanoff_at(X,T) :- holds(on(Y,X), T-1), not holds(on(Y,X), T).
cleanoff(cleanoff_at(X,T), X) :- cleanoff_at(X,T).
start_time(T, cleanoff_at(X,T)) :- cleanoff_at(X,T).
