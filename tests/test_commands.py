from pathlib import Path

from pytest import CaptureFixture

from borg_drone import command
from borg_drone.config import RemoteRepository, LocalRepository


def test_targets_command(
    config_file: Path,
    archive_paths: dict[str, list[str]],
    local_repository_usb: LocalRepository,
    remote_repository_offsite: RemoteRepository,
    remote_repository_offsite_with_overrides: RemoteRepository,
    capfd: CaptureFixture,
):
    command.targets_command(config_file)
    out, err = capfd.readouterr()

    assert out == '\n'.join(
        [
            "[archive1]",
            f"\tpaths   = {', '.join(archive_paths['archive1'])}",
            "\texclude = ['**/venv', '**/.direnv', '**/node_modules']",
            f"\trepos  = {local_repository_usb}, {remote_repository_offsite}",
            "[archive2]",
            f"\tpaths   = {', '.join(archive_paths['archive2'])}",
            "\texclude = []",
            f"\trepos  = {remote_repository_offsite_with_overrides}, {local_repository_usb}",
            "",
        ])
