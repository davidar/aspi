import pytest

scripts = ['euler', 'golf', 'hanoi', 'shortest-path', 'zebra']


@pytest.mark.parametrize('name', scripts)
def test_script(script_runner, name):
    ret = script_runner.run('./aspi.py', stdin=open(f'test/{name}.ldcs', 'r'))
    assert ret.success
    assert ret.stdout == open(f'test/{name}.log', 'r').read()
    assert ret.stderr == ''


def test_shrdlu(script_runner):
    ret = script_runner.run(
        './aspi.py', 'shrdlu/world.lp', 'shrdlu/actions.lp',
        stdin=open('shrdlu/test.in', 'r'))
    assert ret.success
    assert ret.stdout == open('shrdlu/test.out', 'r').read()
    assert ret.stderr == ''
