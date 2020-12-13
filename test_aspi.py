def run(s, name, plan=False):
    args = [name + '/world.lp', name + '/actions.lp'] if plan else []
    ret = s.run('./aspi.py', *args, stdin=open(name + '/test.in', 'r'))
    assert ret.success
    assert ret.stdout == open(name + '/test.out', 'r').read()
    assert ret.stderr == ''


def test_euler(script_runner):
    run(script_runner, 'euler')


def test_golf(script_runner):
    run(script_runner, 'golf')


def test_hanoi(script_runner):
    run(script_runner, 'hanoi', True)


def test_shrdlu(script_runner):
    run(script_runner, 'shrdlu', True)
