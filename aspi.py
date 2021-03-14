#!/usr/bin/env python3
import atexit
import clingo
import enum
import json
import os
import re
import readline
import sh  # type: ignore
import sys
import tempfile
from typing import cast, Dict, List, Optional

import ldcs


readline.parse_and_bind('tab: complete')

try:
    readline.read_history_file('history.log')
    readline.set_history_length(1000)
except FileNotFoundError:
    pass

atexit.register(readline.write_history_file, 'history.log')


def run_mercury(lp: str) -> List[str]:
    with tempfile.TemporaryDirectory() as tempdir:
        with open(os.path.join(tempdir, 'main.m'), 'w') as f:
            print(lp, file=f)
        sh.mmc('main.m', infer_all=True, _cwd=tempdir,
                _err=sys.stderr if 'DEBUG' in os.environ else None)
        result = sh.Command(os.path.join(tempdir, 'main'))().stdout
    for x in json.loads(result):
        if type(x) is list:
            x = f'list{tuple(x)}'
        yield f'what({x})'


class ASPI:
    def __init__(self, args: List[str] = []):
        self.counter = 1
        self.facts = set(['moves(0)'])
        self.ldcs = ldcs.LDCS()
        self.now = 0
        self.program = ''
        self.proofs = True
        self.that = []

        for arg in ['lib/prelude.m', 'lib/macros.ldcs'] + args:
            self.include(arg)

    def include(self, arg: str) -> None:
        if arg.endswith('.lp'):
            self.program += f'#include "{arg}".\n'
        elif arg.endswith('.m'):
            self.program += open(arg, 'r').read()
        elif arg.endswith('.ldcs'):
            with open(arg, 'r') as f:
                while True:
                    try:
                        line = next(f).strip()
                        if len(line) == 0 or line[0] == '%':
                            continue
                        while line[-1] not in '.?!':
                            line += next(f).strip()
                        lp = self.ldcs.toASP(line)
                        if 'macros' in arg:
                            self.ldcs.add_macro(lp.split('\n')[0])
                        else:
                            self.program += lp + '\n'
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
                        self.program += f'csv({v},{r+1},{c+1}).\n'
                    self.program += f'csv_cols({cols},{r+1}).\n'
                self.program += f'csv_rows({rows}).\n'
        elif arg.endswith('.txt'):
            name = os.path.basename(arg)[:-4]
            with open(arg, 'r') as f:
                for line in f:
                    k, v = line.split()
                    self.program += f'{name}({v},{k}).\n'

    def repl(self, cmd: str) -> None:
        if not cmd or cmd.startswith('%'):
            return
        if cmd.startswith('#undef '):
            name = cmd[len('#undef '):-1]
            lines = self.program.split('\n')
            for i in reversed(range(len(lines))):
                line = lines[i]
                if line.startswith(name) or f'@proof({name}' in line:
                    lines.pop(i)
            self.program = '\n'.join(lines)
            return
        if cmd.startswith('#include "'):
            return self.include(cmd[len('#include "'):-2])
        if cmd.startswith('#pragma ') or cmd.startswith('#mode '):
            self.program += f':- {cmd[1:]}\n'
            return
        if cmd == 'thanks.':
            print("YOU'RE WELCOME!")
            sys.exit(0)
        if cmd == '#proof off.':
            self.proofs = False
            return
        res = self.eval(cmd)
        if res is not None:
            self.print(res)
            for fact in self.facts:
                if fact.startswith('moves('):
                    self.now = int(fact[len('moves('):-1])
            self.counter += 1
            self.that = res.shows

    def eval(self, cmd: str) -> Optional['Results']:
        lp = self.ldcs.toASP(cmd.replace('#macro ', ''))
        if lp is None:
            return None
        print('-->', '\n    '.join(line for line in lp.split('\n')))
        lp += '\n'
        if cmd.endswith('.'):
            for line in lp.split('\n'):
                if cmd.startswith('#macro'):
                    if line.strip() and '@proof' not in line:
                        self.ldcs.add_macro(line)
                else:
                    if self.proofs or '@proof' not in line:
                        self.program += line + '\n'
            print('understood.\n')
            return None

        lp = self.program + lp
        for t in self.that:
            if not t.startswith('list'):
                lp += f'that({t}).\n'
        lp += 'main(!IO) :- solutions(what,X), print(X,!IO), nl(!IO).\n'

        try:
            return Results(self, run_mercury(lp))
        except sh.ErrorReturnCode as e:
            print(e.stderr.decode('utf-8'), file=sys.stderr)
            for i, line in enumerate(lp.split('\n')):
                if not line.startswith('csv('):
                    print(f'{i+1:3}|', line, file=sys.stderr)
            sys.exit(1)

    def print(self, res: 'Results') -> None:
        for fact in res.already:
            print(fact + '.')
        for act in res.acts:
            print(act + '!')
        if res.status:
            print(res.status + '.')
        if res.shows:
            terms = [clingo.parse_term(r) for r in res.shows]
            terms.sort()
            that = ' | '.join(res.replace_names(str(t)) for t in terms)
            if len(that) / len(terms) > 30:
                that = that.replace(' | ', '\n    | ')
            print(f'that: {that}.')
        print()


class Results:
    def __init__(self, parent: ASPI, results: List[str]) -> None:
        self.parent = parent
        self.status: Optional[str] = None
        self.acts: List[str] = []
        self.already: List[str] = []
        self.shows: List[str] = []
        self.names: Dict[str, str] = {}
        for result in results:
            self.parse(result)
        self.acts = [self.replace_names(act, t)
                     for t, act in enumerate(self.acts)]
        self.already = [self.replace_names(fact) for fact in self.already]

    def replace_names(self, s: str, offset: int = 0) -> str:
        while True:
            r = s
            for k, v in self.names.items():
                if k[-1] == ')':
                    r = r.replace(k, v)
                else:
                    r = re.sub('\\b' + k + '\\b', v, r)
            if s == r:
                return s
            s = r

    def parse(self, result: str) -> None:
        if result.startswith('assert('):
            self.parse_assert(result)
        elif result.startswith('retract('):
            result = result[len('retract('):-1]
            self.parent.facts.remove(result)
        elif result.startswith('what('):
            result = result[len('what('):-1]
            self.shows.append(result)
        elif result.startswith('history('):
            self.parent.facts.add(result)
        elif result.startswith('already('):
            result = result[len('already('):-1].replace(',', ', ')
            self.already.append(result)
        elif result.startswith('describe('):
            r = result[len('describe('):-1].split(',')
            self.names[r[0]] = ' '.join(r[1:])
        elif result in ('ok', 'yes', 'no'):
            self.status = result

    def parse_assert(self, result: str) -> None:
        result = result[len('assert('):-1]
        self.parent.facts.add(result)
        m = re.fullmatch(r'apply\((.*),\d+\)', result)
        if m:
            self.acts.append(m.group(1).replace(',', ', '))


if __name__ == '__main__':
    aspi = ASPI(sys.argv[1:])
    while True:
        try:
            cmd = input('>>> ')
        except EOFError:
            cmd = 'thanks.'
        except KeyboardInterrupt:
            print('^C')
            continue
        print(cmd)
        if len(cmd) == 0 or cmd[0] == '%':
            continue
        while cmd[-1] not in '.?!':
            cont = input('... ')
            print(cont)
            cmd += cont
        if cmd == '#reset.':
            aspi = ASPI(sys.argv[1:])
        else:
            aspi.repl(cmd)
