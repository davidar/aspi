"""Benchmark: compare Prolog and ASP backend performance on all test cases."""

import glob
import os
import subprocess
import time
import sys


def run_backend(backend, ldcs_path, timeout=60):
    """Run an LDCS file through a backend, return (time_seconds, last_that_line, stderr_snippet)."""
    csv_path = ldcs_path.replace('.ldcs', '.csv')
    if backend == 'prolog':
        args = ['uv', 'run', 'python', 'prolog.py']
    else:
        args = ['uv', 'run', 'python', 'aspi.py']
    if os.path.exists(csv_path):
        args.append(csv_path)

    start = time.monotonic()
    try:
        with open(ldcs_path) as f:
            proc = subprocess.run(args, stdin=f, capture_output=True, text=True, timeout=timeout)
        elapsed = time.monotonic() - start
        # Only show stderr for non-clingo errors (clingo info warnings are noise)
        stderr = ''
        if proc.stderr:
            lines = [l.strip() for l in proc.stderr.split('\n')
                     if l.strip() and '<block>' not in l and ': info:' not in l]
            stderr = ' '.join(lines)[:100]
        if proc.returncode != 0:
            return elapsed, f'CRASH({proc.returncode})', stderr
        lines = [l.strip() for l in proc.stdout.split('\n') if l.startswith('that:')]
        result = lines[-1] if lines else ''
        return elapsed, result, stderr
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        return elapsed, 'TIMEOUT', ''
    except Exception as e:
        elapsed = time.monotonic() - start
        return elapsed, f'ERROR: {e}', ''


def main():
    patterns = ['test/euler/*.ldcs', 'test/db-*.ldcs', 'test/dcg.ldcs', 'test/golf.ldcs']
    tests = []
    for pat in patterns:
        tests.extend(sorted(glob.glob(pat)))

    print(f'{"test":<20} {"prolog":>8} {"asp":>8} {"speedup":>8}  {"match":>5}  notes')
    print('-' * 80)

    total_prolog = 0
    total_asp = 0
    matches = 0
    total = 0

    for path in tests:
        name = path.replace('test/', '').replace('.ldcs', '')

        pt, pr, pe = run_backend('prolog', path)
        at, ar, ae = run_backend('asp', path)

        total_prolog += pt
        total_asp += at
        total += 1

        if pr == 'TIMEOUT':
            speedup = 'T/O'
        elif at == 'TIMEOUT':
            speedup = 'asp T/O'
        elif at > 0:
            speedup = f'{at/pt:.1f}x'
        else:
            speedup = '-'

        if pr == ar:
            match = 'YES'
            matches += 1
        elif pr == 'TIMEOUT' or ar == 'TIMEOUT':
            match = 'T/O'
        else:
            match = 'FAIL'

        notes = ''
        if pe:
            notes = pe[:40]
        if match == 'FAIL':
            notes = f'P:{(pr or "(empty)")[:30]} A:{(ar or "(empty)")[:30]}'

        print(f'{name:<20} {pt:>7.2f}s {at:>7.2f}s {speedup:>8}  {match:>5}  {notes}')

    print('-' * 80)
    print(f'{"TOTAL":<20} {total_prolog:>7.2f}s {total_asp:>7.2f}s {"":>8}  {matches}/{total}')


if __name__ == '__main__':
    main()
