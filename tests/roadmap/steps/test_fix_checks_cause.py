"""The files whose failure the change of a branch causes (#6116).

The two cases are the stops of the fix-checks job on pull requests #6114 and #6041, built from the
text of their logs and files: the tests read no live pull request.

- #6114: the plan adds the keyword-only argument `in_runner` to `_run_pr_review_workflow` of
  `src/devops_cli/commands/review.py`. Two tests in a file that the plan does not list call it
  without the argument.
- #6041: the plan adds an option to a command, so the snapshot of the MCP tool listing differs.
"""

from __future__ import annotations

import pytest

from devops_cli.roadmap.implement.implement_fix_scope import RepairScope, repair_scope
from devops_cli.roadmap.step_files import parse_task_groups
from devops_cli.roadmap.steps.fix_checks import tier1_causes
from devops_cli.roadmap.steps.fix_checks_cause import (
    BranchChange,
    changed_definitions,
    judge_scope,
    snapshot_tests,
)

FOLDER = "openspec/changes/3827-devops-review-runs-in-the-runner"
REVIEW = "src/devops_cli/commands/review.py"
REGRESSION = "tests/git/test_review_worktree_regression.py"
PLAN = f"""\
# Tasks

## 1. Choose the review executor from the runner profile

Changes: `src/devops_cli/security/tool_executor.py`, `src/devops_cli/ai/review/runner.py`, \
`{REVIEW}`, `tests/ai/review/test_review_runner_executor.py` (new).

- [x] 1.1 `test_a_review_in_the_runner_pod_keeps_the_sandbox` in \
`tests/ai/review/test_review_runner_executor.py`
  - Verification: `$ uv run devops ci test tests/ai/review/test_review_runner_executor.py`
"""
REVIEW_BASE = '''\
"""Review commands."""

from pathlib import Path


def review_pr(number: int) -> str:
    return f"PR #{number}"


def _run_pr_review_workflow(pages: list[str], title: str, *, checkout: Path) -> list[str]:
    return execute_review_workflow(pages, title, partial_context=True)
'''
REVIEW_HEAD = REVIEW_BASE.replace(
    "*, checkout: Path) -> list[str]:\n    return execute_review_workflow(pages, title, ",
    "*, checkout: Path, in_runner: bool) -> list[str]:\n"
    "    return execute_review_workflow(pages, title, in_runner=in_runner, ",
)
CALLER = """\
from pathlib import Path


def test_run_pr_review_workflow_partial_context(tmp_path: Path) -> None:
    from devops_cli.commands.review import _run_pr_review_workflow

    assert _run_pr_review_workflow(pages=["page1"], title="PR #42", checkout=tmp_path) == []
"""
IMPORTER = """\
from devops_cli.commands import review


def test_a_pull_request_has_a_title() -> None:
    assert review.review_pr(42) == "PR #42"
"""
UNRELATED = """\
from devops_cli.config.settings import load_settings


def test_the_settings_load() -> None:
    assert load_settings()
"""
# The lines of `gh run view --log-failed` for shard 4 of the tests of #6114: the job, the step
# and the time, then the line of pytest.
_PREFIX = "Tests & Coverage (shard 4 of 4)\tRun tests\t2026-11-17T03:31:42.9740821Z "
_MISSING = (
    "TypeError: _run_pr_review_workflow() missing 1 required keyword-only argument: 'in_runner'"
)
LOG_6114 = "".join(
    f"{_PREFIX}{line}\n"
    for line in (
        f"E           {_MISSING}",
        f"{REGRESSION}:314: TypeError",
        f"FAILED {REGRESSION}::test_run_pr_review_workflow_partial_context - {_MISSING}",
        f"FAILED {REGRESSION}::test_run_pr_review_workflow_with_worktree - {_MISSING}",
        "= 2 failed, 7339 passed, 8 skipped, 7 warnings in 241.27s (0:04:01) =",
    )
)
LISTING = "tests/ai/mcp/test_mcp_tool_listing.py"
LOG_6041 = (
    "1 snapshot failed. 7 snapshots passed.\n"
    f"FAILED {LISTING}::test_the_tool_listing_matches_the_snapshot - "
    "assert [+ received] == [- snapshot]\n"
    "= 1 failed, 6604 passed, 6 skipped, 1 warning in 186.82s (0:03:06) =\n"
)


def _scope() -> RepairScope:
    return repair_scope(parse_task_groups(PLAN), FOLDER)


def _change(**kwargs: frozenset[str]) -> BranchChange:
    """The change of #6114: the branch changes `review.py`, and the signature of one function."""
    return BranchChange(
        paths=frozenset({REVIEW}),
        names=changed_definitions(REVIEW_BASE, REVIEW_HEAD),
        **kwargs,
    )


def _no_read() -> BranchChange:
    """A log that names only paths of the plan needs no read of the branch."""
    pytest.fail("The scope check read the change of the branch.")


def _files(**texts: str) -> dict[str, str]:
    return {REGRESSION: texts.get("regression", CALLER)}


def test_changed_definitions_name_a_changed_signature_and_not_an_unchanged_function() -> None:
    base = REVIEW_BASE + "\n\nclass Runner:\n    def run(self) -> None:\n        pass\n"
    head = REVIEW_HEAD + "\n\nclass Runner:\n    def run(self) -> None:\n        print()\n"

    assert changed_definitions(base, head) == {"_run_pr_review_workflow", "Runner", "run"}
    assert changed_definitions(None, "def added() -> None:\n    pass\n") == {"added"}
    assert changed_definitions(REVIEW_BASE, None) == {"review_pr", "_run_pr_review_workflow"}


def test_a_test_that_calls_a_changed_function_is_in_scope_with_its_file_named() -> None:
    """The case of #6114: the log names no path of the plan, and the failed test calls the
    function whose signature the plan changes."""
    verdict = judge_scope(LOG_6114, _scope(), _change, _files().get)

    assert verdict.in_scope is True
    assert [cause.path for cause in verdict.caused] == [REGRESSION]
    assert "`_run_pr_review_workflow`" in verdict.caused[0].reason
    assert verdict.outside == ()


def test_a_test_of_a_changed_module_is_in_scope() -> None:
    verdict = judge_scope(LOG_6114, _scope(), _change, _files(regression=IMPORTER).get)

    assert [cause.path for cause in verdict.caused] == [REGRESSION]
    assert "`devops_cli.commands.review`" in verdict.caused[0].reason


def test_a_failure_that_the_change_does_not_cause_stops_and_names_the_file() -> None:
    verdict = judge_scope(LOG_6114, _scope(), _change, _files(regression=UNRELATED).get)

    assert verdict.in_scope is False
    assert [cause.path for cause in verdict.outside] == [REGRESSION]
    assert verdict.stop_reason().startswith("Failed check log is outside plan scope: ")
    assert "does not cause" in verdict.stop_reason()


@pytest.mark.parametrize(
    "log",
    [
        "osv-scanner: the ignore of GHSA-0000-0000-0000 ended on 2026-11-10\n",
        f"FAILED {REGRESSION}::test_gone - AssertionError\n",
    ],
    ids=["expired-ignore", "file-not-in-the-checkout"],
)
def test_a_log_that_names_no_file_of_the_checkout_stops_with_a_reason(log: str) -> None:
    verdict = judge_scope(log, _scope(), _change, {}.get)

    assert (verdict.in_scope, verdict.caused, verdict.outside) == (False, (), ())
    assert "names no path of the plan" in verdict.stop_reason()


def test_a_log_that_names_a_path_of_the_plan_is_in_scope_with_no_extra_file() -> None:
    log = f'{REVIEW}:12: error: Missing named argument "in_runner"  [call-arg]\n'

    verdict = judge_scope(log, _scope(), _no_read, {REVIEW: REVIEW_HEAD}.get)

    assert (verdict.in_scope, verdict.caused) == (True, ())


def test_a_lint_error_in_a_caller_outside_the_plan_is_in_scope() -> None:
    """A caller in `src/` that the plan does not list: mypy names it, and it calls the changed
    function."""
    caller = "src/devops_cli/roadmap/review_job.py"
    text = "from devops_cli.commands.review import _run_pr_review_workflow\n"
    log = f'{caller}:1: error: Missing named argument "in_runner"  [call-arg]\n'

    verdict = judge_scope(log, _scope(), _change, {caller: text}.get)

    assert [cause.path for cause in verdict.caused] == [caller]


def test_a_snapshot_test_of_a_changed_command_is_in_scope_and_has_a_fixer_of_tier1() -> None:
    """The case of #6041: the snapshot of the tool listing differs. Tier 1 writes it again, and
    the scope check takes the snapshot test when the branch changes a source module."""
    listing = "from devops_cli.ai.mcp.server import mcp\n"
    change = BranchChange(paths=frozenset({"src/devops_cli/commands/rag.py"}))

    verdict = judge_scope(LOG_6041, _scope(), lambda: change, {LISTING: listing}.get)

    assert snapshot_tests(LOG_6041) == (LISTING,)
    assert tier1_causes("Tests & Coverage (shard 3 of 4)", LOG_6041).snapshots == (LISTING,)
    assert [cause.path for cause in verdict.caused] == [LISTING]
    assert "snapshot" in verdict.caused[0].reason
