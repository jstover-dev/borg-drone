from collections.abc import Generator
from enum import Enum
from typing import Optional

EnvironmentMap = Optional[dict[str, str]]
StringGenerator = Generator[str, None, None]

TargetTuple = Optional[tuple[str, str]]


class OutputFormat(Enum):
    json = 'json'
    yaml = 'yaml'
    text = 'text'
    python = 'python'

    @classmethod
    def values(cls) -> list[str]:
        return [str(x.value) for x in cls]
