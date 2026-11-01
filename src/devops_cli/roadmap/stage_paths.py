"""The paths of a plan against the files of the staged commit (#3010).

The model cannot list files, and the issue body it reads cites paths of an older commit. So a plan
can name a file that does not exist: 25 of the 37 plans of 2026-10-31 did. `path_problems` finds
each such path in the reply. A path is missing when the commit does not hold it and no group up to
the group that names it creates it. The groups are in order, so a group sees the `creates` of the
groups before it and of itself.

A group names paths in four places: `reads`, `changes`, the code spans of its three tasks, and the
words of `verify`. Only the code spans of a task count, as the implement step reads those and no
other text (`step_files`). A word is a path when its last name ends in a suffix that a tracked file
has, or when its first folder is a top-level name of the tree. A label such as `status/blocked`, a
dotted name, an option, a URL or a placeholder is no path, and the check leaves it alone.
"""

from __future__ import annotations

import posixpath
import re
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from enum import StrEnum
from fnmatch import fnmatchcase
from glob import has_magic
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final, Self

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import git
from devops_cli.roadmap.step_files import code_spans

if TYPE_CHECKING:
    from devops_cli.roadmap.stage_change import StageGroup

# The most files with the same name that a problem lists.
SAME_NAME_MAX: Final[int] = 5
# A location after a path: `::test_name` of a test, or `:12` and `:12-20` of a line.
_LOCATION: Final[re.Pattern[str]] = re.compile(r"(?:::.*|:\d+(?:-\d+)?)$")
# The characters of a path word. A quote, a `$`, a `<`, a `*` or a `:` makes a word no path.
_WORD: Final[re.Pattern[str]] = re.compile(r"[\w.@+-]+(?:/[\w.@+-]+)*/?")
_PARENT_DIRECTORY: Final[str] = ".."


class _Place(StrEnum):
    """Where a group names a path."""

    READS = "reads"
    CHANGES = "changes"
    TASK = "task"
    VERIFY = "verify"


def _folders_of(path: str) -> set[str]:
    """The folders above `path`, without the root."""
    return {str(parent) for parent in PurePosixPath(path).parents} - {"."}


class StagedTree:
    """The tracked files of a checkout, with what the check needs to know about them: the folders
    above them, their suffixes, their top-level names and the files of each name."""

    def __init__(self, files: Iterable[str]) -> None:
        self._files = frozenset(files)
        self._folders = frozenset(folder for path in self._files for folder in _folders_of(path))
        self._suffixes = frozenset(PurePosixPath(path).suffix for path in self._files) - {""}
        self._tops = frozenset(path.partition("/")[0] for path in self._files)
        by_name: defaultdict[str, list[str]] = defaultdict(list)
        for path in sorted(self._files):
            by_name[PurePosixPath(path).name].append(path)
        self._by_name = dict(by_name)

    @classmethod
    def read(cls, source: Path, *, operation: str) -> Self:
        """The tracked files of the checkout at `source`: one `git ls-files`. A failed command
        raises `GitOperationError`, so the job never judges a plan on a tree it could not read."""
        listing = git(source, "ls-files", "-z", operation=operation)
        return cls(path for path in listing.split("\0") if path)

    @property
    def files(self) -> frozenset[str]:
        """The files of the tree."""
        return self._files

    def with_files(self, paths: Iterable[str]) -> StagedTree:
        """A tree that also holds `paths`: the files that the job itself writes."""
        return StagedTree([*self._files, *paths])

    def has(self, path: str) -> bool:
        """Whether the tree holds the file or the folder `path`, or a file that a glob matches."""
        path = path.rstrip("/")
        if path in self._files or path in self._folders:
            return True
        return has_magic(path) and any(fnmatchcase(file, path) for file in self._files)

    def same_name(self, path: str) -> list[str]:
        """The files of the tree with the file name of `path`, sorted, at most `SAME_NAME_MAX`."""
        return self._by_name.get(PurePosixPath(path).name, [])[:SAME_NAME_MAX]

    def as_path(self, word: str) -> str | None:
        """The path that `word` names, or None when the word is no path."""
        word = _LOCATION.sub("", word)
        if word.startswith("-") or not _WORD.fullmatch(word):
            return None
        path = posixpath.normpath(word)
        if path in {".", _PARENT_DIRECTORY} or path.startswith(f"{_PARENT_DIRECTORY}/"):
            return None
        known = PurePosixPath(path).suffix in self._suffixes or path.partition("/")[0] in self._tops
        return path if known else None

    def paths_in(self, text: str) -> list[str]:
        """The paths among the words of `text`."""
        return [path for word in text.split() if (path := self.as_path(word)) is not None]


def _named(group: StageGroup, tree: StagedTree) -> Iterator[tuple[_Place, str]]:
    """Each path that `group` names, with the place."""
    yield from ((_Place.READS, path) for path in group.reads)
    yield from ((_Place.CHANGES, path) for path in group.changes)
    for text in (group.test, group.implementation, group.documentation):
        for span in code_spans(text):
            yield from ((_Place.TASK, path) for path in tree.paths_in(span))
    yield from ((_Place.VERIFY, path) for path in tree.paths_in(group.verify))


def _problem(number: int, place: _Place, path: str, tree: StagedTree) -> str:
    texts = MESSAGES.roadmap
    same = tree.same_name(path)
    hint = (
        texts.stage_path_same_name.format(names=", ".join(f"`{name}`" for name in same))
        if same
        else texts.stage_path_no_same_name
    )
    return texts.stage_problem_path.format(
        group=number, path=path, place=texts.stage_path_places[place], hint=hint
    )


def path_problems(groups: Sequence[StageGroup], tree: StagedTree) -> list[str]:
    """One sentence for each path, named in `groups`, that `tree` lacks and that no group up to
    the one that names it creates. A path is named once, at its first place."""
    created: set[str] = set()
    reported: set[str] = set()
    problems: list[str] = []
    for number, group in enumerate(groups, start=1):
        for path in group.creates:
            created |= {path, *_folders_of(path)}
        for place, named in _named(group, tree):
            path = named.rstrip("/")
            if path in reported or path in created or tree.has(path):
                continue
            reported.add(path)
            problems.append(_problem(number, place, path, tree))
    return problems
