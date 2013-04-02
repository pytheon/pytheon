# -*- coding: utf-8 -*-
import os
import sys
import socket
import logging
import subprocess
from os.path import join
from pytheon.compat import PY3
from pytheon.compat import json
from pytheon.compat import urlopen
from ConfigObject import ConfigObject


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
            return [isinstance(v, dict) and self.__class__(v) or v
                                                        for v in value]
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
    if 'PYTHEON_PREFIX' in os.environ:
        templates_dir = os.path.join(os.environ.get('PYTHEON_PREFIX'),
                                     'etc', 'pytheon', 'templates')
    else:
        templates_dir = None
    if os.path.isdir('/etc/pytheon/templates'):
        templates_dir = '/etc/pytheon/templates'
    elif templates_dir and os.path.isdir(templates_dir):
        pass
    else:
        import pytheon.deploy
        templates_dir = join(os.path.dirname(pytheon.deploy.__file__),
                             'templates')
    path = join(templates_dir, template + '.in')
    if not os.path.isfile(path):
        log.error('missing template %r' % path)
        sys.exit(-1)
    return path


def get_free_port():
    s = socket.socket()
    s.bind(('', 0))
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
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                      close_fds=True)
        p = subprocess.Popen(args, **kwargs)
        p.wait()
        return p.stdout.read()
    elif subprocess.call(args, **kwargs) != 0:
        log.error('error while running command: %s', ' '.join(args))
        sys.exit(1)


def buildout(interpreter, buildout='pytheon.cfg', eggs=None, verbose=None, env={}):
    env = dict(os.environ, **env)

    if interpreter.endswith('python'):
        interpreter = 'python' + sys.version[:3]
    ver = interpreter[-3:]
    prefix = env.get('PYTHEON_PREFIX', os.getcwd())
    buildout_bin = join(prefix, 'bin', 'buildout-%s' % ver)
    if os.path.isfile(buildout_bin):
        call(buildout_bin, '-c', buildout, env=env)
        return

    if not os.path.isfile('pytheon-bootstrap.py'):
        bootstrap_url = 'https://raw.github.com/'
        bootstrap_url += 'buildout/buildout/master/bootstrap/bootstrap.py'
        page = urlopen(bootstrap_url)
        data = page.read()
        if PY3:
            data = str(data)
        open('pytheon-bootstrap.py', 'w').write(data)

    if eggs and os.path.isdir(eggs):
        env['PYTHON_EGGS'] = eggs
        env['PYTHONPATH'] = eggs
        call(
            interpreter,
            'pytheon-bootstrap.py',
            #'--eggs=%s' % eggs,
            '-c', buildout,
            env=env
        )
    else:
        call(
            interpreter,
            'pytheon-bootstrap.py',
            '-c', buildout,
            env=env
        )

    buildout_bin = join(prefix, 'bin', 'buildout')
    args = [buildout_bin, '-c', buildout]
    if verbose:
        args.insert(1, '-vvv')
    args
    call(*args, env=env)


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
        raise RuntimeError(
            'Not a VCS directory. Please run "git init" or "hg init"')


def current_branch():
    return call('git', 'branch', '--no-color', silent=True).strip().strip('* ')


def get_sql_url():
    for key in ('PG_URL', 'MYSQL_URL', 'SQLITE_URL'):
        if key in os.environ:
            return os.environ[key]
    cnf = os.path.expanduser('~/.my.cnf')
    if os.path.isfile(cnf):
        prefix = 'mysql'
    else:
        cnf = os.path.expanduser('~/.pg.cnf')
        if os.path.isfile(cnf):
            prefix = 'postgresql'
    if os.path.isfile(cnf):
        cfg = Config.from_file(cnf)
        client = cfg.client
        client.p = prefix
        if 'pass' not in client:
            client['pass'] = client.password
        if 'host' not in client:
            client.host = '127.0.0.1'
        if 'port' not in client:
            if prefix == 'mysql':
                client.port = '3306'
            else:
                client.port = '5432'
        if 'db' in cfg.pytheon:
            client.db = cfg.pytheon.db
        if 'db' not in client and prefix == 'mysql':
            p = subprocess.Popen(
                'echo "show databases" | mysql -h %(host)s | tail -1' % client,
                shell=True, stdout=subprocess.PIPE)
            db = p.stdout.read().strip()
            if db not in ('Database', 'information_schema'):
                client.db = db
        elif 'db' not in client and prefix == 'postgresql':
            p = subprocess.Popen(
                'psql -l | grep `whoami` | tail -n 1 | cut -d' ' -f2',
                shell=True, stdout=subprocess.PIPE)
            db = p.stdout.read().strip()
            if db not in ('Database', 'information_schema'):
                client.db = db

        try:
            url = '%(p)s://%(user)s:%(pass)s@%(host)s:%(port)s/%(db)s' % client
        except KeyError:
            log.error('Can not determine a valid url from %s' % cnf)
        else:
            log.info(
               'Using %(p)s://%(user)s:XXXs@%(host)s:%(port)s/%(db)s' % client)
            if prefix == 'mysql':
                os.environ['MYSQL_URL'] = url
            else:
                os.environ['PG_URL'] = url
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


def engine_dict():
    engine = engine_from_config({})
    url = engine.url
    return dict(
        database=url.database,
        drivername=url.drivername,
        username=url.username,
        password=url.password,
        host=url.host,
      )


def backup_db(backup_dir, dry_run=False):
    from datetime import datetime
    now = datetime.now().strftime('%Y%m%d%H%M')
    data = engine_dict()
    filename = '%(database)s-%(now)s.sql.gz' % dict(data, now=now)
    data['filename'] = os.path.join(
            realpath(os.path.expanduser('~'), 'backups', 'sql'),
            filename)
    if data.get('drivername') == 'mysql':
        log.info('Backuping to %(filename)s', data)
        cmd = ('mysqldump --add-drop-table %(database)s '
               '-u %(username)s -p%(password)s '
               '-h %(host)s | gzip > %(filename)s') % data
        subprocess.call(cmd, shell=True)
    elif data.get('drivername').startswith('postgresql'):
        log.info('Backuping to %(filename)s', data)
        cmd = ('pg_dump -c -w -U %(username)s '
               '%(database)s | gzip > %(filename)s') % data
        subprocess.call(cmd, shell=True)
