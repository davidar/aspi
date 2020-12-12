#!/usr/bin/env python3
import atexit
import collections
import enum
import json
import re
import readline
import sh  # type: ignore
import sys
from typing import cast, Dict, List

import ldcs


readline.parse_and_bind('tab: complete')

try:
    readline.read_history_file('history.log')
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


def readfiles(*args: str) -> str:
    s = ''
    for name in args:
        with open(name, 'r') as f:
            s += f.read()
    return s


def clingo(lp: str) -> List[str]:
    result = sh.clingo(_ok_code=[ClingoExitCode.SAT],
                       _in=lp, outf=2, time_limit=3).stdout
    values = json.loads(result)['Call'][-1]['Witnesses'][0]['Value']
    return cast(List[str], values)


class ASPI:
    def __init__(self, libs: List[str] = []):
        self.counter = 1
        self.facts = set(['moves(0)'])
        self.ldcs = ldcs.LDCS()
        self.now = 0
        self.program = readfiles('lib/prelude.lp', 'lib/planner.lp',
                                 'lib/plans.lp', *libs)

        with open('lib/macros.lp', 'r') as f:
            for line in f:
                if line.strip():
                    self.ldcs.add_macro(line)

    def repl(self, cmd: str) -> None:
        if not cmd or cmd.startswith('%'):
            return
        if cmd == 'thanks.':
            print("YOU'RE WELCOME!")
            sys.exit(0)

        declare = cmd.endswith('.')
        command = cmd.endswith('!')
        lp = self.ldcs.toASP(cmd)
        if lp is None:
            return
        print('-->', '\n    '.join(lp.split('\n')))
        lp += '\n'
        if declare:
            self.program += lp
            print('understood.\n')
            return

        lp += '#const now = ' + str(self.now) + '.\n'
        lp += '#const counter = ' + str(self.counter) + '.\n'
        lp += ''.join(fact + '.\n' for fact in self.facts)
        lp += self.program
        try:
            res = Results(self, clingo(lp))
        except sh.ErrorReturnCode as e:
            if e.exit_code == ClingoExitCode.INTERRUPT:
                print('timeout.\n')
                return
            elif e.exit_code == ClingoExitCode.EXHAUST:
                print('impossible.\n')
                return
            else:
                print(e.stderr.decode('utf-8'), file=sys.stderr)
                print(ClingoExitCode(e.exit_code), file=sys.stderr)
                sys.exit(1)
        for fact in res.already:
            print(fact + '.')
        for act in res.acts:
            print(act + '!')
        if res.ok:
            print('ok.')
        elif command:
            print('failed.')
        if res.shows:
            print('that(' + ' | '.join(res.shows) + ').')
        print()
        for fact in self.facts:
            if fact.startswith('moves('):
                self.now = int(fact[len('moves('):-1])
        self.counter += 1


class Results:
    def __init__(self, parent: ASPI, results: List[str]) -> None:
        self.parent = parent
        self.ok = False
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
                r = r.replace(k, v)
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
        elif result == 'ok':
            self.ok = True

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
        aspi.repl(cmd)
