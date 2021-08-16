'''Send alerts through CLI'''

import click

from snooze_client.cli.utils import parse_kv

@click.command()
@click.argument('keyvalues', nargs=-1)
def alert(server, keyvalues):
    '''Raise an alert in snooze'''
    record = parse_kv(keyvalues)
    server.alert(record)
