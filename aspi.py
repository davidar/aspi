#!/usr/bin/env python3
import json
import re
import sh

import ldcs

ClingoExhausted = sh.ErrorReturnCode_20

def replaceall(s, d):
  r = s
  for k,v in d.items():
    r = r.replace(k,v)
  if s == r: return s
  return replaceall(r, d)

def readfiles(*args):
  s = ''
  for name in args:
    with open(name, 'r') as f:
      s += f.read()
  return s

def clingo(lp):
  try:
    result = sh.clingo(_ok_code=[10], _in=lp, outf=2, time_limit=2).stdout
    values = json.loads(result)['Call'][-1]['Witnesses'][0]['Value']
    return values
  except:
    #print(lp)
    raise

program = readfiles('world.lp', 'actions.lp', 'planner.lp', 'why.lp', 'prelude.lp')
facts = set(['moves(0)'])
counter = 1

with open('macros.lp', 'r') as f:
  for line in f:
    ldcs.add_macro(line)

while True:
  moves = int([fact[len('moves('):-1] for fact in facts if fact.startswith('moves(')][0])
  cmd = input('>>> ')
  print(cmd)

  if not cmd or cmd.startswith('%'): continue
  if cmd == 'thanks.':
    print("YOU'RE WELCOME!")
    break

  declare = cmd.endswith('.')
  cmd = ldcs.transform(cmd)
  print('-->', '\n    '.join(cmd.split('\n')))
  cmd += '\n'
  if declare:
    program += cmd
    print('understood.\n')
    continue

  cmd += '#const now = ' + str(moves) + '.\n'
  cmd += '#const counter = ' + str(counter) + '.\n'
  cmd += ''.join(fact + '.\n' for fact in facts)
  try:
    results = clingo(cmd + program)
  except ClingoExhausted as e:
    print('impossible.\n')
    #print(e.stderr.decode('utf-8'))
    continue

  ok = False
  shows = []
  names = {}
  for result in results:
    if result.startswith('assert('):
      result = result[len('assert('):-1]
      facts.add(result)
      m = re.fullmatch(r'apply\((.*),\d+\)', result)
      if m: print(m.group(1))
    elif result.startswith('retract('):
      result = result[len('retract('):-1]
      facts.remove(result)
    elif result.startswith('show('):
      result = result[len('show('):-1]
      m = re.fullmatch(r'apply\((.*),\d+\)', result)
      if m: result = m.group(1) \
        .replace('(','[').replace(')',']').replace(',', ', ')
      m = re.fullmatch(r'history\(\d+,goal\((.*)\)\)', result)
      if m: result = 'goal.' + m.group(1).replace(',', ', ')
      if result not in shows: shows.append(result)
    elif result.startswith('history('):
      facts.add(result)
    elif result.startswith('already('):
      result = result[len('already('):-1].replace(',', ', ')
      print(replaceall(result, names) + '.')
    elif result.startswith('describe('):
      result = result[len('describe('):-1].split(',')
      names[result[0]] = ' '.join(result[1:]) \
        .replace('(','[').replace(')',']').replace('not_','~')
    elif result == 'ok':
      ok = True
  if ok: print('ok.')
  shows = [replaceall(show, names) for show in shows]
  if shows: print('that(' + ' | '.join(shows) + ').')
  print()
  counter += 1
