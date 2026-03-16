#!/usr/bin/env python3
import atexit
import clingo
import enum
import json
import os
import re
import readline
import sys
from typing import cast, Dict, List, Optional

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


class ClingoError(Exception):
    def __init__(self, exit_code: int, stderr: str = ''):
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f'clingo exit code {exit_code}')


class ClingoContext:
    """Provides @-functions for clingo grounding (replaces #script block)."""

    def __init__(self):
        self.gathered = {}

    def show(self, a):
        return clingo.String(str(a))

    def concatenate(self, a, b):
        return clingo.String(a.string + b.string)

    def reverse(self, a):
        return clingo.String(a.string[::-1])

    def substring(self, a, start, length):
        return clingo.String(a.string[start.number-1:start.number-1+length.number])

    def length(self, a):
        return clingo.Number(len(a.string))

    def decimal(self, a):
        try:
            return clingo.Number(int(a.string))
        except Exception:
            return clingo.Function('error')

    def permutation(self, a):
        import itertools
        return [clingo.String(''.join(t)) for t in itertools.permutations(a.string)]

    def codepoint(self, a):
        try:
            return clingo.Number(ord(a.string))
        except TypeError:
            return clingo.Number(-1)

    def gather(self, i, a):
        if i not in self.gathered:
            self.gathered[i] = []
        if a.type == clingo.SymbolType.Function and a.name == 'gather_sentinel':
            pass
        else:
            self.gathered[i].append(a)
        return i

    def setof(self, i):
        if i not in self.gathered:
            return clingo.Function('empty')
        return clingo.Function('set', sorted(self.gathered[i]))

    def bagof(self, i):
        try:
            return clingo.Function('bag', sorted(a.arguments[0] for a in self.gathered[i]))
        except Exception:
            return clingo.Function('error')

    def countof(self, a):
        return clingo.Number(len(a.arguments))

    def sumof(self, a):
        return clingo.Number(sum(x.number for x in a.arguments) % sys.maxsize)

    def productof(self, a):
        import math
        return clingo.Number(math.prod(x.number for x in a.arguments) % sys.maxsize)

    def minof(self, a):
        if len(a.arguments) == 0 or all(x == clingo.Supremum for x in a.arguments):
            return clingo.Supremum
        return clingo.Number(min(x.number for x in a.arguments if x != clingo.Supremum))

    def maxof(self, a):
        if len(a.arguments) == 0 or all(x == clingo.Infimum for x in a.arguments):
            return clingo.Infimum
        return clingo.Number(max(x.number for x in a.arguments if x != clingo.Infimum))

    def memberof(self, a):
        return a.arguments

    def enumerateof(self, a):
        return [clingo.Tuple_([clingo.Number(i+1), x]) for i, x in enumerate(sorted(a.arguments))]

    def proof(self, head, *args):
        if len(args) == 0:
            return head
        body = set()
        proofs = set()
        for p in args:
            if p.type == clingo.SymbolType.Function and p.name == 'proof':
                for subproof in p.arguments:
                    body.add(subproof.arguments[0])
                    proofs.add(subproof)
            else:
                body.add(p)
        proofs.add(clingo.Tuple_([head] + sorted(body)))
        return clingo.Function('proof', sorted(proofs))

    def context(self, *args):
        """No-op: @context is used for scoping in gather, handled by ASP rules."""
        return clingo.Function('context', list(args))


def _preprocess_asp(lp: str) -> str:
    """Resolve #include directives and remove #script blocks."""
    import re
    # Inline #include directives
    def resolve_includes(text):
        def replace_include(m):
            path = m.group(1)
            try:
                with open(path) as f:
                    content = f.read()
                return resolve_includes(content)
            except FileNotFoundError:
                return m.group(0)  # keep as-is if not found
        return re.sub(r'#include\s+"([^"]+)"\s*\.?', replace_include, text)

    lp = resolve_includes(lp)
    # Strip #script (python) ... #end.
    lp = re.sub(r'#script\s*\(python\).*?#end\.', '', lp, flags=re.DOTALL)
    return lp


def run_clingo(lp: str, time_limit: int = 5) -> List[str]:
    ctl = clingo.Control(['0'])
    ctx = ClingoContext()

    if 'DEBUG' in os.environ:
        print(lp, file=sys.stderr)

    ctl.add('base', [], _preprocess_asp(lp))
    ctl.ground([('base', ())], context=ctx)

    models: List[dict] = []
    interrupted = False

    def on_timeout(signum, frame):
        nonlocal interrupted
        interrupted = True
        ctl.interrupt()

    import signal
    old_handler = signal.signal(signal.SIGALRM, on_timeout)
    signal.alarm(time_limit)
    try:
        with ctl.solve(yield_=True) as handle:
            for model in handle:
                models.append({
                    'Value': [str(a) for a in model.symbols(shown=True)],
                    'Costs': model.cost,
                    'Optimal': model.optimality_proven,
                })
            result = handle.get()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    if interrupted or not models:
        if interrupted:
            raise ClingoError(int(ClingoExitCode.INTERRUPT))
        raise ClingoError(int(ClingoExitCode.EXHAUST))

    if result.unsatisfiable:
        raise ClingoError(int(ClingoExitCode.EXHAUST))
    if not result.satisfiable and not models:
        raise ClingoError(int(ClingoExitCode.UNKNOWN))

    witness = models[-1]

    if witness['Costs'] and any(c != 0 for c in witness['Costs']):
        costs = witness['Costs']
        if costs[0] < 0:
            print(f"reward: {-costs[0]}.")
        else:
            print(f"cost: {costs[0]}.")

    return cast(List[str], witness['Value'])


class ASPI:
    def __init__(self, args: List[str] = []):
        self.counter = 1
        self.facts = set(['moves(0)'])
        self.ldcs = ldcs.LDCS()
        self.now = 0
        self.program = ''
        self.proofs = True

        for arg in ['lib/prelude.lp', 'lib/macros.ldcs', 'lib/plans.ldcs'] + args:
            self.include(arg)

    def include(self, arg: str) -> None:
        if arg.endswith('.lp'):
            self.program += f'#include "{arg}".\n'
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
        # Strip ?! routing suffix — treat as plain query
        if cmd.endswith('?!'):
            cmd = cmd[:-1]
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

    def eval(self, cmd: str) -> Optional['Results']:
        lp = self.ldcs.toASP(cmd.replace('#macro ', ''))
        if lp is None:
            return None
        print('-->', '\n    '.join(
            line for line in lp.split('\n')
            if '@proof' not in line or 'DEBUG' in os.environ))
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

        lp += f'#const now = {self.now}.\n'
        lp += f'#const counter = {self.counter}.\n'
        lp += ''.join(fact + '.\n' for fact in self.facts)
        lp += self.program
        if cmd.endswith('!'):
            lp += '#include "lib/planner.lp".\n'
        try:
            return Results(self, run_clingo(lp))
        except ClingoError as e:
            if e.exit_code == ClingoExitCode.INTERRUPT:
                print('timeout.\n')
                return None
            elif e.exit_code == ClingoExitCode.EXHAUST:
                print('impossible.\n')
                return None
            else:
                print(e.stderr, file=sys.stderr)
                print(ClingoExitCode(e.exit_code), file=sys.stderr)
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
            self.parent.facts.discard(result)
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
