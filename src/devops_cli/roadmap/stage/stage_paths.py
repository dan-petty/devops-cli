"""The paths of a plan against the files of the staged commit (#3010).

The model cannot list files, and the issue body it reads cites paths of an older commit. So a plan
can name a file that does not exist: 25 of the 37 plans of 2026-10-31 did. `path_problems` finds
each such path in the reply and in the change folder of a plan pull request: a group lists a new
file in the `creates` list of a reply, or marks it ` (new)` on its `Changes:` line in `tasks.md`. A
path is missing when the commit does not hold it and no group up to the group that names it creates
it. The groups are in order, so a group sees the `creates` of the groups before it and of itself.

A group names paths in four places: `reads`, `changes`, the code spans of its three tasks, and the
words of `verify`. The paths of a negative search are the paths of its fixed shape (#3263). Only
the code spans of a task count, as the implement step reads those and no other text
(`step_files`). A word is a path when its last name ends in a suffix that a tracked file
has, or when its first folder is a top-level name of the tree. A word with no folder is no path:
it is a search pattern or a fixture that a test writes at run time (`ruff.toml`), and the implement
step accepts a name that holds no file as a file it creates. A label such as `status/blocked`, a
dotted name, an option, a URL or a placeholder is no path either, and the check leaves it alone.
`reads` and `changes` list paths by definition, so the check keeps them strict.
"""

from __future__ import annotations

import posixpath
import re
import shlex
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from enum import StrEnum
from fnmatch import fnmatchcase
from glob import has_magic
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final, Self

from devops_cli.config.constants import CONST_GIT_CLI
from devops_cli.core.process import run_subprocess
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import git
from devops_cli.roadmap.implement.implement_shell_policy import (
    NEGATIVE_SEARCH_WORD,
    read_negative_search,
)
from devops_cli.roadmap.step_files import code_spans

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage_change import StageGroup

# The most files with the same name that a problem lists.
SAME_NAME_MAX: Final[int] = 5
# A location after a path: `::test_name` of a test, or `:12` and `:12-20` of a line.
_LOCATION: Final[re.Pattern[str]] = re.compile(r"(?:::.*|:\d+(?:-\d+)?)$")
# The characters of a path word. A quote, a `$`, a `<`, a `*` or a `:` makes a word no path.
_WORD: Final[re.Pattern[str]] = re.compile(r"[\w.@+-]+(?:/[\w.@+-]+)*/?")
_PARENT_DIRECTORY: Final[str] = ".."
# The folder the stage job writes: a group never changes or creates a path in it.
_CHANGES_DIRECTORY: Final[str] = "openspec/changes"


class _Place(StrEnum):
    """Where a group names a path."""

    READS = "reads"
    CHANGES = "changes"
    TASK = "task"
    VERIFY = "verify"


def _folders_of(path: str) -> set[str]:
    """The folders above `path`, without the root."""
    return {str(parent) for parent in PurePosixPath(path).parents} - {"."}


def change_folder_paths(paths: Iterable[str]) -> list[str]:
    """The paths in `paths` that are the change folder or sit under it. A group never writes
    there: the stage job writes the change, and the groups are the steps after it (#3285)."""
    return [
        path
        for path in paths
        if path == _CHANGES_DIRECTORY or path.startswith(f"{_CHANGES_DIRECTORY}/")
    ]


class StagedTree:
    """The tracked files of a checkout, with what the check needs to know about them: the folders
    above them, their suffixes, their top-level names and the files of each name."""

    def __init__(self, files: Iterable[str], *, source: Path | None = None) -> None:
        self._source = source
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
        return cls((path for path in listing.split("\0") if path), source=source)

    @property
    def source(self) -> Path | None:
        """The source directory of the checkout, or None."""
        return self._source

    @property
    def files(self) -> frozenset[str]:
        """The files of the tree."""
        return self._files

    def with_files(self, paths: Iterable[str]) -> StagedTree:
        """A tree that also holds `paths`: the files that the job itself writes."""
        return StagedTree([*self._files, *paths], source=self._source)

    def callers(self, name: str) -> list[str]:
        """The files under `src/` that call the function `name`, except definition lines."""
        if self._source is None:
            return []
        proc = run_subprocess(
            [CONST_GIT_CLI, "-C", str(self._source), "grep", "-n", "-F", "--", f"{name}(", "src"],
            check=False,
            quiet=True,
        )
        if proc.returncode != 0:
            return []
        calling_files: set[str] = set()
        def_prefix = f"def {name}("
        async_def_prefix = f"async def {name}("
        for line in proc.stdout.splitlines():
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            path, _lineno, content = parts
            stripped = content.strip()
            if stripped.startswith(def_prefix) or stripped.startswith(async_def_prefix):
                continue
            calling_files.add(path)
        return sorted(calling_files)

    def has(self, path: str) -> bool:
        """Whether the tree holds the file or the folder `path`, or a file that a glob matches."""
        path = path.rstrip("/")
        if path in self._files or path in self._folders:
            return True
        return has_magic(path) and any(fnmatchcase(file, path) for file in self._files)

    def has_folder(self, path: str) -> bool:
        """Whether the tree holds the folder `path`."""
        return path.rstrip("/") in self._folders

    def same_name(self, path: str) -> list[str]:
        """The files of the tree with the file name of `path`, sorted, at most `SAME_NAME_MAX`."""
        return self._by_name.get(PurePosixPath(path).name, [])[:SAME_NAME_MAX]

    def as_path(self, word: str) -> str | None:
        """The path that `word` names, or None when the word is no path."""
        word = _LOCATION.sub("", word)
        if word.startswith("-") or not _WORD.fullmatch(word):
            return None
        path = posixpath.normpath(word)
        if "/" not in path or path.startswith(f"{_PARENT_DIRECTORY}/"):
            return None
        known = PurePosixPath(path).suffix in self._suffixes or path.partition("/")[0] in self._tops
        return path if known else None

    def paths_in(self, text: str) -> list[str]:
        """The paths among the words of `text`."""
        return [path for word in text.split() if (path := self.as_path(word)) is not None]

    def code_span_paths(self, text: str) -> list[str]:
        """The paths among the code spans of `text`, in order. Only a code span names a path: the
        other words of a text are prose that a check leaves alone."""
        return [path for span in code_spans(text) for path in self.paths_in(span)]


def _keep_slash(path: str) -> str:
    """`path` in normal form, with the trailing slash kept: a path that ends in `/` is a folder,
    and `README.md/` matches nothing in git."""
    return posixpath.normpath(path) + ("/" if path.endswith("/") else "")


def _verify_paths(verify: str, tree: StagedTree) -> list[str]:
    """The paths that the `verify` command names. A negative search names its paths for sure: the
    reader of the step gives them, one-folder words such as `src/` included, which `as_path`
    leaves alone. A path that is no file of the commit and that no group creates would make the
    search find nothing, and the check pass. `.` is the whole tree. Any other command names the
    words that look like paths."""
    try:
        words = shlex.split(verify)
    except ValueError:
        return tree.paths_in(verify)
    if words[:1] == [NEGATIVE_SEARCH_WORD] and not isinstance(
        found := read_negative_search(words), str
    ):
        return [_keep_slash(path) for path in found.paths if posixpath.normpath(path) != "."]
    return tree.paths_in(verify)


def _named(group: StageGroup, tree: StagedTree) -> Iterator[tuple[_Place, str]]:
    """Each path that `group` names, with the place."""
    yield from ((_Place.READS, path) for path in group.reads)
    yield from ((_Place.CHANGES, path) for path in group.changes)
    for text in (group.test, group.implementation, group.documentation, group.process):
        yield from ((_Place.TASK, path) for path in tree.code_span_paths(text or ""))
    yield from ((_Place.VERIFY, path) for path in _verify_paths(group.verify or "", tree))


def _problem(number: int, place: _Place, path: str, tree: StagedTree, later: int | None) -> str:
    """The sentence for a missing path; `later` is the group after `number` that creates it."""
    texts = MESSAGES.roadmap
    where = texts.stage_path_places[place]
    if later is not None:
        return texts.stage_problem_path_later.format(
            group=number, path=path, place=where, later=later
        )
    same = tree.same_name(path)
    hint = (
        texts.stage_path_same_name.format(names=", ".join(f"`{name}`" for name in same))
        if same
        else texts.stage_path_no_same_name
    )
    return texts.stage_problem_path.format(group=number, path=path, place=where, hint=hint)


def _first_creators(groups: Sequence[StageGroup]) -> dict[str, int]:
    """For each path, and each folder above it, that a group lists in `creates`: the number of
    the first group that does."""
    first: dict[str, int] = {}
    for number, group in enumerate(groups, start=1):
        for path in group.creates:
            for created in (path, *_folders_of(path)):
                first.setdefault(created, number)
    return first


_ADD_PARAMETER: Final[re.Pattern[str]] = re.compile(
    r"\bAdd\s+.+?\s+to\s+`([A-Za-z_][A-Za-z0-9_]*)`"
)


def changed_functions(groups: Sequence[StageGroup]) -> list[str]:
    """The function names that task texts of `groups` add a parameter to."""
    functions: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for text in (group.test, group.implementation, group.documentation, group.process):
            if not text:
                continue
            for match in _ADD_PARAMETER.finditer(text):
                fn = match.group(1)
                if fn not in seen:
                    seen.add(fn)
                    functions.append(fn)
    return functions


def caller_problems(groups: Sequence[StageGroup], tree: StagedTree) -> list[str]:
    """One sentence for each file calling a changed function that `groups` omit from `changes`."""
    if tree.source is None:
        return []
    functions = changed_functions(groups)
    if not functions:
        return []
    all_changes = {path for group in groups for path in group.changes}
    problems: list[str] = []
    for function in functions:
        for caller in tree.callers(function):
            if caller not in all_changes:
                problems.append(
                    MESSAGES.roadmap.stage_problem_missing_caller.format(
                        function=function, path=caller
                    )
                )
    return problems


def path_problems(groups: Sequence[StageGroup], tree: StagedTree) -> list[str]:
    """One sentence for each path, named in `groups`, that `tree` lacks and that no group up to
    the one that names it creates. A path is named once, at its first place. When a later group
    creates the path, the sentence names that group too."""
    creators = _first_creators(groups)
    created: set[str] = set()
    reported: set[str] = set()
    problems: list[str] = []
    for number, group in enumerate(groups, start=1):
        for path in group.creates:
            created |= {path, *_folders_of(path)}
        # A group never writes the change folder or a file under it (#3285): the check holds even
        # for a path the tree holds or a group lists in `creates`, which outrank the next checks.
        for written in change_folder_paths([*group.changes, *group.creates]):
            if written in reported:
                continue
            reported.add(written)
            problems.append(MESSAGES.roadmap.stage_bad_change_path.format(path=written))
        for place, named in _named(group, tree):
            path = named.rstrip("/")
            exists = tree.has_folder(path) if named.endswith("/") else tree.has(path)
            if path in reported or path in created or exists:
                continue
            reported.add(path)
            problems.append(_problem(number, place, path, tree, creators.get(path)))
    problems.extend(caller_problems(groups, tree))
    return problems
