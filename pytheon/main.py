# -*- coding: utf-8 -*-
import sys
import commands
import logging as log
from optparse import OptionParser

parser = OptionParser()
parser.usage = '''usage: %%prog [command] [options]

Valid commands are:

    %s

Valid project commands are:

    %s

Get help on each command with: %%prog [command] -h''' % (
    '\n    '.join(sorted(commands.commands)),
    '\n    '.join(sorted(commands.project_commands)))

if '--verbose' in sys.argv:
    log.basicConfig(stream=sys.stdout, level=log.DEBUG,
                    format='%(levelname)-4s: %(message)s')
else:
    log.basicConfig(stream=sys.stdout, level=log.INFO, format='%(message)s')


def main(args=None, testing=False, **kwargs):
    args = args or sys.argv[1:]
    if args:
        try:
            cmd = args.pop(0)
            cmd = getattr(commands, cmd)
        except Exception, e:
            print e
        else:
            result = cmd(args, **kwargs)
            if isinstance(result, basestring):
                for line in result.strip().split('\n'):
                    line = line.strip()
                    if line.startswith('! '):
                        log.error(line[2:])
                    else:
                        log.info(line)
                    if testing:
                        return result.strip()
            return ''
    parser.parse_args(['-h'])


def run(*args, **kwargs):
    sys.argv[0] = 'pytheon'
    try:
        return main(list(args), testing=True, **kwargs)
    except Exception, e:
        return repr(e)
