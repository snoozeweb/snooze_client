'''Allow alerts to be sent to snooze server'''
import click
import jwt
import requests
import os
import yaml
import json
import socket
import logging
import sys
import functools

from functools import wraps
from  pathlib import Path

from datetime import datetime

from filelock import FileLock
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

log = logging.getLogger('snooze_client')
log.setLevel(logging.INFO)
log.addHandler(logging.StreamHandler(sys.stderr))

if 'SNOOZE_TOKEN_PATH' in os.environ:
    TOKEN_FILE = os.environ['SNOOZE_TOKEN_PATH']
elif 'PWD' in os.environ:
    TOKEN_FILE = os.environ['PWD'] + '/.snooze-token'
elif 'HOME' in os.environ:
    TOKEN_FILE = os.environ['HOME'] + '/.snooze-token'
else:
    TOKEN_FILE = None

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
        except jwt.DecodeError:
            log.warn("Invalid JWT token found at %s. Discarding.", TOKEN_FILE)
            self.login()
        return method(self, *args, **kwargs)
    return wrapper

def get_token():
    '''Attempt to get token from disk'''
    try:
        if TOKEN_FILE:
            with open(TOKEN_FILE, 'r') as f:
                token = f.read()
            return token
        else:
            return None
    except:
        return None

def set_token(token):
    '''Write token to disk'''
    if TOKEN_FILE:
        with FileLock(TOKEN_FILE + '.lock'):
            myfile = os.open(TOKEN_FILE, os.O_CREAT | os.O_WRONLY, 0o600)
            with open(myfile, 'w+') as f:
                f.write(token)

def merge_responses(responses):
    '''Merge API responses'''
    return {'data': functools.reduce(lambda a, b: {k: a.get('data', {}).get(k, []) + b.get('data', {}).get(k, []) for k in list(dict.fromkeys(list(a.get('data', {}).keys()) + list(b.get('data', {}).keys())))}, responses)}

def get_chunks(lst, n):
    '''Split list into chunks of equal size'''
    return [lst[i:i + n] for i in range(0, len(lst), n)]

class Snooze(object):
    '''An object for connecting to the snooze server'''
    def __init__(
            self,
            server=None,
            app_name='snooze_client',
            auth_method=None,
            credentials={},
            token_to_disk=False,
            ca=None,
            timeout=5,
            **kwargs
        ):
        '''
        Create a new connection to snooze server.
        Note: All parameters can be precised in the configuration file at /etc/snooze/client.yaml.
        The configuration file can be overridden with the `SNOOZE_CLIENT_CONFIG_FILE` environment variable.

        Parameters:
        -----------
        server: str
            URI of the snooze server. Example: https://snooze.example.com:5200
        app_name: str
            Name of the client. Used in some endpoint to prepend the name of the entry with client information.
        auth_method: str
            Name of the authentication method. Supported values: local, ldap.
        credentials: dict
            A dictionary of values required by the auth_method.
            Required values for local and ldap: `username`, `password`.
        token_to_disk: bool
            If enabled, will flush the token retreived after authentication to disk.
        ca_bundle: str
            Path to the CA bundle to use for the TLS connection. Will default to the system
            CA bundle if not precised (will not use requests custom CA bundle).
        timeout: float
            Timeout in seconds for each request.
        Returns
        -------
        Snooze
            A snooze server object. Call its method to execute API calls to snooze server.
        '''
        self.load_config()
        self.server = server or self.config.get('server')
        self.app_name = app_name or self.config.get('app_name') or 'snooze_client'
        self.auth_method = auth_method or self.config.get('auth_method', 'local')
        self.credentials = credentials or self.config.get('credentials')
        self.ca = ca or self.config.get('ca_bundle') or ca_bundle()
        if token_to_disk is not None:
            self.token_to_disk = token_to_disk
        else:
            self.token_to_disk = self.config.get('token_to_disk')
        self.timeout = timeout or self.config.get('timeout')
        if not isinstance(self.server, str):
            raise TypeError("Parameter `server` must be a string representing a URL.")
        self.token = get_token()
        try:
            self.auth_payload = jwt.decode(self.token, options={'verify_signature': False})
        except Exception:
            self.auth_payload = None

    def load_config(self):
        '''Fetch configuration from config file if no option is given'''
        config_file = os.environ.get('SNOOZE_CLIENT_CONFIG_FILE', '/etc/snooze/client.yaml')
        path = Path(config_file)
        if path.exists():
            self.config = yaml.safe_load(path.read_text())
        else:
            self.config = {}

    def login(self):
        '''
        Authenticate with the `auth_method` and `credentials` arguments.
        Will set the token attribute of the class if successful.

        Raises:
            AttributeError: Will be raised when the `auth_method` attribute
                is not supported.
            HTTPError: Will be raised if the server answer with something different
                from OK 200.
            Exception: Will be raised if there is no `token` key in the result dictionary.
        '''
        if self.auth_method == 'local' or self.auth_method == 'ldap':
            username = self.credentials.get('username')
            password = self.credentials.get('password')
            auth = HTTPBasicAuth(username, password)
        else:
            raise AttributeError("Authentication method '%s' not supported" % self.auth_method)
        response = requests.post(
            '{}/api/login/{}'.format(self.server, self.auth_method),
            verify=self.ca,
            auth=auth,
            headers={'Content-type': 'application/json'},
            timeout=self.timeout,
        )
        response.raise_for_status()
        if response.json().get('token'):
            self.token = response.json().get('token')
            if self.token_to_disk:
                set_token(self.token)
        else:
            raise Exception("Could not get token")

    def alert_with_defaults(self, record):
        '''Send an alert to snooze, but provide useful defaults based on OS context'''
        if 'host' not in record:
            host = socket.gethostname()
            if '.' in host:
                record['host'], record['domain'] = host.split('.', 2)
            else:
                record['host'] = host
        if 'timestamp' not in record:
            record['timestamp'] = datetime.now().astimezone().isoformat()
        if 'source' not in record:
            record['source'] = 'snooze_client'
        if 'process' not in record:
            record['process'] = self.app_name

        # Send the record normally
        self.alert(record)

    def alert(self, record):
        '''
        Send a new alert to snooze.

        Args:
            record (dict): The alert to send to snooze, in dictionary format.
        '''
        resp = requests.post("{}/api/alert".format(self.server), verify=self.ca, json=record, timeout=self.timeout)
        resp.raise_for_status()

    @authenticated
    def record(self, search=None, ql=None):
        '''
        Return a list of records matching the search.
        If `search` or `ql` is not precised, the default search will be `[]` (everything).

        Args:
            search (list): A list representing the search. Example: ["=", "host", "myhost01"]
            ql (str): A snooze query language string. It will be translated by the server into a
                search (list). Useful for human interfaces.
        Returns:
            list: List of dictionaries representing the records matching the search
        '''
        headers = {}
        headers['Authorization'] = 'JWT ' + self.token
        headers['Content-type'] = 'application/json'
        if search:
            params = {
                's': json.dumps(search),
            }
        elif ql:
            params = {
                'ql': ql,
            }
        else:
            params = {
                's': [],
            }
        resp = requests.get("{}/api/record".format(self.server), verify=self.ca, headers=headers, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json().get('data')

    @authenticated
    def comment(self, comment_type, user_name, user_method, uid, message, modifications=None):
        '''
        Write a comment on a record.

        Args:
            comment_type(str): The type of the comment.
                Supported values: `ack`, `close`, `open`, `esc`, `` (for comment).
            user_name (str): The name of the user to comment with.
            user_method (str): The method associated with the user.
                Supported values: `local`, `ldap` (same as `auth_method`).
            uid (str): UID of the record.
            message (str): Content of the comment.
            modifications (list): An array of modification to send to the record. Used for re-escalations.
        '''
        headers = {}
        headers['Authorization'] = 'JWT ' + self.token
        headers['Content-type'] = 'application/json'
        mycomment = {
            'record_uid': uid,
            'type': comment_type,
            'message': message,
            'name': user_name,
            'method': user_method,
            'date': datetime.now().isoformat(),
        }
        if modifications:
            mycomment['modifications'] = modifications
        resp = requests.post("{}/api/comment".format(self.server), verify=self.ca, headers=headers, json=[mycomment], timeout=self.timeout)
        resp.raise_for_status()
        return resp.json().get('data')


    @authenticated
    def comment_batch(self, comments):
        '''
        Write multiple comments.

        Args:
			comments(dict, list): Comments to write
        '''
        headers = {}
        headers['Authorization'] = 'JWT ' + self.token
        headers['Content-type'] = 'application/json'
        mycomments = []
        if not isinstance(comments, list):
            comments = [comments]
        for comment in comments:
            mycomment = {
                'record_uid': comment['record_uid'],
                'type': comment.get('type', 'comment'),
                'message': comment.get('message', ''),
                'name': comment.get('name', 'Anonymous'),
                'method': comment.get('method', 'local'),
                'date': datetime.now().isoformat(),
				'modifications': comment.get('modifications', []),
            }
            mycomments.append(mycomment)
        responses = []
        for comment_block in get_chunks(mycomments, 10):
            resp = requests.post("{}/api/comment".format(self.server), verify=self.ca, headers=headers, json=comment_block, timeout=self.timeout)
            resp.raise_for_status()
            responses.append(resp.json())
        return merge_responses(responses).get('data')

    @authenticated
    def snooze(self, name, condition=None, ql=None, time_constraint={}, comment=None):
        '''
        Create a snooze entry.

        Args:
            name (str): Name of the snooze entry.
            condition (list): Condition for which this snooze entry will match.
                Example: ["=", "host", "myhost01"]
            time_constraint (Constraint or dict): The time constraint of the snooze entry. Can be
                expressed using objects from the `snooze_client.time_constraints` module, or a
                dictionary.
            comment (str): A comment associated with the snooze entry.
        '''
        headers = {}
        headers['Authorization'] = 'JWT ' + self.token
        headers['Content-type'] = 'application/json'
        if not comment:
            comment = "Created by snooze API"
        if isinstance(time_constraint, Constraint):
            time_constraint = time_constraint.to_time_constraint()
        params = {
            'name': "[{}] {}".format(self.app_name, name),
            'time_constraints': time_constraint,
            'comment': comment,
        }
        if condition:
            params['condition'] = condition
        elif ql:
            params['qls'] = [{'ql': ql, 'field': 'condition'}]
        else:
            params['condition'] = []
        resp = requests.post("{}/api/snooze".format(self.server), verify=self.ca, headers=headers, json=[params], timeout=self.timeout)
        resp.raise_for_status()
        return resp.json().get('data')

    @authenticated
    def snooze_batch(self, filters):
        '''
        Create a snooze entry.

        Args:
			snoozes(dict, list): Snooze filters to write
        '''
        headers = {}
        headers['Authorization'] = 'JWT ' + self.token
        headers['Content-type'] = 'application/json'
        if not isinstance(filters, list):
            filters = [filters]
        myfilters = []
        for f in filters:
            time_constraints = f.get('time_constraints', [])
            if isinstance(time_constraints, Constraint):
                time_constraints = time_constraints.to_time_constraint()
            myfilter = {
                'name': "[{}] {}".format(self.app_name, f['name']),
                'time_constraints': time_constraints,
                'comment': f.get('comment', "Created by snooze API"),
            }
            if f.get('condition'):
                myfilter['condition'] = f['condition']
            elif f.get('ql'):
                myfilter['qls'] = [{'ql': f['ql'], 'field': 'condition'}]
            else:
                myfilter['condition'] = []
            myfilters.append(myfilter)
        responses = []
        for filter_block in get_chunks(myfilters, 10):
            resp = requests.post("{}/api/snooze".format(self.server), verify=self.ca, headers=headers, json=filter_block, timeout=self.timeout)
            resp.raise_for_status()
            responses.append(resp.json())
        return merge_responses(responses).get('data')
