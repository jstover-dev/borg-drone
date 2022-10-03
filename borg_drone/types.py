from collections.abc import Generator
from enum import Enum
from typing import Optional

EnvironmentMap = Optional[dict[str, str]]
StringGenerator = Generator[str, None, None]

TargetTuple: tuple[str, str]


class OutputFormat(Enum):
    json = 'json'
    yaml = 'yaml'
    text = 'text'

    @classmethod
    def values(cls):
        return [x.value for x in cls]
