% PICK UP A BIG RED BLOCK.
goal_once(holding(X)) :- large(X), red(X), block(X).

% FIND A BLOCK WHICH IS TALLER THAN THE ONE YOU ARE HOLDING AND PUT IT INTO THE BOX.
goal_once(on(T, box)) :- block(T), taller_than(T,H), block(H), holds(holding(H)).

% WHAT DOES THE BOX CONTAIN?
show(X) :- holds(on(X, box)).

% WHAT IS THE PYRAMID SUPPORTED BY?
show(S) :- it(X), pyramid(X), holds(on(X,S)).

% HOW MANY BLOCKS ARE NOT IN THE BOX?
show(X) :- block(X), not holds(on(X, box)).

% IS AT LEAST ONE OF THEM NARROWER THAN THE ONE WHICH I TOLD YOU TO PICK UP?
show(X) :- it(X), narrower_than(X,Y), history(goal(holding(Y))).

% IS IT SUPPORTED?
show(on(X,Y)) :- it(X), holds(on(X,Y)).

% WILL YOU PLEASE STACK UP BOTH OF THE RED BLOCKS AND EITHER A GREEN CUBE OR A PYRAMID?
:def holds(stack(A,B,C; A,C,B; B,A,C; B,C,A; C,A,B; C,B,A), TIME) :- holds(on(A,B), TIME), holds(on(B,C), TIME), C != table, C != box.
green_cube_or_pyramid(C) :- green(C), cube(C). \
green_cube_or_pyramid(C) :- pyramid(C). \
goal_once(stack(A,B,C)) :- red(A), block(A), red(B), block(B), A != B, green_cube_or_pyramid(C).

% WHICH CUBE IS SITTING ON THE TABLE?
show(X) :- cube(X), holds(on(X, table)).

% PUT A SMALL ONE ONTO THE GREEN CUBE WHICH SUPPORTS A PYRAMID.
goal_once(on(S,C)) :- small(S), block(S), green(C), cube(C), holds(on(P,C)), pyramid(P).

% PUT THE LITTLEST PYRAMID ON TOP OF IT.
smallest_pyramid(X) :- pyramid(X), smaller_than(X,P) : pyramid(P), P != X. \
goal(on(P,S)) :- history(counter-1, goal(on(S,_))), smallest_pyramid(P).

% HOW MANY THINGS ARE ON TOP OF GREEN CUBES?
:def holds(above(A,B), TIME) :- holds(on(A,B), TIME).
:def holds(above(A,C), TIME) :- holds(above(A,B), TIME), holds(above(B,C), TIME).
show(X) :- holds(above(X,C)), green(C), cube(C).

% HAD YOU TOUCHED ANY PYRAMID BEFORE YOU PUT THE GREEN ONE ON THE LITTLE CUBE?
% WHEN DID YOU PICK IT UP?
show((P,S)) :- pyramid(P), apply(pickup(P),S), S < T, green(X), pyramid(X), apply(put_on(X,C),T), small(C), cube(C).

% WHAT DID THE RED CUBE SUPPORT BEFORE YOU STARTED TO CLEAN IT OFF?
show(X) :- holds(on(X,red_cube),S), S < T, apply(pickup(Y),T), holds(on(Y,red_cube),T-1).

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
