"""A move of a set of modules by name prefix, and the check that it covers the set (#3372).

A task group moves a top-level Python module by a name prefix when its `changes` holds the old
path `<folder>/<stem>.py` and its `creates` holds a new path under `<folder>/<prefix>/`, where
`<prefix>` is the stem up to its first `_`, or the whole stem. `move_prefix_problems` requires
every top-level module of that prefix in the staged tree to appear in the `changes` of a group,
so a plan that moves `stage_ready.py` and leaves `stage_verify.py` is refused. It reads no
`test_*` module and no `conftest.py`: those names are no module of a job prefix.

`move_verify_problems` refuses a move group whose `! git grep` literal equals the import path of
one module of the prefix, the bare prefix included. A search for `devops_cli.roadmap.stage.stage`
matches the old `stage.py` and the new `stage/` package, so it proves nothing after the move. A
search for the dotted prefix `devops_cli.roadmap.stage_` covers every module of the prefix.
"""

from __future__ import annotations

import shlex
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Final

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement.implement_shell_policy import (
    NEGATIVE_SEARCH_WORD,
    read_negative_search,
)

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage_change import StageGroup
    from devops_cli.roadmap.stage.stage_paths import StagedTree

_PYTHON_SUFFIX: Final[str] = ".py"
_TEST_MODULE_PREFIX: Final[str] = "test_"
_CONFTEST: Final[str] = "conftest.py"
_SOURCE_DIRECTORY: Final[str] = "src"


@dataclass(frozen=True)
class _PrefixMove:
    """A group that moves the modules of one prefix, and the modules of the prefix in the tree."""

    number: int
    folder: PurePosixPath
    prefix: str
    modules: tuple[str, ...]

    @property
    def import_path(self) -> str:
        """The import path of the folder, such as `devops_cli.roadmap`."""
        parts = self.folder.parts
        if parts[:1] == (_SOURCE_DIRECTORY,):
            parts = parts[1:]
        return ".".join(parts)


def _is_module(name: str) -> bool:
    """Whether `name` is a top-level Python module of a job prefix: not a test module and not
    `conftest.py`."""
    return (
        name.endswith(_PYTHON_SUFFIX)
        and not name.startswith(_TEST_MODULE_PREFIX)
        and name != _CONFTEST
    )


def _prefix_of(stem: str) -> str:
    """The prefix of a module name: the stem up to its first `_`, or the whole stem."""
    return stem.split("_", 1)[0]


def _modules_of(tree: StagedTree, folder: PurePosixPath, prefix: str) -> tuple[str, ...]:
    """The top-level modules of `prefix` in `folder` that the tree holds, sorted."""
    return tuple(
        sorted(
            path
            for path in tree.files
            if (pure := PurePosixPath(path)).parent == folder
            and _is_module(pure.name)
            and (pure.stem == prefix or pure.stem.startswith(f"{prefix}_"))
        )
    )


def _moves(groups: Sequence[StageGroup], tree: StagedTree) -> Iterator[_PrefixMove]:
    """Each group that moves a prefix, once for each prefix, with the modules of the tree."""
    for number, group in enumerate(groups, start=1):
        seen: set[tuple[PurePosixPath, str]] = set()
        for old in group.changes:
            old_path = PurePosixPath(old)
            if old_path.suffix != _PYTHON_SUFFIX:
                continue
            prefix = _prefix_of(old_path.stem)
            subpackage = old_path.parent / prefix
            if (old_path.parent, prefix) in seen or not any(
                PurePosixPath(new).is_relative_to(subpackage) for new in group.creates
            ):
                continue
            seen.add((old_path.parent, prefix))
            yield _PrefixMove(
                number, old_path.parent, prefix, _modules_of(tree, old_path.parent, prefix)
            )


def move_prefix_problems(groups: Sequence[StageGroup], tree: StagedTree) -> list[str]:
    """One sentence for each module of a moved prefix that no group names in `changes`."""
    texts = MESSAGES.roadmap
    changed = {path for group in groups for path in group.changes}
    return [
        texts.stage_problem_move_prefix.format(
            group=move.number, prefix=move.prefix, folder=str(move.folder), path=path
        )
        for move in _moves(groups, tree)
        for path in move.modules
        if path not in changed
    ]


def _literals(command: str) -> tuple[str, ...]:
    """The literals of a valid `! git grep` command, or none for another command."""
    try:
        words = shlex.split(command)
    except ValueError:
        return ()
    if words[:1] != [NEGATIVE_SEARCH_WORD]:
        return ()
    found = read_negative_search(words)
    return () if isinstance(found, str) else found.literals


def move_verify_problems(groups: Sequence[StageGroup], tree: StagedTree) -> list[str]:
    """One sentence for each move group whose `! git grep` literal, each `-e` literal included,
    names one module of the prefix, the bare prefix included."""
    texts = MESSAGES.roadmap
    problems: list[str] = []
    for move in _moves(groups, tree):
        group = groups[move.number - 1]
        if group.verify is None:
            continue
        stems = {PurePosixPath(path).stem for path in move.modules} | {move.prefix}
        named = {f"{move.import_path}.{stem}" for stem in stems}
        problems.extend(
            texts.stage_problem_move_verify.format(
                group=move.number,
                prefix=move.prefix,
                command=group.verify,
                literal=literal,
                expected=f"{move.import_path}.{move.prefix}_",
            )
            for literal in _literals(group.verify)
            if literal in named
        )
    return problems
