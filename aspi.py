#!/usr/bin/env python3
import json
import re
import sh
import sys

import ldcs

ClingoExhausted = sh.ErrorReturnCode_20


def replaceall(s, d, d2={}):
    r = s
    for k, v in d.items():
        if k in d2:
            v += ' ' + d2[k]
        r = r.replace(k, v)
    if s == r:
        return s
    return replaceall(r, d)


def readfiles(*args):
    s = ''
    for name in args:
        with open(name, 'r') as f:
            s += f.read()
    return s


def clingo(lp):
    result = sh.clingo(_ok_code=[10], _in=lp, outf=2, time_limit=2).stdout
    values = json.loads(result)['Call'][-1]['Witnesses'][0]['Value']
    return values


program = readfiles('world.lp', 'actions.lp',
                    'planner.lp', 'why.lp', 'prelude.lp')
facts = set(['moves(0)'])
counter = 1

with open('macros.lp', 'r') as f:
    for line in f:
        ldcs.add_macro(line)


def repl(cmd):
    global program, counter
    if not cmd or cmd.startswith('%'):
        return
    if cmd == 'thanks.':
        print("YOU'RE WELCOME!")
        sys.exit(0)

    declare = cmd.endswith('.')
    cmd = ldcs.transform(cmd)
    print('-->', '\n    '.join(cmd.split('\n')))
    cmd += '\n'
    if declare:
        program += cmd
        print('understood.\n')
        return

    now = int([fact[len('moves('):-1]
               for fact in facts if fact.startswith('moves(')][0])
    cmd += '#const now = ' + str(now) + '.\n'
    cmd += '#const counter = ' + str(counter) + '.\n'
    cmd += ''.join(fact + '.\n' for fact in facts)
    try:
        results = clingo(cmd + program)
    except ClingoExhausted:
        print('impossible.\n')
        return
    except sh.ErrorReturnCode as e:
        print(e.stderr.decode('utf-8'), file=sys.stderr)
        sys.exit(1)
    print_results(results, now)
    counter += 1


def print_results(results, now):
    ok = False
    acts = []
    shows = []
    names = {}
    names_t = {}
    for result in results:
        ret = parse_result(result, acts, shows, names, names_t)
        if ret is True:
            ok = True
        elif ret is not None:
            print(ret)
    for t, act in enumerate(acts):
        print(replaceall(act, names, names_t[now+t]) + '!')
    if ok:
        print('ok.')
    shows = [replaceall(show, names, names_t[now]) for show in shows]
    if shows:
        print('that(' + ' | '.join(shows) + ').')
    print()


def parse_result(result, acts, shows, names, names_t):
    if result.startswith('assert('):
        parse_assert(result, acts)
    elif result.startswith('retract('):
        result = result[len('retract('):-1]
        facts.remove(result)
    elif result.startswith('what('):
        parse_what(result, shows)
    elif result.startswith('history('):
        facts.add(result)
    elif result.startswith('already('):
        result = result[len('already('):-1].replace(',', ', ')
        return replaceall(result, names) + '.'
    elif result.startswith('describe('):
        result = result[len('describe('):-1].split(',')
        names[result[0]] = ' '.join(result[1:])
    elif result.startswith('describe_extra('):
        parse_describe_extra(result, names_t)
    elif result == 'ok':
        return True


def parse_assert(result, acts):
    result = result[len('assert('):-1]
    facts.add(result)
    m = re.fullmatch(r'apply\((.*),\d+\)', result)
    if m:
        acts.append(m.group(1).replace(',', ', '))


def parse_what(result, shows):
    result = result[len('what('):-1]
    m = re.fullmatch(r'apply\((.*),\d+\)', result)
    if m:
        result = m.group(1).replace(
            '(', '[').replace(')', ']').replace(',', ', ')
    m = re.fullmatch(r'history\(\d+,goal\((.*)\)\)', result)
    if m:
        result = 'goal.' + m.group(1).replace(',', ', ')
    shows.append(result)


def parse_describe_extra(result, names_t):
    result = result[len('describe_extra('):-1].split(',')
    t = int(result[0])
    if t not in names_t:
        names_t[t] = {}
    names_t[t][result[1]] = ' '.join(result[2:]).replace(
        '(', '[').replace(')', ']').replace('not_', '~')


if __name__ == '__main__':
    while True:
        cmd = input('>>> ')
        print(cmd)
        repl(cmd)
