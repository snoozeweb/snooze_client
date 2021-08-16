'''Module for CLI implementation of /api/record endpoint'''

import click
import json

from click_option_group import optgroup
from snooze_client.cli.utils import pass_server

def print_records(records):
    for record in records:
        line = "{} {} {} {} {}".format(
            record['timestamp'],
            record['host'],
            record['process'],
            record['severity'],
            record['message'],
        )
        print(line)

@click.command()
@optgroup.group('Record options', help='Options related to the record')
@optgroup.option('-S', '--search', type=str, default='[]', help='The search of the record (as json)')
@pass_server
def record(server, search):
    search = json.loads(search)
    records = server.record(search)
    print_records(records)
