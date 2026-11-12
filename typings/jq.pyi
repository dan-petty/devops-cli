"""The part of jq.py 1.13.0 that devops-cli calls. jq.py ships no type information."""

from typing import Any

class _ProgramWithInput:
    def all(self) -> list[Any]: ...

class _Program:
    def input_value(self, value: Any) -> _ProgramWithInput: ...

def compile(program: str, args: dict[str, Any] | None = None) -> _Program: ...
