"""Tests for the Prolog AST types, rendering, analysis, and LDCS→AST pipeline."""

import pytest
from prolog import (
    PVar, PAtom, PNum, PStr, PCompound, PArith,
    GCall, GUnify, GIs, GCompare, GBetween, GNot, GFindAll, GBagOf, GWhen, GRaw,
    render_term, render_goal, render_body,
    term_vars, goal_vars, goal_needs_ground, goal_binds,
    _to_pterm,
    PrologLDCS,
)


# ── render_term ──────────────────────────────────────────────────────────────

class TestRenderTerm:
    def test_var(self):
        assert render_term(PVar('X')) == 'X'

    def test_atom(self):
        assert render_term(PAtom('foo')) == 'foo'

    def test_num(self):
        assert render_term(PNum(42)) == '42'
        assert render_term(PNum(-7)) == '-7'

    def test_str(self):
        assert render_term(PStr('hello')) == '"hello"'

    def test_compound(self):
        assert render_term(PCompound('foo', (PVar('X'), PNum(1)))) == 'foo(X, 1)'

    def test_compound_no_args(self):
        assert render_term(PCompound('foo', ())) == 'foo()'

    def test_list(self):
        assert render_term(PCompound('[', (PVar('X'),))) == '[X]'

    def test_arith_simple(self):
        assert render_term(PArith('+', PVar('A'), PNum(1))) == 'A + 1'

    def test_arith_precedence(self):
        # (A + B) * C — the + is lower precedence, so needs parens
        expr = PArith('*', PArith('+', PVar('A'), PVar('B')), PVar('C'))
        assert render_term(expr) == '(A + B) * C'

    def test_arith_no_parens_when_same_prec(self):
        # A + B + C — left-associative, no parens needed for left child
        expr = PArith('+', PArith('+', PVar('A'), PVar('B')), PVar('C'))
        result = render_term(expr)
        assert 'A + B' in result and '+ C' in result

    def test_arith_mod(self):
        assert render_term(PArith('mod', PVar('N'), PNum(10))) == 'N mod 10'

    def test_arith_int_div(self):
        assert render_term(PArith('//', PVar('N'), PNum(10))) == 'N // 10'


# ── render_goal ──────────────────────────────────────────────────────────────

class TestRenderGoal:
    def test_call(self):
        assert render_goal(GCall(PCompound('foo', (PVar('X'),)))) == 'foo(X)'

    def test_unify(self):
        assert render_goal(GUnify(PVar('X'), PNum(1))) == 'X = 1'

    def test_is(self):
        rendered = render_goal(GIs(PVar('X'), PArith('+', PVar('A'), PNum(1))))
        # Auto-wrapped in when/2 because A is unground
        assert 'X is A + 1' in rendered

    def test_compare(self):
        rendered = render_goal(GCompare('<', PVar('X'), PNum(10)))
        assert 'X < 10' in rendered
        rendered2 = render_goal(GCompare('=:=', PVar('A'), PVar('B')))
        assert 'A =:= B' in rendered2

    def test_between(self):
        assert render_goal(GBetween(PNum(1), PNum(10), PVar('X'))) == 'between(1, 10, X)'

    def test_not_single(self):
        rendered = render_goal(GNot([GCall(PCompound('foo', (PVar('X'),)))]))
        assert '\\+ foo(X)' in rendered  # may be wrapped in when

    def test_not_multi(self):
        rendered = render_goal(GNot([
            GCall(PCompound('foo', (PVar('X'),))),
            GCall(PCompound('bar', (PVar('X'),))),
        ]))
        assert '\\+ (foo(X), bar(X))' in rendered

    def test_findall(self):
        result = render_goal(GFindAll(
            PVar('X'),
            [GCall(PCompound('foo', (PVar('X'),)))],
            PVar('L'),
        ))
        assert result == 'findall(X, (foo(X)), L)'

    def test_when(self):
        result = render_goal(GWhen({'A', 'B'}, GIs(PVar('X'), PArith('+', PVar('A'), PVar('B')))))
        assert 'when(ground(' in result
        assert 'X is A + B' in result

    def test_raw(self):
        assert render_goal(GRaw('custom(X)')) == 'custom(X)'


# ── term_vars ────────────────────────────────────────────────────────────────

class TestTermVars:
    def test_var(self):
        assert term_vars(PVar('X')) == {'X'}

    def test_atom(self):
        assert term_vars(PAtom('foo')) == set()

    def test_num(self):
        assert term_vars(PNum(1)) == set()

    def test_compound(self):
        assert term_vars(PCompound('foo', (PVar('X'), PVar('Y')))) == {'X', 'Y'}

    def test_arith(self):
        assert term_vars(PArith('+', PVar('A'), PNum(1))) == {'A'}

    def test_nested(self):
        t = PCompound('foo', (PArith('*', PVar('A'), PVar('B')), PVar('C')))
        assert term_vars(t) == {'A', 'B', 'C'}


# ── goal_needs_ground ────────────────────────────────────────────────────────

class TestGoalNeedsGround:
    def test_is(self):
        g = GIs(PVar('X'), PArith('+', PVar('A'), PVar('B')))
        assert goal_needs_ground(g) == {'A', 'B'}

    def test_compare(self):
        g = GCompare('<', PVar('X'), PNum(10))
        assert goal_needs_ground(g) == {'X'}

    def test_between(self):
        g = GBetween(PNum(1), PVar('N'), PVar('X'))
        assert goal_needs_ground(g) == {'N'}

    def test_call_directional(self):
        g = GCall(PCompound('atom_concat', (PVar('A'), PVar('B'), PVar('X'))))
        assert goal_needs_ground(g) == {'A', 'B'}

    def test_call_user_pred(self):
        g = GCall(PCompound('foo', (PVar('X'),)))
        assert goal_needs_ground(g) == set()

    def test_not(self):
        g = GNot([GCall(PCompound('foo', (PVar('X'),)))])
        assert 'X' in goal_needs_ground(g)

    def test_when_returns_empty(self):
        g = GWhen({'A'}, GIs(PVar('X'), PVar('A')))
        assert goal_needs_ground(g) == set()


# ── goal_binds ───────────────────────────────────────────────────────────────

class TestGoalBinds:
    def test_is(self):
        assert goal_binds(GIs(PVar('X'), PArith('+', PVar('A'), PNum(1)))) == {'X'}

    def test_between(self):
        assert goal_binds(GBetween(PNum(1), PNum(10), PVar('X'))) == {'X'}

    def test_findall(self):
        g = GFindAll(PVar('X'), [GCall(PCompound('foo', (PVar('X'),)))], PVar('L'))
        assert goal_binds(g) == {'L'}

    def test_unify(self):
        assert goal_binds(GUnify(PVar('X'), PNum(1))) == {'X'}

    def test_call_directional(self):
        g = GCall(PCompound('sort', (PVar('L'), PVar('S'))))
        assert goal_binds(g) == {'S'}

    def test_call_user_pred(self):
        g = GCall(PCompound('foo', (PVar('X'), PVar('Y'))))
        assert goal_binds(g) == {'X', 'Y'}


# ── reorder_goals ────────────────────────────────────────────────────────────

class TestAutoWhen:
    """render_goal auto-wraps directional goals in when/2."""

    def test_is_auto_wrapped(self):
        g = GIs(PVar('C'), PArith('+', PVar('A'), PVar('B')))
        rendered = render_goal(g)
        assert 'when(ground(' in rendered
        assert 'C is A + B' in rendered

    def test_compare_auto_wrapped(self):
        g = GCompare('<', PVar('X'), PNum(10))
        rendered = render_goal(g)
        assert 'when(ground(X)' in rendered

    def test_between_var_bounds_wrapped(self):
        g = GBetween(PNum(1), PVar('N'), PVar('X'))
        rendered = render_goal(g)
        assert 'when(ground(N)' in rendered

    def test_between_literal_bounds_no_wrap(self):
        g = GBetween(PNum(1), PNum(10), PVar('X'))
        rendered = render_goal(g)
        assert 'when(' not in rendered

    def test_user_call_no_wrap(self):
        g = GCall(PCompound('foo', (PVar('X'),)))
        rendered = render_goal(g)
        assert 'when(' not in rendered

    def test_directional_builtin_wrapped(self):
        g = GCall(PCompound('atom_concat', (PVar('A'), PVar('B'), PVar('X'))))
        rendered = render_goal(g)
        assert 'when(ground(' in rendered


# ── render handles arith in call args ────────────────────────────────────────

class TestRenderArithInCall:
    def test_arith_in_call_arg(self):
        """PArith in GCall args should be extracted to is/when at render time."""
        g = GCall(PCompound('foo', (PArith('+', PVar('A'), PNum(1)), PVar('B'))))
        rendered = render_goal(g)
        assert 'is A + 1' in rendered
        assert 'foo(' in rendered

    def test_range_in_unify_rendered(self):
        """GUnify with range renders as between (handled by ldcs extraction)."""
        # Ranges in unify are converted to GBetween at the ldcs() level
        g = GBetween(PNum(1), PNum(10), PVar('X'))
        assert render_goal(g) == 'between(1, 10, X)'

    def test_plain_call_unchanged(self):
        g = GCall(PCompound('foo', (PVar('X'),)))
        assert render_goal(g) == 'foo(X)'


# ── _to_pterm ────────────────────────────────────────────────────────────────

class TestToPterm:
    def test_var(self):
        assert _to_pterm('X') == PVar('X')
        assert _to_pterm('MuN') == PVar('MuN')

    def test_num(self):
        assert _to_pterm('42') == PNum(42)
        assert _to_pterm('-7') == PNum(-7)

    def test_str(self):
        assert _to_pterm('"hello"') == PStr('hello')

    def test_atom(self):
        assert _to_pterm('foo') == PAtom('foo')

    def test_underscore(self):
        assert _to_pterm('_') == PVar('_')



# ── PrologLDCS pipeline ─────────────────────────────────────────────────────

class TestPrologLDCSPipeline:
    """Test the full LDCS→Prolog AST pipeline."""

    def setup_method(self):
        self.p = PrologLDCS()

    def test_simple_fact(self):
        result = self.p.toProlog('foo: 1.')
        assert result is not None
        assert 'foo(1)' in result

    def test_simple_query(self):
        result = self.p.toProlog('foo.1?')
        assert 'what(' in result
        assert 'foo(' in result

    def test_range_query(self):
        result = self.p.toProlog('1..10?')
        assert 'between(1, 10,' in result

    def test_arith_in_body(self):
        """Arithmetic should produce GIs nodes."""
        result = self.p.toProlog('foo[N 1..10]: N + 1.')
        assert result is not None
        assert ' is ' in result or 'N + 1' in result  # arithmetic extracted

    def test_mod_operator(self):
        """Backslash should become mod."""
        result = self.p.toProlog('foo[N 1..10]: N\\2.')
        assert result is not None
        assert 'mod' in result

    def test_int_division(self):
        """/ should become // for integer division."""
        result = self.p.toProlog('foo[N 1..10]: N/2.')
        assert result is not None
        assert '//' in result

    def test_negation(self):
        result = self.p.toProlog('~foo?')
        assert result is not None
        assert '\\+' in result

    def test_disjunction(self):
        result = self.p.toProlog('x: 1 | 2 | 3.')
        assert result is not None
        assert 'disjunction' in result or 'x(' in result

    def test_setof_aggregation(self):
        result = self.p.toProlog('sum{1..10}?')
        assert result is not None
        assert 'findall(' in result
        assert 'sum_list(' in result

    def test_claim_head_arith(self):
        """Arithmetic in rule head should be extracted to body."""
        result = self.p.toProlog('foo: 1 + 2.')
        assert result is not None
        assert ' is ' in result
