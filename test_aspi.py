import pytest
import os.path
import sys
import io
import contextlib


class TestRunClingo:
    """Test the in-process clingo integration (no sh dependency)."""

    def test_simple_query(self):
        from aspi import run_clingo
        result = run_clingo('#show what/1. what(1..3).')
        assert sorted(result) == ['what(1)', 'what(2)', 'what(3)']

    def test_unsatisfiable(self):
        from aspi import run_clingo, ClingoError, ClingoExitCode
        with pytest.raises(ClingoError) as exc_info:
            run_clingo(':- #true. #show what/1.')  # explicit constraint makes it unsat
        assert exc_info.value.exit_code == ClingoExitCode.EXHAUST

    def test_context_functions(self):
        """@-functions should work via ClingoContext."""
        from aspi import run_clingo
        # Test @show function
        result = run_clingo('#show what/1. what(@show(42)).')
        assert result == ['what("42")']

    def test_include_prelude(self):
        """Including lib/prelude.lp should work (script block stripped)."""
        from aspi import run_clingo
        result = run_clingo('''
            #include "lib/prelude.lp".
            what(1..3).
        ''')
        what_results = sorted(r for r in result if r.startswith('what('))
        assert what_results == ['what(1)', 'what(2)', 'what(3)']


class TestASPIRepl:
    """Test the ASPI REPL end-to-end."""

    def setup_method(self):
        from aspi import ASPI
        self.aspi = ASPI()

    def _query(self, *cmds):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            for cmd in cmds:
                self.aspi.repl(cmd)
        output = buf.getvalue()
        that_lines = [l for l in output.split('\n') if l.startswith('that:')]
        return that_lines[-1] if that_lines else ''

    def test_simple_range(self):
        assert self._query('1..5?') == 'that: 1 | 2 | 3 | 4 | 5.'

    def test_sum_range(self):
        assert self._query('sum{1..10}?') == 'that: 55.'

    def test_fact_query(self):
        assert self._query('foo: 42.', 'foo?') == 'that: 42.'

    def test_multiple(self):
        assert self._query('sum{0..999 multiple[3|5]}?') == 'that: 233168.'


scripts = [
    'db-call',
    'db-dept',
    'db-wiz',
    'dcg',
    'golf',
    'hanoi',
    'shortest-path',
#    'shrdlu',  # crashes on small'est.{pyramid} planning step
#    'zebra',
]

for i in range(1000):
    name = f'euler/{i:03}'
    if os.path.exists(f'test/{name}.ldcs'):
        scripts.append(name)

for i in (116, 10131, 10154):
    scripts.append(f'uva/{i}')


@pytest.mark.parametrize('name', scripts)
def test_script(script_runner, name):
    args = ['./aspi.py']
    if os.path.exists(f'test/{name}.csv'):
        args.append(f'test/{name}.csv')
    ret = script_runner.run(*args, stdin=open(f'test/{name}.ldcs', 'r'))
    assert ret.success
    if not os.path.exists(f'test/{name}.log'):
        with open(f'test/{name}.log', 'w') as f:
            f.write(ret.stdout)
    assert ret.stdout == open(f'test/{name}.log', 'r').read()
    assert ret.stderr == ''
