#program base.
% https://www.uv.es/ivorra/Filosofia/TC/cubos.png
init(on(
  green_cube_1,big_red; big_red,table;
  green_pyramid,red_cube; red_cube,table;
  red_pyramid,green_cube_2; green_cube_2,table;
  blue_pyramid,box; box,table;
  blue_block,table)).

pyramid(red_pyramid; green_pyramid; blue_pyramid).
cube(red_cube; green_cube_1; green_cube_2).
block(big_red; blue_block).
block(X) :- cube(X).

object(X) :- block(X).
object(X) :- pyramid(X).

location(table; box).
location(X) :- block(X).

red(big_red; red_cube; red_pyramid).
green(green_cube_1; green_cube_2; green_pyramid).
blue(blue_block; blue_pyramid).
colour(red, X) :- red(X).
colour(green, X) :- green(X).
colour(blue, X) :- blue(X).

large(big_red; green_cube_1; green_cube_2; blue_block).
small(red_cube).

taller_than(blue_block,big_red; red_pyramid,blue_pyramid; blue_pyramid,green_pyramid; red_pyramid,red_cube).
taller_than(A,C) :- taller_than(A,B), taller_than(B,C).
shorter_than(A,B) :- taller_than(B,A).

bigger_than(blue_block,P) :- pyramid(P).
bigger_than(
  blue_block,big_red; big_red,green_cube_1; big_red,green_cube_2; green_cube_1,red_cube; green_cube_2,red_cube;
  blue_pyramid,red_pyramid; red_pyramid,green_pyramid).
bigger_than(A,C) :- bigger_than(A,B), bigger_than(B,C).
smaller_than(A,B) :- bigger_than(B,A).

wider_than(box,blue_block; big_red,red_cube).
narrower_than(A,B) :- wider_than(B,A).

holds(num_on(N,X), T) :- location(X), T = 0..now, #count { Y : object(Y), holds(on(Y,X), T) } = N.
holds(many_on(X), T) :- holds(num_on(N,X), T), N > 1.
#program step(t).
holds(num_on(N,X), now+t) :- location(X), #count { Y : object(Y), holds(on(Y,X), now+t) } = N.
holds(many_on(X), now+t) :- holds(num_on(N,X), now+t), N > 1.
#program base.
