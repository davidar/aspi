def test_euler(script_runner):
    ret = script_runner.run('./aspi.py', stdin=open('euler/test.in', 'r'))
    assert ret.success
    assert ret.stdout == open('euler/test.out', 'r').read()
    assert ret.stderr == ''


def test_shrdlu(script_runner):
    ret = script_runner.run('./aspi.py', 'shrdlu/world.lp', 'shrdlu/actions.lp',
                            stdin=open('shrdlu/test.in', 'r'))
    assert ret.success
    assert ret.stdout == open('shrdlu/test.out', 'r').read()
    assert ret.stderr == ''
