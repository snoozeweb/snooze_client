'''CLI for snooze client'''

import click
import subprocess
import socket

from subprocess import CalledProcessError, TimeoutExpired

from snooze_client import Snooze

COMMON_OPTIONS = [
    click.option('--server', '-s', help='URI of the Snooze server'),
]

def add_options(options):
    def callback(func):
        for option in reversed(options):
            func = option(func)
        return func
    return callback

@click.group()
def snooze():
    pass

def parse_arguments(keyvalues):
    '''Parse arguments to make a record'''
    record = {}
    for keyvalue in keyvalues:
        if '=' not in keyvalue:
            raise ValueError("Options must be of format key=value")
        key, value = keyvalue.split('=', 1)
        record[key] = value
    return record

@snooze.command()
@add_options(COMMON_OPTIONS)
@click.argument('keyvalues', nargs=-1)
def alert(server, keyvalues):
    '''Raise an alert in snooze'''
    client = Snooze(server)
    record = parse_arguments(keyvalues)
    client.alert(record)
def wrap_error(server, err):
    snooze = Snooze(server)
    record = {}
    record['source'] = 'wrap'
    record['wrap_cmd'] = ' '.join(err.cmd)
    record['process'] = err.cmd[0]
    host = socket.gethostname()
    if '.' in host:
        record['fqdn'] = host
        record['host'] = host.split('.', 1)[0]
    else:
        record['host'] = host
    record['wrap_exitcode'] = err.returncode
    record['wrap_stdout'] = err.stdout
    record['wrap_stderr'] = err.stderr
    if hasattr(err, 'timeout'):
        record['wrap_timeout'] = err.timeout
    record['message'] = err.message
    snooze.alert(record)

@click.command()
@add_options(COMMON_OPTIONS)
@click.option('--timeout', '-t', help='Timeout for the command that is run')
@click.argument('cmd', nargs=-1)
def snooze_wrap(server, timeout, cmd):
    '''
    Wrap a command to send a snooze notification if it fails (non-zero exit code).
    Useful for cronjobs.
    '''
    options = {
        'timeout': timeout,
    }
    try:
        result = subprocess.run(cmd, **options)
    except (CalledProcessError, TimeoutExpired) as err:
        wrap_error(server, err)
