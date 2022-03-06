import logging
from argparse import ArgumentParser
from typing import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import command
from .config import Archive, ConfigValidationError, DEFAULT_CONFIG_FILE, filter_archives, parse_config

logger = logging.getLogger(__package__)


@dataclass
class ProgramArguments:
    command: Callable
    config_file: Path
    archives: list[str] = field(default_factory=list)


GLOBAL_COMMANDS = {
    'list': command.list_command,
}

ARCHIVE_COMMANDS = {
    'init': command.init_command,
    'info': command.info_command,
    'create': command.create_command,
    'key-export': command.key_export_command,
    'key-cleanup': command.key_cleanup_command,
}


def parse_args() -> ProgramArguments:
    parser = ArgumentParser()
    parser.add_argument(
        "--config-file",
        "-c",
        default=DEFAULT_CONFIG_FILE,
        type=Path,
        help="Path to configuration file",
        metavar="FILE")

    command_subparser = parser.add_subparsers(dest='command', required=True)

    for cmd in GLOBAL_COMMANDS:
        command_subparser.add_parser(cmd)

    for cmd in ARCHIVE_COMMANDS:
        subparser = command_subparser.add_parser(cmd)
        subparser.add_argument('archives', nargs='+')

    args = parser.parse_args()
    return ProgramArguments(**args.__dict__)


def read_config(file: Path) -> list[Archive]:
    try:
        return parse_config(file)
    except ConfigValidationError as ex:
        logger.error(f"Error(s) while parsing config file {file}: \n{ex}")
        exit(1)
    except FileNotFoundError:
        if file == DEFAULT_CONFIG_FILE:
            with file.open('w') as f:
                yaml.dump({'repositories': {}, 'archives': {}}, f)
            return read_config(file)
        else:
            logging.error(f'Unable to read configuration file: {file}')
            exit(1)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format=' %(name)s | %(asctime)s | %(levelname)-8s | %(message)s',
    )
    args = parse_args()

    archives = read_config(args.config_file)
    logger.info(f'Configuration file: {args.config_file}')

    if args.command in GLOBAL_COMMANDS:
        GLOBAL_COMMANDS[str(args.command)](archives)

    elif args.command in ARCHIVE_COMMANDS:
        ARCHIVE_COMMANDS[str(args.command)](filter_archives(archives, names=args.archives))


if __name__ == "__main__":
    main()
