from logging import getLogger
from secrets import token_hex

from .config import Archive, CONFIG_PATH

logger = getLogger(__name__)


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
