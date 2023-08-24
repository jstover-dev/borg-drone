import os
from dataclasses import dataclass, fields, field, asdict
from itertools import chain
from logging import getLogger
from pathlib import Path, PurePosixPath
from secrets import token_hex
from typing import ClassVar, Optional, Union, Any, TypeVar, TYPE_CHECKING
from urllib.parse import urlparse
from collections.abc import Iterable

import yaml

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

logger = getLogger(__package__)

T = TypeVar('T')
DataclassT = TypeVar("DataclassT", bound="DataclassInstance")


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

    def log_errors(self) -> None:
        for error in self.errors:
            logger.error(f'> {error}')


@dataclass(frozen=True)
class PruneOptions:
    keep_hourly: Optional[int] = None
    keep_daily: Optional[int] = None
    keep_weekly: Optional[int] = None
    keep_monthly: Optional[int] = None
    keep_yearly: Optional[int] = None

    @classmethod
    def from_yaml(cls: type[T], data: list[dict[str, int]]) -> T:
        return cls(**{k: v for option in data for k, v in option.items()})

    @property
    def argv(self) -> list[str]:
        return list(
            chain(
                *[
                    (f'--{option.replace("_", "-")}', str(value))
                    for option, value in asdict(self).items()
                    if value is not None
                ]))


@dataclass(frozen=True)
class ConfigItem:
    name: str
    required_attributes: ClassVar[set[str]]

    @classmethod
    def from_dict(cls: type[DataclassT], obj: dict[str, Any]) -> DataclassT:
        return cls(**{k: v for k, v in obj.items() if k in [x.name for x in fields(cls)]})

    def to_dict(self: DataclassT) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass(frozen=True)
class LocalRepository(ConfigItem):
    name: str
    encryption: str
    path: str
    prune: PruneOptions = field(default_factory=PruneOptions)
    compact: bool = False
    rclone_upload_path: str = ''

    required_attributes = {'encryption', 'path'}
    is_remote = False

    @property
    def url(self) -> str:
        return self.path


@dataclass(frozen=True)
class RemoteRepository(ConfigItem):
    name: str
    encryption: str
    hostname: str
    path: str = '.'
    username: Optional[str] = None
    port: int = 22
    ssh_key: Optional[str] = None
    prune: PruneOptions = field(default_factory=PruneOptions)
    compact: bool = False

    required_attributes = {'encryption', 'hostname'}
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


@dataclass(frozen=True)
class Archive(ConfigItem):
    name: str
    paths: list[str]
    exclude: list[str] = field(default_factory=list)
    one_file_system: bool = False
    compression: str = 'lz4'

    required_attributes = {'repositories', 'paths'}


@dataclass
class Target:
    archive: Archive
    repo: Union[LocalRepository, RemoteRepository]

    @property
    def name(self) -> str:
        return f'{self.archive.name}:{self.repo.name}'

    @property
    def config_path(self) -> Path:
        path = CONFIG_PATH / self.name.replace(':', '_')
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

    @property
    def initialised(self) -> bool:
        return (self.config_path / '.initialised').exists()

    @property
    def borg_repository_path(self) -> str:
        if self.repo.is_remote:
            url = urlparse(self.repo.url)
            return url._replace(path=os.path.join(url.path, self.archive.name)).geturl()
        else:
            return str(PurePosixPath(self.repo.url) / self.archive.name)

    @property
    def environment(self) -> dict[str, str]:
        env = dict(
            BORG_PASSCOMMAND=f'cat {self.password_file}',
            BORG_RELOCATED_REPO_ACCESS_IS_OK='yes',
            BORG_REPO=self.borg_repository_path,
        )
        if self.repo.is_remote:
            borg_rsh = 'ssh -o VisualHostKey=no'

            ssh_key = getattr(self.repo, 'ssh_key', None)
            if ssh_key:
                borg_rsh += f' -i {ssh_key}'
            env.update(BORG_RSH=borg_rsh)
        return env

    def create_password_file(self, contents: Optional[str] = None) -> None:
        passwd = self.config_path / 'passwd'
        if not passwd.exists():
            passwd.write_text(contents or token_hex(32))
            logger.info(f'Created passphrase file: {passwd}')

    def to_dict(self) -> dict[str, Any]:
        return {'archive': self.archive.to_dict(), 'repo': self.repo.to_dict()}


def validate_config(data: dict[str, Any]) -> None:

    errors = set()

    # Check required keys
    missing_keys = sorted({'repositories', 'archives'} - set(data.keys()))
    if missing_keys:
        errors.add(f'Missing required keys: {missing_keys}')

    repository_types = data.get('repositories', {}).keys()
    invalid_repo_types = set(repository_types) - {'local', 'remote'}
    if invalid_repo_types:
        errors.add(f'Invalid repository types: {invalid_repo_types}')

    local_repositories = data.get('repositories', {}).get('local', {})
    remote_repositories = data.get('repositories', {}).get('remote', {})
    repo_names = [*local_repositories.keys(), *remote_repositories.keys()]
    archives = data.get('archives', {})

    if not repo_names:
        errors.add('No repositories were defined')

    # Check required attributes for local repository
    for name, repository in local_repositories.items():
        for attribute in LocalRepository.required_attributes:
            if repository.get(attribute) is None:
                errors.add(f'Repository "{name}" is missing attribute "{attribute}"')

    # Check required attributes for remote repository
    for name, repository in remote_repositories.items():
        for attribute in RemoteRepository.required_attributes:
            if repository.get(attribute) is None:
                errors.add(f'Repository "{name}" is missing attribute "{attribute}"')

    # Check for duplicate local/remote repository names
    repository_duplicates = set(item for item in repo_names if repo_names.count(item) > 1)
    if repository_duplicates:
        errors |= set(f'Duplicate repository name: {name}' for name in repository_duplicates)

    # Validate repository upload_path strings
    for name, repository in local_repositories.items():
        rclone_upload_path = repository.get('rclone_upload_path')
        if rclone_upload_path:
            if rclone_upload_path.count(':') != 1:
                errors.add(f'Invalid rclone_upload_path "{rclone_upload_path}". Path must contain a single colon')

    for name, archive in archives.items():
        # Check required attributes for archive
        for attribute in Archive.required_attributes:
            if archive.get(attribute) is None:
                errors.add(f'Archive "{name}" is missing attribute "{attribute}"')

        # Make sure all repository references are valid
        for archive_repository in archive.get('repositories', []):
            if archive_repository not in repo_names:
                errors.add(f'Invalid repository reference: {archive_repository}')

    # Validate Prune Options
    for prune_opts in (x.get('prune', []) for x in local_repositories.values()):
        try:
            PruneOptions.from_yaml(prune_opts)
        except TypeError:
            errors.add(f'Invalid prune options: {prune_opts}')

    if errors:
        err = ConfigValidationError(errors)
        err.log_errors()
        raise err


def parse_config(file: Path) -> list[Target]:
    yaml_data = yaml.safe_load(file.read_text())
    validate_config(yaml_data)

    repositories: dict[str, Union[LocalRepository, RemoteRepository]] = {}

    for name, repo in yaml_data['repositories'].get('local', {}).items():
        repo['prune'] = PruneOptions.from_yaml(repo.get('prune', []))
        local_repository: LocalRepository = LocalRepository.from_dict({'name': name, **repo})
        repositories[name] = local_repository

    for name, repo in yaml_data['repositories'].get('remote', {}).items():
        repo['prune'] = PruneOptions.from_yaml(repo.get('prune', []))
        remote_repository: RemoteRepository = RemoteRepository.from_dict({'name': name, **repo})
        repositories[name] = remote_repository

    targets = []
    for name, archive_data in yaml_data['archives'].items():

        # Read repositories name and override values from archive
        repository_list = archive_data['repositories']
        if isinstance(repository_list, list):
            repository_list = {name: {} for name in repository_list}
        else:
            repository_list = {k: v if v is not None else {} for k, v in repository_list.items()}

        target_repos = []
        for archive_repository, overrides in repository_list.items():
            if 'prune' in overrides:
                overrides['prune'] = PruneOptions.from_yaml(overrides['prune'])
            repo = repositories[archive_repository]
            repo = type(repo).from_dict(dict(repo.to_dict(), **overrides))
            target_repos.append(repo)

        archive = Archive.from_dict({'name': name, **archive_data})
        targets += [Target(archive=archive, repo=repo) for repo in target_repos]

    return targets


def read_config(file: Path) -> list[Target]:
    try:
        return parse_config(file)
    except FileNotFoundError:
        if file == DEFAULT_CONFIG_FILE:
            file.write_text((Path(__file__).parent / 'example.yml').read_text())
            return read_config(file)
        else:
            raise ConfigValidationError([f'No such file: {file}'])
