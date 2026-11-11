"""One way to read a config file, and one way to report a config file that does not load (#2451,
#4481).

A settings save writes a config file with ruamel.yaml, which writes YAML 1.2 (`round_trip`). So
`parse_config_yaml` reads a config file as YAML 1.2, with the safe loader of the same library. A
YAML 1.1 reader, such as PyYAML, reads a bare `off`, `on`, `yes` or `no` as a bool and a bare
`12:30` as the number 750, so a string that a save wrote changed type at the next load.

A config file can hold a credential. The message of a YAML error quotes the line where the parser
stopped, and its mark holds the text of the file. The loaders of ruamel.yaml also raise
`ValueError`, `KeyError`, `IndexError` or `AttributeError` for a tagged value that they cannot
build, such as `!!int <text>`, and the message quotes the value. They raise `RecursionError` for a
document that nests too deep. The decode of a file that is not UTF-8 raises `UnicodeDecodeError`,
whose `object` holds the bytes of the file.

`load_yaml` turns each of these errors into one ConfigurationError that names the file, the type of
the error, and its line and column when the error has a mark. The error quotes no text of the file.
It has no cause and no context that holds the first error.

Each function imports ruamel.yaml when it runs. The settings module imports this module, and the
import of ruamel.yaml adds 29 modules, so a command that reads no config file does not pay for it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final

from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import ERRORS

# The errors of a value that a loader cannot build, and of the UTF-8 decode: `UnicodeDecodeError`
# is a `ValueError`, and `KeyError` and `IndexError` are `LookupError`s. The round trip raises
# `AttributeError` for `!!omap <text>`. `tests/config/test_config_file_that_is_not_yaml.py` and
# `tests/config/test_config_yaml_load_errors.py` hold a file for each. An `OSError` names only the
# file, so it is not here and goes up.
_BUILD_ERRORS: Final[tuple[type[Exception], ...]] = (
    ValueError,
    LookupError,
    AttributeError,
    RecursionError,
)


def yaml_load_errors() -> tuple[type[Exception], ...]:
    """The errors of a load of a config file: the `YAMLError` of ruamel.yaml, and the errors of a
    value that the loader cannot build."""
    from ruamel.yaml.error import YAMLError

    return (YAMLError, *_BUILD_ERRORS)


def parse_config_yaml(text: str | bytes) -> Any:
    """The YAML 1.2 document of the config file text `text`, or None when it holds no document.

    The safe loader of ruamel.yaml builds only plain types. `pure=True` keeps the Python parser of
    YAML 1.2 also when ruamel.yaml.clib is installed. A new loader for each call shares no state
    between threads. A key that a mapping holds two times raises `DuplicateKeyError`.
    """
    from ruamel.yaml import YAML

    return YAML(typ="safe", pure=True).load(text)


def load_yaml[T](parse: Callable[[], T], *, name: str, action: str) -> T:
    """The result of `parse`, which reads the YAML of the file `name`.

    An error of `yaml_load_errors()` raises ConfigurationError. Its message starts with `action`,
    such as `Cannot read the config file`. The error is raised after the `except` block, so it has
    no cause and no context. Another error, such as an `OSError`, goes up as it is.
    """
    errors = yaml_load_errors()
    try:
        return parse()
    except errors as exc:
        error_type, location = type(exc).__name__, yaml_error_location(exc)
    raise ConfigurationError(
        ERRORS.config.not_yaml.format(
            action=action, path=name, error_type=error_type, location=location
        )
    )


def yaml_error_location(exc: Exception) -> str:
    """` at line <n>, column <n>` where a parser stopped, counted from 1, or "" when the error has
    no mark. A function reads it, so that no frame of the traceback of the ConfigurationError holds
    the mark."""
    mark = getattr(exc, "problem_mark", None)
    if mark is None:
        return ""
    return ERRORS.config.not_yaml_location.format(line=mark.line + 1, column=mark.column + 1)
