import subprocess
from json import JSONEncoder
from pathlib import Path
from subprocess import Popen, PIPE, STDOUT, DEVNULL, CalledProcessError
from typing import Any, Callable, TypeVar, Optional
from dataclasses import asdict
import logging

from typing_extensions import ParamSpec

from .config import ConfigValidationError, read_config, PruneOptions, Target
from .types import StringGenerator, EnvironmentMap, TargetTuple

logger = logging.getLogger(__package__)


class Colour:
    RESET = '\x1b[0m'
    GREY = '\x1b[38;20m'
    DARK_GREY = '\x1b[90;20m'
    YELLOW = '\x1b[33;20m'
    RED = '\x1b[31;20m'
    BOLD_RED = '\x1b[31;1m'
    GREEN = '\x1b[32;20m'


class ColourLogFormatter(logging.Formatter):
    datefmt = '%Y-%m-%d %H:%M:%S'
    fmt = '%(asctime)s │ %(levelname)s │ %(message)s'

    def __init__(self) -> None:
        super().__init__()
        self.formatters = {
            logging.DEBUG: self.mkformat(Colour.DARK_GREY),
            logging.INFO: self.mkformat(Colour.GREY),
            logging.WARNING: self.mkformat(Colour.YELLOW),
            logging.ERROR: self.mkformat(Colour.RED),
            logging.CRITICAL: self.mkformat(Colour.BOLD_RED),
        }

    @classmethod
    def mkformat(cls, colour: str) -> logging.Formatter:
        asctime = f'{colour}%(asctime)s{Colour.RESET}'
        levelname = f'{colour}%(levelname)-7s{Colour.RESET}'
        message = f'{colour}%(message)s{Colour.RESET}'
        return logging.Formatter(cls.fmt % locals(), datefmt=cls.datefmt)

    def format(self, record: logging.LogRecord) -> str:
        return self.formatters[record.levelno].format(record)


def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(level)
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(ColourLogFormatter())
    logger.addHandler(ch)


def execute(cmd: list[str], env: EnvironmentMap = None, stderr: int = STDOUT) -> StringGenerator:
    logger.info('> ' + ' '.join(cmd))
    for var, value in (env or {}).items():
        logger.debug(f'>  ENV: {var} = {value}')
    with Popen(cmd, stdout=PIPE, stderr=stderr, universal_newlines=True, env=env) as proc:
        while True:
            if proc.stdout is None:
                break
            line = proc.stdout.readline()
            if not line:
                break
            yield line.strip()
        if proc.stdout is not None:
            proc.stdout.close()
        return_code = proc.wait()
        if return_code:
            raise CalledProcessError(return_code, ' '.join(cmd))
    logger.info(f'{Colour.GREEN}Command executed successfully{Colour.RESET}')


def run_cmd(cmd: list[str], env: EnvironmentMap = None, stderr: int = STDOUT) -> list[str]:
    logger.info('')
    output = []
    for line in execute(cmd, env, stderr):
        logger.info(line)
        output.append(line)
    return output


def get_targets(config_file: Path, sync_target: TargetTuple = None) -> list[Target]:
    targets = read_config(config_file)
    if sync_target is None:
        return targets
    archive, repo = sync_target
    if archive:
        targets = [t for t in targets if t.archive.name == archive]
    if repo:
        targets = [t for t in targets if t.repo.name == repo]
    if not targets:
        raise ConfigValidationError([f'No targets found matching {":".join(sync_target)}'])
    return targets


def update_ssh_known_hosts(hostname: str) -> None:
    ssh_dir = Path.home() / '.ssh'
    ssh_dir.mkdir(mode=700, exist_ok=True)
    known_hosts = ssh_dir / 'known_hosts'
    if not known_hosts.exists():
        known_hosts.touch(mode=600, exist_ok=True)
    with known_hosts.open() as f:
        matched = [line for line in f if line.split(' ')[0] == hostname]
    if not matched:
        lines = run_cmd(['ssh-keyscan', '-H', hostname], stderr=DEVNULL)
        if lines:
            host_keys = '\n'.join(lines)
            with known_hosts.open('a') as f:
                f.write(f'\n{host_keys}')


class CustomJSONEncoder(JSONEncoder):

    def default(self, o: Any) -> Any:
        if isinstance(o, PruneOptions):
            return [{k: v} for k, v in asdict(o).items() if v is not None]
        return super().default(o)


T = TypeVar('T')
P = ParamSpec('P')


def require_borg(fn: Callable[P, T]) -> Callable[P, Optional[T]]:
    """
    Decorator to ensure borg is installed before the function is called
    """

    def wrapped(*args: P.args, **kwargs: P.kwargs) -> Optional[T]:
        try:
            subprocess.run(['borg', '-V'], capture_output=True)
        except FileNotFoundError:
            logger.error('Unable to locate borg executable')
            return None
        return fn(*args, **kwargs)

    return wrapped
