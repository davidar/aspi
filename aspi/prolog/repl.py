"""PrologASPI — hybrid ASP+Prolog REPL."""

import io
import contextlib
import os
import re
import sys
from typing import Dict, List, Optional

from aspi import ldcs
from aspi import asp as asp_backend
from aspi.prolog.compiler import PrologLDCS
from aspi.prolog.engine import PrologEngine
from aspi.prolog.formatting import _format_prolog_term, _parse_prolog_list, _term_sort_key


class PrologASPI:
    def __init__(self, args: List[str] = []) -> None:
        self.counter = 1
        self.ldcs = PrologLDCS()
        self._display_ldcs = ldcs.LDCS()
        self._asp = None
        self._asp_args = list(args)
        self._asp_cmd_buffer: List[str] = []
        self._prolog_cmd_buffer: List[str] = []
        self.engine = PrologEngine()
        self.proofs = False
        self.names: Dict[str, str] = {}
        for arg in args:
            self.include(arg)

    def _ensure_asp(self) -> asp_backend.ASPI:
        if self._asp is None:
            self._asp_ldcs = ldcs.LDCS()
            self._asp = asp_backend.ASPI(self._asp_args)
            self.engine._extra_facts_fn = lambda: list(self._asp.facts) + [f'now({self._asp.now})']
            for cmd in self._asp_cmd_buffer:
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        self._asp.repl(cmd)
                except Exception:
                    pass
            self._asp_cmd_buffer = []
        return self._asp

    def _ensure_prolog(self) -> None:
        if not self._prolog_cmd_buffer:
            return
        for cmd in self._prolog_cmd_buffer:
            with contextlib.redirect_stdout(io.StringIO()):
                if cmd.startswith('#undef '):
                    name = cmd[len('#undef '):-1]
                    self.engine.clauses = [c for c in self.engine.clauses if not c.startswith(name)]
                    self.engine._dirty = True
                else:
                    self.eval(cmd)
        self._prolog_cmd_buffer = []

    def include(self, arg: str) -> None:
        if arg.endswith('.lp'):
            return
        if arg.endswith('.ldcs'):
            with open(arg, 'r') as f:
                while True:
                    try:
                        line = next(f).strip()
                        if len(line) == 0 or line[0] == '%':
                            continue
                        while line[-1] not in '.?!':
                            line += next(f).strip()
                        if 'macros' in arg:
                            if not hasattr(self, '_asp_ldcs'):
                                self._asp_ldcs = ldcs.LDCS()
                            lp = self._asp_ldcs.toASP(line)
                            self.ldcs.add_macro(lp.split('\n')[0])
                        else:
                            pl = self.ldcs.toProlog(line)
                            if pl:
                                for clause in pl.split('\n'):
                                    if clause.strip():
                                        self.engine.add_clause(clause)
                    except StopIteration:
                        break
        elif arg.endswith('.csv'):
            with open(arg, 'r') as f:
                rows = 0
                for r, line in enumerate(f):
                    rows += 1
                    cols = 0
                    for c, v in enumerate(line.split(',')):
                        cols += 1
                        v = v.strip()
                        self.engine.add_clause(f'csv({v},{r+1},{c+1}).')
                    self.engine.add_clause(f'csv_cols({cols},{r+1}).')
                self.engine.add_clause(f'csv_rows({rows}).')
        elif arg.endswith('.txt'):
            name = os.path.basename(arg)[:-4]
            with open(arg, 'r') as f:
                for line in f:
                    k, v = line.split()
                    self.engine.add_clause(f'{name}({v},{k}).')

    def _asp_query(self, cmd: str) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self._ensure_asp().repl(cmd)
        output = buf.getvalue()
        for line in output.split('\n'):
            line = line.rstrip()
            if line:
                print(line)
        print()
        lines = output.split('\n')
        joined = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('| ') and joined:
                joined[-1] += ' ' + stripped
            else:
                joined.append(stripped)
        self.engine.retract_all('that', 1)
        for line in joined:
            if line.startswith('that: ') and line.endswith('.'):
                content = line[len('that: '):-1]
                for wrapper in ('set', 'bag'):
                    if content.startswith(wrapper + '(') and content.endswith(')'):
                        self.engine.add_clause(f'that({content}).')
                        content = None
                        break
                if content is not None:
                    for val in self._split_bar_values(content):
                        self.engine.add_clause(f'that({val}).')
        self.counter += 1

    def _split_bar_values(self, s: str) -> list:
        values = []
        depth = 0
        current = []
        for ch in s:
            if ch in '([':
                depth += 1
            elif ch in ')]':
                depth -= 1
            current.append(ch)
            if depth == 0 and len(current) >= 3 and ''.join(current[-3:]) == ' | ':
                values.append(''.join(current[:-3]).strip())
                current = []
        if current:
            values.append(''.join(current).strip())
        return values

    def repl(self, cmd: str) -> None:
        if not cmd or cmd.startswith('%'):
            return
        if cmd == 'thanks.':
            print("YOU'RE WELCOME!")
            sys.exit(0)
        if cmd.endswith('?!'):
            self._asp_query(cmd[:-1])
            return
        if cmd.endswith('!') or cmd.startswith('#fluent '):
            self._ensure_asp().repl(cmd)
            return
        if self._asp is not None:
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    self._asp.repl(cmd)
            except Exception:
                pass
        else:
            self._asp_cmd_buffer.append(cmd)
        if cmd.startswith('#undef '):
            self._prolog_cmd_buffer.append(cmd)
            return
        if cmd.startswith('#include "'):
            return self.include(cmd[len('#include "'):-2])
        if cmd == '#proof off.':
            self.proofs = False
            self.ldcs._proofs = False
            return
        if cmd.startswith('#macro '):
            cmd = cmd.replace('#macro ', '')
        if cmd.endswith('.'):
            lp = self._display_ldcs.toASP(cmd)
            if lp:
                lines = [l for l in lp.split('\n') if not l.strip().startswith('proof(')]
                print('-->', '\n    '.join(lines))
            self._prolog_cmd_buffer.append(cmd)
            print('understood.\n')
            return
        self._ensure_prolog()
        res = self.eval(cmd)
        if res is not None:
            wrapper = self.ldcs._result_wrapper if cmd.endswith('?') else None
            self.print_results(res, wrapper=wrapper)
            self.counter += 1

    def eval(self, cmd: str) -> Optional[List]:
        pl = self.ldcs.toProlog(cmd)
        if pl is None:
            return None
        print('-->', '\n    '.join(line for line in pl.split('\n')))
        if cmd.endswith('.'):
            for clause in pl.split('\n'):
                clause = clause.strip()
                if clause:
                    self.engine.add_clause(clause)
                    m = re.match(r'describe\((.+?),\s*(.+)\)\.$', clause)
                    if m:
                        self.names[m.group(1).strip()] = m.group(2).strip()
            print('understood.\n')
            return None
        if cmd.endswith('?'):
            lines = [l.strip() for l in pl.split('\n') if l.strip()]
            helpers = []
            query_clause = None
            for line in lines:
                if line.startswith('what('):
                    query_clause = line
                elif line.startswith('yes ') or line.startswith('no '):
                    helpers.append(line)
                else:
                    helpers.append(line)
            for h in helpers:
                self.engine.add_clause(h)
            if query_clause:
                if ' :- ' in query_clause:
                    return self.engine.query_with_extra('what(What)', extra_clauses=query_clause)
                else:
                    m = re.match(r'what\((.+)\)\.?', query_clause)
                    if m:
                        return [{'What': m.group(1)}]
            if any('yes' in h for h in helpers):
                return self.engine.query_with_extra(
                    '(yes -> What = yes ; no -> What = no ; What = unknown)',
                    extra_clauses='\n'.join(helpers))
        return None

    def _replace_names(self, s: str) -> str:
        for k, v in self.names.items():
            s = s.replace(k, v)
        return s

    def print_results(self, results: List, wrapper: str = None) -> None:
        if not results:
            print('impossible.\n')
            return
        raw_values = [r['What'] for r in results if 'What' in r]
        if wrapper == 'bag' and len(raw_values) == 1 and raw_values[0].startswith('['):
            raw_values = _parse_prolog_list(raw_values[0])
        values = [_format_prolog_term(v) for v in raw_values]
        if values == ['yes']:
            print('yes.\n')
            return
        if values == ['no']:
            print('no.\n')
            return
        if values:
            if wrapper == 'bag':
                unique = sorted(values, key=_term_sort_key)
            else:
                seen = set()
                unique = []
                for v in values:
                    if v not in seen:
                        seen.add(v)
                        unique.append(v)
                unique.sort(key=_term_sort_key)
            if self.names:
                unique = [self._replace_names(v) for v in unique]
            self.engine.retract_all('that', 1)
            if wrapper in ('set', 'bag'):
                that = f'{wrapper}({",".join(unique)})'
                self.engine.add_clause(f'that({that}).')
            else:
                for v in unique:
                    self.engine.add_clause(f'that({v}).')
                that = ' | '.join(unique)
                if len(unique) > 1 and len(that) / len(unique) > 30:
                    that = that.replace(' | ', '\n    | ')
            print(f'that: {that}.')
        print()
