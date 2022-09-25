import os
from itertools import chain, groupby
from pathlib import Path
from logging import getLogger
from subprocess import CalledProcessError

from .config import RemoteRepository
from .util import run_cmd, get_targets, execute, update_ssh_known_hosts

logger = getLogger(__package__)


def init_command(config_file: Path, target_names: list[str]) -> None:
    for target in get_targets(config_file, target_names):
        if target.initialised:
            logger.info(f'{target.repo.name}:{target.name}: Already initialised')
            continue

        target.create_password_file()

        # Check / add server host key
        if isinstance(target.repo, RemoteRepository):
            try:
                update_ssh_known_hosts(target.repo.hostname)
            except CalledProcessError as ex:
                logger.error(ex)
                continue

        try:
            argv = ['borg', 'init', '--encryption', target.repo.encryption]
            run_cmd(argv, env=target.environment)
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


def info_command(config_file: Path, archives: list[str]) -> None:
    for target in get_targets(config_file, archives):
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


def targets_command(config_file: Path) -> None:
    for name, targets in groupby(get_targets(config_file), key=lambda x: x.name):
        targets = list(targets)
        if not targets:
            continue
        print(f'[{name}]')
        print(f'\tpaths   = {", ".join(targets[0].paths)}')
        print(f'\texclude = {targets[0].exclude}')
        print(f'\trepos  = {", ".join([str(target.repo) for target in targets])}')
