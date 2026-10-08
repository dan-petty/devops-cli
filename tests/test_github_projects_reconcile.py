"""Unit tests for GitHub Projects v2 custom field reconciler."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.github import rate_limiter
from devops_cli.github.projects import (
    FieldChange,
    MutationBudget,
    ReconcileResult,
    plan_item_changes,
    reconcile_dry_run,
    reconcile_project_custom_fields,
)
from devops_cli.github.rate_limiter import get_github_rate_limiter
from tests.project_reconcile_fake import (
    REPO,
    ProjectGitHub,
    card,
    collapse,
    issue,
    pull,
    request_kind,
)

_URL = "https://github.com/owner/repo/issues/7"
_STATUSES = ("New", "Ready", "In Progress", "In Review", "Done")


def _issue(
    state: str = "OPEN", labels: list[str] | None = None, **extra: object
) -> dict[str, object]:
    return {
        "html_url": _URL,
        "state": state,
        "labels": [{"name": n} for n in labels or []],
        **extra,
    }


def _changes(
    item: dict[str, object],
    current: dict[str, str | None] | None = None,
    **kwargs: object,
) -> list[tuple[str, str | None, str, str]]:
    planned = plan_item_changes(item, current or {}, status_options=_STATUSES, **kwargs)  # type: ignore[arg-type]
    return [(c.field, c.old, c.new, c.source) for c in planned]


def test_a_set_status_is_left_alone_when_nothing_forces_it() -> None:
    """The board owns Status; a label must not revert a person's triage."""
    assert _changes(_issue(labels=["status/in-progress"]), {"status": "Ready"}) == []


def test_an_unset_status_comes_from_an_exact_status_label() -> None:
    assert _changes(_issue(labels=["status/in-progress"])) == [
        ("Status", None, "In Progress", "label status/in-progress")
    ]


def test_a_status_label_only_matches_exactly() -> None:
    """`status/ready-to-merge` and `status/triage` are not `status/ready`."""
    assert _changes(_issue(labels=["status/ready-to-merge", "status/triage"])) == [
        ("Status", None, "New", "default for an unset status")
    ]


def test_blocked_maps_only_when_the_board_has_a_blocked_status() -> None:
    with_blocked = plan_item_changes(
        _issue(labels=["status/blocked"]), {}, status_options=(*_STATUSES, "Blocked")
    )
    assert (
        _changes(_issue(labels=["status/blocked"])),
        [(c.field, c.new) for c in with_blocked],
    ) == (
        [("Status", None, "New", "default for an unset status")],
        [("Status", "Blocked")],
    )


def test_a_closed_issue_is_forced_to_done() -> None:
    assert _changes(_issue(state="CLOSED"), {"status": "In Progress"}) == [
        ("Status", "In Progress", "Done", "issue closed")
    ]


def test_an_open_pull_request_is_forced_into_review_and_a_draft_into_progress() -> None:
    pr_url = "https://github.com/owner/repo/pull/9"
    ready = {"html_url": pr_url, "state": "open", "labels": [], "pull_request": {}}
    draft = {**ready, "draft": True}
    assert (
        _changes(ready, {"status": "New"}),
        _changes(draft, {"status": "New"}),
    ) == (
        [("Status", "New", "In Review", "open pull request")],
        [("Status", "New", "In Progress", "draft pull request")],
    )


def test_an_issue_with_an_open_linked_pull_request_is_forced_into_review() -> None:
    assert _changes(_issue(), {"status": "Ready"}, has_open_pr=True) == [
        ("Status", "Ready", "In Review", "linked open pull request")
    ]


def test_priority_is_set_from_its_label_only_when_unset() -> None:
    labelled = _issue(labels=["priority/p1-high"])
    assert (
        _changes(labelled, {"status": "Ready"}),
        _changes(labelled, {"status": "Ready", "priority": "P3-Low"}),
        _changes(_issue(), {"status": "Ready"}),
    ) == (
        [("Priority", None, "P1-High", "label priority/p1-high")],
        [],
        [],
    )


def test_a_matching_value_is_not_rewritten_whatever_its_case() -> None:
    assert _changes(_issue(state="CLOSED"), {"status": "done"}) == []


def test_value_and_effort_are_never_inferred() -> None:
    """An inferred field that keeps writing reads as decided; unset is honest."""
    fields = [c[0] for c in _changes(_issue(labels=["type/feature", "priority/p0-critical"]))]
    assert {"Value", "Effort"} & set(fields) == set()


def test_the_milestone_the_board_mirrors_is_never_written() -> None:
    item = _issue(milestone={"title": "v0.2.24"})
    assert _changes(item, {"status": "Ready", "milestone": "v0.2.23"}) == []


def test_a_backlog_label_reads_as_new() -> None:
    """`status/backlog` names the status the board now calls New."""
    assert _changes(_issue(labels=["status/backlog"])) == [
        ("Status", None, "New", "label status/backlog")
    ]


def test_a_field_change_records_the_item_it_belongs_to() -> None:
    change = plan_item_changes(_issue(state="CLOSED"), {}, status_options=_STATUSES)[0]
    assert change == FieldChange(
        url=_URL, field="Status", old=None, new="Done", source="issue closed"
    )


def _reconcile(
    fake: ProjectGitHub, mode: str = "write", state: str = "open", limit: int = 25
) -> ReconcileResult:
    """Reconcile board 2 of `o/r` against `fake`, standing in for `run_gh`."""
    with patch("devops_cli.github.projects.run_gh", side_effect=fake.run_gh):
        return reconcile_project_custom_fields(
            "o", REPO, 2, mode=mode, state=state, budget=MutationBudget(limit=limit)
        )


def _five_changes() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Three cards needing five changes, and two open issues off the board."""
    cards = [card(1), card(2), card(3, status="Ready")]
    labelled = ("priority/p1-high",)
    issues = [issue(n, labels=labelled) for n in (1, 2, 3)] + [issue(10), issue(11)]
    return cards, issues


def _rate_limit_reply(remaining: int = 5000) -> str:
    """`gh api rate_limit` as REST answers it, every resource reset an hour from now."""
    reset = int(time.time()) + 3600
    resource = {"limit": 5000, "remaining": remaining, "used": 0, "reset": reset}
    return json.dumps({"resources": {name: resource for name in ("core", "graphql", "search")}})


@pytest.mark.parametrize("ledger", ["no graphql entry", "an entry past its reset"])
def test_reconcile_reads_an_unknown_quota_and_plans_the_board(ledger: str) -> None:
    """Fault 1 of #892: an unknown or expired ledger entry no longer reads as exhausted. Through
    the real `run_gh`, its `acquire` refreshes the ledger from `gh api rate_limit` before the
    budget query, whose GraphQL reply then decides, and the plan holds the board's changes."""
    limiter = get_github_rate_limiter()
    if ledger == "an entry past its reset":
        limiter.update_quota("graphql", remaining=4000, reset_epoch=time.time() - 60, limit=5000)
    cards, issues = _five_changes()
    fake = ProjectGitHub(cards, issues)
    refreshed: list[list[str]] = []

    def rate_limit(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        refreshed.append(cmd)
        assert cmd == ["gh", "api", "rate_limit"]
        return subprocess.CompletedProcess(cmd, 0, _rate_limit_reply(), "")

    with (
        patch.object(rate_limiter, "_burst_protected_subprocess", side_effect=fake),
        patch.object(rate_limiter, "run_subprocess", side_effect=rate_limit),
        patch("devops_cli.github.rate_limiter.time.sleep"),
    ):
        result = reconcile_project_custom_fields("o", REPO, 2, mode="plan")
    quota = limiter.get_quota("graphql")
    assert (
        len(result.planned),
        result.summary(),
        bool(refreshed),
        quota.is_valid(),
        (quota.remaining or 5000) <= fake.server.remaining,
        fake.edits,
    ) == (5, "Would change 3 of 3 items on project #2 (5 field changes).", True, True, True, [])


@pytest.mark.parametrize("mode", ["plan", "write"])
def test_reconcile_refuses_to_start_below_the_floor(mode: str) -> None:
    """With 100 GraphQL points left the run does not start: it names the points and the reset
    and reads nothing past the budget query, so a write run writes nothing."""
    cards, issues = _five_changes()
    fake = ProjectGitHub(cards, issues, remaining=101)
    with pytest.raises(GitHubRateLimitError) as refused:
        _reconcile(fake, mode=mode)
    assert (
        "100 points left until 00:00 UTC" in refused.value.message,
        fake.kinds(),
        fake.edits,
    ) == (True, ["RoadmapBoardBudget"], [])


@pytest.mark.parametrize("state", ["open", "closed", "all"])
def test_reconcile_never_adds_a_card_whatever_the_state(state: str) -> None:
    """An open issue, a closed issue, an open pull request and a merged one, all off the board,
    stay off it. Only the open issue waits for intake, and only a run that listed open issues
    can count it."""
    fake = ProjectGitHub(
        [card(1, status="Ready")],
        [issue(1), issue(10), issue(11, "closed")],
        [pull(12), pull(13, "closed", merged=True)],
    )
    result = _reconcile(fake, state=state)
    intake = "1 open issue is not on the board (awaiting intake: devops roadmap intake)."
    assert (fake.adds, result.intake_line(), "item-add" in str(fake.sent)) == (
        [],
        None if state == "closed" else intake,
        False,
    )


def test_two_open_issues_off_the_board_are_counted_in_the_plural() -> None:
    cards, issues = _five_changes()
    result = _reconcile(ProjectGitHub(cards, issues), mode="plan")
    assert result.intake_line() == (
        "2 open issues are not on the board (awaiting intake: devops roadmap intake)."
    )


def test_the_mutation_budget_stops_the_run_and_says_what_remains() -> None:
    """Budget 3, five planned changes on cards already on the board and two open issues off it:
    three changes made, no card added, and the stop line names the budget and the two left."""
    cards, issues = _five_changes()
    fake = ProjectGitHub(cards, issues)
    result = _reconcile(fake, limit=3)
    assert (
        len(result.applied),
        len(fake.edits),
        fake.adds,
        result.stop_line(),
        result.remaining == result.planned[3:],
    ) == (
        3,
        3,
        [],
        "Stopped early (mutation budget of 3 reached): 2 planned changes remain.",
        True,
    )


def test_the_graphql_quota_stops_the_run_between_writes() -> None:
    """The ledger falls below the floor after two writes: the run stops before the third,
    names the quota and counts the three changes left."""
    limiter = get_github_rate_limiter()

    def spend(count: int) -> None:
        if count == 2:
            limiter.update_quota("graphql", remaining=100, reset_epoch=4_102_444_800.0, limit=5000)

    cards, issues = _five_changes()
    fake = ProjectGitHub(cards, issues, on_edit=spend)
    result = _reconcile(fake)
    assert (len(fake.edits), result.stop_line()) == (
        2,
        "Stopped early (GraphQL has 100 points left until 00:00 UTC, below the 250 kept in "
        "reserve): 3 planned changes remain.",
    )


def test_a_failed_write_is_counted_among_the_changes_that_remain() -> None:
    """An item-edit that exits 1 is not dropped: the run stops there and counts it."""
    cards, issues = _five_changes()
    fake = ProjectGitHub(cards, issues, fail_edits=(2,))
    result = _reconcile(fake)
    assert (
        len(result.applied),
        result.remaining[0] == result.planned[1],
        result.stop_line(),
    ) == (
        1,
        True,
        "Stopped early (the write of Priority on #1 failed: GraphQL: the write failed): "
        "4 planned changes remain.",
    )


@pytest.mark.parametrize("limit", [3, 25])
def test_the_plan_matches_the_live_run(limit: int) -> None:
    """Both evaluate only the cards on the board, and the plan is the live run's applied
    changes followed by its remaining ones."""
    cards, issues = _five_changes()
    prs = [pull(12, body="Closes #3")]
    plan = _reconcile(ProjectGitHub(cards, issues, prs), mode="plan")
    live = _reconcile(ProjectGitHub(cards, issues, prs), limit=limit)
    assert (
        plan.items_evaluated,
        live.items_evaluated,
        plan.planned,
        live.applied + live.remaining,
        plan.remaining,
    ) == (3, 3, live.planned, plan.planned, [])


def test_a_complete_run_applies_every_change_and_reports_no_stop() -> None:
    cards, issues = _five_changes()
    result = _reconcile(ProjectGitHub(cards, issues))
    assert (result.stop_line(), result.remaining, result.summary()) == (
        None,
        [],
        "Changed 3 of 3 items on project #2 (5 field changes).",
    )


def test_status_comes_from_the_boards_own_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A board without Blocked keeps `status/blocked` from mapping. The run is in a checkout
    with no project template, so a template read would fail it."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    fake = ProjectGitHub(
        [card(1)], [issue(1, labels=("status/blocked",))], statuses=("New", "Ready", "Done")
    )
    result = _reconcile(fake, mode="plan")
    assert [(c.field, c.new) for c in result.planned] == [("Status", "New")]


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        (subprocess.CompletedProcess([], 1, "", "HTTP 502"), "Failed to read project #2 fields"),
        (
            subprocess.CompletedProcess([], 0, json.dumps({"fields": [], "totalCount": 0}), ""),
            "Project #2 has no Status field with options",
        ),
        (
            subprocess.CompletedProcess([], 0, json.dumps({"fields": [], "totalCount": 3}), ""),
            "Read 0 of 3 project #2 fields, so the read is incomplete.",
        ),
    ],
)
def test_an_unread_status_field_fails_the_run(
    reply: subprocess.CompletedProcess[str], message: str
) -> None:
    """A failed, empty or partial field read must not let every unset card default to New."""
    fake = ProjectGitHub([card(1)], [issue(1, labels=("status/ready",))])

    def gh(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return reply if cmd[1:3] == ["project", "field-list"] else fake(cmd)

    with (
        patch("devops_cli.github.projects.run_gh", side_effect=gh),
        pytest.raises(GitHubOperationError) as failed,
    ):
        reconcile_project_custom_fields("o", REPO, 2, mode="plan")
    assert (message in failed.value.message, fake.edits) == (True, [])


@pytest.mark.parametrize("mode", ["plan", "write"])
def test_a_value_the_board_has_no_option_for_refuses_the_run_before_any_write(mode: str) -> None:
    """A board without In Review can't take an open pull request's Status. The run refuses
    before its first write, naming the value and the board's options, rather than stopping at a
    write that fails on every run and blocks the changes after it."""
    statuses = ("New", "Ready", "In Progress", "Done", "Blocked")
    fake = ProjectGitHub([card(1), card(12, "pull")], [issue(1)], [pull(12)], statuses=statuses)
    with pytest.raises(GitHubOperationError) as refused:
        _reconcile(fake, mode=mode)
    assert (refused.value.message, fake.edits) == (
        "'In Review' is not a Status option on the board; "
        "the options are New, Ready, In Progress, Done, Blocked.",
        [],
    )


def test_a_failed_fetch_raises_rather_than_reading_as_empty() -> None:
    """A failed read must stay distinct from a board or repository with nothing in it."""
    failed = MagicMock(returncode=1, stdout="", stderr="HTTP 502")
    with (
        patch("devops_cli.github.projects.run_gh", return_value=failed),
        pytest.raises(GitHubOperationError),
    ):
        reconcile_project_custom_fields("o", REPO, 2, mode="write")


def test_the_dry_run_lists_the_requests_a_run_sends_in_order() -> None:
    """The request plan is built by the argument builders the run uses, so it lists the kinds
    of request a write run sends, in the order it sends them."""
    cards, issues = _five_changes()
    fake = ProjectGitHub(cards, issues)
    _reconcile(fake)
    planned = reconcile_dry_run("o", REPO, 2, state="open")
    assert (
        collapse(request_kind(list(request.argv[1:])) for request in planned.requests),
        planned.mode,
    ) == (fake.kinds(), "dry-run")


def test_a_plan_dry_run_lists_no_write() -> None:
    planned = reconcile_dry_run("o", REPO, 2, writes=False)
    assert [r for r in planned.requests if "item-edit" in r.argv] == []


def test_the_issue_fetch_leaves_pull_requests_to_the_pulls_fetch() -> None:
    """Read as issues, pull requests lack their merge state and would be reconciled twice."""
    from devops_cli.github.projects import _fetch_repository_issues

    listing = [{"number": 1, "html_url": "u1"}, {"number": 2, "html_url": "u2", "pull_request": {}}]
    with patch(
        "devops_cli.github.projects.run_gh",
        return_value=MagicMock(returncode=0, stdout=json.dumps(listing), stderr=""),
    ):
        assert [it["number"] for it in _fetch_repository_issues("owner/repo")] == [1]
