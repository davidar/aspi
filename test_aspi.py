import pytest
import os.path

scripts = ['dcg', 'golf', 'hanoi', 'shortest-path', 'shrdlu', 'zebra', 'uva/10131']

for i in range(1000):
    name = f'euler/{i:03}'
    if os.path.exists(f'test/{name}.ldcs'):
        scripts.append(name)


@pytest.mark.parametrize('name', scripts)
def test_script(script_runner, name):
    args = ['./aspi.py']
    if os.path.exists(f'test/{name}.csv'):
        args.append(f'test/{name}.csv')
    ret = script_runner.run(*args, stdin=open(f'test/{name}.ldcs', 'r'))
    assert ret.success
    if not os.path.exists(f'test/{name}.log'):
        with open(f'test/{name}.log', 'w') as f:
            f.write(ret.stdout)
    assert ret.stdout == open(f'test/{name}.log', 'r').read()
    assert ret.stderr == ''
