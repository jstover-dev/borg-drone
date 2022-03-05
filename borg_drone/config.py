import os
from dataclasses import dataclass, fields
from pathlib import Path

import yaml


class ConfigValidationError(Exception):
    """Named exception raised when configuration file fails validation"""


@dataclass
class Remote:
    name: str
    hostname: str
    username: str
    ssh_key: str
    encryption: str
    prune: list[dict[str, int]]


@dataclass
class Archive:
    name: str
    remote: Remote
    paths: list[str]
    exclude: list[str]


def xdg_config_path(name: str, create: bool = False) -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    path = Path(xdg_config_home) / name
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


CONFIG_PATH = xdg_config_path("borg-drone", create=True)


def parse_config(file: Path) -> list[Archive]:

    config = yaml.safe_load(file.read_text())

    def override_referenced_section(section: str, data: dict):
        """
        Allow simple "referencing" of other section objects.
        Strings will be replaced with dictionaries containing the referenced object, and
        Dictionaries will be used as override values.

        `section` must match a top-level config section
        """
        reference_errors = []

        if isinstance(data[section], list):
            data[section] = {name: {} for name in data[section]}

        for key, value in data[section].items():
            try:
                data[section][key] = {**config[section][key], **(value or {})}
            except KeyError:
                data[section][key] = None
                reference_errors.append(f'No such entry in "{section}" section: {key}')

        data[section] = {k: v for k, v in data[section].items() if v is not None}

        return reference_errors

    targets = []
    errors = []

    for archive_name, archive_config in config['archives'].items():

        # backup.remotes can refer to top-level remotes
        errors += override_referenced_section('remotes', archive_config)

        remotes = []
        for remote_name, remote_config in archive_config['remotes'].items():
            remote_config['name'] = remote_name

            missing_fields = set(x.name for x in fields(Remote)) - set(remote_config)
            if missing_fields:
                reason = f'Missing {len(missing_fields)} attributes: {missing_fields}'
                errors.append(f'Remote "{remote_name}" is invalid: {reason}')
            else:
                remotes.append(Remote(**remote_config))

        for remote in remotes:
            required_attrs = set(x.name for x in fields(Archive)) - {'remote', 'exclude', 'name'}
            missing_fields = required_attrs - set(archive_config)
            if missing_fields:
                reason = f'Missing {len(missing_fields)} attributes: {missing_fields}'
                errors.append(f'Archive "{archive_name}" is invalid: {reason}')
                break
            else:
                targets.append(
                    Archive(
                        name=archive_name,
                        remote=remote,
                        paths=archive_config['paths'],
                        exclude=archive_config.get('exclude', []),
                    ))

    if errors:
        raise ConfigValidationError('> ' + '\n> '.join(map(str, errors)))

    return targets
