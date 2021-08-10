'''Allow alerts to be sent to snooze server'''
import click
import requests
import os
import yaml

from  pathlib import Path

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

def fetch_token():
    pass

class Snooze(object):
    '''An object for connecting to the snooze server'''
    def __init__(self, server=None, auth=None, **kwargs):
        '''Create a new connection to snooze server'''
        self.load_config()
        self.server = server or self.config.get('server')
        if not isinstance(self.server, str):
            raise TypeError("Parameter `server` must be a string representing a URL.")
        if auth:
            pass

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
        pass

    def alert(self, record):
        '''Send a new alert to snooze'''
        requests.post("{}/api/alert".format(self.server), verify=ca_bundle(), json=record)

    def snooze(self):
        pass
