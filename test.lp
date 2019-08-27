% PICK UP A BIG RED BLOCK.
goal_once$holding[big red block]

% GRASP THE PYRAMID.
goal$holding[pyramid]

% FIND A BLOCK WHICH IS TALLER THAN THE ONE YOU ARE HOLDING AND PUT IT INTO THE BOX.
:def holding(X) :- holds(holding(X)).
goal_once$on[block taller_than.holding, box]

% WHAT DOES THE BOX CONTAIN?
:def holds(above(A,B), TIME) :- holds(on(A,B), TIME).
:def holds(above(A,C), TIME) :- holds(above(A,B), TIME), holds(above(B,C), TIME).
:def above(A,B) :- holds(above(A,B)).
[above.box]

% WHAT IS THE PYRAMID SUPPORTED BY?
:def holds(supports(A,B), TIME) :- holds(on(B,A), TIME).
:def supports(A,B) :- holds(supports(A,B)).
[supports[that pyramid]]

% HOW MANY BLOCKS ARE NOT IN THE BOX?
[block ~above.box]

% IS AT LEAST ONE OF THEM NARROWER THAN THE ONE WHICH I TOLD YOU TO PICK UP?
[that narrower_than.history$goal$holding]

% IS IT SUPPORTED?
[supports.that]

% CAN THE TABLE PICK UP BLOCKS?
[exists(table action$pickup.block)]

% CAN A PYRAMID BE SUPPORTED BY A BLOCK?
[exists(pyramid action$put_on.block)]

% CAN A PYRAMID SUPPORT A PYRAMID?
[exists(pyramid action$put_on.pyramid)]

% STACK UP TWO PYRAMIDS.
goal_once$on[pyramid, pyramid]

% WILL YOU PLEASE STACK UP BOTH OF THE RED BLOCKS AND EITHER A GREEN CUBE OR A PYRAMID?
:def holds(stack(A,B,C; A,C,B; B,A,C; B,C,A; C,A,B; C,B,A), TIME) :- holds(on(A,B), TIME), holds(on(B,C), TIME), not table(C), C != box.
goal_once$stack[red block, red block, green cube | pyramid]

% WHICH CUBE IS SITTING ON THE TABLE?
:def on(A,B) :- holds(on(A,B)).
[cube on.table]

% IS THERE A LARGE BLOCK BEHIND A PYRAMID?
:def holds(behind(B,A), TIME) :- holds(above(B,X), TIME), holds(above(A,Y), TIME), table(X), table(Y), holds(behind(X,Y), TIME).
:def behind(B,A) :- holds(behind(B,A)).
[large block behind.pyramid]

% PUT A SMALL ONE ONTO THE GREEN CUBE WHICH SUPPORTS A PYRAMID.
goal_once$on[small block, green cube supports.pyramid]

% PUT THE LITTLEST PYRAMID ON TOP OF IT.
:def that(X) :- history(counter-1, goal(on(X,_))).
goal_once$on[most(little, pyramid), that]

% DOES THE SHORTEST THING THE TALLEST PYRAMID'S SUPPORT SUPPORTS SUPPORT ANYTHING GREEN?
[green on.most(short, on.supports.most(tall, pyramid))]

% WHAT COLOR IS IT?
[colour.supports.that]

% HOW MANY THINGS ARE ON TOP OF GREEN CUBES?
[above[green cube]]

% HAD YOU TOUCHED ANY PYRAMID BEFORE YOU PUT THE GREEN ONE ON THE LITTLE CUBE?
:macro before(E,F) :- end_time(S,E), S < T, start_time(T,F).
[pickup.pyramid before.goal.=on[green pyramid, little cube]]

% WHEN DID YOU PICK IT UP?
show((E,goal(G))) :- that(E), E = apply(pickup(P),S), plan_times(C,S), history(C, goal(G)).

% WHY?
:def explain(apply(X,S), (apply(A,T), demands(A,F,true)))  :- adds(X,F),    plan_interval(C, T1, T2), T1 <= S, S <= T2, demands(A,F,true),  apply(A,T), S < T, T <= T2, S = 1..now.
:def explain(apply(X,S), (apply(A,T), demands(A,F,false))) :- deletes(X,F), plan_interval(C, T1, T2), T1 <= S, S <= T2, demands(A,F,false), apply(A,T), S < T, T <= T2, S = 1..now, holds(F, S-1).
show(R) :- that((E,G)), explain(E,R).

% WHY DID YOU CLEAR OFF THAT CUBE?
show(R) :- it((A, demands(pickup(C),on(Y,C),false))), cube(C), explain(A,R).

% WHY DID YOU DO THAT?
:def explain(apply(A,T), goal(G)) :- plan_interval(C,S,T), history(C, goal(G)), action(A).
show(R) :- it((A,D)), explain(A,R).
show(R) :- it((A,D)), explain(A,R).
show(R) :- it((A,D)), explain(A,R).

% WHY DID YOU DO THAT?
:def explain(goal(G), history(C, goal(G))) :- history(C, goal(G)).
show(R) :- it(G), explain(G,R).

% HOW DID YOU DO IT?
:def steps(C, apply(A,T)) :- plan_times(C,T), apply(A,T).
show(A) :- it(history(C,G)), steps(C,A).

% HOW MANY OBJECTS DID YOU TOUCH WHILE YOU WERE DOING IT?
show(X) :- it(apply(pickup(X), T)).

% WHAT DID THE RED CUBE SUPPORT BEFORE YOU STARTED TO CLEAN IT OFF?
:def cleanoff(X,T) :- apply(pickup(Y), T), holds(on(Y,X), T-1).
show(X) :- holds(on(X,red_cube),S), S < T, cleanoff(red_cube, T).

% THERE WERE FIVE BLOCKS TO THE LEFT OF THE BOX THEN.
:def holds(left_of(B,A), TIME) :- holds(above(B,X), TIME), holds(above(A,Y), TIME), table(X), table(Y), holds(left_of(X,Y), TIME).
show(X) :- cleanoff(red_cube,T), block(X), holds(left_of(X,box), T-1).
[count(that)]

% PUT THE BLUE PYRAMID ON THE BLOCK IN THE BOX.
goal$on[blue pyramid, block above.box]

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

% WHY DID YOU DROP IT?
:def explain(A,R) :- apply(A,T), explain(apply(A,T), R).
:def explain(A, nonexistent) :- action(A), not apply(A,T) : T = 1..now.
show(R) :- explain(put_on(B,T),R), superblock(B), table(T).

% IS THERE ANYTHING TO THE RIGHT OF THE RED PYRAMID?
:def holds(right_of(A,B), TIME) :- holds(left_of(B,A), TIME).
:def right_of(A,B) :- holds(right_of(A,B)).
goal_once(left_of(red_pyramid,box)).
[right_of[red pyramid]]

thanks.
