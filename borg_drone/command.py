import os
from itertools import chain
from pathlib import Path
from logging import getLogger
from subprocess import Popen, PIPE, STDOUT, DEVNULL, CalledProcessError

from .config import Archive, RemoteRepository

logger = getLogger(__package__)


def execute(cmd: list[str], env: dict = None, stderr: int = STDOUT):
    logger.info('> ' + ' '.join(cmd))
    if env:
        logger.info(f'> {env}')
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


def run_cmd(cmd: list[str], env: dict = None, stderr: int = STDOUT) -> list[str]:
    output = []
    for line in execute(cmd, env, stderr):
        logger.info(line)
        output.append(line)
    logger.info('')
    return output


def init_command(targets: list[Archive]):
    for target in targets:
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
                    lines = run_cmd(['ssh-keyscan', '-t', 'rsa', target.repo.hostname], stderr=DEVNULL)
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


def key_export_command(targets: list[Archive]):
    exported = []
    for target in targets:
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


def key_cleanup_command(targets: list[Archive]):
    for target in targets:
        for keyfile in (target.keyfile, target.paper_keyfile):
            if keyfile.exists():
                keyfile.unlink()
                logger.info(f'Removed {keyfile}')


def create_command(targets: list[Archive]):
    for target in targets:
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


def info_command(targets: list[Archive]):
    for target in targets:
        try:
            run_cmd(['borg', 'info'], env=target.environment)
        except CalledProcessError as ex:
            logger.error(ex)


def list_command(targets: list[Archive]):
    if not targets:
        logger.info('No archives found in configuration file!')
        return
    for target in targets:
        logger.info(target)
