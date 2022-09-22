import logging
from argparse import ArgumentParser
from typing import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__, command
from .config import ConfigValidationError, DEFAULT_CONFIG_FILE

logger = logging.getLogger(__package__)

CommandFunction = Callable[[Path, list[str]], None]


@dataclass
class ProgramArguments:
    command: CommandFunction
    config_file: Path
    archives: list[str] = field(default_factory=list)


def parse_args() -> ProgramArguments:

    command_functions: dict[str, CommandFunction] = {
        'version': lambda *_: print(__version__),
        'targets': command.targets_command,
        'init': command.init_command,
        'info': command.info_command,
        'list': command.list_command,
        'create': command.create_command,
        'key-export': command.key_export_command,
        'key-cleanup': command.key_cleanup_command,
    }

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
    for cmd in command_functions:
        subparser = command_subparser.add_parser(cmd)
        subparser.add_argument('archives', nargs='*')

    args = parser.parse_args()
    args.command = command_functions[args.command]

    return ProgramArguments(**args.__dict__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s │ %(levelname)-7s │ %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
    args = parse_args()

    try:
        args.command(args.config_file, args.archives)
    except ConfigValidationError as ex:
        logger.error(f'Error(s) encountered while reading configuration file: {ex}')
        ex.log_errors()
        exit(1)


if __name__ == "__main__":
    main()
