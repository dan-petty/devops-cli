"""The ADRs of a repository, as the alternatives check reads them (#3505).

An ADR is a file of `docs/adr/` named `<four digits>-<name>.md`. The check keeps its number, the
title of its first level-1 heading and its `Considered Options` section: each ADR of the project
records there the tools it chose and the tools it rejected, and a whole ADR holds many times the
tokens of its options. A repository with no `docs/adr/` has no ADR, and that is no error.

`names` is the test of the check whether a text names a tool. The check applies it to the title and
the body of an item, and to the text of an ADR.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from devops_cli.config.constants import CONST_ROADMAP_ADR_DIRECTORY
from devops_cli.exceptions.git import GitHubFileNotFoundError
from devops_cli.roadmap.step_files import MARKDOWN, section_text
from devops_cli.roadmap.store import RoadmapStore

_ADR_NAME = re.compile(r"(?P<number>\d{4})-.+\.md")
_OPTIONS_TITLE = frozenset({"considered options"})
# A space, `-`, `_` or `.` between the words of a tool name is one separator, so "Argo Workflows"
# names `argo-workflows`.
_SEPARATOR = r"[\s._-]+"


@dataclass(frozen=True)
class Adr:
    """What the check keeps of one ADR: its number, its title and its `Considered Options`
    section with the heading, or no text when it has none."""

    number: int
    title: str
    options: str

    @property
    def entry(self) -> str:
        """The ADR as the request to the model shows it: its number as four digits and its title,
        then its options."""
        head = f"ADR {self.number:04d}: {self.title}"
        return f"{head}\n{self.options}" if self.options else head


def _number_of(path: str) -> int | None:
    """The number in the file name of `path`, or None when the name is no ADR name."""
    found = _ADR_NAME.fullmatch(PurePosixPath(path).name)
    return int(found["number"]) if found else None


def _title_of(text: str) -> str | None:
    """The text of the first level-1 heading of `text`, or None when it has none."""
    tokens = MARKDOWN.parse(text)
    for index, token in enumerate(tokens[:-1]):
        if token.type == "heading_open" and token.tag == "h1" and token.level == 0:
            return tokens[index + 1].content.strip() or None
    return None


def adr_of(path: str, text: str) -> Adr | None:
    """The ADR that the file `path` holds as `text`, or None when its name is no ADR name or it
    has no title."""
    number = _number_of(path)
    title = _title_of(text)
    if number is None or title is None:
        return None
    return Adr(number, title, section_text(text, _OPTIONS_TITLE))


def read_adrs(store: RoadmapStore) -> tuple[Adr, ...]:
    """The ADRs of the repository on its default branch, the highest number first, so that a cut
    of the text drops the oldest first. A repository with no `docs/adr/` has none. Any other
    failed read raises."""
    try:
        paths = store.repository_files(CONST_ROADMAP_ADR_DIRECTORY)
    except GitHubFileNotFoundError:
        return ()
    adrs = (
        adr_of(path, store.repository_file(path)) for path in paths if _number_of(path) is not None
    )
    return tuple(sorted((adr for adr in adrs if adr is not None), key=lambda adr: -adr.number))


def names(text: str, name: str) -> bool:
    """Whether `text` names the tool `name`: it holds the last segment of `name` (the part after
    `owner/` of a repository, or a package name) as a whole word. The test ignores case and takes
    a space, `-`, `_` and `.` as one separator. A letter, a digit, `_` or `-` next to the name
    means it is part of a longer word, so `pytest-cov` does not name `pytest`."""
    parts = [re.escape(part) for part in re.split(_SEPARATOR, name.rsplit("/", 1)[-1]) if part]
    if not parts:
        return False
    word = _SEPARATOR.join(parts)
    return re.search(rf"(?<![\w-]){word}(?![\w-])", text, re.IGNORECASE) is not None


__all__ = ["Adr", "adr_of", "names", "read_adrs"]
