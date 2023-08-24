from dataclasses import asdict
from pathlib import Path

import yaml
import pytest

from borg_drone.config import Archive, LocalRepository, RemoteRepository, PruneOptions, Target


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
def archive1():
    return Archive(
        name='archive1',
        paths=['~/.ssh', '~/.gnupg', '~/src', '~/bin', '~/Desktop', '~/Documents', '~/Pictures'],
        exclude=['**/venv', '**/.direnv', '**/node_modules'],
        one_file_system=True,
        compression='lz4'
    )


@pytest.fixture
def archive2():
    return Archive(
        name='archive2',
        paths=['/data'],
        exclude=[],
        one_file_system=False,
        compression='lz4',
    )


@pytest.fixture
def config_data(archive1, archive2) -> dict:
    return {
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
                'paths': archive1.paths,
                'exclude': archive1.exclude,
                'one_file_system': archive1.one_file_system
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
                'paths': archive2.paths
            }
        }
    }


@pytest.fixture
def expected_targets(archive1, archive2, local_repository_usb, remote_repository_offsite, remote_repository_offsite_with_overrides):
    return [
        Target(
            archive=archive1,
            repo=local_repository_usb,
        ),
        Target(
            archive=archive1,
            repo=remote_repository_offsite,
        ),
        Target(
            archive=archive2,
            repo=remote_repository_offsite_with_overrides,
        ),
        Target(
            archive=archive2,
            repo=local_repository_usb,
        ),
    ]

@pytest.fixture
def config_file(config_data: dict, tmp_path: Path):
    file = tmp_path / 'config.yml'
    with file.open('w') as f:
        yaml.dump(config_data, f)
    yield file


