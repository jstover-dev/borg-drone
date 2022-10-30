from json import JSONEncoder
from pathlib import Path
from subprocess import Popen, PIPE, STDOUT, DEVNULL, CalledProcessError
from typing import Optional, Any
from dataclasses import asdict
import logging

from .config import ConfigValidationError, read_config, Archive, PruneOptions
from .types import StringGenerator, EnvironmentMap

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


def setup_logging() -> None:
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
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


def get_targets(config_file: Path, names: Optional[list[str]] = None) -> list[Archive]:
    if names is None:
        names = []
    read_all = not names or 'all' in names
    targets = [target for target in read_config(config_file) if read_all or target.name in names]
    if not targets:
        raise ConfigValidationError([f'No targets found matching names: {names}'])
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
