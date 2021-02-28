# aspi
*[Answer Set Programming](https://en.wikipedia.org/wiki/Answer_set_programming), Interactively*
[![Gitpod ready-to-code](https://img.shields.io/badge/Gitpod-ready--to--code-blue?logo=gitpod)](https://gitpod.io/#https://github.com/davidar/aspi)

This project started as an interactive shell for [clingo](https://github.com/potassco/clingo), and is gradually morphing into an experimental programming language based on [Lambda Dependency-Based Compositional Semantics](https://arxiv.org/abs/1309.4408) (λdcs). It supports a variety of declarative programming paradigms in a cohesive manner:

- [Functional programming](https://en.wikipedia.org/wiki/Functional_programming)
  ```
  fib[0]: 0.
  fib[1]: 1.
  fib[N 2..45]: fib[N-1] + fib[N-2].
  ```
- [Relational programming](http://matt.might.net/articles/microkanren/)
  ```
  pythag(A n2, B n2, C n2): (A**2) = ((B**2) + (C**2)).
  ```
- [Constraint programming](https://en.wikipedia.org/wiki/Constraint_programming)
  ```
  triple(A,B,C): pythag(A,B,C), ((A+B)+C) = 96?
  ```
  - [Zebra puzzle solver](test/zebra.log)
- [Logic programming](https://en.wikipedia.org/wiki/Logic_programming)
  ```
  mine: block ~red ~supports.pyramid.
  in.box mine?
  ```
- [Definite clause grammars](https://en.wikipedia.org/wiki/Definite_clause_grammar)
  ```
  #macro words[A,B]: concatenate[A, " ", B].
  sentence[s(N,V)]: words[noun_phrase.N, verb_phrase.V].
  noun_phrase[np(D,N)]: words[det D, noun N].
  verb_phrase[vp(V,N)]: words[verb V, noun_phrase.N].
  det: "a" | "the".
  noun: "bat" | "cat".
  verb: "eats".
  parse.S: sentence'.S.
  ```
  ```
  >>> parse."the bat eats a cat"?
  that: s(np("the","bat"),vp("eats",np("a","cat"))).
  ```
- [Predicating type specifiers](https://www.cs.cmu.edu/Groups/AI/html/cltl/clm/node47.html)
  ```
  collatz[N even n3]: N / 2.
  collatz[N odd n3]: (3*N) + 1.
  say[N multiple.100 100..900]: concatenate[say[N/100], " hundred"].
  ```
- [Automated planning](https://en.wikipedia.org/wiki/Automated_planning_and_scheduling)
  - [Tower of Hanoi solver](test/hanoi.log)
  - [SHRDLU-inspired dialogue](test/shrdlu.log)

The language is still unstable and lacking much documentation yet, but there are several example programs in this repo, e.g. [solutions to Project Euler-like problems](test/euler/).

## Syntax

λdcs can be used to write logic programs in a concise, [pointfree](https://wiki.haskell.org/Pointfree) manner. Below are a number of examples comparing how λdcs expressions translate to standard logic programs, as well as monadic functional programs.

<table>
<thead><tr><th scope="col"></th><th scope="col">λdcs</th><th scope="col">ASP logic program</th><th scope="col">Haskell</th></tr></thead>
<tbody>
<tr><th scope="row">Unary predicate</th>
<td>

```
seattle?
```

</td><td>

```prolog
what(A) :- seattle(A).
```

</td><td>

```haskell
[Seattle]
```

</td></tr>
<tr><th scope="row">Join binary to unary predicate</th>
<td>

```
place_of_birth.seattle?
```

</td><td>

```prolog
what(B) :- place_of_birth(B,A), seattle(A).
```

</td><td>

```haskell
placeOfBirth =<< [Seattle]
```

</td></tr>
<tr><th scope="row">Reverse operator</th>
<td>

```
place_of_birth'.john?
```

</td><td>

```prolog
what(B) :- place_of_birth(A,B), john(A).
```

</td><td>

```haskell
inv placeOfBirth =<< [John]
```

</td></tr>
<tr><th scope="row">Join chain</th>
<td>

```
children.place_of_birth.seattle?
```

</td><td>

```prolog
what(C) :- children(C,B),
           place_of_birth(B,A),
           seattle(A).
```

</td><td>

```haskell
children =<< placeOfBirth =<< [Seattle]
```

</td></tr>
<tr><th scope="row">Intersection</th>
<td>

```
profession.scientist place_of_birth.seattle?
```

</td><td>

```prolog
what(C) :- profession(C,A), scientist(A),
           place_of_birth(C,B), seattle(B).
```

</td><td>

```haskell
[ x | x <- profession =<< [Scientist]
    , x' <- placeOfBirth =<< [Seattle]
    , x == x' ]
```

</td></tr>
<tr><th scope="row">Union</th>
<td>

```
oregon | washington | type.canadian_province?
```

</td><td>

```prolog
what(C) :- disjunction(C).
disjunction(B) :- oregon(B).
disjunction(B) :- washington(B).
disjunction(B) :- type(B,A),
                  canadian_province(A).
```

</td><td>

```haskell
[Oregon] <|> [Washington]
         <|> (type' =<< [CanadianProvince])
```

</td></tr>
<tr><th scope="row">Negation</th>
<td>

```
type.us_state ~border.california?
```

</td><td>

```prolog
what(D) :- type(D,A), us_state(A),
           not negation(D).
negation(C) :- border(C,B), california(B).
```

</td><td>

```haskell
(type' =<< [USState]) \\ (border =<< [California])
```

</td></tr>
<tr><th scope="row">Aggregation</th>
<td>

```
count{type.us_state}?
```

</td><td>

```prolog
what(C) :- C = #count { B : type(B,A),
                            us_state(A) }.
```

</td><td>

```haskell
[length . nub $ type' =<< [USState]]
```

</td></tr>
<tr><th scope="row">μ abstraction</th>
<td>

```
X children.influenced.X?
```

</td><td>

```prolog
what(B) :- B = MuX, children(B,A),
           influenced(A,MuX).
```

</td><td>

```haskell
[ x | x <- universe
    , x' <- children =<< influenced =<< [x]
    , x == x' ]
```

</td></tr>
<tr><th scope="row">λ abstraction</th>
<td>

```
number_of_children.X: count{children'.X}.
```

</td><td>

```prolog
number_of_children(B,MuX) :-
  B = #count { A : children(MuX,A) }.
```

</td><td>

```haskell
numberOfChildren x =
  [length . nub $ inv children =<< [x]]
```

</td></tr>
</tbody>
</table>

The Haskell code above uses the following definitions:

```haskell
universe :: (Bounded a, Enum a) => [a]
universe = [minBound .. maxBound]

inv :: (Bounded a, Enum a, Eq b) => (a -> [b]) -> b -> [a]
inv f y = [ x | x <- universe, y' <- f x, y == y' ]
```
