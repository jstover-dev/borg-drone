import os
from dataclasses import dataclass, fields, field
from logging import getLogger
from pathlib import Path
from secrets import token_hex
from typing import ClassVar, Optional, Union, Type, Any, TypeVar
from urllib.parse import urlparse
from collections.abc import Iterable

import yaml

logger = getLogger(__package__)


def xdg_config_path(name: str, create: bool = False) -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    path = Path(xdg_config_home) / name
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


CONFIG_PATH = xdg_config_path("borg-drone", create=True)

DEFAULT_CONFIG_FILE = CONFIG_PATH / 'config.yml'


class ConfigValidationError(Exception):
    """Exception raised when configuration file fails validation"""

    def __init__(self, errors: Iterable[str]):
        super().__init__()
        self.errors = errors

    def log_errors(self):
        for error in self.errors:
            logger.error(f'> {error}')


T = TypeVar('T')


def object_from_dict(cls: Type[T], data: dict[str, Any]) -> T:
    return cls(**{k: v for k, v in data.items() if k in [x.name for x in fields(cls)]})


@dataclass
class ConfigItem:
    name: str

    _required_attributes_: ClassVar[set[str]] = set()

    @classmethod
    def validate(cls, obj: dict[str, Any]) -> Optional[str]:
        missing_attrs = cls._required_attributes_ - set(obj)
        if missing_attrs:
            return f'Missing {len(missing_attrs)} attributes: {missing_attrs}'
        return None

    @classmethod
    def from_dict(cls: Type[T], obj: dict[str, Any]) -> T:
        return cls(**{k: v for k, v in obj.items() if k in [x.name for x in fields(cls)]})


@dataclass
class LocalRepository(ConfigItem):
    name: str
    encryption: str
    path: str
    prune: list[dict[str, int]] = field(default_factory=list)
    compact: bool = False

    is_remote = False
    _required_attributes_ = {'name', 'encryption', 'path'}

    @property
    def url(self) -> str:
        return self.path

    def __str__(self):
        return f'local:{self.path}'


@dataclass
class RemoteRepository(ConfigItem):
    name: str
    encryption: str
    hostname: str
    path: str = '.'
    username: Optional[str] = None
    port: int = 22
    ssh_key: Optional[str] = None
    prune: list[dict[str, int]] = field(default_factory=list)
    compact: bool = False

    _required_attributes_ = {'name', 'encryption', 'hostname'}
    is_remote = True

    @property
    def url(self) -> str:
        username = f'{self.username}@' if self.username else ''
        # Ensure relative paths start with /./
        path = self.path
        if not Path(path).is_absolute():
            path = '/' + path
            if not self.path.startswith('.'):
                path = '/.' + path
        return f'ssh://{username}{self.hostname}:{self.port}{path}'

    def __str__(self):
        return f'remote:{self.username}@{self.hostname}/{self.path}'


@dataclass
class Archive(ConfigItem):
    name: str
    repo: Union[LocalRepository, RemoteRepository]
    paths: list[str]
    exclude: list[str] = field(default_factory=list)
    one_file_system: bool = False
    compression: str = 'lz4'

    _required_attributes_ = {'name', 'repo', 'paths'}

    @property
    def config_path(self) -> Path:
        name = f'{self.name}_{self.repo.name}'
        path = CONFIG_PATH / name
        path.mkdir(exist_ok=True)
        return path

    @property
    def password_file(self) -> Path:
        return self.config_path / 'passwd'

    @property
    def keyfile(self) -> Path:
        return self.config_path / 'keyfile.bin'

    @property
    def paper_keyfile(self) -> Path:
        return self.config_path / 'keyfile.txt'

    def create_password_file(self, contents: str = None) -> None:
        passwd = self.config_path / 'passwd'
        if not passwd.exists():
            passwd.write_text(contents or token_hex(32))
            logger.info(f'Created passphrase file: {passwd}')

    @property
    def initialised(self) -> bool:
        return (self.config_path / '.initialised').exists()

    @property
    def environment(self) -> dict[str, str]:
        env = dict(
            BORG_PASSCOMMAND=f'cat {self.password_file}',
            BORG_RELOCATED_REPO_ACCESS_IS_OK='yes',
        )

        if isinstance(self.repo, RemoteRepository):
            url = urlparse(self.repo.url)
            borg_repo = url._replace(path=os.path.join(url.path, self.name)).geturl()
            borg_rsh = 'ssh -o VisualHostKey=no'
            if self.repo.ssh_key:
                borg_rsh += f' -i {self.repo.ssh_key}'
            env.update(BORG_RSH=borg_rsh)
        else:
            borg_repo = os.path.join(self.repo.url, self.name)

        env.update(BORG_REPO=borg_repo)

        return env

    def to_dict(self) -> dict:
        return {k: v.__dict__ if isinstance(v, ConfigItem) else v for k, v in self.__dict__.items()}


# TODO: Clean this up
def parse_config(file: Path) -> list[Archive]:

    def replace_references(
        data: dict[str, Any],
        section: str,
        references: dict[str, Any],
    ) -> list[str]:
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
                data[section][key] = {**references[key], **(value or {})}
            except KeyError:
                data[section][key] = None
                reference_errors.append(f'No such entry in "{section}" section: {key}')

        data[section] = {k: v for k, v in data[section].items() if v is not None}

        return reference_errors

    targets: list[Archive] = []
    errors = set()

    config = yaml.safe_load(file.read_text())

    # Check for duplicated repository names in remote/local section
    repo_names = []
    for repo_type in ('remote', 'local'):
        repo_names += list(config['repositories'].get(repo_type, {}))
    repository_duplicates = set(item for item in repo_names if repo_names.count(item) > 1)
    if repository_duplicates:
        errors |= set(f'Duplicate repository name: {name}' for name in repository_duplicates)

    for archive_name, archive_config in config['archives'].items():

        # config.repositories can refer to either local or remote repositories
        repositories = {
            name: dict(repo, type=repo_type)
            for repo_type in ['remote', 'local']
            for name, repo in config['repositories'].get(repo_type, {}).items()
        }
        errors |= set(replace_references(archive_config, 'repositories', repositories))

        # Read remotes
        remotes: list[Union[LocalRepository, RemoteRepository]] = []
        for repo_name, repo_config in archive_config['repositories'].items():
            repo_config['name'] = repo_name

            repo_type: Union[Type[RemoteRepository], Type[LocalRepository]]

            repo_type = RemoteRepository if repo_config.pop('type') == 'remote' else LocalRepository
            invalid_reason = repo_type.validate(repo_config)
            if invalid_reason:
                errors.add(f'Repository "{repo_name}" is invalid: {invalid_reason}')
            else:
                remotes.append(repo_type.from_dict(repo_config))

        # Validate archives
        for remote in remotes:
            archive_params = {'name': archive_name, 'repo': remote, **archive_config}
            invalid_reason = Archive.validate(archive_params)
            if invalid_reason:
                errors.add(f'Archive "{archive_name}" is invalid: {invalid_reason}')
                break
            else:
                targets.append(Archive.from_dict(archive_params))

    if errors:
        raise ConfigValidationError(errors)

    return targets


def read_config(file: Path) -> list[Archive]:
    try:
        return parse_config(file)
    except FileNotFoundError:
        if file == DEFAULT_CONFIG_FILE:
            with file.open('w') as f:
                yaml.dump({'repositories': {}, 'archives': {}}, f)
            return read_config(file)
        else:
            raise ConfigValidationError([f'No such file: {file}'])
