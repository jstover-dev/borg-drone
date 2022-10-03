import json
import os
from getpass import getpass
from itertools import chain, groupby
from pathlib import Path
from logging import getLogger
from subprocess import CalledProcessError

from .config import RemoteRepository
from .util import run_cmd, get_targets, execute, update_ssh_known_hosts
from .types import OutputFormat, TargetTuple

logger = getLogger(__package__)


def generate_config_command(config_file: Path) -> None:
    if config_file.exists():
        raise RuntimeError(f'Configuration file already exists: {config_file}')
    config_file.write_text((Path(__file__).parent / 'example.yml').read_text())
    logger.info(f'Configuration file created: {config_file}')
    logger.info(f'Edit this file to configure the application')


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
    logger.info(f'You can do this by running: `borg-drone key-cleanup`')
    for f in exported:
        logger.info(f'\t{f}')


def key_import_command(config_file: Path, target: TargetTuple, keyfile: Path, password_file: Path):
    if password_file is None:
        password = getpass('Enter password for existing archive: ')
    else:
        password = password_file.read_text()
    repo, archive = target
    for target in get_targets(config_file, [archive]):
        if target.repo.name == repo:
            target.create_password_file(contents=password)
            try:
                run_cmd(['borg', 'key', 'import', '::', str(keyfile)], env=target.environment)
            except CalledProcessError as ex:
                logger.error(ex)
            logger.info(f'Imported keys for {repo}:{archive} successfully')


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
                run_cmd(['borg', 'compact', '--cleanup-commits', '::'], env=target.environment)
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


def targets_command(config_file: Path, output: OutputFormat = 'text') -> None:
    all_targets = get_targets(config_file)

    if output == 'json':
        print(json.dumps([x.to_dict() for x in all_targets], indent=2))
        return

    elif output == 'yaml':
        print(config_file.read_text())
        return

    for name, targets in groupby(all_targets, key=lambda x: x.name):
        targets = list(targets)
        if not targets:
            continue
        print(f'[{name}]')
        print(f'\tpaths   = {", ".join(targets[0].paths)}')
        print(f'\texclude = {targets[0].exclude}')
        print(f'\trepos  = {", ".join([str(target.repo) for target in targets])}')
