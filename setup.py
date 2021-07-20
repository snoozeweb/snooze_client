from setuptools import setup, find_packages

url = "https://github.com/Nemega/snooze"
setup(
    name="snooze-client",
    version='1.0.3',
    author='Guillaume Ludinard, Florian Dematraz',
    author_email='guillaume.ludi@gmail.com, ',
    description="Client library for snooze server",
    long_description_content_type="text/markdown",
    url=url,
    packages=find_packages(include=['snooze_client', 'snooze_client.*']),
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
    ],
    entry_points={
        'console_scripts': [
            'snooze_client = snooze_client.cli:snooze'
        ],
    },
    install_requires = [
        'PyYAML',
        'click',
        'pathlib',
        'requests',
    ],
)

