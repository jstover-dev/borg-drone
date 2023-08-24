import json
import os
import subprocess
from getpass import getpass
from pathlib import Path, PurePosixPath
from logging import getLogger
from subprocess import CalledProcessError
from typing import Optional

from .config import RemoteRepository, LocalRepository
from .util import run_cmd, get_targets, execute, update_ssh_known_hosts, CustomJSONEncoder, require_borg
from .types import OutputFormat, TargetTuple

logger = getLogger(__package__)


def generate_config_command(config_file: Path, overwrite: bool = False) -> None:
    """
    Generate an example configuration file.
    If the file exists and force=True, the file will be overwritten.
    """
    if config_file.exists() and not overwrite:
        raise RuntimeError(f'Configuration file already exists: {config_file}')
    config_file.write_text((Path(__file__).parent / 'example.yml').read_text())
    logger.info(f'Configuration file created: {config_file}')
    logger.info(f'Edit this file to configure the application')


@require_borg
def init_command(config_file: Path, sync_target: TargetTuple) -> None:
    """
    Wrapper for calling 'borg init' on all targets for the provided archives
    Initialises all configured borg repositories
    """
    for target in get_targets(config_file, sync_target):
        if target.initialised:
            logger.info(f'{target.name} already initialised')
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


@require_borg
def key_export_command(config_file: Path, sync_target: TargetTuple) -> None:
    """
    Export the repo keyfile that was produced by the 'init' command.
    These key and password files can be imported by using 'key-import'
    """
    passwords = {}
    exported = []
    for target in get_targets(config_file, sync_target):
        try:
            lines = list(execute(['borg', 'key', 'export', '--paper'], env=target.environment))
        except CalledProcessError as ex:
            logger.error(ex)
            continue
        else:
            target.paper_keyfile.write_text('\n'.join(lines))

        try:
            run_cmd(['borg', 'key', 'export', '::', str(target.keyfile)], env=target.environment)
        except CalledProcessError as ex:
            logger.error(ex)
            continue

        passwords[f'{target.name}:{target.repo.name}'] = target.password_file.read_text()
        exported += [target.keyfile, target.paper_keyfile]

    logger.info(f'{len(exported)} Encryption keys exported')
    if passwords:
        logger.warning('Repository passwords. You should back up these values to a safe location:')
        maxlen = max(map(len, passwords))
        for repo, pw in passwords.items():
            logger.info(f'\t{repo:{maxlen}} : {pw}')
    if exported:
        logger.warning('MAKE SURE TO BACKUP THESE FILES, AND THEN REMOVE FROM THE LOCAL FILESYSTEM!')
        logger.warning(f'You can delete these files by running: `borg-drone key-cleanup`')
        for f in exported:
            logger.info(f'\t{f}')


@require_borg
def key_import_command(
        config_file: Path, sync_target: TargetTuple, keyfile: Optional[Path], password_file: Optional[Path]) -> None:
    """
    Import a key file and password into a already configured target.
    This is mostly useful after restoring a backup since it allows for continued use of the repository.

    repo_target is a tuple given as (repo, archive)
    """
    if keyfile is None:
        raise RuntimeError('keyfile must not be empty')
    if sync_target is None:
        raise RuntimeError('No target provided')
    if password_file is None:
        password = getpass('Enter password for existing archive: ')
    else:
        password = password_file.read_text()

    for target in get_targets(config_file, sync_target):
        target.create_password_file(contents=password)
        try:
            run_cmd(['borg', 'key', 'import', '::', str(keyfile)], env=target.environment)
        except CalledProcessError as ex:
            logger.error(ex)
        logger.info(f'Imported keys for {target.name} successfully')


def key_cleanup_command(config_file: Path) -> None:
    """
    Delete all unnecessary keys that were produced by 'key export' command
    These keys are not needed for proper function of borg-drone
    """
    found = 0
    for target in get_targets(config_file):
        for keyfile in (target.keyfile, target.paper_keyfile):
            if keyfile.exists():
                keyfile.unlink()
                found += 1
                logger.info(f'Removed {keyfile}')
    logger.info(f'{found} files removed')


@require_borg
def create_command(config_file: Path, sync_target: TargetTuple) -> None:
    """
    Wrapper for calling 'borg create' on all targets for the provided archives
    Also calls 'borg prune' and 'borg compact' if specified by the configuration
    """
    for target in get_targets(config_file, sync_target):
        archive = target.archive
        argv = ['borg', 'create', '--stats', '--compression', archive.compression]
        if archive.one_file_system:
            argv.append('--one-file-system')
        for pattern in archive.exclude:
            argv += ['--exclude', pattern]
        argv.append('::{now}')
        argv += map(os.path.expanduser, archive.paths)
        run_cmd(argv, env=target.environment)

        if target.repo.prune:
            prune_argv = ['borg', 'prune', '-v', '--list', *target.repo.prune.argv]
            run_cmd(prune_argv, env=target.environment)

        if target.repo.compact:
            run_cmd(['borg', 'compact', '--cleanup-commits', '::'], env=target.environment)

        if isinstance(target.repo, LocalRepository) and target.repo.rclone_upload_path:
            try:
                subprocess.run(['rclone', '-V'], capture_output=True)
            except FileNotFoundError:
                logger.warning('Unable to locate rclone executable')
            else:
                remote_name, remote_base_path = target.repo.rclone_upload_path.split(':', 1)
                remote_path = PurePosixPath(remote_base_path) / target.archive.name
                upload_path = f'{remote_name}:{remote_path}'
                run_cmd(['rclone', 'sync', '-v', '--stats-one-line', target.borg_repository_path, upload_path])


@require_borg
def info_command(config_file: Path, target: TargetTuple) -> None:
    """
    Wrapper for calling 'borg info' on all targets for the provided archives
    """
    for t in get_targets(config_file, target):
        try:
            run_cmd(['borg', 'info'], env=t.environment)
        except CalledProcessError as ex:
            logger.error(ex)


@require_borg
def list_command(config_file: Path, target: TargetTuple) -> None:
    """
    Wrapper for calling 'borg list' on all targets for the provided archives
    """
    for t in get_targets(config_file, target):
        try:
            run_cmd(['borg', 'list'], env=t.environment)
        except CalledProcessError as ex:
            logger.error(ex)


def targets_command(config_file: Path, output: OutputFormat = OutputFormat.text) -> None:
    """
    Print all all targets to stdout.
    Output format can be either 'json', 'yaml', or 'text'
    """
    targets = get_targets(config_file, ('', ''))

    if output == OutputFormat.json:
        print(json.dumps([x.to_dict() for x in targets], indent=2, cls=CustomJSONEncoder))

    elif output == OutputFormat.yaml:
        print(config_file.read_text())

    elif output == OutputFormat.text:
        for target in targets:
            print(f'{target.name}')
            print(f'\tpaths   │ {", ".join(target.archive.paths)}')
            if target.archive.exclude:
                print(f'\texclude │ {", ".join(target.archive.exclude)}')
            print(f'\trepo    │ {target.repo.name} [{target.repo.url}]')
            print()
        return

    elif output == OutputFormat.python:
        for target in targets:
            print(target)
