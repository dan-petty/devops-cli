"""Shared helpers of the readers of the inventory: file lookup, line lookup and parse errors (#3896)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import yaml

from devops_cli.exceptions.research import InventoryError

# The prefix of the digest in an image reference.
_DIGEST_PREFIX = "sha256:"


def relative(root: Path, path: Path) -> str:
    """The path of `path` from `root`, with `/` separators."""
    return path.relative_to(root).as_posix()


def matching_files(root: Path, *patterns: str) -> list[Path]:
    """The files of `root` that match a glob pattern, sorted, with none below a hidden directory.

    The first segment of a pattern may be hidden (`.github`): only the segments after it are held
    to the rule, so a copy of the repository under `.data/` or a `.terraform/` cache is not read.
    """
    found: set[Path] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            below = path.relative_to(root).parts[1:]
            if path.is_file() and not any(part.startswith(".") for part in below[:-1]):
                found.add(path)
    return sorted(found)


@contextmanager
def parse_errors(root: Path, path: Path) -> Iterator[None]:
    """Raise `InventoryError` that names `path` when the code in the block cannot read or parse it."""
    try:
        yield
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise InventoryError(
            f"Cannot read the pins of {relative(root, path)}: {exc}",
            details={"file": relative(root, path)},
        ) from exc


def split_image(reference: str) -> tuple[str, str]:
    """The name and the version of an image reference.

    The version is the tag; a reference with a digest and no tag gives the digest, and a reference
    with neither gives `latest`, which is what a pull of it gets. docker-py splits the reference
    by the Docker grammar. It strips only the digest of a reference with a tag and a digest, so the
    split is applied twice. docker-py is imported here, as a module-level import would slow every
    command that imports this module.
    """
    from docker.utils import parse_repository_tag

    name, tag = parse_repository_tag(reference)
    if tag and tag.startswith(_DIGEST_PREFIX):
        name, inner_tag = parse_repository_tag(name)
        return name, inner_tag or tag
    return name, tag or "latest"


def is_template(value: str) -> bool:
    """Whether `value` holds a template or a variable, so it names no image or version yet."""
    return any(mark in value for mark in ("{{", "${", "$("))


class LineIndex:
    """Finds the lines of a text that show a pin, for a file whose parser gives no line.

    Each call for the same text gives the next line that shows it, so two pins with the same text
    get two lines. A text that no line shows gives 0.
    """

    def __init__(self, text: str) -> None:
        self._lines = text.splitlines()
        self._cursor: dict[str, int] = {}

    def find(self, needle: str) -> int:
        """The next line (from 1) that holds `needle`."""
        return self._next(needle, lambda line: needle in line)

    def find_line(self, text: str) -> int:
        """The next line (from 1) that is `text`, with no space at either end."""
        return self._next(text, lambda line: line.strip() == text)

    def find_where(self, key: str, match: Callable[[str], bool]) -> int:
        """The next line (from 1) that `match` accepts. `key` names the search for the cursor."""
        return self._next(key, match)

    def _next(self, key: str, match: Callable[[str], bool]) -> int:
        for index in range(self._cursor.get(key, 0), len(self._lines)):
            if match(self._lines[index]):
                self._cursor[key] = index + 1
                return index + 1
        return 0
