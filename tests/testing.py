# -*- coding: utf-8 -*-
from pytheon import models
import unittest2 as unittest
from os.path import join
from time import sleep
import subprocess
import tempfile
import shutil
import os

skipIf = unittest.skipIf

class TestCase(unittest.TestCase):

    app = 'wsgiapp'

    def setUp(self):
        self.curdir = os.getcwd()
        self.wd = tempfile.mkdtemp(prefix='pytheon-wd-')
        self.addCleanup(shutil.rmtree, self.wd)
        if os.path.isdir(self.wd):
            shutil.rmtree(self.wd)
        os.makedirs(self.wd)

        if 'PYTHEON_EGGS_DIR' not in os.environ:
            os.environ['PYTHEON_EGGS_DIR'] = os.path.expanduser('~/eggs')
        self.home = tempfile.mkdtemp(prefix='pytheon-home-')
        self.addCleanup(shutil.rmtree, self.home)
        if os.path.isdir(self.home):
            shutil.rmtree(self.home)
        os.makedirs(self.home)
        os.environ['HOME'] = self.home
        self.writeFile('''
[pytheon]
api_host = localshost:6543

''', self.home, '.pytheonrc')

        self.db = join(self.home, 'pytheon.db')
        if os.path.isfile(self.db):
            os.remove(self.db)

        os.chdir(self.wd)
        self.addCleanup(os.chdir, self.curdir)

    def assertIsFile(self, *args):
        filename = os.path.join(self.wd, *args)
        if not os.path.isdir(filename):
            assert os.path.isfile(filename), os.listdir(os.path.dirname(filename))
        return filename

    def assertIsDir(self, *args):
        dirname = os.path.join(self.wd, *args)
        if not os.path.isdir(dirname):
            assert os.path.isdir(dirname), os.listdir(os.path.dirname(dirname))
        return dirname

    def assertNotIsDir(self, *args):
        dirname = os.path.join(self.wd, *args)
        assert not os.path.isdir(dirname), os.listdir(dirname)
        return dirname

    def writeFile(self, text, *args):
        filename = os.path.join(*args)
        fd = open(filename, 'w')
        fd.write(text)
        name = fd.name
        fd.close()
        return name

    def runCommand(self, cmd):
        self.assertEqual(subprocess.call(cmd), 0)

    def cat(self, *args):
        filename = join(*args)
        name = os.path.basename(filename)
        print '='*len(name)
        print name
        print '='*len(name)
        print open(filename).read().strip()
        print '='*len(name)
        print ''

    def cat_files(self):
        self.cat(self.app, 'pytheon.cfg')

        bin_dir = self.assertIsDir(self.app, 'bin')
        log_dir = self.assertIsDir('var', 'log')
        etc_dir = self.assertIsDir('etc')

        self.cat(etc_dir, 'deploy.ini')
        self.cat(etc_dir, 'supervisor.conf')
        self.cat(self.app, 'bin', 'pytheon-serve')
        self.cat(etc_dir, 'versions.cfg')

