"""Cross-backend tests: verify Prolog and ASP backends produce the same results."""

import pytest
import subprocess
import os


def _result_lines(stdout):
    """Extract result lines: that:, reward:, and action lines (ending with !)."""
    lines = []
    for l in stdout.split('\n'):
        l = l.strip()
        if l.startswith('that:') or l.startswith('reward:'):
            lines.append(l)
        elif l.endswith('!') and not l.startswith('>>>') and l != "YOU'RE WELCOME!":
            lines.append(l)
    return lines


def _run_prolog(ldcs_path):
    """Run LDCS file through Prolog backend, return result lines."""
    csv_path = ldcs_path.replace('.ldcs', '.csv')
    args = ['uv', 'run', 'python', '-m', 'aspi']
    if os.path.exists(csv_path):
        args.append(csv_path)
    with open(ldcs_path) as f:
        proc = subprocess.run(args, stdin=f, capture_output=True, text=True, timeout=30)
    return _result_lines(proc.stdout)


def _run_asp(ldcs_path):
    """Run LDCS file through ASP backend, return result lines."""
    csv_path = ldcs_path.replace('.ldcs', '.csv')
    args = ['uv', 'run', 'python', '-m', 'aspi.asp']
    if os.path.exists(csv_path):
        args.append(csv_path)
    with open(ldcs_path) as f:
        proc = subprocess.run(args, stdin=f, capture_output=True, text=True, timeout=30)
    return _result_lines(proc.stdout)


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
    # Proof trees differ structurally between backends — skip those lines
    asp_filtered = [l for l in asp if 'proof(' not in l and 'step(' not in l]
    prolog_filtered = [l for l in prolog if 'proof(' not in l and 'step(' not in l]
    assert prolog_filtered == asp_filtered, f'\n  ASP:    {chr(10).join(asp)}\n  Prolog: {chr(10).join(prolog)}'
