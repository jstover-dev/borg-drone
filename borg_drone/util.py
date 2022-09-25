from pathlib import Path
from subprocess import Popen, PIPE, STDOUT, DEVNULL, CalledProcessError
from typing import Generator, Optional
from logging import getLogger

from .config import ConfigValidationError, read_config, Archive

logger = getLogger(__package__)

EnvironmentMap = Optional[dict[str, str]]
StringGenerator = Generator[str, None, None]


def execute(cmd: list[str], env: EnvironmentMap = None, stderr: int = STDOUT) -> StringGenerator:
    logger.info('> ' + ' '.join(cmd))
    for var, value in (env or {}).items():
        logger.info(f'>  ENV: {var} = {value}')
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
            raise CalledProcessError(return_code, cmd)


def run_cmd(cmd: list[str], env: EnvironmentMap = None, stderr: int = STDOUT) -> list[str]:
    output = []
    for line in execute(cmd, env, stderr):
        logger.info(line)
        output.append(line)
    logger.info('')
    return output


def get_targets(config_file: Path, names: list[str] = None) -> list[Archive]:
    targets = [target for target in read_config(config_file) if (not names) or target.name in names]
    if not targets:
        raise ConfigValidationError([f'No targets found matching names: {names}'])
    return targets




def update_ssh_known_hosts(hostname: str):
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
