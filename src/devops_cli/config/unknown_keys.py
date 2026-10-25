"""The error for the config file keys that a settings section refuses (#2201).

The `ai` section and each section under it refuse a key that they do not declare (`extra="forbid"`
in pydantic). The validation error of pydantic gives only the location of such a key in the merged
settings. This error also gives the file and the line of each key, the release that removed the key
when `CONST_REMOVED_CONFIG_KEYS` holds it, and the `devops config unset` command that removes it.
That command edits the file and loads no settings, so it works while the key stops the load.
"""

from __future__ import annotations

import shlex
from collections.abc import Iterable, Sequence
from pathlib import Path

from pydantic import ValidationError

from devops_cli.config.constants import (
    CONST_AI_SERVING_SETTINGS,
    CONST_CONFIG_UNSET_COMMAND,
    CONST_PROJECT_CONFIG_ENV,
    CONST_PYDANTIC_EXTRA_FORBIDDEN,
    CONST_REMOVED_CONFIG_KEYS,
)
from devops_cli.config.round_trip import KeyPath, find
from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import ERRORS

# A key in a config file: the index of the file in the files searched, the file, and the line.
_Location = tuple[int, Path, int]


def refused_keys(error: ValidationError) -> list[KeyPath]:
    """The key path of each key that a settings section refuses, from the validation error of the
    merged settings."""
    return [
        tuple(str(part) for part in item["loc"])
        for item in error.errors(include_url=False, include_input=False)
        if item["type"] == CONST_PYDANTIC_EXTRA_FORBIDDEN
    ]


def unknown_keys_error(
    keys: Sequence[KeyPath], files: Iterable[Path | None], *, active: Path
) -> ConfigurationError:
    """The error that gives one line for each of `keys`: the file and the line of the key in the
    first of `files` that holds it, the reason when one is known, and the command that removes it.

    The lines go in the order of the files and of the lines in them, and a key that no file holds
    goes last. `active` is the file that `devops config unset` edits. For a key in another file,
    the command sets `DEVOPS_CLI_CONFIG` to that file.
    """
    texts = [
        (path, path.read_text(encoding="utf-8"))
        for path in files
        if path is not None and path.is_file()
    ]
    located = sorted(
        ((key, _locate(".".join(key), texts)) for key in keys),
        key=lambda item: (0, item[1][0], item[1][2]) if item[1] else (1, 0, 0),
    )
    dotted = [".".join(key) for key, _ in located]
    return ConfigurationError(
        "\n".join(_describe(key, where, active) for key, where in located),
        key=dotted[0],
        details={"unknown_keys": dotted},
    )


def _locate(dotted: str, texts: Sequence[tuple[Path, str]]) -> _Location | None:
    """The first file of `texts` that holds the key `dotted`, with its index and the line."""
    for index, (path, text) in enumerate(texts):
        found = find(text, dotted, name=str(path))
        if found is not None:
            return index, path, found[1]
    return None


def _describe(key: KeyPath, where: _Location | None, active: Path) -> str:
    """The line of the error for one key."""
    dotted = ".".join(key)
    command = f"{CONST_CONFIG_UNSET_COMMAND} {shlex.quote(dotted)}"
    location = ""
    if where is not None:
        _, path, line = where
        location = ERRORS.config.unknown_key_location.format(path=path, line=line)
        if path.resolve() != active.resolve():
            command = f"{CONST_PROJECT_CONFIG_ENV}={shlex.quote(str(path))} {command}"
    return ERRORS.config.unknown_key.format(
        key=dotted, location=location, reason=_reason(key), command=command
    )


def _reason(key: KeyPath) -> str:
    """Why the settings do not declare the key, when the table of removed keys or the per-model
    sampling and serving settings tell it, else nothing."""
    release = CONST_REMOVED_CONFIG_KEYS.get(".".join(key))
    if release is not None:
        return ERRORS.config.unknown_key_removed.format(release=release)
    if key[-1] in CONST_AI_SERVING_SETTINGS:
        return ERRORS.config.unknown_key_serving
    return ""
