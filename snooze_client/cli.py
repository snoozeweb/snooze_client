'''CLI for snooze client'''

import click
import subprocess
import socket

from subprocess import CalledProcessError, TimeoutExpired, Popen, PIPE

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

def wrap_error(server, cmd, stdout, stderr, message, severity='err', timeout=None, exit_code=None):
    print("Error: The command {} failed".format(cmd))
    snooze = Snooze(server)
    record = {}
    record['source'] = 'wrap'
    record['wrap_cmd'] = ' '.join(cmd)
    record['process'] = cmd[0]
    host = socket.gethostname()
    if '.' in host:
        record['fqdn'] = host
        record['host'] = host.split('.', 1)[0]
    else:
        record['host'] = host
    if exit_code:
        record['wrap_exitcode'] = exit_code
    record['wrap_stdout'] = stdout.decode()
    record['wrap_stderr'] = stderr.decode()
    if timeout:
        record['wrap_timeout'] = timeout
    record['severity'] = severity
    record['message'] = message
    print("Sending alert: {}".format(record))
    snooze.alert(record)

@click.command()
@add_options(COMMON_OPTIONS)
@click.option('--timeout', '-t', type=int, help='Timeout for the command that is run')
@click.option('--ok', '-o', type=int, multiple=True, default=[0], help='Exit code that are considered valid (that should not send an alert).')
@click.option('--warning', '-w', type=int, multiple=True, default=[], help='Exit code that should return a warning alert')
@click.option('--critical', '-c', type=int, multiple=True, default=[], help='Exit code that should return a critical alert')
@click.option('--fatal', '-f', type=int, multiple=True, default=[], help='Exit code that should return a fatal alert')
@click.option('--sh', '-S', default=None, help='Execute the command in a shell if present')
@click.argument('cmd', nargs=-1)
def snooze_wrap(server, timeout, ok, critical, warning, fatal, cmd, sh):
    '''
    Wrap a command to send a snooze notification if it fails (non-zero exit code).
    Useful for cronjobs.
    '''
    options = {
        'timeout': timeout,
        'shell': sh,
    }
    try:
        cmd = list(cmd)
        process = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate(**options)
        exit_code = process.returncode
        if exit_code in ok:
            print("Command {} executed successfully (exit {})".format(cmd, exit_code))
        else:
            if exit_code in warning:
                severity = 'warning'
            elif exit_code in critical:
                severity = 'critical'
            elif exit_code in fatal:
                severity = 'fatal'
            else:
                severity = 'err'
            message = "Command {} failed with exit {} ({})".format(cmd, exit_code, severity)
            wrap_error(server, cmd, stdout, stderr, message, severity, exit_code=exit_code) 
    except TimeoutExpired as err:
        process.kill()
        stdout, stderr = process.communicate()
        message = "Command {} timed out after {}s".format(cmd, timeout)
        wrap_error(server, cmd, stdout, stderr, message, timeout=timeout)
