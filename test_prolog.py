#!/usr/bin/env python3
"""Tests for the Prolog backend."""

import pytest
import prolog
import ldcs


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_plcs():
    """Create a PrologLDCS with reset gensym counter for deterministic output."""
    p = prolog.PrologLDCS()
    p._sym_counter = 0
    return p


# ── _quote_atoms_in_term ─────────────────────────────────────────────────────

class TestQuoteAtomsInTerm:
    def test_bare_atom(self):
        assert prolog._quote_atoms_in_term('ahmed') == '"ahmed"'

    def test_number(self):
        assert prolog._quote_atoms_in_term('42') == '42'

    def test_negative_number(self):
        assert prolog._quote_atoms_in_term('-7') == '-7'

    def test_functor_not_quoted(self):
        assert prolog._quote_atoms_in_term('row(42)') == 'row(42)'

    def test_atom_arg_quoted(self):
        assert prolog._quote_atoms_in_term('row(ahmed,42)') == 'row("ahmed",42)'

    def test_nested_compound(self):
        result = prolog._quote_atoms_in_term('s(np(the,bat),vp(eats,np(a,cat)))')
        assert result == 's(np("the","bat"),vp("eats",np("a","cat")))'

    def test_single_quoted_atom(self):
        assert prolog._quote_atoms_in_term("'Germany'") == '"Germany"'

    def test_single_quoted_with_spaces(self):
        assert prolog._quote_atoms_in_term("'Human Resources'") == '"Human Resources"'

    def test_single_quoted_in_compound(self):
        result = prolog._quote_atoms_in_term("row(2,country(3),'Croatia',1611)")
        assert result == 'row(2,country(3),"Croatia",1611)'

    def test_already_double_quoted(self):
        assert prolog._quote_atoms_in_term('"hello"') == '"hello"'

    def test_mixed(self):
        result = prolog._quote_atoms_in_term("row(10,country(1),'Germany',3582)")
        assert result == 'row(10,country(1),"Germany",3582)'


# ── _format_prolog_term ──────────────────────────────────────────────────────

class TestFormatPrologTerm:
    def test_int(self):
        assert prolog._format_prolog_term('42') == '42'

    def test_negative(self):
        assert prolog._format_prolog_term('-7') == '-7'

    def test_str_atom_quoted(self):
        """Bare atom strings should be quoted."""
        assert prolog._format_prolog_term('ahmed') == '"ahmed"'

    def test_str_compound(self):
        """Compound term string from term_to_atom should have atoms quoted."""
        result = prolog._format_prolog_term('s(np(the,bat))')
        assert result == 's(np("the","bat"))'

    def test_str_already_quoted(self):
        assert prolog._format_prolog_term('"hello"') == '"hello"'

    def test_str_single_quoted(self):
        assert prolog._format_prolog_term("'Germany'") == '"Germany"'

    def test_str_compound_with_single_quotes(self):
        result = prolog._format_prolog_term("row(2,'Croatia',1611)")
        assert result == 'row(2,"Croatia",1611)'


# ── End-to-end: toProlog ─────────────────────────────────────────────────────

class TestToProlog:
    """Test full LDCS->Prolog compilation."""

    def setup_method(self):
        self.p = make_plcs()
        # Load macros the same way PrologASPI does
        asp = ldcs.LDCS()
        with open('lib/macros.ldcs') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('%'):
                    continue
                try:
                    while line[-1] not in '.?!':
                        line += next(f).strip()
                    result = asp.toASP(line)
                    self.p.add_macro(result.split('\n')[0])
                except StopIteration:
                    break

    def test_simple_fact(self):
        result = self.p.toProlog('foo: 1.')
        assert 'foo(1)' in result

    def test_simple_query(self):
        result = self.p.toProlog('foo?')
        assert 'what(' in result

    def test_range_query(self):
        result = self.p.toProlog('1..10?')
        assert 'between(1, 10,' in result

    def test_sum_aggregation(self):
        result = self.p.toProlog('sum{1..10}?')
        assert 'findall(' in result
        assert 'sum_list(' in result

    def test_count_aggregation(self):
        result = self.p.toProlog('count{1..10}?')
        assert 'findall(' in result
        assert 'length(' in result

    def test_negation(self):
        result = self.p.toProlog('~foo?')
        assert '\\+' in result

    def test_disjunction(self):
        result = self.p.toProlog('det: "a" | "the".')
        assert 'det(' in result

    def test_multiple_macro(self):
        """The multiple macro should expand to mod-based check."""
        result = self.p.toProlog('multiple.3?')
        assert 'mod' in result or '\\' in result

    def test_show_macro(self):
        result = self.p.toProlog('show.42?')
        assert 'term_to_atom(' in result

    def test_forall_superlative(self):
        """multiple'each should produce forall, not @memberof."""
        result = self.p.toProlog("multiple'each.{1..10} n4?")
        assert 'forall(' in result, f'Expected forall in: {result}'
        assert '@memberof' not in result, f'Unexpected @memberof in: {result}'

    def test_th_superlative(self):
        """N'th should produce nth1, not @enumerateof."""
        result = self.p.toProlog("3'th.{1..10}?")
        assert 'nth1(' in result, f'Expected nth1 in: {result}'
        assert '@enumerateof' not in result, f'Unexpected @enumerateof in: {result}'

    def test_th_superlative_structure(self):
        """nth1 should have correct arg order: nth1(Index, List, Element)."""
        result = self.p.toProlog("3'th.{1..10}?")
        # The index (3) should be the first arg to nth1
        import re
        m = re.search(r'nth1\(([^,]+),\s*([^,]+),\s*([^)]+)\)', result)
        assert m, f'No nth1 call found in: {result}'
        # Index should reference the value 3, list should be the sorted set var,
        # element should flow to what()
        idx, lst, elem = m.group(1), m.group(2), m.group(3)
        # The what() variable should match the element
        wm = re.search(r'what\((\w+)\)', result)
        assert wm, f'No what() found in: {result}'
        what_var = wm.group(1)
        # what var should be the element (3rd arg of nth1)
        assert what_var == elem, f'what({what_var}) should match nth1 element arg {elem}, got: {result}'


# ── PrologEngine (requires SWI-Prolog) ───────────────────────────────────────

class TestPrologEngine:
    def setup_method(self):
        self.engine = prolog.PrologEngine()

    def test_add_and_query(self):
        self.engine.add_clause('test_fact(1).')
        self.engine.add_clause('test_fact(2).')
        results = self.engine.query('test_fact(What)')
        values = sorted(r['What'] for r in results)
        assert values == ['1', '2']

    def test_retract_all(self):
        self.engine.add_clause('temp(1).')
        self.engine.add_clause('temp(2).')
        self.engine.retract_all('temp', 1)
        results = self.engine.query('temp(What)')
        assert results == []

    def test_arithmetic(self):
        results = self.engine.query_with_extra(
            'what(What)', extra_clauses='what(X) :- X is 2 + 3.')
        assert results[0]['What'] == '5'

    def test_between(self):
        results = self.engine.query('between(1, 5, What)')
        values = [r['What'] for r in results]
        assert values == ['1', '2', '3', '4', '5']

    def test_findall(self):
        self.engine.add_clause('testnum(1).')
        self.engine.add_clause('testnum(2).')
        self.engine.add_clause('testnum(3).')
        results = self.engine.query_with_extra(
            'what(What)',
            extra_clauses='what(S) :- findall(X, testnum(X), L), sum_list(L, S).')
        assert results[0]['What'] == '6'

    def test_query_with_extra(self):
        self.engine.add_clause('base(1).')
        results = self.engine.query_with_extra(
            'what(What)',
            extra_clauses='what(X) :- base(X).')
        assert len(results) == 1
        assert results[0]['What'] == '1'


# ── Integration: LDCS -> Prolog -> answer ─────────────────────────────────────

class TestIntegration:
    """End-to-end tests: LDCS input -> Prolog evaluation -> correct output."""

    def setup_method(self):
        self.aspi = prolog.PrologASPI()

    def _query(self, *cmds: str) -> str:
        """Run commands, return last 'that:' line."""
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            for cmd in cmds:
                self.aspi.repl(cmd)
        output = buf.getvalue()
        that_lines = [l for l in output.split('\n') if l.startswith('that:')]
        return that_lines[-1] if that_lines else ''

    def test_simple_fact_query(self):
        assert self._query('foo: 1.', 'foo?') == 'that: 1.'

    def test_sum_range(self):
        """Euler 001 core: sum of 1..10."""
        assert self._query('sum{1..10}?') == 'that: 55.'

    def test_fib(self):
        """Fibonacci via recursive definition."""
        result = self._query(
            'fib[0]: 0.',
            'fib[1]: 1.',
            'fib[N 2..20]: fib[N-1] + fib[N-2].',
            'fib[10]?'
        )
        assert result == 'that: 55.'

    def test_multiple(self):
        result = self._query('sum{0..999 multiple[3|5]}?')
        assert result == 'that: 233168.'

    def test_count_that(self):
        """that/1 should be asserted after queries."""
        result = self._query(
            '1..5?',
            'count{that}?'
        )
        assert result == 'that: 5.'

    def test_product_bag(self):
        """Bag (non-dedup) product."""
        result = self._query(
            'product{{1..3}}?'
        )
        assert result == 'that: 6.'

    def test_string_output_quoted(self):
        """String results should be double-quoted."""
        result = self._query('show.42?')
        assert result == 'that: "42".'

    def test_disjunction(self):
        result = self._query('det: "a" | "the".', 'det?')
        assert result == 'that: "a" | "the".'

    def test_enum(self):
        result = self._query(
            '#enum dog: owner="ken" name="darcy" | owner="bob" name="lassie".',
            'owner.dog?'
        )
        # Should have quoted string output
        assert '"ken"' in result
        assert '"bob"' in result

    def test_th_superlative_compile(self):
        """Check the generated Prolog for N'th."""
        p = make_plcs()
        result = p.toProlog("2'th.{5..10}?")
        # Should have nth1 with index bound to 2
        assert 'nth1(' in result
        # Index 2 should appear
        assert '= 2' in result or ', 2,' in result, f'Index 2 not found in: {result}'
        # The nth1 index arg and the = 2 binding should use the same variable
        import re
        m = re.search(r'nth1\((\w+),', result)
        idx_var = m.group(1)
        assert f'{idx_var} = 2' in result or f'2 = {idx_var}' in result or idx_var == '2', \
            f'nth1 index var {idx_var} not bound to 2 in: {result}'

    def test_th_superlative_simple(self):
        """N'th should extract the Nth element from a sorted set.
        Use offset set so index != element value."""
        result = self._query("2'th.{5..10}?")
        assert result == 'that: 6.'  # 2nd of [5,6,7,8,9,10] = 6

    def test_th_superlative_with_defined_set(self):
        """N'th on a set defined by facts."""
        result = self._query(
            'item: 10 | 20 | 30.',
            "2'th.{item}?"
        )
        assert result == 'that: 20.'  # 2nd of sorted [10,20,30] = 20

    def test_bag_aggregation(self):
        """Double-brace {{...}} produces bags (with duplicates)."""
        result = self._query(
            'val: 1 | 1 | 2.',
            'count{{val}}?'
        )
        assert result == 'that: 3.'  # bag keeps duplicates

    def test_bag_product(self):
        """product of a bag."""
        result = self._query(
            'val: 2 | 3 | 5.',
            'product{{val}}?'
        )
        assert result == 'that: 30.'

    def test_grouped_bag(self):
        """{{f[X]}} groups by X — each group is a bag of values."""
        result = self._query(
            'score["alice"]: 10 | 20.',
            'score["bob"]: 30.',
            'total[S]: sum{{score.S}}.',
            'total."alice"?'
        )
        assert result == 'that: 30.'  # sum of alice's scores

    def test_bag_compile_uses_findall(self):
        """Double-brace bag should use findall (not sort/dedup)."""
        p = make_plcs()
        p.toProlog('nums: 2 | 3 | 5.')
        r2 = p.toProlog('bag: {{nums}}.')
        assert 'findall(' in r2, f'bag should use findall: {r2}'
        # bag should NOT sort (that would be a set)
        assert 'sort(' not in r2, f'bag should not sort: {r2}'

    def test_negation_filter_compile(self):
        """Check compilation of ~predicate filter."""
        p = make_plcs()
        p.toProlog('num: 1 | 2 | 3 | 4 | 5 | 6.')
        p.toProlog('bad: 2 | 4 | 6.')
        result = p.toProlog('~bad num?')
        assert '\\+' in result, f'Expected \\+ negation in: {result}'
        assert 'num(' in result, f'Expected num( in: {result}'

    def test_negation_filter(self):
        """~predicate should exclude matching items."""
        result = self._query(
            'num: 1 | 2 | 3 | 4 | 5 | 6.',
            'bad: 2 | 4 | 6.',
            '~bad num?'
        )
        assert result == 'that: 1 | 3 | 5.'

    def test_not_term_simple(self):
        """not_term (inline negation via 'not') should work."""
        result = self._query(
            'hot: 1 | 2 | 3.',
            'cold: 4 | 5 | 6.',
            'warm: hot ~cold.',
            'warm?'
        )
        assert result == 'that: 1 | 2 | 3.'

    def test_not_term_compile(self):
        """Check how not_term compiles negation."""
        p = make_plcs()
        p.toProlog('hot: 1 | 2 | 3.')
        result = p.toProlog('~hot?')
        # Should have \+ hot(...)
        assert '\\+' in result, f'Expected \\+ in: {result}'

    def test_negation_with_lift(self):
        """Negation that requires lifting (multi-term body)."""
        p = make_plcs()
        p.toProlog('big: (> 5) 1..10.')
        result = p.toProlog('~big.1..10?')
        # Check what the lifted negation looks like
        all_rules = '\n'.join(p.rules)
        full = f'{result}\n{all_rules}'
        assert '\\+' in full, f'Expected \\+ in: {full}'

    def test_tilde_negation_simple(self):
        """~pred should negate: items where pred does NOT hold."""
        result = self._query(
            'item: 1 | 2 | 3 | 4.',
            'special: 2 | 4.',
            # Items that are NOT special — use 'not' keyword form
            'item ~special?',
        )
        assert result == 'that: 1 | 3.'

    def test_tilde_negation_conj_compile(self):
        """Check what ~pred pred compiles to (conjunction, not composition)."""
        p = make_plcs()
        p.toProlog('fruit: "apple" | "banana" | "cherry".')
        p.toProlog('red: "apple" | "cherry".')
        result = p.toProlog('~red fruit?')
        # Should negate red and conjoin with fruit
        assert '\\+' in result, f'Expected negation in: {result}'
        assert 'fruit' in result, f'Expected fruit grounding in: {result}'

    def test_tilde_negation_conj(self):
        """~pred pred should filter set by negation of pred (conjunction)."""
        result = self._query(
            'fruit: "apple" | "banana" | "cherry".',
            'red: "apple" | "cherry".',
            # Fruit that are NOT red
            '~red fruit?',
        )
        assert result == 'that: "banana".'

    def test_bag_as_value(self):
        """A bag can be used as a value and then aggregated."""
        result = self._query(
            'nums: 2 | 3 | 5.',
            'bag: {{nums}}.',
            'product.bag?'
        )
        assert result == 'that: 30.'

    def test_max_of_products(self):
        """Find the maximum product across grouped bags — euler/011 pattern."""
        result = self._query(
            'line["a"]: 2 | 3.',
            'line["b"]: 4 | 5.',
            'lines: {{line[L]}}.',
            'max{product.lines}?'
        )
        assert result == 'that: 20.'  # max(2*3=6, 4*5=20) = 20

    def test_say_number_words(self):
        """Number-to-words: say[N\10] should produce say(X, N mod 10)."""
        p = make_plcs()
        p.toProlog('say.0: "".')
        p.toProlog('say.1: "one".')
        p.toProlog('say.2: "two".')
        p.toProlog('say.10: "ten".')
        p.toProlog('say.20: "twenty".')
        result = p.toProlog('say[N ~multiple.10 20..99]: concatenate[say[(N/10)*10], " ", say[N\\10]].')
        # The body should reference 'mod' not 'MuNmod10'
        assert 'MuNmod' not in result, f'Variable should not merge with mod: {result}'
        assert 'mod' in result, f'Expected mod operator in: {result}'

    def test_say_number_basic(self):
        """Basic number-to-words lookup."""
        result = self._query(
            'say.1: "one".',
            'say.2: "two".',
            'say.3: "three".',
            'say.1?',
        )
        assert result == 'that: "one".'

    def test_say_number_compound(self):
        """Compound number-to-words with concatenation."""
        result = self._query(
            'say.0: "".',
            'say.1: "one".',
            'say.2: "two".',
            'say.3: "three".',
            'say.10: "ten".',
            'say.20: "twenty".',
            'say.30: "thirty".',
            'say[N ~multiple.10 20..99]: concatenate[say[(N/10)*10], " ", say[N\\10]].',
            'say.21?',
        )
        assert result == 'that: "twenty one".'

    def test_char_count(self):
        """count{{...}} aggregation pattern from euler/017."""
        result = self._query(
            'word: "hello".',
            '#macro char.S: substring.S length=1.',
            'count{{char.word}}?',
        )
        assert result == 'that: 5.'


    def test_define_multi_arg_join_head(self):
        """define_heads with multi-arg join should produce the right head predicate."""
        result = self._query(
            'name: "alice" | "bob".',
            'score["alice"]: 10.',
            'score["bob"]: 20.',
            'doubled[name S]: score.S * 2.',
            'doubled."alice"?',
        )
        assert result == 'that: 20.'

    def test_define_with_aggregation(self):
        """define with aggregation in the body."""
        result = self._query(
            'score["alice"]: 10 | 20.',
            'score["bob"]: 30.',
            'total[S]: sum{{score.S}}.',
            'total."alice"?',
        )
        assert result == 'that: 30.'

    def test_char_macro_basic(self):
        """char macro should extract individual characters."""
        result = self._query(
            '#macro char.S: substring.S length=1.',
            'char."hello"?',
        )
        assert '"h"' in result and '"o"' in result

    def test_letter_value(self):
        """letter.char should compute character positions (A=1, B=2, etc.)."""
        result = self._query(
            '#macro char.S: substring.S length=1.',
            '#macro letter.C: (codepoint.C - codepoint."A") + 1.',
            'letter.char."A"?',
        )
        assert result == 'that: 1.'

    def test_sum_letter_char(self):
        """sum of letter values of a string."""
        result = self._query(
            '#macro char.S: substring.S length=1.',
            '#macro letter.C: (codepoint.C - codepoint."A") + 1.',
            'sum{{letter.char."AB"}}?',
        )
        assert result == 'that: 3.'  # A=1, B=2

    def test_position_nth(self):
        """N'th superlative should find the Nth element of a set."""
        result = self._query(
            'item: "c" | "a" | "b".',
            '2\'th.{item}?',
        )
        assert result == 'that: "b".'  # sorted: a=1, b=2, c=3

    def test_define_position_value_score(self):
        """Full euler/022 pattern: position * value for named items."""
        result = self._query(
            'name: "AB" | "C".',
            '#macro char.S: substring.S length=1.',
            '#macro letter.C: (codepoint.C - codepoint."A") + 1.',
            'value[name S]: sum{{letter.char.S}}.',
            'value."AB"?',
        )
        assert result == 'that: 3.'  # A=1 + B=2


# ── LDCS file-based tests ─────────────────────────────────────────────────────

import glob
import io
import contextlib
import subprocess


_KNOWN_FAILURES = {
    'euler/011': 'performance — grouped bag over CSV grid with tabling too slow',
    'euler/019': 'missing date/calendar builtins',
    'euler/027': 'performance — n4 domain with prime search',
    'euler/030': 'performance — brute force digit power sums',
    'db-call': 'complex SQL join semantics — start_time/duration arithmetic differs',
    'db-dept': 'complex SQL subquery — negation in multi-join context',
}


def _discover_ldcs_tests():
    """Find all .ldcs files that have a .log with expected 'that:' output."""
    patterns = ['test/euler/*.ldcs', 'test/db-*.ldcs', 'test/dcg.ldcs', 'test/golf.ldcs']
    tests = []
    for pat in patterns:
        for ldcs_path in sorted(glob.glob(pat)):
            log_path = ldcs_path.replace('.ldcs', '.log')
            try:
                with open(log_path) as f:
                    lines = [l.strip() for l in f if l.startswith('that:')]
                if lines:
                    expected = lines[-1]
                    name = ldcs_path.replace('test/', '').replace('.ldcs', '')
                    marks = []
                    if name in _KNOWN_FAILURES:
                        marks.append(pytest.mark.xfail(
                            reason=_KNOWN_FAILURES[name], strict=True))
                    tests.append(pytest.param(ldcs_path, expected, id=name,
                                             marks=marks))
            except FileNotFoundError:
                pass
    return tests


@pytest.mark.parametrize('ldcs_path,expected', _discover_ldcs_tests())
def test_ldcs_file(ldcs_path, expected):
    """Run an LDCS file through the Prolog backend and check the last 'that:' line."""
    csv_path = ldcs_path.replace('.ldcs', '.csv')
    args = ['uv', 'run', 'python', 'prolog.py']
    import os
    if os.path.exists(csv_path):
        args.append(csv_path)

    with open(ldcs_path) as f:
        proc = subprocess.Popen(
            args, stdin=f, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True)
        try:
            stdout, stderr = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            import os, signal
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            pytest.fail(f'Timed out after 30s')
        result = subprocess.CompletedProcess(args, proc.returncode, stdout, stderr)

    that_lines = [l.strip() for l in result.stdout.split('\n') if l.startswith('that:')]
    actual = that_lines[-1] if that_lines else ''
    assert actual == expected, f'\n  expected: {expected}\n  actual:   {actual}\n  stderr:   {result.stderr[:200]}'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
