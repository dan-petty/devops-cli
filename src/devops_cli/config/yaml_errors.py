"""One way to read a config file that a YAML parser cannot load (#2451).

A config file can hold a credential. The message of a PyYAML error quotes the line where the parser
stopped, and the `buffer` of its mark holds the full text of the file. The safe loader of PyYAML and
the round-trip loader of ruamel.yaml also raise `ValueError`, `KeyError`, `IndexError` or
`AttributeError` for a tagged value that they cannot build, such as `!!int <text>`, and the message
quotes the value. They raise `RecursionError` for a document that nests too deep. The decode of a
file that is not UTF-8 raises `UnicodeDecodeError`, whose `object` holds the bytes of the file.

`load_yaml` turns each of these errors into one ConfigurationError that names the file, the type of
the error, and its line and column when the error has a mark. The error quotes no text of the file.
It has no cause and no context that holds the first error. This module does not import ruamel.yaml,
which the start of every command would then load. A caller that parses with ruamel.yaml passes the
error class of ruamel.yaml in `errors`.
"""

from __future__ import annotations

from collections.abc import Callable

import yaml

from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import ERRORS

# The errors of `yaml.safe_load` and of the UTF-8 decode: `UnicodeDecodeError` is a `ValueError`,
# and `KeyError` and `IndexError` are `LookupError`s. `tests/config/test_config_file_that_is_not_yaml.py`
# holds a file for each. An `OSError` names only the file, so it is not here and goes up.
YAML_LOAD_ERRORS: tuple[type[Exception], ...] = (
    yaml.YAMLError,
    ValueError,
    LookupError,
    AttributeError,
    RecursionError,
)


def load_yaml[T](
    parse: Callable[[], T],
    *,
    name: str,
    action: str,
    errors: tuple[type[Exception], ...] = YAML_LOAD_ERRORS,
) -> T:
    """The result of `parse`, which reads the YAML of the file `name`.

    An error of `errors` raises ConfigurationError. Its message starts with `action`, such as
    `Cannot read the config file`. The error is raised after the `except` block, so it has no cause
    and no context. Another error, such as an `OSError`, goes up as it is.
    """
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
    no mark. PyYAML and ruamel.yaml give the same `problem_mark`. A function reads it, so that no
    frame of the traceback of the ConfigurationError holds the mark."""
    mark = getattr(exc, "problem_mark", None)
    if mark is None:
        return ""
    return ERRORS.config.not_yaml_location.format(line=mark.line + 1, column=mark.column + 1)
