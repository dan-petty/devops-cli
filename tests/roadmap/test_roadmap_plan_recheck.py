"""`devops roadmap plan-recheck`: one result for each change folder on the default branch (#3492)."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from devops_cli.openspec.tool import OpenSpecTool
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.plan_recheck import PlanResult, recheck_plans, render_recheck
from devops_cli.roadmap.stage_change import StageProposal, render_change
from devops_cli.roadmap.store import GitHubState, ItemField
from tests.support.builders import make_stage_proposal
from tests.support.roadmap_stage import VALID_REPORT, StageRepo

CREATED = datetime(2026, 11, 4, tzinfo=UTC).date()
FIELDS = {ItemField.STATUS: "Planned", ItemField.PRIORITY: "P1-High"}


class _Tool:
    """An OpenSpec that accepts every change."""

    def run(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        del args, cwd
        return subprocess.CompletedProcess([], 0, VALID_REPORT, "")


def _proposal(test_file: str = "tests/test_sample.py") -> StageProposal:
    """The stock plan, with its new test module at `test_file`."""
    stock = make_stage_proposal()
    group = stock.groups[0]
    update = {
        "changes": ["src/devops_cli/sample.py", test_file],
        "creates": [test_file],
        "creates_lines": {test_file: 40},
        "test": group.test.replace("tests/test_sample.py", test_file) if group.test else None,
        "verify": group.verify.replace("tests/test_sample.py", test_file) if group.verify else None,
    }
    return make_stage_proposal(groups=[group.model_copy(update=update)])


def _plan(issue: int, proposal: StageProposal | None = None) -> dict[str, str]:
    change = f"{issue}-keep-the-last-comment"
    return render_change(change, proposal or _proposal(), {"comment-thread"}, created=CREATED)


def _recheck(repo: StageRepo, store: InMemoryRoadmapStore) -> dict[str, tuple[PlanResult, int]]:
    recheck = recheck_plans(repo.clone, store, tool=cast("OpenSpecTool", _Tool()))
    return {r.folder: (r.result, r.issue) for r in recheck.records}


def _store(*, closed: tuple[int, ...] = (), count: int = 3) -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore()
    for number in range(1, count + 1):
        state = GitHubState.CLOSED if number in closed else GitHubState.OPEN
        store.seed_issue(f"An item {number}", state=state, fields=FIELDS)
    return store


def test_each_numbered_folder_gets_one_result(stage_repo: StageRepo) -> None:
    ok = _plan(1)
    no_design = _plan(2, _proposal("tests/test_other.py"))
    del no_design["openspec/changes/2-keep-the-last-comment/design.md"]
    broken = _plan(3, _proposal("tests/test_third.py"))
    broken["openspec/changes/3-keep-the-last-comment/tasks.md"] = "# Tasks\n\nNothing here.\n"
    stage_repo.track({**ok, **no_design, **broken})

    results = _recheck(stage_repo, _store())

    assert results == {
        "1-keep-the-last-comment": (PlanResult.OK, 1),
        "2-keep-the-last-comment": (PlanResult.REWRITE, 2),
        "3-keep-the-last-comment": (PlanResult.NEW_PLAN, 3),
    }


def test_a_folder_of_a_closed_issue_is_cleanup_and_no_count_holds_it(
    stage_repo: StageRepo,
) -> None:
    stage_repo.track({**_plan(1), **_plan(2, _proposal("tests/test_other.py"))})
    store = _store(closed=(2,), count=2)

    recheck = recheck_plans(stage_repo.clone, store, tool=cast("OpenSpecTool", _Tool()))

    assert {r.issue: r.result for r in recheck.records} == {
        1: PlanResult.OK,
        2: PlanResult.CLEANUP,
    }
    assert len(recheck.live) == 1
    assert recheck.summary()["live"] == 1
    assert "1 folders count. 1 folders of closed issues are left out" in render_recheck(recheck)


def test_a_plan_whose_new_file_is_on_the_default_branch_is_delivered(
    stage_repo: StageRepo,
) -> None:
    stage_repo.track({**_plan(1), "tests/test_sample.py": "def test_it() -> None: ...\n"})

    results = _recheck(stage_repo, _store(count=1))

    assert results == {"1-keep-the-last-comment": (PlanResult.DELIVERED, 1)}


def test_a_plan_with_no_verification_line_is_a_rewrite_and_counts_as_unverified(
    stage_repo: StageRepo,
) -> None:
    files = _plan(1)
    path = "openspec/changes/1-keep-the-last-comment/tasks.md"
    command = "`uv run devops ci test tests/test_sample.py`"
    files[path] = (
        files[path]
        .replace(
            f"\n  - Verification: {command} fails on the base",
            f", and verify that {command} fails on the base",
        )
        .replace(f"\n  - Verification: {command} passes", f", and verify that {command} passes")
    )
    stage_repo.track(files)

    recheck = recheck_plans(stage_repo.clone, _store(count=1), tool=cast("OpenSpecTool", _Tool()))

    (record,) = recheck.records
    assert record.result is PlanResult.REWRITE
    assert recheck.unverified == 1
    assert "No group of `tasks.md` has a `Verification:` line" in render_recheck(recheck)


def test_the_first_problem_of_an_unreadable_plan_is_its_reason(stage_repo: StageRepo) -> None:
    files = _plan(1)
    files["openspec/changes/1-keep-the-last-comment/tasks.md"] = "# Tasks\n\nNothing here.\n"
    stage_repo.track(files)

    recheck = recheck_plans(stage_repo.clone, _store(count=1), tool=cast("OpenSpecTool", _Tool()))

    (record,) = recheck.records
    assert (record.result, record.readable) == (PlanResult.NEW_PLAN, False)
    assert len(record.reasons) == 1
    assert "1-keep-the-last-comment" in record.reasons[0]
    assert recheck.unreadable == 1
