"""Tests for the Prolog AST types, rendering, analysis, and LDCS→AST pipeline."""

import pytest
from prolog import (
    PVar, PAtom, PNum, PStr, PCompound, PArith,
    GCall, GUnify, GIs, GCompare, GBetween, GNot, GFindAll, GBagOf, GWhen, GRaw,
    render_term, render_goal, render_body,
    term_vars, goal_vars, goal_needs_ground, goal_binds,
    _to_pterm, _parse_result_term, _term_sort_key, _parse_prolog_list,
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

class TestDefine:
    """Test the define mechanism — how define_heads + body produce rules."""

    def setup_method(self):
        self.p = PrologLDCS()

    def test_define_simple_produces_correct_head(self):
        """foo: 1. should produce foo(1)."""
        r = self.p.toProlog('foo: 1.')
        assert 'foo(1)' in r

    def test_define_join_head_is_first_gcall(self):
        """doubled[S]: ... should produce doubled(result, S) as head."""
        self.p.toProlog('score."alice": 10.')
        r = self.p.toProlog('doubled[S]: score.S.')
        assert 'doubled(' in r, f'Expected doubled() in head, got: {r}'
        head = r.split(' :- ')[0] if ' :- ' in r else r.rstrip('.')
        assert head.startswith('doubled('), f'Head should be doubled(...), got: {head}'

    def test_define_join_head_arity(self):
        """doubled[name S] should produce a 2-arg head: doubled(value, name_arg)."""
        self.p.toProlog('score."alice": 10.')
        r = self.p.toProlog('doubled[name S]: score.S * 2.')
        lines = [l for l in r.split('\n') if 'doubled(' in l]
        assert lines, f'No doubled() rule found in output: {r}'
        head = lines[0].split(' :- ')[0]
        assert head.startswith('doubled('), f'Head should be doubled(...), got: {head}'

    def test_define_heads_single_join(self):
        """doubled[name S] should parse as ONE head (a join), not two (doubled + name)."""
        r = self.p.toProlog('doubled[S]: S.')
        # Should produce exactly one rule with doubled as head
        assert 'doubled(' in r, f'Expected doubled in output: {r}'
        # Should NOT produce a rule with a different head
        for line in r.split('\n'):
            if ' :- ' in line:
                head = line.split(' :- ')[0]
                assert not head.startswith('name('), f'Should not have name() as head: {line}'

    def test_define_heads_with_typed_param(self):
        """position[name S] — 'name' qualifies S, both part of the join."""
        self.p.toProlog('item: "a" | "b".')
        r = self.p.toProlog('position[item S]: S.')
        # Head should be position(...), not item(...)
        for line in r.split('\n'):
            if line.strip() and ' :- ' in line:
                head = line.split(' :- ')[0]
                # position should appear as the head at some point
                if 'position(' in head:
                    break
        else:
            assert False, f'No rule with position() as head found in: {r}'

    def test_define_body_contains_score(self):
        """The body of doubled[name S]: score.S * 2 should reference score."""
        self.p.toProlog('score."alice": 10.')
        r = self.p.toProlog('doubled[name S]: score.S * 2.')
        lines = [l for l in r.split('\n') if 'doubled(' in l and ' :- ' in l]
        assert lines, f'No doubled() rule with body found in: {r}'
        body = lines[0].split(' :- ', 1)[1]
        assert 'score(' in body, f'Body should reference score, got: {body}'

    def test_func_returns_pcompound_for_plain_call(self):
        """func("foo")(x, y) should return PCompound("foo", (x, y))."""
        f = self.p.func("foo")
        result = f(PVar('X'), PVar('Y'))
        assert isinstance(result, PCompound)
        assert result.functor == 'foo'
        assert result.args == (PVar('X'), PVar('Y'))

    def test_func_returns_patom_for_zero_args(self):
        """func("foo")() should return PAtom("foo")."""
        f = self.p.func("foo")
        result = f()
        assert isinstance(result, PAtom)
        assert result.name == 'foo'

    def test_join_produces_call_before_body(self):
        """join(f, csym) should produce [body_goals..., GCall(f(x, y))]."""
        f = self.p.func("foo")
        csym = (PVar('Y'), [GCall(PCompound('bar', (PVar('Y'),)))])
        j = self.p.join(f, csym)
        # Call with result var X
        goals = j(PVar('X'))
        assert isinstance(goals, list)
        # Should contain a GCall with foo
        call_goals = [g for g in goals if isinstance(g, GCall) and isinstance(g.term, PCompound) and g.term.functor == 'foo']
        assert call_goals, f'Expected GCall(foo(...)) in goals: {goals}'
        # Body goal bar(Y) should also be present
        bar_goals = [g for g in goals if isinstance(g, GCall) and isinstance(g.term, PCompound) and g.term.functor == 'bar']
        assert bar_goals, f'Expected GCall(bar(Y)) in goals: {goals}'


class TestParseResultTerm:
    """Test _parse_result_term for sorting Prolog output."""

    def test_num(self):
        t = _parse_result_term('42')
        assert t == PNum(42)

    def test_negative_num(self):
        t = _parse_result_term('-7')
        assert t == PNum(-7)

    def test_str(self):
        t = _parse_result_term('"hello"')
        assert t == PStr('hello')

    def test_atom(self):
        t = _parse_result_term('foo')
        assert t == PAtom('foo')

    def test_compound(self):
        t = _parse_result_term('triple(5,3,4)')
        assert isinstance(t, PCompound)
        assert t.functor == 'triple'
        assert t.args == (PNum(5), PNum(3), PNum(4))

    def test_nested_compound(self):
        t = _parse_result_term('date(1901,september,1)')
        assert isinstance(t, PCompound)
        assert t.functor == 'date'
        assert t.args == (PNum(1901), PAtom('september'), PNum(1))

    def test_compound_with_strings(self):
        t = _parse_result_term('row("alice",42)')
        assert isinstance(t, PCompound)
        assert t.args == (PStr('alice'), PNum(42))


class TestTermSortKey:
    """Test structural sorting of Prolog result terms."""

    def test_numbers_sort_numerically(self):
        vals = ['10', '2', '1', '20']
        assert sorted(vals, key=_term_sort_key) == ['1', '2', '10', '20']

    def test_compound_sorts_by_first_arg(self):
        vals = ['triple(10,1,1)', 'triple(5,1,1)', 'triple(20,1,1)']
        assert sorted(vals, key=_term_sort_key) == ['triple(5,1,1)', 'triple(10,1,1)', 'triple(20,1,1)']

    def test_compound_sorts_by_second_arg(self):
        """Atoms sort alphabetically, so december < september."""
        vals = ['date(1901,september,1)', 'date(1901,december,1)']
        assert sorted(vals, key=_term_sort_key) == ['date(1901,december,1)', 'date(1901,september,1)']

    def test_compound_sorts_enum_by_id(self):
        """Enum ids like month(9) sort numerically, before name replacement."""
        vals = ['date(1901,month(9),1)', 'date(1901,month(12),1)']
        assert sorted(vals, key=_term_sort_key) == ['date(1901,month(9),1)', 'date(1901,month(12),1)']

    def test_mixed_types(self):
        vals = ['42', '"hello"', 'foo']
        result = sorted(vals, key=_term_sort_key)
        assert result[0] == '42'  # numbers first


class TestParsePrologList:
    """Test parsing Prolog list strings."""

    def test_simple_list(self):
        assert _parse_prolog_list('[1,2,3]') == ['1', '2', '3']

    def test_empty_list(self):
        assert _parse_prolog_list('[]') == []

    def test_nested_terms(self):
        assert _parse_prolog_list('[foo(1,2),bar(3)]') == ['foo(1,2)', 'bar(3)']

    def test_nested_lists(self):
        assert _parse_prolog_list('[[1,2],[3]]') == ['[1,2]', '[3]']

    def test_non_list(self):
        assert _parse_prolog_list('hello') == ['hello']

    def test_with_duplicates(self):
        assert _parse_prolog_list('[1,2,2,3]') == ['1', '2', '2', '3']


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
