from pathlib import Path
from logging import getLogger
from subprocess import Popen, PIPE, STDOUT, DEVNULL, CalledProcessError


from .config import Archive

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


def run_cmd(cmd: list[str], env: dict = None, stderr: int = STDOUT):
    for line in execute(cmd, env, stderr):
        logger.info(line)


def init_command(config: list[Archive], archive: str):
    targets = [x for x in config if x.name == archive]

    for target in targets:
        if target.initialised:
            logger.info(f'{target.repo.name}:{target.name}: Already initialised')
            continue

        target.create_password_file()

        # Check / add server host key
        if target.repo.is_remote:
            known_hosts = Path.home() / '.ssh' / 'known_hosts'
            with known_hosts.open() as f:
                matched = [line for line in f if line.split(' ')[0] == target.repo.hostname]
            if not matched:
                host_key = list(execute(['ssh-keyscan', '-t', 'rsa', target.repo.hostname], stderr=DEVNULL))
                if host_key:
                    with known_hosts.open('a') as f:
                        f.write(f'\n{host_key[0]}')

        try:
            run_cmd(
                ['borg', 'init', '--encryption', target.repo.encryption],
                env=target.environment
            )
        except CalledProcessError as ex:
            logger.error(ex)
        else:
            logger.info(f'{target.name} initialised')
            (target.config_path / '.initialised').touch(exist_ok=True)


def export_keys_command(config: list[Archive], archive: str):
    targets = [x for x in config if x.name == archive]
    exported = []
    for target in targets:
        paper_keyfile = target.config_path / 'keyfile.txt'
        try:
            lines = list(execute(['borg', 'key', 'export', '--paper'], env=target.environment))
        except CalledProcessError as ex:
            logger.error(ex)
        else:
            paper_keyfile.write_text('\n'.join(lines))
            exported.append(paper_keyfile)

        keyfile = target.config_path / 'keyfile.bin'
        try:
            run_cmd(['borg', 'key', 'export', '::', str(keyfile)], env=target.environment)
        except CalledProcessError as ex:
            logger.error(ex)
        else:
            exported.append(keyfile)


    logger.info(f'Encryption keys exported')
    logger.info('MAKE SURE TO BACKUP THESE FILES, AND THEN REMOVE FROM THE LOCAL FILESYSTEM!')
    logger.info(f'You can do this by running: `borg-drone delete-exports {archive}`')
    for f in exported:
        logger.info(f'\t{f}')


def delete_exports_command(config: list[Archive], archive: str):
    targets = [x for x in config if x.name == archive]
    for target in targets:
        for key_name in ('keyfile.txt', 'keyfile.bin'):
            keyfile = target.config_path / key_name
            if keyfile.exists():
                keyfile.unlink()
                logger.info(f'Removed {keyfile}')


def list_command(config: list[Archive]):
    for backup in config:
        print(backup)
