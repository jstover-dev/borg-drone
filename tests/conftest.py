from dataclasses import asdict
from pathlib import Path

import yaml
import pytest

from borg_drone.config import Archive, LocalRepository, RemoteRepository, PruneOptions


@pytest.fixture
def local_repository_usb():
    return LocalRepository(
        name='usb',
        encryption='keyfile-blake2',
        path='/path/to/usb',
        prune=PruneOptions(
            keep_daily=7,
            keep_weekly=3,
            keep_monthly=6,
            keep_yearly=2,
        ),
        compact=False,
    )


@pytest.fixture
def remote_repository_offsite():
    return RemoteRepository(
        name='offsite',
        encryption='repokey-blake2',
        hostname='offsite.example.com',
        path='.',
        username='backup',
        port=22,
        ssh_key='~/.ssh/borg',
        prune=PruneOptions(
            keep_daily=7,
            keep_weekly=3,
            keep_monthly=6,
            keep_yearly=2,
        ),
        compact=False,
    )


@pytest.fixture
def remote_repository_offsite_with_overrides(remote_repository_offsite):
    attrs = asdict(remote_repository_offsite)
    attrs['prune'] = PruneOptions(keep_daily=1, keep_monthly=2)
    return RemoteRepository(**dict(attrs, encryption='encryption_override'))


@pytest.fixture
def archive_paths() -> dict[str, list[str]]:
    return {
        'archive1': [
            '~/.ssh',
            '~/.gnupg',
            '~/src',
            '~/bin',
            '~/Desktop',
            '~/Documents',
            '~/Pictures',
        ],
        'archive2': [
            '/data',
        ]
    }


@pytest.fixture
def archive1_targets(local_repository_usb, remote_repository_offsite, archive_paths):
    return [
        Archive(
            name='archive1',
            repo=repo,
            paths=archive_paths['archive1'],
            exclude=[
                '**/venv',
                '**/.direnv',
                '**/node_modules',
            ],
            one_file_system=True,
            compression='lz4',
        ) for repo in (local_repository_usb, remote_repository_offsite)
    ]


@pytest.fixture
def archive2_targets(local_repository_usb, remote_repository_offsite, archive_paths):
    return [
        Archive(
            name='archive2',
            repo=repo,
            paths=archive_paths['archive2'],
            exclude=[],
            one_file_system=False,
            compression='lz4',
        ) for repo in (local_repository_usb, remote_repository_offsite)
    ]


@pytest.fixture
def mock_targets(archive1_targets, archive2_targets):
    return [*archive1_targets, *archive2_targets]


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
                            'keep_daily': 7
                        },
                        {
                            'keep_weekly': 3
                        },
                        {
                            'keep_monthly': 6
                        },
                        {
                            'keep_yearly': 2
                        },
                    ]
                }
            },
            'remote': {
                'offsite': {
                    'hostname': 'offsite.example.com',
                    'username': 'backup',
                    'port': 22,
                    'ssh_key': '~/.ssh/borg',
                    'encryption': 'repokey-blake2',
                    'prune': [
                        {
                            'keep_daily': 7
                        },
                        {
                            'keep_weekly': 3
                        },
                        {
                            'keep_monthly': 6
                        },
                        {
                            'keep_yearly': 2
                        },
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
                                'keep_daily': 1
                            },
                            {
                                'keep_monthly': 2
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
