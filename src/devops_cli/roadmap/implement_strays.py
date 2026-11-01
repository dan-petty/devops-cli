"""The stray files of an implement step (#3092).

The prompt asks the agent to keep scratch files under `.data/agent/scratch/`, and the agent still
leaves some in the checkout. The step stages the whole checkout and gives every changed Python file
to `ruff` and `mypy`, so such a file stopped the step and, if it passed, reached the commit. A
stray file is an untracked file that git does not ignore (`git ls-files --others
--exclude-standard`) and that its group does not allow. The group allows:

- a path that it names in a code span: its `Changes:` line, where the plan marks a created path
  with `(new)`, and its tasks;
- a file under the change folder of the item;
- a new `test_*.py` file under `tests/`, in the directory of a test file that the group names.

This module only decides. The step lists the files, deletes the stray ones and reports them.
"""

from __future__ import annotations

import posixpath
from collections.abc import Iterable
from pathlib import PurePosixPath

from devops_cli.roadmap.step_files import TaskGroup, code_spans

_TESTS = "tests"
_TEST_FILE = "test_*.py"


def _named(group: TaskGroup) -> frozenset[str]:
    """The code spans of the text of `group`, as normalised paths."""
    return frozenset(posixpath.normpath(span) for span in code_spans(group.text))


def _in_named_test_directory(path: PurePosixPath, named: frozenset[str]) -> bool:
    """Whether `path` is a test file under `tests/` whose directory holds a test file that the
    group names."""
    if path.parts[:1] != (_TESTS,) or not path.match(_TEST_FILE):
        return False
    return any(
        PurePosixPath(name).parent == path.parent and PurePosixPath(name).parts[:1] == (_TESTS,)
        for name in named
        if name.endswith(".py")
    )


def stray_files(untracked: Iterable[str], group: TaskGroup, change: str) -> list[str]:
    """The names of `untracked` that `group` does not allow, in their order. `untracked` holds the
    paths that git lists, relative to the checkout. `change` is the change folder of the item,
    relative to the checkout."""
    named = _named(group)
    folder = PurePosixPath(change)
    strays: list[str] = []
    for name in untracked:
        path = PurePosixPath(posixpath.normpath(name))
        if str(path) in named or path.is_relative_to(folder):
            continue
        if _in_named_test_directory(path, named):
            continue
        strays.append(name)
    return strays
