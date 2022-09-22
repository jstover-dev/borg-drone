import os
from itertools import chain, groupby
from pathlib import Path
from logging import getLogger
from subprocess import Popen, PIPE, STDOUT, DEVNULL, CalledProcessError
from typing import Generator, Optional

from .config import ConfigValidationError, RemoteRepository, read_config, Archive

logger = getLogger(__package__)

EnvironmentMap = Optional[dict[str, str]]
StringGenerator = Generator[str, None, None]


def execute(cmd: list[str], env: EnvironmentMap = None, stderr: int = STDOUT) -> StringGenerator:
    logger.info('> ' + ' '.join(cmd))
    for var, value in (env or {}).items():
        logger.info(f'> ENV: {var} = {value}')
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


def get_targets(config_file: Path, names: list[str]) -> list[Archive]:
    targets = [target for target in read_config(config_file) if (not names) or target.name in names]
    if not targets:
        raise ConfigValidationError([f'No targets found matching names: {names}'])
    return targets


def init_command(config_file: Path, target_names: list[str]) -> None:
    for target in get_targets(config_file, target_names):
        if target.initialised:
            logger.info(f'{target.repo.name}:{target.name}: Already initialised')
            continue

        target.create_password_file()

        # Check / add server host key
        if isinstance(target.repo, RemoteRepository):
            ssh_dir = Path.home() / '.ssh'
            ssh_dir.mkdir(mode=700, exist_ok=True)
            known_hosts = ssh_dir / 'known_hosts'
            if not known_hosts.exists():
                known_hosts.touch(mode=600, exist_ok=True)
            with known_hosts.open() as f:
                matched = [line for line in f if line.split(' ')[0] == target.repo.hostname]
            if not matched:
                try:
                    lines = run_cmd(['ssh-keyscan', '-H', target.repo.hostname], stderr=DEVNULL)
                except CalledProcessError as ex:
                    logger.error(ex)
                    continue

                if lines:
                    host_keys = '\n'.join(lines)
                    with known_hosts.open('a') as f:
                        f.write(f'\n{host_keys}')

        try:
            run_cmd(
                ['borg', 'init', '--encryption', target.repo.encryption], env=target.environment)
        except CalledProcessError as ex:
            logger.error(ex)
        else:
            logger.info(f'{target.name} initialised')
            (target.config_path / '.initialised').touch(exist_ok=True)


def key_export_command(config_file: Path, target_names: list[str]) -> None:
    exported = []
    for target in get_targets(config_file, target_names):
        try:
            lines = list(execute(['borg', 'key', 'export', '--paper'], env=target.environment))
        except CalledProcessError as ex:
            logger.error(ex)
        else:
            target.paper_keyfile.write_text('\n'.join(lines))

        try:
            run_cmd(['borg', 'key', 'export', '::', str(target.keyfile)], env=target.environment)
        except CalledProcessError as ex:
            logger.error(ex)

        exported += [target.keyfile, target.paper_keyfile]

    logger.info(f'Encryption keys exported')
    logger.info('MAKE SURE TO BACKUP THESE FILES, AND THEN REMOVE FROM THE LOCAL FILESYSTEM!')
    logger.info(f'You can do this by running: `borg-drone delete-exports`')
    for f in exported:
        logger.info(f'\t{f}')


def key_cleanup_command(config_file: Path, target_names: list[str]) -> None:
    for target in get_targets(config_file, target_names):
        for keyfile in (target.keyfile, target.paper_keyfile):
            if keyfile.exists():
                keyfile.unlink()
                logger.info(f'Removed {keyfile}')


def create_command(config_file: Path, target_names: list[str]) -> None:
    for target in get_targets(config_file, target_names):
        argv = ['borg', 'create', '--stats', '--compression', target.compression]
        if target.one_file_system:
            argv.append('--one-file-system')
        for pattern in target.exclude:
            argv += ['--exclude', pattern]
        argv.append('::{now}')
        argv += map(os.path.expanduser, target.paths)
        try:
            run_cmd(argv, env=target.environment)
        except CalledProcessError as ex:
            logger.error(ex)

        if target.repo.prune:
            prune_argv = ['borg', 'prune', '-v', '--list']
            prune_argv += chain(
                *[
                    (f'--{arg}', str(value))
                    for prune_arg in target.repo.prune
                    for arg, value in prune_arg.items()
                ])
            try:
                run_cmd(prune_argv, env=target.environment)
            except CalledProcessError as ex:
                logger.error(ex)

        if target.repo.compact:
            try:
                run_cmd(['borg', 'compact', '--cleanup-commits'])
            except CalledProcessError as ex:
                logger.error(ex)


def info_command(config_file: Path, target_names: list[str]) -> None:
    for target in get_targets(config_file, target_names):

        try:
            run_cmd(['borg', 'info'], env=target.environment)
        except CalledProcessError as ex:
            logger.error(ex)


def list_command(config_file: Path, target_names: list[str]) -> None:
    for target in get_targets(config_file, target_names):
        try:
            run_cmd(['borg', 'list'], env=target.environment)
        except CalledProcessError as ex:
            logger.error(ex)


def targets_command(config_file: Path, target_names: list[str]) -> None:
    for name, targets in groupby(get_targets(config_file, target_names), key=lambda x: x.name):
        targets = list(targets)
        if not targets:
            continue
        print(f'[{name}]')
        print(f'\tpaths   = {", ".join(targets[0].paths)}')
        print(f'\texclude = {targets[0].exclude}')
        print(f'\trepos  = {", ".join([str(target.repo) for target in targets])}')

