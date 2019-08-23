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

large(big_red; green_cube_1; green_cube_2; blue_block).
small(red_cube).

taller_than(blue_block,big_red).

bigger_than(blue_block,P) :- pyramid(P).
bigger_than(
  blue_block,big_red; big_red,green_cube_1; big_red,green_cube_2; green_cube_1,red_cube; green_cube_2,red_cube;
  blue_pyramid,red_pyramid; red_pyramid,green_pyramid).
bigger_than(A,C) :- bigger_than(A,B), bigger_than(B,C).
smaller_than(A,B) :- bigger_than(B,A).

wider_than(box,blue_block; big_red,red_cube).
narrower_than(A,B) :- wider_than(B,A).
