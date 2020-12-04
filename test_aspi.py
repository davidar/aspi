def test_aspi(script_runner):
    ret = script_runner.run('./aspi.py', stdin=open('test.in', 'r'))
    assert ret.success
    assert ret.stdout == open('test.out', 'r').read()
    assert ret.stderr == ''
