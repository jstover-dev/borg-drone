import logging
from argparse import ArgumentParser
from typing import Any, Callable, Optional
from dataclasses import dataclass
from pathlib import Path

from . import __version__, command
from .util import setup_logging
from .config import ConfigValidationError, DEFAULT_CONFIG_FILE
from .types import OutputFormat, TargetTuple

logger = logging.getLogger(__package__)

CommandFunction = Callable[[Path, list[str]], None]


@dataclass
class ProgramArguments:
    command: str
    debug: bool
    config_file: Path
    force: bool = False
    format: OutputFormat = OutputFormat.text
    keyfile: Optional[Path] = None
    password_file: Optional[Path] = None
    TARGET: TargetTuple = None


# Map subcommands to a command function
command_functions: dict[str, Callable[[ProgramArguments], Any]] = {
    'version': lambda args: print(__version__),
    'generate-config': lambda args: command.generate_config_command(
        args.config_file,
        overwrite=args.force,
    ),
    'targets': lambda args: command.targets_command(
        args.config_file,
        output=OutputFormat(args.format),
    ),
    'init': lambda args: command.init_command(
        args.config_file,
        args.TARGET,
    ),
    'info': lambda args: command.info_command(
        args.config_file,
        args.TARGET,
    ),
    'list': lambda args: command.list_command(
        args.config_file,
        args.TARGET,
    ),
    'create': lambda args: command.create_command(
        args.config_file,
        args.TARGET,
    ),
    'key-export': lambda args: command.key_export_command(
        args.config_file,
        args.TARGET,
    ),
    'key-cleanup': lambda args: command.key_cleanup_command(
        args.config_file,
    ),
    'key-import': lambda args: command.key_import_command(
        args.config_file,
        args.TARGET,
        args.keyfile,
        args.password_file,
    )
}

HELP_TEXT = {
    'TARGET': 'Select targets using "[ARCHIVE]:[REPO]" syntax',
    'KEYFILE': 'Select borg repo key file',
    'PASSWORD_FILE': 'Select borg password file',
}


def parse_args() -> ProgramArguments:

    # pseudo-type for a string with format archive:repo
    def archive_target(text: str) -> TargetTuple:
        target = tuple(text.split(':', 1))
        if len(target) != 2:
            raise ValueError(f'String "{text}" does not match format "ARCHIVE:[REPO]"')
        return target[0].strip(), target[1].strip()

    parser = ArgumentParser()
    parser.add_argument(
        '--config-file',
        '-c',
        default=DEFAULT_CONFIG_FILE,
        type=Path,
        help='Path to configuration file',
        metavar='FILE',
    )

    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug logging')

    command_subparser = parser.add_subparsers(dest='command', required=True)

    # version
    command_subparser.add_parser('version')

    # generate-config
    genconf_subparser = command_subparser.add_parser('generate-config', help='Generate a default configuration file')
    genconf_subparser.add_argument('--force', '-f', action='store_true', default=False)

    # targets
    targets_subparser = command_subparser.add_parser('targets')
    targets_subparser.add_argument('--format', '-f', choices=OutputFormat.values(), default='text')

    # init
    init_subparser = command_subparser.add_parser('init', help='Run "borg init" on specified targets')
    init_subparser.add_argument('TARGET', type=archive_target, help=HELP_TEXT['TARGET'])

    # info
    info_subparser = command_subparser.add_parser('info', help='Run "borg info" on specified targets')
    info_subparser.add_argument('TARGET', type=archive_target, help=HELP_TEXT['TARGET'])

    # list
    list_subparser = command_subparser.add_parser('list', help='Run "borg list" on specified targets')
    list_subparser.add_argument('TARGET', type=archive_target, help=HELP_TEXT['TARGET'])

    # create
    create_subparser = command_subparser.add_parser('create', help='Create a new backup on specified targets')
    create_subparser.add_argument('TARGET', type=archive_target, help=HELP_TEXT['TARGET'])

    # key-export
    key_export_subparser = command_subparser.add_parser('key-export', help='Export and display secrets')
    key_export_subparser.add_argument('TARGET', type=archive_target, help=HELP_TEXT['TARGET'])

    # key-cleanup
    command_subparser.add_parser('key-cleanup', help='Remove unnecessary secrets from disk')

    # key-import
    key_import_subparser = command_subparser.add_parser('key-import', help='Import existing borg keyfile and password')
    key_import_subparser.add_argument('TARGET', type=archive_target, help=HELP_TEXT['TARGET'])
    key_import_subparser.add_argument('--keyfile', type=Path, required=True, help=HELP_TEXT['KEYFILE'])
    key_import_subparser.add_argument('--password-file', type=Path, default=None, help=HELP_TEXT['PASSWORD_FILE'])

    return ProgramArguments(**parser.parse_args().__dict__)


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)
    logger.debug(args)
    try:
        command_functions[args.command](args)
    except ConfigValidationError as ex:
        logger.error(f'Error(s) encountered while reading configuration file: {ex}')
        ex.log_errors()
        exit(1)
    except Exception as ex:
        logger.error(ex)
        exit(1)


if __name__ == "__main__":
    main()
