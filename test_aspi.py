def run(s, name):
    ret = s.run('./aspi.py', stdin=open(f'test/{name}.ldcs', 'r'))
    assert ret.success
    assert ret.stdout == open(f'test/{name}.log', 'r').read()
    assert ret.stderr == ''


def test_euler(script_runner):
    run(script_runner, 'euler')


def test_golf(script_runner):
    run(script_runner, 'golf')


def test_hanoi(script_runner):
    run(script_runner, 'hanoi')


def test_shortest_path(script_runner):
    run(script_runner, 'shortest-path')


def test_zebra(script_runner):
    run(script_runner, 'zebra')


def test_shrdlu(script_runner):
    ret = script_runner.run(
        './aspi.py', 'shrdlu/world.lp', 'shrdlu/actions.lp',
        stdin=open('shrdlu/test.in', 'r'))
    assert ret.success
    assert ret.stdout == open('shrdlu/test.out', 'r').read()
    assert ret.stderr == ''
