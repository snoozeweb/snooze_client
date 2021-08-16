'''Login'''

import click

from snooze_client.cli import snoozegroup

@snoozegroup.command()
@click.option('--auth-method', '-A', type=click.Choice(['local', 'ldap', 'jwt']), help='Authentication method to use.')
def login(server):
    pass
