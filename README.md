# aspi
*[Answer Set Programming](https://en.wikipedia.org/wiki/Answer_set_programming), Interactively*
[![Gitpod ready-to-code](https://img.shields.io/badge/Gitpod-ready--to--code-blue?logo=gitpod)](https://gitpod.io/#https://github.com/davidar/aspi)

This project started as an interactive shell for [clingo](https://github.com/potassco/clingo), and is gradually morphing into an experimental programming language based on [Lambda Dependency-Based Compositional Semantics](https://arxiv.org/abs/1309.4408). It supports a variety of declarative programming paradigms in a cohesive manner:

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
- [Predicating type specifiers](https://www.cs.cmu.edu/Groups/AI/html/cltl/clm/node47.html)
  ```
  collatz[N even n3]: N / 2.
  collatz[N odd n3]: (3*N) + 1.
  say[N multiple.100 100..900]: concatenate[say[N/100], "hundred"].
  ```
- [Automated planning](https://en.wikipedia.org/wiki/Automated_planning_and_scheduling)
  - [Tower of Hanoi solver](test/hanoi.log)
  - [SHRDLU-inspired dialogue](shrdlu/test.out)

The language is still unstable and lacking much documentation yet, but there are several example programs in this repo, e.g. [solutions to Project Euler-like problems](test/euler.log).
