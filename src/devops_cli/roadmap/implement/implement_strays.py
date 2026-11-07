"""The stray files of an implement step (#3092).

The prompt asks the agent to keep scratch files under `.data/agent/scratch/`, and the agent still
leaves some in the checkout. The step stages the whole checkout and gives every changed Python file
to `ruff` and `mypy`, so such a file stopped the step and, if it passed, reached the commit. A
stray file is an untracked file that git does not ignore (`git ls-files --others
--exclude-standard`), or a new file that the index holds because the agent staged it (`git diff
--cached --name-only --diff-filter=A`), and that its group does not allow. The group allows:

- a path that it names in a code span: its `Changes:` line, where the plan marks a created path
  with `(new)`, and its tasks;
- a file under the change folder of the item;
- a file under `src/`, `tests/`, `docs/` or `openspec/`. The plan may leave out a fixture, a
  `conftest.py` or a helper module that the code needs, and a deleted file would break the commit
  without a sign. These files go to the normal checks, which fail on a real defect.

A directory in the list is a stray file at any place: git lists a directory only when it holds a
nested git repository.

A fix step is stricter (#3824): it may change only a path that the plan names or a file under the
change folder (`unplanned_paths`). A path of the plan is a code span in the text of any group, so
the `Reads:` line, the `Changes:` line and the tasks all name paths.

This module only decides. The step lists the files, unstages and deletes the stray ones and reports
them. A fix step names no file in its group, so it applies the same rule with the four project
directories (#3488).
"""

from __future__ import annotations

import posixpath
from collections.abc import Iterable
from pathlib import PurePosixPath

from devops_cli.roadmap.step_files import TaskGroup, code_spans

_PROJECT_DIRECTORIES = frozenset({"src", "tests", "docs", "openspec"})


def _named(group: TaskGroup) -> frozenset[str]:
    """The code spans of the text of `group`, as normalised paths."""
    return frozenset(posixpath.normpath(span) for span in code_spans(group.text))


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
        if not name.endswith("/") and next(iter(path.parts), "") in _PROJECT_DIRECTORIES:
            continue
        strays.append(name)
    return strays


def unplanned_paths(changed: Iterable[str], groups: Iterable[TaskGroup], change: str) -> list[str]:
    """The names of `changed` that the plan does not name, in their order (#3824). `changed` holds
    every path that a step added, changed or deleted, relative to the checkout. The plan names a
    path in a code span of the text of any of its `groups`. A file under the change folder `change`
    is always allowed."""
    named = frozenset().union(*(_named(group) for group in groups))
    folder = PurePosixPath(change)
    return [
        name
        for name in changed
        if posixpath.normpath(name) not in named
        and not PurePosixPath(posixpath.normpath(name)).is_relative_to(folder)
    ]
