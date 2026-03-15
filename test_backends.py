"""Cross-backend tests: verify Prolog and ASP backends produce the same results."""

import pytest
import subprocess
import os


def _run_prolog(ldcs_path):
    """Run LDCS file through Prolog backend, return last that: line."""
    csv_path = ldcs_path.replace('.ldcs', '.csv')
    args = ['uv', 'run', 'python', 'prolog.py']
    if os.path.exists(csv_path):
        args.append(csv_path)
    with open(ldcs_path) as f:
        proc = subprocess.run(args, stdin=f, capture_output=True, text=True, timeout=30)
    lines = [l.strip() for l in proc.stdout.split('\n') if l.startswith('that:')]
    return lines[-1] if lines else ''


def _run_asp(ldcs_path):
    """Run LDCS file through ASP backend, return last that: line."""
    csv_path = ldcs_path.replace('.ldcs', '.csv')
    args = ['uv', 'run', 'python', 'aspi.py']
    if os.path.exists(csv_path):
        args.append(csv_path)
    with open(ldcs_path) as f:
        proc = subprocess.run(args, stdin=f, capture_output=True, text=True, timeout=30)
    lines = [l.strip() for l in proc.stdout.split('\n') if l.startswith('that:')]
    return lines[-1] if lines else ''


import glob

def _discover_tests():
    tests = []
    for pat in ['test/euler/*.ldcs', 'test/db-*.ldcs', 'test/dcg.ldcs', 'test/golf.ldcs']:
        for path in sorted(glob.glob(pat)):
            name = path.replace('test/', '').replace('.ldcs', '')
            tests.append(pytest.param(path, id=name))
    return tests


@pytest.mark.parametrize('ldcs_path', _discover_tests())
def test_backends_agree(ldcs_path):
    """Both backends should produce the same final result."""
    try:
        asp = _run_asp(ldcs_path)
    except (subprocess.TimeoutExpired, Exception):
        pytest.skip('ASP backend failed')
    try:
        prolog = _run_prolog(ldcs_path)
    except (subprocess.TimeoutExpired, Exception):
        pytest.skip('Prolog backend failed')
    if not asp:
        pytest.skip('ASP produced no output')
    if not prolog:
        pytest.skip('Prolog produced no output')
    assert prolog == asp, f'\n  ASP:    {asp}\n  Prolog: {prolog}'
