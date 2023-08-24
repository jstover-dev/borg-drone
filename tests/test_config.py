from pathlib import Path

from borg_drone.config import Target


def test_parse_config(config_file: Path, expected_targets: list[Target]):
    from borg_drone.config import parse_config
    assert parse_config(config_file) == expected_targets
