# -*- coding: utf-8 -*-
from __future__ import with_statement
import os
import os.path
import sys
import logging as log
import functools
from pytheon import http
from pytheon import utils
from pytheon.utils import Config
from optparse import OptionParser
# totot
commands = []
project_commands = []

filename = os.path.expanduser('~/.pytheonrc')
global_config = utils.user_config()


def with_project(func):
    @functools.wraps(func)
    def wrapped(parser, options, args):
        config = utils.project_config()
        if not os.path.isfile(config._filename):
            parser.error('It look like you are not in a valid pytheon project')
        elif not config.deploy.project_name:
            parser.error('It look like you are not in a valid pytheon project')
        return func(parser, options, args, config)
    wrapped.project_command = True
    return wrapped


def with_parser(parser):
    parser.add_option("--verbose",
                       action="store_true", dest="verbose", default=False)

    def wrapper(func):
        if getattr(func, 'project_command', False):
            project_commands.append(func.func_name)
        else:
            commands.append(func.func_name)
        parser.usage = '%%prog %s [options]\n\n%s' % (func.func_name,
                                                      func.__doc__.strip())

        @functools.wraps(func)
        def wrapped(args, **kwargs):
            options, args = parser.parse_args(args)
            try:
                result = func(parser, options, args, **kwargs)
            except KeyboardInterrupt:
                sys.exit(-1)
            except Exception, e:
                log.exception(e)
                print ''
                parser.parse_args(['-h'])
            else:
                return result
        return wrapped
    return wrapper


def commit(binary, filename):
    utils.call(binary, 'add', filename, silent=True)
    utils.call(binary, 'commit', filename, '-m',
               '"[pytheon] auto update %s"' % filename, silent=True)


parser = OptionParser()
parser.add_option('-e', '--email', action='store', default=utils.user(),
                  metavar='EMAIL', dest='username',
                  help='E-mail. Default: %s' % utils.user())
parser.add_option('-k', '--confirm-key', action='store', default=None,
                  dest='key', help='Confirm key')
parser.add_option('-r', '--reset-password',
                  action='store_true', dest='reset',
                  help='Send a password reset request')


@with_parser(parser)
def register(parser, options, args):
    """register on pytheon"""
    if options.key and options.reset:
        parser.error("You can't reset a password with a confirmation key")

    config = utils.user_config()
    if options.username:
        config.pytheon.username = options.username
        config.write()

    if not config.pytheon.username:
        parser.error('Please specify a valid email')

    if options.key:
        return http.request('/v1/set_password/%s' % options.key.strip('/'),
                            auth=False,
                            password=utils.get_input('Password',
                            password=True))
    elif options.reset:
        return http.request('/v1/reset_password/', auth=False,
                            email=options.username)
    else:
        return http.request('/v1/register', auth=False, email=options.username)


parser = OptionParser()
parser.add_option('-b', '--buildout', action='store_true', default=False,
                  dest='buildout',
                  help='Use buildout.cfg file instead of deploy.ini')
parser.add_option('-n', '--project-name', action='store',
                  default=os.path.basename(os.getcwd()),
                  dest='project_name', help='Specify application name')
parser.add_option('-e', '--email', action='store', default=utils.user(),
                  metavar='EMAIL', dest='username',
                  help='E-mail. Default: %s' % utils.user())


@with_parser(parser)
def create(parser, options, args):
    """create your pytheon project"""
    binary = utils.vcs_binary()

    global_config = utils.user_config()
    if not os.path.isfile(global_config._filename):
        global_config.pytheon = dict(
                username=options.username or utils.get_input('Username'),
            )
        global_config.write()
    rc = global_config.pytheon

    config = utils.project_config(filename=options.buildout)
    if not os.path.isfile(config._filename):
        if not options.project_name:
            options.project_name = utils.get_input('Project name',
                           default=os.path.basename(os.getcwd()))
        config.deploy = dict(
                version='1',
                use='gunicorn',
                project_name=options.project_name,
            )
    if options.project_name:
        config.deploy.project_name = options.project_name
    config.write()

    kw = dict(username=rc.username, project_name=config.deploy.project_name)
    if binary == 'git':
        remote = os.environ.get('PYTHEON_REMOTE',
                        'git@git.pytheon.net:%(project_name)s.git').rstrip('/')
        remote = remote % kw
        utils.call(binary, 'remote', 'add', 'pytheon', remote, silent=True)

    else:
        remote = os.environ.get('PYTHEON_REMOTE',
                        'hg@hg.pytheon.net/%(project_name)s').rstrip('/')
        remote = remote % kw
        filename = '.hg/hgrc'
        config = Config.from_file(filename)
        config.paths.pytheon = remote
        config.write()

    commit(binary, config._filename)

    return http.request('/v1/applications', name=config.deploy.project_name)


parser = OptionParser()
parser.add_option('-l', '--list', action='store_true', default=False,
                  dest='list', help='List your application')
parser.add_option('--delete', action='store', default=None, metavar='APP',
                  dest='delete', help='Delete application')


@with_parser(parser)
def apps(parser, options, args):
    """Application related command"""

    if options.delete:
        return http.request('/v1/applications/%s' % options.delete,
                            method='DELETE')
    return http.request('/v1/applications')

parser = OptionParser()
parser.add_option('-l', '--list', action='store_true', default=False,
                  dest='list', help='List your application addons')
parser.add_option('--add', action='store', default=None,
                  metavar='ADDON:PLAN',
                  dest='add', help='Add application addon')
parser.add_option('--upgrade', action='store', default=None,
                  metavar='ADDON:PLAN',
                  dest='upgrade', help='Upgrade application addon')
parser.add_option('--delete', action='store', default=None, metavar='ADDON',
                  dest='delete', help='Delete application addon')
parser.add_option('--all', action='store_true', default=False,
                  dest='all', help='List all available addons')


@with_parser(parser)
@with_project
def addons(parser, options, args, config):
    """Addon management"""

    path = '/v1/applications/%s/addons' % config.deploy.project_name
    if options.all:
        return http.request('/v1/addons')
    elif options.add:
        try:
            id, plan = options.add.split(':')
        except ValueError:
            parser.error('Please specify a addon:plan')
        return http.request(path, method='POST', id=id, plan=plan)
    elif options.upgrade:
        try:
            id, plan = options.upgrade.split(':')
        except ValueError:
            parser.error('Please specify a addon:plan')
        return http.request('%s/%s' % (path, id), method='POST', plan=plan)
    elif options.delete:
        return http.request('%s/%s' % (path, options.delete),
                            method='DELETE')  # FIXME
    else:
        return http.request(path)


parser = OptionParser()


@with_parser(parser)
@with_project
def deploy(parser, options, args, config):
    """Deploy current repository to pytheon"""

    binary = utils.vcs_binary()

    if binary == 'git':
        state = utils.call(binary, 'status', '-s', silent=True)
    else:
        state = utils.call(binary, 'status', silent=True)
    if state:
        parser.error('You have some uncommited changes. Deploy aborted.')

    for filename in ('buildout.cfg', 'deploy.ini'):
        if os.path.isfile(filename):
            break

    if binary == 'git':
        utils.call('git', 'push', 'pytheon', 'master')
    else:
        utils.call('hg', 'push', 'pytheon')

    log.info('Deploy success')


parser = OptionParser()
parser.add_option('-e', '--email', action='store', default=utils.user(),
                  metavar='EMAIL', dest='username',
                  help='E-mail. Default: %s' % utils.user())
parser.add_option('-v', '--version', action='store', default=None,
                  dest='version',
                  help='open a shell for the versioned application')


@with_parser(parser)
@with_project
def shell(parser, options, args, config):
    """Open a ssh shell on pytheon"""
    kw = dict(project_name=global_config.pytheon.project_name)
    utils.call('ssh', '%(project_name)s@pytheon.net' % kw)

parser = OptionParser()
parser.add_option('-e', '--enable', action='store_true', default=False,
                  dest='enable', help='disable maintenance page')
parser.add_option('-d', '--disable', action='store_true', default=False,
                  dest='disable', help='disable maintenance page')


@with_parser(parser)
@with_project
def maintenance(parser, options, args):
    """toggle maintenance page"""
    if options.enable:
        log.info('maintenance page is now enabled')
    elif options.disable:
        log.info('maintenance page is now disabled')
    else:
        parser.parse_args(['-h'])

parser = OptionParser()
parser.add_option('-n', '--name', action='store',
                  dest='name', help='Specify key name')


@with_parser(parser)
def add_key(parser, options, args):
    """Add a public key to pytheon account"""
    if args:
        filename = args[0]
        filename = os.path.expandvars(os.path.expanduser(filename))
        if not os.path.isfile(filename):
            log.error("File %s not found." % filename)
    else:
        filename = os.path.expanduser("~/.ssh/id_rsa.pub")
        if not os.path.isfile(filename):
            filename = os.path.expanduser("~/.ssh/id_dsa.pub")
        if not os.path.isfile(filename):
            parser.error("Default key files ~/.ssh/id_rsa.pub and"
            "~/.ssh/id_dsa.pub were not found. Please specify key filename")
    raw_data = ''
    with open(filename, 'r') as key_file:
        raw_data = key_file.read(30000)
    if not raw_data:
        log.error("Could not read file %s. Please check file permissions"
          % filename)
        return
    if not raw_data.startswith("ssh-"):
        log.error("File %s does not seems to be a public key. "
                  "Please make sure it is not your private key"
                   % filename)
        return
    params = dict(raw_data=raw_data)
    if options.name:
        params.update(dict(name=options.name))
    return http.request('/v1/account/keys', **params)
