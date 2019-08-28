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
[#any(table action$pickup.block)]

% CAN A PYRAMID BE SUPPORTED BY A BLOCK?
[#any(pyramid action$put_on.block)]

% CAN A PYRAMID SUPPORT A PYRAMID?
[#any(pyramid action$put_on.pyramid)]

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
goal_once$on[#most(little, pyramid), that]

% DOES THE SHORTEST THING THE TALLEST PYRAMID'S SUPPORT SUPPORTS SUPPORT ANYTHING GREEN?
[green on.#most(short, on.supports.#most(tall, pyramid))]

% WHAT COLOR IS IT?
[colour.supports.that]

% HOW MANY THINGS ARE ON TOP OF GREEN CUBES?
[above[green cube]]

% HAD YOU TOUCHED ANY PYRAMID BEFORE YOU PUT THE GREEN ONE ON THE LITTLE CUBE?
:macro before(E,F) :- end_time(S,E), S < T, start_time(T,F).
[pickup.pyramid before.goal.=on[green pyramid, little cube]]

% WHEN DID YOU PICK IT UP?
:def event(history(C,G)) :- history(C,G).
:macro during(E,F) :- start_time(S1,E), end_time(S2,E), start_time(T1,F), end_time(T2,F), T1 <= S1, S2 <= T2, E != F.
[event during'.that]

% WHY?
[why.that.2]

% WHY DID YOU DO THAT?
[why.that]
[why.that]

% HOW DID YOU DO IT?
:def event(apply(A,T)) :- apply(A,T).
[event during.that]

% HOW MANY OBJECTS DID YOU TOUCH WHILE YOU WERE DOING IT?
[#count(pickup.object during.that.2)]

% WHAT DID THE RED CUBE SUPPORT BEFORE YOU STARTED TO CLEAN IT OFF?
:def end_time(T, holds(P,T)) :- holds(P,T).
:def cleanoff_at(X,T) :- apply(pickup(Y), T), holds(on(Y,X), T-1).
:def cleanoff(cleanoff_at(X,T), X) :- cleanoff_at(X,T).
:def start_time(T, cleanoff_at(X,T)) :- cleanoff_at(X,T).
[on[X red cube; before.cleanoff.X]]

% THERE WERE FIVE BLOCKS TO THE LEFT OF THE BOX THEN.
:def holds(left_of(B,A), TIME) :- holds(above(B,X), TIME), holds(above(A,Y), TIME), table(X), table(Y), holds(left_of(X,Y), TIME).
show(X) :- cleanoff_at(red_cube,T), block(X), holds(left_of(X,box), T-1).
[#count(that)]

% PUT THE BLUE PYRAMID ON THE BLOCK IN THE BOX.
goal$on[blue pyramid, block above.box]

% IS THERE ANYTHING WHICH IS BIGGER THAN EVERY PYRAMID BUT IS NOT AS WIDE AS THE THING THAT SUPPORTS IT?
[X object #each(bigger_than, pyramid) on.wider_than.X]

% A "STEEPLE" IS A STACK WHICH CONTAINS TWO GREEN CUBES AND A PYRAMID.
:def steeple$stack[green cube, green cube, pyramid]

% ARE THERE ANY STEEPLES NOW?
[#any(steeple holds)]

% BUILD ONE.
goal_once[steeple]

% CALL THE BIGGEST BLOCK "SUPERBLOCK".
:def superblock[#most(big, block)]

% HAVE YOU PICKED SUPERBLOCK UP SINCE WE BEGAN?
:def picked_up(X) :- apply(pickup(X),T).
[#any(superblock picked_up)]

% WHY DID YOU DROP IT?
[why.=put_on[superblock, table]]

% IS THERE ANYTHING TO THE RIGHT OF THE RED PYRAMID?
:def holds(right_of(A,B), TIME) :- holds(left_of(B,A), TIME).
:def right_of(A,B) :- holds(right_of(A,B)).
goal_once$left_of[red pyramid, box]
[right_of[red pyramid]]

thanks.
