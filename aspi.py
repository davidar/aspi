#!/usr/bin/env python3
import atexit
import collections
import enum
import json
import re
import readline
import sh  # type: ignore
import sys
from typing import cast, Dict, List, Optional, Union

import ldcs


readline.parse_and_bind('tab: complete')

try:
    readline.read_history_file('history.log')
    readline.set_history_length(1000)
except FileNotFoundError:
    pass

atexit.register(readline.write_history_file, 'history.log')


class ClingoExitCode(enum.IntFlag):
    # https://github.com/potassco/clasp/issues/42
    UNKNOWN = 0  # Satisfiablity of problem not known; search not started.
    INTERRUPT = 1  # Run was interrupted.
    SAT = 10  # At least one model was found.
    EXHAUST = 20  # Search-space was completely examined.
    MEMORY = 33  # Run was interrupted by out of memory exception.
    ERROR = 65  # Run was interrupted by internal error.
    NO_RUN = 128  # Search not started because of syntax or command line error.


def clingo(lp: str) -> List[str]:
    result = json.loads(sh.clingo(
        outf=2, time_limit=4, _in=lp,
        _ok_code=[
            ClingoExitCode.SAT,
            ClingoExitCode.SAT | ClingoExitCode.EXHAUST
        ]).stdout)
    witness = result['Call'][-1]['Witnesses'][-1]
    if result['Result'] == 'OPTIMUM FOUND':
        costs = result['Models']['Costs']
        assert costs == witness['Costs']
        print(f"cost: {costs[0]}.")
    return cast(List[str], witness['Value'])


class ASPI:
    def __init__(self, libs: List[str] = []):
        self.counter = 1
        self.facts = set(['moves(0)'])
        self.ldcs = ldcs.LDCS()
        self.now = 0
        self.program = ''
        for lib in ['lib/prelude.lp', 'lib/plans.lp'] + libs:
            self.program += f'#include "{lib}".\n'

        with open('lib/macros.lp', 'r') as f:
            for line in f:
                if line.strip():
                    self.ldcs.add_macro(line)

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
        if cmd == 'thanks.':
            print("YOU'RE WELCOME!")
            sys.exit(0)
        res = self.eval(cmd)
        if res is not None:
            self.print(res)
            for fact in self.facts:
                if fact.startswith('moves('):
                    self.now = int(fact[len('moves('):-1])
            self.counter += 1

    def eval(self, cmd: str) -> Optional['Results']:
        lp = self.ldcs.toASP(cmd)
        if lp is None:
            return None
        print('-->', '\n    '.join(
            line for line in lp.split('\n') if '@proof' not in line))
        lp += '\n'
        if cmd.endswith('.'):
            if cmd.startswith('#macro'):
                for line in lp.split('\n'):
                    if line.strip() and '@proof' not in line:
                        self.ldcs.add_macro(line)
            else:
                self.program += lp
            print('understood.\n')
            return None

        lp += f'#const now = {self.now}.\n'
        lp += f'#const counter = {self.counter}.\n'
        lp += ''.join(fact + '.\n' for fact in self.facts)
        lp += self.program
        if cmd.endswith('!'):
            lp += '#include "lib/planner.lp".\n'
        try:
            return Results(self, clingo(lp))
        except sh.ErrorReturnCode as e:
            if e.exit_code == ClingoExitCode.INTERRUPT:
                print('timeout.\n')
                return None
            elif e.exit_code == ClingoExitCode.EXHAUST:
                print('impossible.\n')
                return None
            else:
                print(e.stderr.decode('utf-8'), file=sys.stderr)
                print(ClingoExitCode(e.exit_code), file=sys.stderr)
                for i, line in enumerate(lp.split('\n')):
                    print(i, line, file=sys.stderr)
                sys.exit(1)

    def print(self, res: 'Results') -> None:
        for fact in res.already:
            print(fact + '.')
        for act in res.acts:
            print(act + '!')
        if res.status:
            print(res.status + '.')
        if res.shows:
            terms: List[Union[str, int]] = []
            for r in res.shows:
                if r.isnumeric():
                    terms.append(int(r))
                else:
                    terms.append(r)
            terms.sort()
            that = ' | '.join(str(t) for t in terms)
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
        self.names_t: Dict[int, Dict[str, str]] = collections.defaultdict(dict)
        for result in results:
            self.parse(result)
        self.acts = [self.replace_names(act, t)
                     for t, act in enumerate(self.acts)]
        self.already = [self.replace_names(fact) for fact in self.already]
        self.shows = [self.replace_names(show) for show in self.shows]

    def replace_names(self, s: str, offset: int = 0) -> str:
        d = self.names_t[self.parent.now + offset]
        while True:
            r = s
            for k, v in self.names.items():
                if k in d:
                    v += ' ' + d[k]
                r = re.sub('\\b' + k + '\\b', v, r)
            if s == r:
                return s
            d = {}
            s = r

    def parse(self, result: str) -> None:
        if result.startswith('assert('):
            self.parse_assert(result)
        elif result.startswith('retract('):
            result = result[len('retract('):-1]
            self.parent.facts.remove(result)
        elif result.startswith('what('):
            self.parse_what(result)
        elif result.startswith('history('):
            self.parent.facts.add(result)
        elif result.startswith('already('):
            result = result[len('already('):-1].replace(',', ', ')
            self.already.append(result)
        elif result.startswith('describe('):
            r = result[len('describe('):-1].split(',')
            self.names[r[0]] = ' '.join(r[1:])
        elif result.startswith('describe_extra('):
            self.parse_describe_extra(result)
        elif result in ('ok', 'yes', 'no'):
            self.status = result

    def parse_assert(self, result: str) -> None:
        result = result[len('assert('):-1]
        self.parent.facts.add(result)
        m = re.fullmatch(r'apply\((.*),\d+\)', result)
        if m:
            self.acts.append(m.group(1).replace(',', ', '))

    def parse_what(self, result: str) -> None:
        result = result[len('what('):-1]
        m = re.fullmatch(r'apply\((.*),\d+\)', result)
        if m:
            result = m.group(1).replace(
                '(', '[').replace(')', ']').replace(',', ', ')
        m = re.fullmatch(r'history\(\d+,goal\((.*)\)\)', result)
        if m:
            result = 'goal.' + m.group(1).replace(',', ', ')
        self.shows.append(result)

    def parse_describe_extra(self, result: str) -> None:
        r = result[len('describe_extra('):-1].split(',')
        t = int(r[0])
        self.names_t[t][r[1]] = ' '.join(r[2:]).replace(
            '(', '[').replace(')', ']').replace('not_', '~')


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
        if cmd == '#reset.':
            aspi = ASPI(sys.argv[1:])
        else:
            aspi.repl(cmd)
