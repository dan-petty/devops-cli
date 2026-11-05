"""What the tests of a behavior group share (#3042): a JUnit report of a replay on the base commit,
and the `tasks.md` of a behavior group, whose first task names a test that fails on the base.

A replay runs pytest, which is an edge. A test answers that run with the report that it gives, so
the step reads the outcome of each test that the test chose.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

BEHAVIOR_TASKS = """\
# Tasks

## 1. The first group

Reads: `CONTEXT.md`. Changes: `tests/test_shout.py` (new), `src/devops_cli/shout.py` (new).

- [ ] 1.1 Add the failing test `tests/test_shout.py` for `src/devops_cli/shout.py`
  - Verification: `uv run devops ci test tests/test_shout.py` fails on the base
- [ ] 1.2 Add `shout` to `src/devops_cli/shout.py`
  - Verification: `uv run devops ci test tests/test_shout.py`

## 2. The second group

Reads: `CONTEXT.md`. Changes: `CONTEXT.md`.

- [ ] 2.1 Document the function in `CONTEXT.md`
  - Verification: `uv run devops docs check`

## Criteria

- Group 1: The job keeps every comment.
"""
BEHAVIOR_FIRST_TICKED = BEHAVIOR_TASKS.replace("- [ ] 1.", "- [x] 1.")
BEHAVIOR_TICKED = BEHAVIOR_FIRST_TICKED.replace("- [ ] 2.", "- [x] 2.")
SHOUT_TEST_ID = "tests.test_shout::test_shout"


def junit(*cases: tuple[str, str]) -> str:
    """A JUnit report with one testcase for each `(test id, status)` pair of `cases`, where the
    status is `passed`, `failed` (a call-phase failure) or `errored` (a collection error)."""
    body = ""
    for test_id, status in cases:
        classname, _, name = test_id.rpartition("::")
        marker = {
            "passed": "",
            "failed": '<failure message="assert"/>',
            "errored": '<error message="collection"/>',
        }[status]
        body += f'<testcase classname="{classname}" name="{name}">{marker}</testcase>'
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<testsuites><testsuite name="pytest">{body}</testsuite></testsuites>'
    )


def answer_pytest_on_base(programs: ProcessFake, *reports: str) -> None:
    """Answer each pytest run of a replay with the next report, and the last one when the reports
    run out. Pytest exits 1, as it does when a test fails. A replay reads the report that the run
    wrote at its `--junitxml` path."""
    pending = list(reports)

    def answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        path = next(word for word in call.argv if word.startswith("--junitxml="))
        report = pending.pop(0) if len(pending) > 1 else pending[0]
        Path(path.removeprefix("--junitxml=")).write_text(report, encoding="utf-8")
        return subprocess.CompletedProcess(call.argv, 1, stdout="", stderr="")

    programs.answer(lambda call: "pytest" in call.argv, ProcessAnswer(side_effect=answer))
