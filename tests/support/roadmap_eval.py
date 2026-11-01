"""What the tests of `devops roadmap eval implement` share (#3030): a fixture folder written under
`tmp_path`, the diffs of a good and a bad result for the sample change of
`tests.support.implement_step`, and the reply of a model that does the group.
"""

from __future__ import annotations

import difflib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tests.support.implement_step import (
    BODY,
    SAMPLE,
    SHOUT_CODE,
    TASKS,
    TASKS_PATH,
    TEST_BODY,
    TICKED,
)

CHANGE = "1-sample-change"
PLAN = {
    "proposal.md": "# Proposal\n\nWhy the sample shouts.\n",
    "design.md": "# Design\n\nShout in capitals.\n",
    "tasks.md": TASKS,
}
TEST_PATH = "tests/test_sample.py"
CODE_PATH = "src/sample.py"
SCRATCH_PATH = "scratch.py"


def unified(path: str, old: str | None, new: str | None) -> str:
    """The diff that turns `old` into `new` at `path`, as `git diff` writes it. `None` is no file."""
    before = [] if old is None else old.splitlines(keepends=True)
    after = [] if new is None else new.splitlines(keepends=True)
    body = "".join(
        difflib.unified_diff(
            before,
            after,
            fromfile="/dev/null" if old is None else f"a/{path}",
            tofile="/dev/null" if new is None else f"b/{path}",
        )
    )
    mode = (
        "new file mode 100644\n"
        if old is None
        else "deleted file mode 100644\n"
        if new is None
        else ""
    )
    return f"diff --git a/{path} b/{path}\n{mode}{body}"


def good_diff() -> str:
    """The result of a model that writes the test and the code, and ticks group 1."""
    return (
        unified(TASKS_PATH, TASKS, TICKED)
        + unified(TEST_PATH, None, TEST_BODY)
        + unified(CODE_PATH, SAMPLE, SHOUT_CODE)
    )


def scratch_diff() -> str:
    """The result of a model that also leaves a scratch file at the root."""
    return good_diff() + unified(SCRATCH_PATH, None, "print('scratch')\n")


def case_data(**overrides: Any) -> dict[str, Any]:
    """The `case.json` of a valid fixture for the sample change, with `overrides`."""
    data: dict[str, Any] = {
        "name": "sample",
        "source": "a test",
        "issue": 1,
        "title": "Make the sample shout",
        "group": 1,
        "change": CHANGE,
        "base": "0123456789abcdef0123456789abcdef01234567",
        "changes": [TEST_PATH, CODE_PATH],
        "tests_pass": ["uv run devops ci test tests/test_sample.py"],
        "results": [
            {"name": "good", "source": "a test", "diff": "good.diff", "fails": []},
            {
                "name": "scratch",
                "source": "a test",
                "diff": "scratch.diff",
                "fails": ["diff_scope", "no_scratch"],
            },
        ],
    }
    return data | overrides


def write_fixture(
    root: Path,
    *,
    case: Mapping[str, Any] | None = None,
    diffs: Mapping[str, str] | None = None,
    folder: str = "sample",
) -> Path:
    """Write a fixture folder under `root`: the case, the issue body, the plan, and the diffs by
    file name (the good and the scratch diff when none are given). Returns the folder."""
    given = {"good.diff": good_diff(), "scratch.diff": scratch_diff()} if diffs is None else diffs
    base = root / folder
    (base / "plan").mkdir(parents=True)
    (base / "results").mkdir()
    (base / "case.json").write_text(json.dumps(case or case_data()), encoding="utf-8")
    (base / "issue.md").write_text(BODY, encoding="utf-8")
    for name, text in PLAN.items():
        (base / "plan" / name).write_text(text, encoding="utf-8")
    for name, text in given.items():
        (base / "results" / name).write_text(text, encoding="utf-8")
    return base
