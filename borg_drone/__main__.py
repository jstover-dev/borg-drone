import logging
from argparse import ArgumentParser
from typing import Callable, Any
from dataclasses import dataclass
from pathlib import Path

from . import __version__, command
from .config import ConfigValidationError, DEFAULT_CONFIG_FILE

logger = logging.getLogger(__package__)

CommandFunction = Callable[[Path, list[str]], None]


@dataclass
class ProgramArguments:
    command: str
    config_file: Path
    target: tuple[str, str] = None
    targets: list[tuple[str, str]] = None
    archives: list[str] = None
    keyfile: Path = None
    password_file: Path = None


@dataclass
class Command:
    name: str


# pseudo-type for a string with format archive:repo
def archive_target(text: str) -> tuple[str, str]:
    target = tuple(text.split(':', 1))
    if len(target) != 2:
        raise ValueError(f'String "{text}" does not match format "REPO:ARCHIVE"')
    return target[0], target[1]


def parse_args() -> Callable:

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
    command_subparser.add_parser('targets')

    init_subparser = command_subparser.add_parser('init')
    init_subparser.add_argument('archives', nargs='*')

    info_subparser = command_subparser.add_parser('info')
    info_subparser.add_argument('archives', nargs='*')

    list_subparser = command_subparser.add_parser('list')
    list_subparser.add_argument('archives', nargs='*')

    create_subparser = command_subparser.add_parser('create')
    create_subparser.add_argument('archives', nargs='*')

    key_export_subparser = command_subparser.add_parser('key-export')
    key_export_subparser.add_argument('archives', nargs='*')

    key_cleanup_subparser = command_subparser.add_parser('key-cleanup')
    key_cleanup_subparser.add_argument('archives', nargs='*')

    key_import_subparser = command_subparser.add_parser('key-import')
    key_import_subparser.add_argument('target', type=archive_target)
    key_import_subparser.add_argument('--keyfile', type=Path, required=True)
    key_import_subparser.add_argument('--password-file', type=Path, default=None)

    command_functions: dict[str, Callable[[ProgramArguments], Any]] = {
        'version': lambda args: print(__version__),
        'targets': lambda args: command.targets_command(args.config_file),
        'init': lambda args: command.init_command(args.config_file, args.targets),
        'info': lambda args: command.info_command(args.config_file, args.targets),
        'list': lambda args: command.list_command(args.config_file, args.archives),
        'create': lambda args: command.create_command(args.config_file, args.archives),
        'key-export': lambda args: command.key_export_command(args.config_file, args.archives),
        'key-cleanup': lambda args: command.key_cleanup_command(args.config_file, args.archives),
        'key-import': lambda args: command.key_import_command(args.config_file, args.target, args.keyfile, args.password_file)
    }

    program_args = ProgramArguments(**parser.parse_args().__dict__)

    return lambda: command_functions[program_args.command](program_args)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s │ %(levelname)-7s │ %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
    run_command = parse_args()

    try:
        run_command()
    except ConfigValidationError as ex:
        logger.error(f'Error(s) encountered while reading configuration file: {ex}')
        ex.log_errors()
        exit(1)


if __name__ == "__main__":
    main()
