from pathlib import Path

from pytest import CaptureFixture

from borg_drone import command
from borg_drone.config import RemoteRepository, LocalRepository


def test_targets_command(
    config_file: Path,
    local_repository_usb: LocalRepository,
    remote_repository_offsite: RemoteRepository,
    remote_repository_offsite_with_overrides: RemoteRepository,
    capfd: CaptureFixture,
):
    command.targets_command(config_file)
    out, err = capfd.readouterr()

    assert out == '\n'.join(
        (
            'archive1:usb',
            '\tpaths   │ ~/.ssh, ~/.gnupg, ~/src, ~/bin, ~/Desktop, ~/Documents, ~/Pictures',
            '\texclude │ **/venv, **/.direnv, **/node_modules',
            '\trepo    │ usb [/path/to/usb]',
            '',
            'archive1:offsite',
            '\tpaths   │ ~/.ssh, ~/.gnupg, ~/src, ~/bin, ~/Desktop, ~/Documents, ~/Pictures',
            '\texclude │ **/venv, **/.direnv, **/node_modules',
            '\trepo    │ offsite [offsite.example.com]',
            '',
            'archive2:offsite',
            '\tpaths   │ /data',
            '\trepo    │ offsite [offsite.example.com]',
            '',
            'archive2:usb',
            '\tpaths   │ /data',
            '\trepo    │ usb [/path/to/usb]',
            '\n',
        ))
    return
