# -*- coding: utf-8 -*-
from testing import *
from webtest import TestApp
from webtest import TestRequest
from webtest import TestResponse
from paste.deploy import loadapp
from sqlalchemy import engine_from_config
from pytheon import utils
from pytheon.main import run
import httplib
import tempfile
import types
import sys
import os

root = os.path.dirname(os.path.dirname(__file__))
api_config = os.path.join(root, '..', 'pytheon.api', 'test.ini')
paster = os.path.join(root, 'bin', 'paster')
post_receive = os.path.join(root, 'bin', 'pytheon-deploy')

class Response(TestResponse):

    def __init__(self, *args, **kwargs):
        self._status = kwargs.pop('status')
        TestResponse.__init__(self, *args, **kwargs)

    @property
    def status(self):
        return self.status_int

    @status.setter
    def set_status(self, value):
        self._status = value

    @property
    def reason(self):
        return self.status

    def read(self):
        return self.body

    def getheaders(self):
        return self._headerlist

    def getheader(self, name, default='text/plain'):
        return self.headers.get(name, default)

class TestCli(TestCase):

    app = None
    email = 'user@example.com'

    def setUp(self):
        TestCase.setUp(self)
        self.wsgi_app = TestApp(loadapp('config:%s' % api_config,
            global_conf={'testing': 'true',
                         'sqlalchemy.url': 'sqlite:///%s' % self.db,
                         #'sqlalchemy.echo': 'true',
                         }))

        class HTTPConnection(object):

            def __init__(conn, *args, **kwargs):
                pass

            def request(conn, method, path, params, headers):
                meth = getattr(self.wsgi_app, method.lower())
                if method.lower() in ('delete',):
                    conn.resp = meth(str(path), headers=headers)
                else:
                    conn.resp = meth(str(path), params=params, headers=headers)

            def getresponse(self):
                return self.resp

        _TestResponse = TestRequest.ResponseClass
        _HTTPConnection = httplib.HTTPConnection
        self.addCleanup(setattr, TestRequest, 'TestResponse', _TestResponse)
        self.addCleanup(setattr, httplib, 'HTTPConnection', _HTTPConnection)

        TestRequest.ResponseClass = Response
        httplib.HTTPConnection = HTTPConnection


    def get_user(self):
        self.engine = engine_from_config({'sqlalchemy.url': 'sqlite:///%s' % self.db})
        return self.engine.execute('select * from users where email=?', self.email)

    def test_cli(self):
        out = run('register', '-e', self.email)
        self.assertIn('check', out.lower())

        u = self.get_user().fetchone()
        out = run('register', '-e', self.email)
        self.assertIn(' is already used', out.lower())

        # avoid prompt
        os.environ['TEST_PASSWORD'] = 'totototo'

        key = '%s/%s' % (u.id, u.register_key)
        out = run('register', '-e', self.email, '-k', key)
        self.assertIn('password set', out.lower())

        # init git server
        gitolite = join(self.home, '.gitolite')
        os.makedirs(gitolite)
        self.writeFile('''
[git]
url = %(repos)s
        ''' % dict(repos=join(self.home, 'repos')),
        gitolite, 'pytheon.ini')

        repo = join(self.home, 'repos', 'test-project.git')
        os.makedirs(repo)
        self.runCommand(['git', 'init', '--bare', repo])
        self.writeFile('''#!/bin/sh
%s --app-name=www --git-url=%s --testing
            ''' % (post_receive, repo),
            repo, 'hooks', 'post-receive')
        self.runCommand(['chmod', '+x', join(repo, 'hooks', 'post-receive')])

        os.environ['PYTHEON_REMOTE'] = join(self.home, 'repos', '%(project_name)s.git')

        # init git config and project repo
        self.runCommand(['git', 'init'])
        self.runCommand(['git', 'config', 'user.name', '"Your Name"'])
        self.runCommand(['git', 'config', 'user.email', 'you@example.com'])
        self.writeFile('''DATABASES = {}; URLS='urls.py''', 'settings.py')
        self.runCommand(['git', 'add', '-A'])
        self.runCommand(['git', 'commit', '-m', 'changes'])

        # create project on pytheon with invalid name
        #out = run('create', '-n', 'test_project')
        #self.assertIn('Applications names must be composed of only letters, '
        #               'digits and hyphens and cannot start with a hyphen', out)

        # create project on pytheon
        out = run('create', '-n', 'test-project')
        self.assertIn('Application test-project created', out)

        # now we can use the cookie
        config = utils.user_config()
        self.assertIn('auth_cookie', config.pytheon)
        del os.environ['TEST_PASSWORD']

        # deploy
        self.runCommand(['git', 'status'])
        run('deploy')

        # api calls
        out = run('apps', '-l')
        self.assertIn('- test-project', out)

        out = run('addons', '--all')
        self.assertIn('- mysql', out)

        out = run('addons', '-l')
        self.assertIn('- No addons', out)

        out = run('addons', '--add', 'mysql:premium')
        self.assertIn('You cannot access this resource', out)

        resp = self.wsgi_app.get('/update_model', dict(model='User', field='email',
                                                       value=self.email, payment_ok='true'))
        out = run('addons', '--add', 'mysql:basic')
        self.assertIn('Addon added', out)

        out = run('addons', '--upgrade', 'mysql:premium')
        self.assertIn('Addon plan changed', out)

        out = run('addons', '--delete', 'mysql')
        self.assertIn('Addon removed', out)

        out = run('addons', '--add', 'mysql:premium')
        self.assertIn('Addon added', out)

        out = run('addons', '-l')
        self.assertIn('- mysql', out)

        out = run('apps', '--delete', 'test-project')
        self.assertIn('Application deleted', out)

        out = run('apps', '-l')
        self.assertIn('- No application', out)

        ## Test ssh keys
        key_file = self.writeFile("ssh-rsa sdfsdfsdf\n",
                                  self.wd, "pytheon-key1")
        key_file2 = self.writeFile("ssh-rsa 2sdfsdfsdf\n",
                                   self.wd, "pytheon-key2")
        key_file3 = self.writeFile("ssh-rsa 3sdfsdfsdf\n",
                                   self.wd, "pytheon-key3")
        key_file4 = self.writeFile("ssh-rsa 4sdfsdfsdf\n",
                                   self.wd, "pytheon-key4")
        fake_key = self.writeFile("fake file\n",
                                   self.wd, "pytheon-fake-key")

        out = run('add_key', fake_key)
        #self.assertIn('File %s does not seems to be a public key.', out)

        out = run('add_key', key_file)
        self.assertIn('Key added', out)
        out = run('add_key', key_file2)
        self.assertIn('Key added', out)
        out = run('add_key', key_file)
        self.assertIn('Key added', out)

        out = run('add_key', '-n',
            'spiderman@withgreatpowercomesgreatresponsibility.com',
            key_file3)
        self.assertIn('Key added', out)
        out = run('add_key', '-n',
            'spiderman@withgreatpowercomesgreatresponsibility.com',
            key_file4)
        self.assertIn('A key with this name already exists', out)

class TestBadArgs(TestCase):

    def test_invalid_command(self):
        self.assertRaises(SystemExit, run, 'toto')

    def test_valid_command_help(self):
        self.assertRaises(SystemExit, run, 'register', '-e')
        self.assertRaises(SystemExit, run, 'register', '-k', 'toto', '-r')

