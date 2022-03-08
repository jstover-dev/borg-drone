import logging
from argparse import ArgumentParser
from typing import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import __version__, command
from .config import Archive, ConfigValidationError, DEFAULT_CONFIG_FILE, filter_archives, parse_config

logger = logging.getLogger(__package__)


@dataclass
class ProgramArguments:
    command: Callable[[list[Archive]], None]
    config_file: Path
    archives: list[str] = field(default_factory=list)


COMMANDS: dict[str, Callable[[list[Archive]], None]] = {
    'targets': command.target_command,
    'init': command.init_command,
    'info': command.info_command,
    'list': command.list_command,
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
        metavar="FILE",
    )
    command_subparser = parser.add_subparsers(dest='command', required=True)

    command_subparser.add_parser('version')

    for cmd in COMMANDS:
        subparser = command_subparser.add_parser(cmd)
        subparser.add_argument('archives', nargs='*')

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


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s │ %(levelname)-7s │ %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
    args = parse_args()

    if args.command == 'version':
        print(__version__)
        exit(0)

    targets = read_config(args.config_file)
    logger.info(f'Configuration file: {args.config_file}')

    if args.archives:
        targets = filter_archives(targets, names=args.archives)

    if not targets:
        logger.info('No matching targets found in configuration file!')
        exit(1)

    COMMANDS[str(args.command)](targets)


if __name__ == "__main__":
    main()
