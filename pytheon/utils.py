# -*- coding: utf-8 -*-
import os
import sys
import socket
import urllib
import logging
import subprocess
from os.path import join
from ConfigObject import ConfigObject

try:
    import json
except ImportError:
    import simplejson as json

log = logging.getLogger('Pytheon')

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
    if os.path.isdir('/etc/pytheon/templates'):
        templates_dir = '/etc/pytheon/templates'
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
    buildout_bin = '/var/share/pytheon/bin/buildout-%s' % ver
    if os.path.isfile(buildout_bin):
        call(buildout_bin, '-c', buildout, env=env)
        return

    if not os.path.isfile('pytheon-bootstrap.py'):
        page = urllib.urlopen(
         'http://svn.zope.org/*checkout*/zc.buildout/trunk/bootstrap/bootstrap.py')
        open('pytheon-bootstrap.py', 'w').write(page.read())
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
    call('bin/buildout', '-c', buildout, env=env)

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

