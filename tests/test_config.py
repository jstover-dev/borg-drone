from pathlib import Path

from borg_drone.config import Archive


def test_parse_config(
        config_file: Path, local_repository_usb, remote_repository_offsite, remote_repository_offsite_with_overrides):
    from borg_drone.config import parse_config

    expected_config = [
        Archive(
            name='archive1',
            repo=local_repository_usb,
            paths=['~/.ssh', '~/.gnupg', '~/src', '~/bin', '~/Desktop', '~/Documents', '~/Pictures'],
            exclude=['**/venv', '**/.direnv', '**/node_modules'],
            one_file_system=True,
            compression='lz4'),
        Archive(
            name='archive1',
            repo=remote_repository_offsite,
            paths=['~/.ssh', '~/.gnupg', '~/src', '~/bin', '~/Desktop', '~/Documents', '~/Pictures'],
            exclude=['**/venv', '**/.direnv', '**/node_modules'],
            one_file_system=True,
            compression='lz4'),
        Archive(
            name='archive2',
            repo=remote_repository_offsite_with_overrides,
            paths=['/data'],
            exclude=[],
            one_file_system=False,
            compression='lz4'),
        Archive(
            name='archive2',
            repo=local_repository_usb,
            paths=['/data'],
            exclude=[],
            one_file_system=False,
            compression='lz4'),
    ]
    config = parse_config(config_file)
    assert config == expected_config
