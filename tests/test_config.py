from pathlib import Path


def test_parse_config(config_file: Path):
    from borg_drone.config import parse_config
    assert parse_config(config_file) == {}
