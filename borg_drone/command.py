from logging import getLogger
from secrets import token_hex
from subprocess import Popen, PIPE, STDOUT, CalledProcessError

from .config import Archive, CONFIG_PATH

logger = getLogger(__name__)


def run_cmd(cmd: list[str]):
    with Popen(cmd, stdout=PIPE, stderr=STDOUT, universal_newlines=True) as proc:
        while True:
            if proc.stdout is None:
                break
            line = proc.stdout.readline()
            if not line:
                break
            logger.info('\t' + line.strip())
        if proc.stdout is not None:
            proc.stdout.close()
        return_code = proc.wait()
        if return_code:
            logger.error(CalledProcessError(return_code, cmd))


def init_command(config: list[Archive], archive: str):
    targets = [x for x in config if x.name == archive]

    for target in targets:
        name = f'{target.name}_{target.remote.name}'
        passwd = CONFIG_PATH / f'{name}.passwd'

        if not passwd.exists():
            passwd.write_text(token_hex(32))
            logger.info(f'Created passphrase file: {passwd}')


def list_command(config: list[Archive]):
    for backup in config:
        print(backup)
