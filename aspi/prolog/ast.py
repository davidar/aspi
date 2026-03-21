"""Prolog AST types — PTerm and PGoal dataclasses."""

from dataclasses import dataclass
from typing import Callable, List, Tuple


@dataclass(frozen=True)
class PVar:
    name: str

@dataclass(frozen=True)
class PAtom:
    name: str

@dataclass(frozen=True)
class PNum:
    value: int | float

@dataclass(frozen=True)
class PStr:
    value: str

@dataclass(frozen=True)
class PCompound:
    functor: str
    args: tuple  # of PTerm

@dataclass(frozen=True)
class PArith:
    op: str
    left: 'PTerm'
    right: 'PTerm'

PTerm = PVar | PAtom | PNum | PStr | PCompound | PArith

def _no_str(self):
    raise TypeError(f'{type(self).__name__} was converted to str — use render_term() instead.\n{self!r}')

for _cls in (PVar, PAtom, PNum, PStr, PCompound, PArith):
    _cls.__str__ = _no_str
    _cls.__format__ = lambda self, spec: _no_str(self)


@dataclass
class GCall:
    term: PTerm

@dataclass
class GUnify:
    left: PTerm
    right: PTerm

@dataclass
class GIs:
    target: PTerm
    expr: PTerm

@dataclass
class GCompare:
    op: str
    left: PTerm
    right: PTerm

@dataclass
class GBetween:
    lo: PTerm
    hi: PTerm
    var: PTerm

@dataclass
class GNot:
    goals: list

@dataclass
class GFindAll:
    template: PTerm
    goals: list
    result: PTerm

@dataclass
class GBagOf:
    template: PTerm
    goals: list
    result: PTerm

@dataclass
class GWhen:
    vars: set
    goal: 'PGoal'

@dataclass
class GRaw:
    text: str

PGoal = GCall | GUnify | GIs | GCompare | GBetween | GNot | GFindAll | GBagOf | GWhen | GRaw

# Internal types for PrologLDCS
PBody = List[PGoal]
PCSym = Tuple[PTerm, PBody]
PUnary = Callable[[PTerm], PBody]
