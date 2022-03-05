import sys
import logging
from argparse import ArgumentParser
from typing import Callable, Optional
from dataclasses import dataclass
from pathlib import Path

from . import borg_commands
from .config import ConfigValidationError, parse_config, Archive, CONFIG_PATH


@dataclass
class ProgramArguments:
    command: Callable
    config_file: Path
    archive: Optional[str] = None


def parse_args() -> ProgramArguments:
    parser = ArgumentParser()
    parser.add_argument(
        "--config-file",
        "-c",
        default=CONFIG_PATH / "config.yml",
        type=Path,
        help="Path to configuration file",
        metavar="FILE")

    command_subparser = parser.add_subparsers(dest='command', required=True)

    list_parser = command_subparser.add_parser('list')

    init_parser = command_subparser.add_parser('init')
    init_parser.add_argument('archive')

    return ProgramArguments(**parser.parse_args().__dict__)


def read_config() -> list[Archive]:
    cfg_file = Path(__file__).parents[1] / "example.yml"
    try:
        return parse_config(cfg_file)
    except ConfigValidationError as ex:
        print(f"Error(s) while parsing config file {cfg_file}: \n{ex}", file=sys.stderr)
        exit(1)


def main():
    logging.basicConfig(level=logging.INFO)
    args = parse_args()

    if args.command == 'list':
        borg_commands.list_command(read_config())

    elif args.command == 'init':
        borg_commands.init_command(read_config(), args.archive)


if __name__ == "__main__":
    main()
