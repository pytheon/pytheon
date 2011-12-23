# -*- coding: utf-8 -*-
import sys

PY3 = sys.version_info[0] == 3

try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

try:
    import json
except ImportError:
    import simplejson as json
