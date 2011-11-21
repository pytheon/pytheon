# -*- coding: utf-8 -*-
import os
import sys
import socket
import logging
import subprocess
from os.path import join
try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen
from ConfigObject import ConfigObject

try:
    import json
except ImportError:
    import simplejson as json

log = logging.getLogger('Pytheon')

PY3 = sys.version_info[0] == 3

class JSON(dict):
    """an advanced dict to allow easy manipulation of JSON objects"""

    def __init__(self, value):
        if value:
            if isinstance(value, basestring):
                value = json.loads(value)
            dict.__init__(self, value)

    def __getattr__(self, attr):
        value = self.get(attr)
        if value is None:
            return None
        elif isinstance(value, dict):
            return self.__class__(value)
        elif isinstance(value, (list, tuple)):
            return [isinstance(v, dict) and self.__class__(v) or v for v in value]
        return value

    def __str__(self):
        return json.dumps(self)

class Config(ConfigObject):

    filename = None

    def write(self, path_or_fd=None):
        if path_or_fd is None and self._filename:
            path_or_fd = self._filename
        if isinstance(path_or_fd, basestring):
            fd = open(path_or_fd, 'w')
        else:
            fd = path_or_fd
        ConfigObject.write(self, fd)
        if isinstance(path_or_fd, basestring):
            fd.close()

    @classmethod
    def from_file(cls, filename, **kwargs):
        config = cls(defaults=kwargs)
        config.read(filename)
        config._filename = filename
        return config

    @classmethod
    def from_template(cls, template, **kwargs):
        config = cls(defaults=kwargs)
        config.read(template_path(template))
        return config

def user_config():
    filename = os.path.expanduser('~/.pytheonrc')
    return Config.from_file(filename)

def user():
    return user_config().pytheon.username or ''

def project_config(filename=None):
    if not filename:
        for filename in ('buildout.cfg', 'deploy.ini'):
            if os.path.isfile(filename):
                break
    return Config.from_file(filename)

def template_path(template):
    templates_dir = os.path.join(os.environ.get('PYTHEON_PREFIX'),
                                 'etc', 'pytheon', 'templates')
    print templates_dir
    if os.path.isdir('/etc/pytheon/templates'):
        templates_dir = '/etc/pytheon/templates'
    elif os.path.isdir(templates_dir):
        pass
    else:
        import pytheon.deploy
        templates_dir = join(os.path.dirname(pytheon.deploy.__file__), 'templates')
    path = join(templates_dir, template + '.in')
    if not os.path.isfile(path):
        log.error('missing template %r' % path)
        sys.exit(-1)
    return path

def get_free_port():
    s = socket.socket()
    s.bind(('',0))
    ip, port = s.getsockname()
    s.close()
    log.warn('use a new TCP port: %s' % port)
    return port

def realpath(*args):
    dirname = os.path.realpath(join(*args))
    if not os.path.isdir(dirname) and dirname[-4] != '.':
        os.makedirs(dirname)
    return dirname

def call(*args, **kwargs):
    if 'silent' in kwargs:
        del kwargs['silent']
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        p = subprocess.Popen(args, **kwargs)
        p.wait()
        return p.stdout.read()
    elif subprocess.call(args, **kwargs) != 0:
        log.error('error while running command: %s',' '.join(args))
        sys.exit(1)

def buildout(interpreter, buildout='pytheon.cfg', eggs=None, env={}):
    env = dict(os.environ, **env)

    ver = interpreter[-3:]
    prefix = env.get('PYTHEON_PREFIX', os.getcwd())
    buildout_bin = join(prefix, 'bin', 'buildout-%s' % ver)
    if os.path.isfile(buildout_bin):
        call(buildout_bin, '-c', buildout, env=env)
        return

    if not os.path.isfile('pytheon-bootstrap.py'):
        if ver[0] == '3':
            bootstrap_url = 'http://svn.zope.org/*checkout*/zc.buildout/branches/2/bootstrap/bootstrap.py'
        else:
            bootstrap_url = 'http://svn.zope.org/*checkout*/zc.buildout/trunk/bootstrap/bootstrap.py'
        page = urlopen(bootstrap_url)
        data = page.read()
        if PY3:
            data = str(data)
        open('pytheon-bootstrap.py', 'w').write(data)
    if eggs and os.path.isdir(eggs):
        env['PYTHON_EGGS'] = eggs
        env['PYTHONPATH'] = eggs
        call(interpreter, 'pytheon-bootstrap.py',
                       '--distribute',
                       '--eggs=%s' % eggs,
                       '-c', buildout,
                       env=env)
    else:
        call(interpreter, 'pytheon-bootstrap.py', '--distribute', '-c', buildout, env=env)

    buildout_bin = join(prefix, 'bin', 'buildout')
    call(buildout_bin, '-c', buildout, env=env)


def get_input(prompt='', default=None, password=None):
    if password:
        if 'TEST_PASSWORD' in os.environ:
            return os.environ['TEST_PASSWORD']
        import getpass
        value = None
        while not value:
            value = getpass.getpass()
        return value
    if default:
        prompt += ' [%s]: ' % default
    else:
        prompt += ': '
    value = None
    while not value:
        value = raw_input(prompt)
        if not value and default:
            return default
        elif value:
            return value

def vcs_binary():
    if os.path.isdir('.git'):
        return 'git'
    elif os.path.isdir('.hg'):
        return 'hg'
    else:
        raise RuntimeError('Not a VCS directory. Please run "git init" or "hg init"')

def current_branch():
    return call('git', 'branch', '--no-color', silent=True).strip().strip('* ')

def get_sql_url():
    for key in ('PQ_URL', 'MYSQL_URL', 'SQLITE_URL'):
        if key in os.environ:
            return os.environ[key]
    my_cnf = os.path.expanduser('~/.my.cnf')
    if os.path.isfile(my_cnf):
        cfg = Config.from_file(my_cnf).client
        if 'host' not in cfg:
            cfg.host = '127.0.0.1'
        if 'port' not in cfg:
            cfg.port = '3306'
        if 'db' not in cfg:
            p = subprocess.Popen('echo "show databases" | mysql | tail -1',
                                 shell=True, stdout=subprocess.PIPE)
            db = p.stdout.read().strip()
            if db not in ('Database', 'information_schema'):
                cfg.db = db
        try:
            url = 'mysql://%(user)s:%(pass)s@%(host)s:%(port)s/%(db)s' % cfg
        except KeyError:
            pass
        os.environ['MYSQL_URL'] = url
        return url

def engine_from_config(config, **params):
    sql_url = get_sql_url()
    prefix = params.get('prefix', 'sqlalchemy.')
    if sql_url:
        config['%surl' % prefix] = sql_url
    if config:
        import sqlalchemy
        return sqlalchemy.engine_from_config(config, **params)
    raise RuntimeError('SQLAlchemy configuration dict is empty')
