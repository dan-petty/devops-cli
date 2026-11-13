"""The check runs that GitHub sent for the head of pull request 5357, recorded in
`tests/fixtures/github/check_runs_pr_5357_head.json` (#5383).

20 of the 25 checks of that head have two runs in two check suites: a run of the push and a newer
run of a close and reopen. The older run of Fail-to-Pass Check failed and its newer run passed.
"""

from __future__ import annotations

import json
from typing import Any, Final

from tests.support.paths import FIXTURES

PR_5357_HEAD: Final = "f7064d0f0cf3803ddf60630afadf38bbaa2b4167"
REPLACED_CHECK: Final = "Fail-to-Pass Check"


def pr_5357_head_runs(*, newer_fails: bool = False) -> list[dict[str, Any]]:
    """The recorded check runs, in the order GitHub sent them.

    With `newer_fails`, the two runs of Fail-to-Pass Check swap their conclusions, so the older
    run passed and the newer run failed.
    """
    recorded = json.loads(
        (FIXTURES / "github" / "check_runs_pr_5357_head.json").read_text(encoding="utf-8")
    )
    runs: list[dict[str, Any]] = recorded["check_runs"]
    if newer_fails:
        for run in runs:
            if run["name"] == REPLACED_CHECK:
                run["conclusion"] = "success" if run["conclusion"] == "failure" else "failure"
    return runs
