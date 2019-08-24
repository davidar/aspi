% PICK UP A BIG RED BLOCK.
goal_once(holding(X)) :- large(X), red(X), block(X).

% FIND A BLOCK WHICH IS TALLER THAN THE ONE YOU ARE HOLDING AND PUT IT INTO THE BOX.
goal_once(on(T, box)) :- block(T), taller_than(T,H), block(H), holds(holding(H)).

% WHAT DOES THE BOX CONTAIN?
:def holds(above(A,B), TIME) :- holds(on(A,B), TIME).
:def holds(above(A,C), TIME) :- holds(above(A,B), TIME), holds(above(B,C), TIME).
:def holds(in_box(X), TIME) :- holds(above(X, box), TIME).
show(X) :- holds(in_box(X)).

% WHAT IS THE PYRAMID SUPPORTED BY?
show(S) :- it(X), pyramid(X), holds(on(X,S)).

% HOW MANY BLOCKS ARE NOT IN THE BOX?
show(X) :- block(X), not holds(on(X, box)).

% IS AT LEAST ONE OF THEM NARROWER THAN THE ONE WHICH I TOLD YOU TO PICK UP?
show(X) :- it(X), narrower_than(X,Y), history(goal(holding(Y))).

% IS IT SUPPORTED?
show(on(X,Y)) :- it(X), holds(on(X,Y)).

% CAN A PYRAMID BE SUPPORTED BY A BLOCK?
show(true) :- action(put_on(P,B)), pyramid(P), block(B). \
show(false) :- not show(true).

% CAN A PYRAMID SUPPORT A PYRAMID?
show(true) :- action(put_on(P,Q)), pyramid(P), pyramid(Q). \
show(false) :- not show(true).

% STACK UP TWO PYRAMIDS.
goal_once(on(P,Q)) :- pyramid(P), pyramid(Q).

% WILL YOU PLEASE STACK UP BOTH OF THE RED BLOCKS AND EITHER A GREEN CUBE OR A PYRAMID?
:def holds(stack(A,B,C; A,C,B; B,A,C; B,C,A; C,A,B; C,B,A), TIME) :- holds(on(A,B), TIME), holds(on(B,C), TIME), C != table, C != box.
green_cube_or_pyramid(C) :- green(C), cube(C). \
green_cube_or_pyramid(C) :- pyramid(C). \
goal_once(stack(A,B,C)) :- red(A), block(A), red(B), block(B), A != B, green_cube_or_pyramid(C).

% WHICH CUBE IS SITTING ON THE TABLE?
show(X) :- cube(X), holds(on(X, table)). \
show(on(Y,X)) :- cube(X), holds(on(X, table)), holds(on(Y,X)).

% PUT A SMALL ONE ONTO THE GREEN CUBE WHICH SUPPORTS A PYRAMID.
goal_once(on(S,C)) :- small(S), block(S), green(C), cube(C), holds(on(P,C)), pyramid(P).

% PUT THE LITTLEST PYRAMID ON TOP OF IT.
smallest_pyramid(X) :- pyramid(X), smaller_than(X,P) : pyramid(P), P != X. \
goal(on(P,S)) :- history(counter-1, goal(on(S,_))), smallest_pyramid(P).

% DOES THE SHORTEST THING THE TALLEST PYRAMID'S SUPPORT SUPPORTS SUPPORT ANYTHING GREEN?
tallest_pyramid_support(S) :- holds(on(P,S)), pyramid(P), taller_than(P,Q) : pyramid(Q), P != Q. \
tps_supports(X) :- tallest_pyramid_support(S), holds(on(X,S)). \
shortest_tpss(X) :- tps_supports(X), shorter_than(X,Y) : tps_supports(Y), X != Y. \
show(Y) :- shortest_tpss(X), holds(on(Y,X)), green(Y).

% WHAT COLOR IS IT?
show(C) :- it(Y), holds(on(Y,X)), colour(C,X).

% HOW MANY THINGS ARE ON TOP OF GREEN CUBES?
show(X) :- holds(above(X,C)), green(C), cube(C).

% HAD YOU TOUCHED ANY PYRAMID BEFORE YOU PUT THE GREEN ONE ON THE LITTLE CUBE?
% WHEN DID YOU PICK IT UP?
touched(P,S) :- pyramid(P), apply(pickup(P),S), S < T-1, green(X), pyramid(X), apply(put_on(X,C),T), small(C), cube(C). \
show(P) :- touched(P,S). \
show(goal(G)) :- touched(P,S), plan_interval(C, T1, T2), T1 <= S, S <= T2, history(C, goal(G)).

% WHAT DID THE RED CUBE SUPPORT BEFORE YOU STARTED TO CLEAN IT OFF?
:def cleanoff(X,T) :- apply(pickup(Y), T), holds(on(Y,X), T-1).
show(X) :- holds(on(X,red_cube),S), S < T, cleanoff(red_cube, T).

% PUT THE BLUE PYRAMID ON THE BLOCK IN THE BOX.
goal(on(blue_pyramid,B)) :- block(B), holds(on(B,box)).

% IS THERE ANYTHING WHICH IS BIGGER THAN EVERY PYRAMID BUT IS NOT AS WIDE AS THE THING THAT SUPPORTS IT?
show(X) :- object(X), bigger_than(X,P) : pyramid(P); holds(on(X,B)), wider_than(B,X).

% A "STEEPLE" IS A STACK WHICH CONTAINS TWO GREEN CUBES AND A PYRAMID.
:def holds(steeple, TIME) :- holds(stack(A,B,C), TIME), green(A), cube(A), green(B), cube(B), A != B, pyramid(C).

% ARE THERE ANY STEEPLES NOW?
show(true) :- holds(steeple). \
show(false) :- not holds(steeple).

% BUILD ONE.
goal(steeple).

% CALL THE BIGGEST BLOCK "SUPERBLOCK".
:def superblock(B) :- block(B), bigger_than(B,X) : block(X), X != B.

% HAVE YOU PICKED SUPERBLOCK UP SINCE WE BEGAN?
picked_up(X) :- apply(pickup(X),T). \
show(true) :- picked_up(B), superblock(B). \
show(false) :- not picked_up(B), superblock(B).

thanks.
