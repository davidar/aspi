"""PrologEngine — subprocess interface to SWI-Prolog."""

import os
import re
import sys
from typing import Dict, List, Optional, Tuple


class PrologEngine:
    """Runs SWI-Prolog queries via subprocess."""

    def __init__(self) -> None:
        self.clauses: List[str] = []
        self.predicates: Dict[Tuple[str, int], bool] = {}
        self._prelude = ''
        self._extra_facts_fn = None
        self._load_prelude()

    def _load_prelude(self) -> None:
        # Navigate from aspi/prolog/engine.py -> aspi/ -> project root -> lib/prelude.pl
        package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_dir = os.path.dirname(package_dir)
        prelude_path = os.path.join(project_dir, 'lib', 'prelude.pl')
        if os.path.exists(prelude_path):
            self._prelude = open(prelude_path).read()

    def add_clause(self, clause: str) -> None:
        clause = clause.strip()
        if not clause:
            return
        self.clauses.append(clause)
        pred_info = self._extract_pred(clause.rstrip('.'))
        if pred_info and pred_info not in self.predicates:
            self.predicates[pred_info] = False

    def retract_all(self, name: str, arity: int) -> None:
        prefix = f'{name}('
        self.clauses = [c for c in self.clauses if not c.startswith(prefix)]

    def _build_program(self, extra: str = '') -> str:
        all_clauses = '\n'.join(self.clauses)
        for (name, arity) in list(self.predicates.keys()):
            self.predicates[(name, arity)] = self._is_recursive(name, all_clauses)
        decls = []
        for (name, arity), recursive in self.predicates.items():
            decls.append(f':- discontiguous {name}/{arity}.')
            if recursive:
                decls.append(f':- table {name}/{arity}.')
        planning_facts = ''
        if self._extra_facts_fn:
            planning_facts = '\n'.join(f'{f}.' for f in self._extra_facts_fn())
        return '\n'.join([
            self._prelude, '',
            '\n'.join(decls), '',
            all_clauses, '', planning_facts, '', extra,
        ])

    def _is_recursive(self, name: str, program: str) -> bool:
        for line in program.split('\n'):
            line = line.strip()
            if not line or line.startswith('%'):
                continue
            if ' :- ' in line:
                head, body = line.split(' :- ', 1)
                head_pred = self._extract_pred(head.rstrip('.'))
                if head_pred and head_pred[0] == name and name + '(' in body:
                    return True
        return False

    def _run_query(self, program: str, goal: str, timeout: float = 30) -> List[Dict]:
        """Write program to temp file, run swipl, parse results."""
        import subprocess, tempfile
        query_directive = (
            f':- (findall(What, ({goal}), Results_) -> true ; Results_ = []),\n'
            f'   forall(member(R_, Results_), '
            f'format("result:~q~n", [R_])),\n'
            f'   halt.\n'
        )
        full = program + '\n' + query_directive

        with tempfile.NamedTemporaryFile(mode='w', suffix='.pl', delete=False) as f:
            f.write(full)
            f.flush()
            tmppath = f.name

        try:
            proc = subprocess.run(
                ['swipl', '-q', tmppath],
                capture_output=True, text=True, timeout=timeout)
            results = []
            for line in proc.stdout.split('\n'):
                if line.startswith('result:'):
                    val = line[len('result:'):]
                    results.append({'What': val})
            if proc.stderr and 'DEBUG' in os.environ:
                print(proc.stderr, file=sys.stderr)
            return results
        except subprocess.TimeoutExpired:
            return []
        except Exception as e:
            if 'DEBUG' in os.environ:
                print(f'swipl error: {e}', file=sys.stderr)
            return []
        finally:
            os.unlink(tmppath)

    def query(self, goal: str, timeout: float = 30) -> List:
        program = self._build_program()
        return self._run_query(program, goal, timeout)

    def query_once(self, goal: str, timeout: float = 30):
        results = self.query(goal, timeout)
        return results[0] if results else None

    def query_with_extra(self, goal: str, extra_clauses: str, timeout: float = 30) -> List:
        program = self._build_program(extra=extra_clauses)
        return self._run_query(program, goal, timeout)

    def reset(self) -> None:
        self.clauses.clear()
        self.predicates.clear()

    def _extract_pred(self, clause: str) -> Optional[Tuple[str, int]]:
        head = clause.split(':-')[0].strip() if ':-' in clause else clause.strip()
        m = re.match(r'(\w+)\((.+)\)$', head)
        if m:
            return m.group(1), self._count_args(m.group(2))
        elif re.match(r'^\w+$', head):
            return head, 0
        return None

    def _count_args(self, args_str: str) -> int:
        depth = 0
        count = 1
        for ch in args_str:
            if ch in '([': depth += 1
            elif ch in ')]': depth -= 1
            elif ch == ',' and depth == 0: count += 1
        return count
