# -*- coding: utf-8 -*-
import logging
import httplib
import ssl
import sys
import base64
import socket
import os.path
from urllib import urlencode
from datetime import datetime, timedelta
from Cookie import SimpleCookie
from pytheon import utils
from pytheon.utils import json
from pytheon.ssl_match_hostname import match_hostname, CertificateError

log = logging.getLogger(__name__)

try:
    import keyring
except ImportError:
    keyring = None

ca_certs = utils.join(os.path.dirname(__file__), 'pytheon.pem')


class HTTPSConnection(httplib.HTTPSConnection):
    """HTTPSConnection that performs certficate validation :
       - Checks that the server certficate was signed by one of
         the authorities whose certfication
       - Checks that the server hostname is the same as the certificate
         common name it provided"""
    def __init__(self, host, ca_certs, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                 ssl_version=ssl.PROTOCOL_SSLv3):
        """Constructor.
           Args :
            ca_certs: Path to the file which contains concatenated certificates
                      of the authorities your trust in PEM format.
           ssl_version: SSL protocol version you want to support.
                        Defaults to TLSv1 only."""
        httplib.HTTPSConnection.__init__(self, host, port=443, timeout=timeout)
        self.ca_certs = ca_certs
        self.ssl_version = ssl_version

    def connect(self):
        """Connects to the specified host.
        Exceptions :
            Raises SSLError if the server certificate was not signed by
                an authority whose certificate is in ca_certs.
            Raises CertificateError if the server hostname does not match
                the certificate common name.
        """
        sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock = ssl.wrap_socket(sock, ssl_version=self.ssl_version,
            cert_reqs=ssl.CERT_REQUIRED, ca_certs=self.ca_certs)
        match_hostname(self.sock.getpeercert(), self.host)

def auth_basic(retry=False):
    config = utils.user_config()
    username = config.pytheon.username or utils.get_input('Username')
    password = None
    if keyring:
        log.debug('Use keyring module. Great!')
        password = keyring.get_password('basic:api.pytheon.net', username)
    if password == None or retry:
        password = utils.get_input('Password', password=True)
    if keyring:
        keyring.set_password('basic:api.pytheon.net', username, password)
    auth = base64.encodestring('%s:%s' % (username, password))
    return {'Authorization' : 'Basic ' + auth.strip()}

def auth_cookie():
    config = utils.user_config()
    if keyring:
        log.debug('Use keyring module. Great!')
        cookie = keyring.get_password('cookie:api.pytheon.net', config.pytheon.username)
    else:
        config = utils.user_config()
        cookie = config.pytheon.auth_cookie or None
    if cookie is not None:
        return {'Cookie' : 'auth_tkt=%s' % cookie}
    return None

def save_cookie(headers):
    config = utils.user_config()
    for k,v in headers:
        if k.lower() == 'set-cookie':
            cookie = SimpleCookie(v)
            auth_cookie = cookie['auth_tkt'].value
            log.debug('Cookie: %s', auth_cookie)
            if keyring:
                keyring.set_password('cookie:api.pytheon.net', config.pytheon.username, auth_cookie)
            else:
                config.pytheon.auth_cookie = auth_cookie
                config.write()

def request(path, method='GET', auth=True, host=None, json=False, **params):
    config = utils.user_config()
    headers = {}

    if params:
        method = 'POST'
        params = urlencode(params)
        headers['Content-Type'] = "application/x-www-form-urlencoded"
    else:
        params = None

    if json:
        headers['Accept'] = 'application/json'
    else:
        headers['Accept'] = 'text/plain'

    if auth:
        cookie_auth = auth_cookie()
        if cookie_auth is not None:
            log.debug('Use cookie: %s' % cookie_auth)
            headers.update(cookie_auth)
        else:
            log.debug('Use auth basic')
            headers.update(auth_basic())

    def get_conn(host):
        host, port = host.split(':')
        port = int(port)
        if port == 443:
            ## This HTTPSConnection *REQUIRES* a file containing concatenated
            ## PEM certificates of the authorities you trust. This means you
            ## *HAVE TO* bundle certificates with your application
            ## (as firefox does).
            ##
            ## If you are running on a debian/ubuntu system,
            ## mozilla certificates are located in
            ## /usr/share/ca-certificates/mozilla/ .You can concatenate
            ## them with the command :
            ## for cert in /usr/share/ca-certificates/mozilla/*crt; \
            ##      do cat $cert >> mozcerts.pem; done
            ##
            ## You may want to bundle *only* your server certificate/your ca
            ## certificate with your application to make it more secure.
            conn = HTTPSConnection(host, ca_certs)
        else:
            conn = httplib.HTTPConnection(host, port)
        return conn

    host = host or config.pytheon.api_host or 'api.pytheon.net:443'
    try:
        conn = get_conn(host)
        conn.request(method, path, params, headers)
        resp = conn.getresponse()
    except socket.error:
        raise
        raise OSError('Unable to contact %s' % host)

    if resp.status == 401 and cookie_auth is not None:
        log.info('Invalid password or session is expired')
        headers.update(auth_basic(retry=True))
        del headers['Cookie']
        conn = get_conn(host)
        conn.request(method, path, params, headers)
        resp = conn.getresponse()

    data = resp.read()
    if resp.status != 200:
        log.error("%d - %s " % (resp.status, resp.reason))
        if resp.status == 500:
            sys.exit(1)

    save_cookie(resp.getheaders())
    if resp.getheader('Content-Type', 'text/plain') == 'application/json':
        return json.loads(data)
    return data
