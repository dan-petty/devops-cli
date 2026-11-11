"""The repair scope of a fix turn after a push (#4028).

A fix turn may change only a path that the plan names and the files of the change folder
(`unplanned_paths`, #3824). The turn still costs model requests before that check stops it, and a
failed check whose cause lies outside the plan, such as `Deploy Preview`, gives the turn nothing to
fix. The job asks the scope first: a failed check whose log names no path of the scope is no work
for a fix turn, so the job stops the item with no model request.

The scope holds the paths that the plan names in the code spans of its groups, and the folder of
the change. The log of the failed run is the evidence: it names the files that a
linter, a type check or a test reports, with the same paths as the annotations of the check run.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_REASON_PATHS
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement.implement_strays import plan_paths
from devops_cli.roadmap.step_files import TaskGroup


@dataclass(frozen=True)
class RepairScope:
    """The paths a fix turn may change: `paths` of the plan, in order, and every file under the
    change folder `folder`."""

    paths: tuple[str, ...]
    folder: str

    def names(self, log: str) -> bool:
        """Whether `log` names a path of the scope or a file of the change folder. A path is a whole
        word of the log: `src/app.py` is in `/runner/src/app.py:3` and not in `src/app.pyc`."""
        words = (rf"{re.escape(path)}(?![\w-])" for path in self.paths)
        return any(
            re.search(rf"(?<![\w.-]){tail}", log) for tail in (*words, re.escape(self.folder) + "/")
        )

    def listing(self) -> str:
        """The scope as one line for a stop reason: the change folder, then the paths of the plan,
        cut to `CONST_ROADMAP_IMPLEMENT_REASON_PATHS` names with the count of the rest."""
        names = [f"`{self.folder}/`", *(f"`{path}`" for path in self.paths)]
        shown = names[:CONST_ROADMAP_IMPLEMENT_REASON_PATHS]
        text = ", ".join(shown)
        if len(names) > len(shown):
            text += MESSAGES.roadmap.implement_paths_more.format(count=len(names) - len(shown))
        return text


def repair_scope(groups: Iterable[TaskGroup], folder: str) -> RepairScope:
    """The scope of the plan `groups` and the change folder `folder`, relative to the checkout. A
    code span with a space is a command and no path."""
    paths = sorted(path for path in plan_paths(groups) if " " not in path)
    return RepairScope(paths=tuple(paths), folder=folder)
