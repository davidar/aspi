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

#show describe/1.
#show describe/2.
#show describe/3.
#show describe/4.
#show describe/5.
#show describe/6.
#show describe/7.
#show describe/8.
#show describe/9.
describe(big_red, large, red, block).
describe(red_cube, red, cube).
describe(blue_block, blue, block).
describe(P, C, pyramid) :- pyramid(P), colour(C,P).
describe(T, table) :- table(T).
describe(C, green, cube, supports(X)) :- green(C), cube(C), supports(C,X).
describe(C, green, cube, not_supports(X)) :- green(C), cube(C), not supports_something(C), green(G), cube(G), C != G, supports(G,X), C != X.

supports_something(X) :- supports(X,Y).

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
holds(behind(B,A), T) :- holds(above(B,X), T), holds(above(A,Y), T), table(X), table(Y), holds(behind(X,Y), T).
holds(left_of(B,A), T) :- holds(above(B,X), T), holds(above(A,Y), T), table(X), table(Y), holds(left_of(X,Y), T).
holds(right_of(A,B), T) :- holds(left_of(B,A), T).
#program step(t).
holds(num_on(N,X), now+t) :- location(X), #count { Y : object(Y), holds(on(Y,X), now+t) } = N.
holds(many_on(X), now+t) :- holds(num_on(N,X), now+t), N > 1.
holds(stack(A,B; B,A), now+t) :- holds(on(A,B), now+t), not table(B), B != box.
holds(stack(A,B,C; A,C,B; B,A,C; B,C,A; C,A,B; C,B,A), now+t) :- holds(on(A,B), now+t), holds(on(B,C), now+t), not table(C), C != box.
holds(above(A,B), now+t) :- holds(on(A,B), now+t).
holds(above(A,C), now+t) :- holds(above(A,B), now+t), holds(above(B,C), now+t).
holds(in(A,B), now+t) :- holds(above(A,B), now+t).
holds(contains(A,B), now+t) :- holds(in(B,A), now+t).
holds(supports(A,B), now+t) :- holds(on(B,A), now+t).
holds(behind(B,A), now+t) :- holds(above(B,X), now+t), holds(above(A,Y), now+t), table(X), table(Y), holds(behind(X,Y), now+t).
holds(left_of(B,A), now+t) :- holds(above(B,X), now+t), holds(above(A,Y), now+t), table(X), table(Y), holds(left_of(X,Y), now+t).
holds(right_of(A,B), now+t) :- holds(left_of(B,A), now+t).
#program base.

holding(X) :- holds(holding(X)).
on(A,B) :- holds(on(A,B)).
above(A,B) :- holds(above(A,B)).
in(A,B) :- holds(in(A,B)).
contains(A,B) :- holds(contains(A,B)).
supports(A,B) :- holds(supports(A,B)).
behind(B,A) :- holds(behind(B,A)).
left_of(A,B) :- holds(left_of(A,B)).
right_of(A,B) :- holds(right_of(A,B)).
