'''CLI for snooze client'''

import click

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

@snooze.command()
@add_options(COMMON_OPTIONS)
@click.argument('keyvalues', nargs=-1)
def alert(server, keyvalues):
    client = Snooze(server)
    record = {}
    for keyvalue in keyvalues:
        if '=' not in keyvalue:
            raise ValueError("Options must be of format key=value")
        key, value = keyvalue.split('=', 2)
        record[key] = value
    client.alert(record)
