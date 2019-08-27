#!/usr/bin/env python3
import json
import sh

import ldcs

def readfiles(*args):
  s = ''
  for name in args:
    with open(name, 'r') as f:
      s += f.read()
  return s

def clingo(lp):
  try:
    result = sh.clingo(_ok_code=[10], _in=lp, outf=2, time_limit=1).stdout
    values = json.loads(result)['Call'][-1]['Witnesses'][0]['Value']
    return values
  except:
    #print(lp)
    raise

program = readfiles('world.lp', 'actions.lp', 'planner.lp', 'why.lp', 'prelude.lp')
facts = set(['moves(0)'])
counter = 1

while True:
  moves = int([fact[len('moves('):-1] for fact in facts if fact.startswith('moves(')][0])
  cmd = input('>>> ')
  print(cmd)
  while cmd.endswith('\\'):
    cont = input('... ')
    print(cont)
    cmd = cmd[:-1] + '\n' + cont
  if not cmd or cmd.startswith('%'): continue
  if cmd == 'thanks.':
    print("YOU'RE WELCOME!")
    break
  if cmd.startswith(':macro '):
    cmd = cmd[len(':macro '):]
    ldcs.add_macro(cmd)
    continue
  if '[' in cmd:
    cmd = ldcs.transform(cmd)
    print('-->', '\n    '.join(cmd.split('\n')))
  cmd += '\n'
  if 'goal_once' in cmd:
    cmd += '{ goal(F) : goal_once(F) } = 1.\n'
  if cmd.startswith(':def '):
    cmd = cmd[len(':def '):]
    program += cmd
    if 'TIME' in cmd:
      cmd = cmd.replace('TIME', '(now+t)')
      program += '#program step(t).\n'
      program += cmd
      program += '#program base.\n'
    print('understood.\n')
    continue

  cmd += '#const now = ' + str(moves) + '.\n'
  cmd += '#const counter = ' + str(counter) + '.\n'
  cmd += ''.join(fact + '.\n' for fact in facts)
  try:
    results = clingo(cmd + program)
  except sh.ErrorReturnCode_1 as e:
    print("I CAN'T\n")
    #print(e.stderr.decode('utf-8'))
    continue
  shows = []
  for result in results:
    if result.startswith('assert('):
      result = result[len('assert('):-1]
      facts.add(result)
      print(result + '.')
    elif result.startswith('retract('):
      result = result[len('retract('):-1]
      facts.remove(result)
    elif result.startswith('show('):
      result = result[len('show('):-1]
      shows.append(result + '.')
    elif result.startswith('history('):
      facts.add(result)
  print('\n'.join(shows))
  print()
  counter += 1
