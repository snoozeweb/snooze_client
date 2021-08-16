'''Allow alerts to be sent to snooze server'''
import click
import jwt
import requests
import os
import yaml
import json

from functools import wraps
from  pathlib import Path

from datetime import datetime

from requests.auth import HTTPBasicAuth
from snooze_client.time_constraints import Constraint

CA_BUNDLE_PATHS = [
    '/etc/ssl/certs/ca-certificates.crt', # Debian / Ubuntu / Gentoo
    '/etc/pki/tls/certs/ca-bundle.crt', # RHEL 6
    '/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem', # RHEL 7
    '/etc/ssl/ca-bundle.pem', # OpenSUSE
    '/etc/pki/tls/cacert.pem', # OpenELEC
    '/etc/ssl/cert.pem', # Alpine Linux
]

def ca_bundle():
    '''Returns Linux CA bundle path'''
    if os.environ.get('SSL_CERT_FILE'):
        return os.environ.get('SSL_CERT_FILE')
    elif os.environ.get('REQUESTS_CA_BUNDLE'):
        return os.environ.get('REQUESTS_CA_BUNDLE')
    else:
        for ca_path in CA_BUNDLE_PATHS:
            if Path(ca_path).exists():
                return ca_path

def authenticated(method):
    '''Decorator for methods that require authentication'''
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        '''Wrapper'''
        if not self.token:
            self.login()
        try:
            jwt.decode(self.token, options={'verify_signature': False})
        except jwt.ExpiredSignatureError:
            self.login()
        return method(self, *args, **kwargs)
    return wrapper

class Snooze(object):
    '''An object for connecting to the snooze server'''
    def __init__(self, server=None, app_name='snooze_client', auth_method=None, credentials={}, **kwargs):
        '''Create a new connection to snooze server'''
        self.load_config()
        self.server = server or self.config.get('server')
        self.app_name = app_name
        self.token = None
        self.auth_method = auth_method or self.config.get('auth_method')
        self.credentials = credentials or self.config.get('credentials')
        self.ca = self.config.get('ca_bundle') or ca_bundle()
        if not isinstance(self.server, str):
            raise TypeError("Parameter `server` must be a string representing a URL.")

    def load_config(self):
        '''Fetch configuration from config file if no option is given'''
        config_file = os.environ.get('SNOOZE_CLIENT_CONFIG_FILE', '/etc/snooze/client.yaml')
        path = Path(config_file)
        if path.exists():
            self.config = yaml.safe_load(path.read_text())
        else:
            self.config = {}

    def get_token_from_file(self):
        token_file = os.environ['HOME'] + '.snooze-token'
        if os.path.exists(token_file):
            with open(token_file, 'r') as myfile:
                token = myfile.read()
                return token
        else:
            return None

    def login(self):
        '''
        Authenticate with the `auth_method` and `credentials` arguments.
        '''
        if self.auth_method == 'local' or self.auth_method == 'ldap':
            username = self.credentials.get('username')
            password = self.credentials.get('password')
            auth = HTTPBasicAuth(username, password)
        else:
            raise Exception("Authentication method '{}' not supported".format(self.auth_method))
        response = requests.post(
            '{}/api/login/{}'.format(self.server, self.auth_method),
            verify=self.ca,
            auth=auth,
            headers={'Content-type': 'application/json'},
        )
        if response.json().get('token'):
            self.token = response.json().get('token')
        else:
            raise Exception("Could not get token")

    def alert(self, record):
        '''Send a new alert to snooze'''
        requests.post("{}/api/alert".format(self.server), verify=self.ca, json=record)

    @authenticated
    def record(self, search=[]):
        headers = {}
        headers['Authorization'] = 'JWT ' + self.token
        headers['Content-type'] = 'application/json'
        mysearch = {
            's': json.dumps(search),
        }
        print(mysearch)
        resp = requests.get("{}/api/record".format(self.server), verify=self.ca, headers=headers, params=mysearch)
        resp.raise_for_status()
        return resp.json().get('data')

    @authenticated
    def comment(self, comment_type, user, uid, message):
        headers = {}
        headers['Authorization'] = 'JWT ' + self.token
        headers['Content-type'] = 'application/json'
        mycomment = {
            'record_uid': uid,
            'type': comment_type,
            'message': message,
            'user': user,
            'date': datetime.now().isoformat(),
        }
        print(mycomment)
        resp = requests.post("{}/api/comment".format(self.server), verify=self.ca, headers=headers, json=[mycomment])
        print(resp.content)
        resp.raise_for_status()

    @authenticated
    def snooze(self, name, condition=list, time_constraint={}, comment=None):
        '''Create a snooze'''
        headers = {}
        headers['Authorization'] = 'JWT ' + self.token
        headers['Content-type'] = 'application/json'
        mysnooze = {}
        if not comment:
            comment = "Created by snooze API"
        if isinstance(time_constraint, Constraint):
            time_constraint = time_constraint.to_time_constraint()
        mysnooze = {
            'name': "[{}] {}".format(self.app_name, name),
            'condition': condition,
            'time_constraints': time_constraint,
            'comment': comment,
        }
        print(mysnooze)
        resp = requests.post("{}/api/snooze".format(self.server), verify=self.ca, headers=headers, json=[mysnooze])
        print(resp.content)
        resp.raise_for_status()
