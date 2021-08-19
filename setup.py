'''Setup module'''

from setuptools import setup, find_packages

setup(
    name="snooze-client",
    version='1.0.9',
    author='Guillaume Ludinard, Florian Dematraz',
    author_email='guillaume.ludi@gmail.com, ',
    description="Client library for snooze server",
    long_description_content_type="text/markdown",
    url='https://github.com/snoozeweb/snooze_client',
    packages=find_packages(include=['snooze_client', 'snooze_client.*']),
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
    ],
    entry_points={
        'console_scripts': [
            'snooze_client = snooze_client.cli:snoozegroup',
            'snooze_wrap = snooze_client.cli:snooze_wrap',
        ],
    },
    install_requires=[
        'PyYAML',
        'click',
        'pathlib',
        'requests',
    ],
)
