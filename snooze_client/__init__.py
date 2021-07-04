'''Allow alerts to be sent to snooze server'''
import click
import requests
import os
import yaml

from  pathlib import Path

class Snooze:
    def __init__(self, server=None):
        '''Create a new connection to snooze server'''
        self.load_config()
        self.server = server or self.config.get('server')
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

    def alert(self, record):
        '''Send a new alert to snooze'''
        requests.post(f"{self.server}/api/alert", json=record)
