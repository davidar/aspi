"""Unified CLI entrypoint for aspi."""

import sys


def main():
    args = sys.argv[1:]

    from aspi.prolog.repl import PrologASPI
    repl_instance = PrologASPI(args)

    while True:
        try:
            cmd = input('>>> ')
        except EOFError:
            cmd = 'thanks.'
        except KeyboardInterrupt:
            print('^C')
            continue
        print(cmd)
        if len(cmd) == 0 or cmd[0] == '%':
            continue
        while cmd[-1] not in '.?!':
            cont = input('... ')
            print(cont)
            cmd += cont
        if cmd == '#reset.':
            repl_instance = PrologASPI(args)
        else:
            repl_instance.repl(cmd)


if __name__ == '__main__':
    main()
