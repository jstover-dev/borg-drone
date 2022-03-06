from pathlib import Path

import yaml
import pytest


@pytest.fixture
def config_file(tmp_path: Path):
    file = tmp_path / 'config.yml'
    config = {
        'repositories': {
            'local': {
                'usb': {
                    'path': '/path/to/usb',
                    'encryption': 'keyfile-blake2',
                    'prune': [
                        {
                            'keep-daily': 7
                        },
                        {
                            'keep-weekly': 3
                        },
                        {
                            'keep-monthly': 6
                        },
                        {
                            'keep-yearly': 2
                        },
                    ]
                }
            },
            'remote': {
                'offsite': {
                    'hostname': 'offsite.example.comt',
                    'username': 'backup',
                    'port': 22,
                    'ssh_key': '~/.ssh/borg',
                    'encryption': 'repokey-blake2',
                    'prune': [
                        {
                            'keep-daily': 7
                        }, {
                            'keep-weekly': 3
                        }, {
                            'keep-monthly': 6
                        }, {
                            'keep-yearly': 2
                        }
                    ]
                },
            }
        },
        'archives': {
            'archive1': {
                'repositories': ['usb', 'offsite'],
                'paths': [
                    '~/.ssh',
                    '~/.gnupg',
                    '~/src',
                    '~/bin',
                    '~/Desktop',
                    '~/Documents',
                    '~/Pictures',
                ],
                'exclude': ['**/venv', '**/.direnv', '**/node_modules'],
                'one_file_system': True
            },
            'archive2': {
                'repositories': {
                    'usb': None,
                    'offsite': {
                        'encryption': 'encryption_override',
                        'prune': [
                            {
                                'keep-daily': 1
                            },
                            {
                                'keep-monthly': 2
                            },
                        ]
                    },
                },
                'paths': ['/data']
            }
        }
    }
    with file.open('w') as f:
        yaml.dump(config, f)
    yield file
