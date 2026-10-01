"""Unit tests for GitHub Projects v2 custom field reconciler."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.projects import (
    FieldChange,
    plan_item_changes,
    reconcile_project_custom_fields,
)

_URL = "https://github.com/owner/repo/issues/7"
_STATUSES = ("Backlog", "Ready", "In Progress", "In Review", "Done")


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
        ("Status", None, "Backlog", "default for an unset status")
    ]


def test_blocked_maps_only_when_the_board_has_a_blocked_status() -> None:
    with_blocked = plan_item_changes(
        _issue(labels=["status/blocked"]), {}, status_options=(*_STATUSES, "Blocked")
    )
    assert (
        _changes(_issue(labels=["status/blocked"])),
        [(c.field, c.new) for c in with_blocked],
    ) == (
        [("Status", None, "Backlog", "default for an unset status")],
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
        _changes(ready, {"status": "Backlog"}),
        _changes(draft, {"status": "Backlog"}),
    ) == (
        [("Status", "Backlog", "In Review", "open pull request")],
        [("Status", "Backlog", "In Progress", "draft pull request")],
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


def test_category_value_and_effort_are_never_inferred() -> None:
    """An inferred field that keeps writing reads as decided; unset is honest."""
    fields = [c[0] for c in _changes(_issue(labels=["type/feature", "priority/p0-critical"]))]
    assert {"Category", "Value", "Effort"} & set(fields) == set()


def test_the_milestone_field_mirrors_the_issue_milestone() -> None:
    item = _issue(milestone={"title": "v0.2.24"})
    assert _changes(item, {"status": "Ready", "milestone": "v0.2.23"}) == [
        ("Milestone", "v0.2.23", "v0.2.24", "issue milestone")
    ]


def test_a_field_change_records_the_item_it_belongs_to() -> None:
    change = plan_item_changes(_issue(state="CLOSED"), {}, status_options=_STATUSES)[0]
    assert change == FieldChange(
        url=_URL, field="Status", old=None, new="Done", source="issue closed"
    )


def test_reconcile_project_custom_fields_dry_run() -> None:
    with (
        patch("devops_cli.github.projects._is_graphql_quota_exhausted", return_value=False),
        patch("devops_cli.github.projects._fetch_project_items_data", return_value={}),
        patch("devops_cli.github.projects._fetch_repository_issues", return_value=[]),
        patch("devops_cli.github.projects._fetch_repository_prs", return_value=[]),
    ):
        res = reconcile_project_custom_fields(
            owner="owner",
            repo="owner/repo",
            project_number=2,
            dry_run=True,
        )
        assert (res["dry_run"], res["project_number"], res["changes"]) == (True, 2, [])


def test_reconcile_project_custom_fields_live() -> None:
    existing_items_resp = [
        {
            "id": "item_1",
            "content": {"url": "https://example.com/owner/repo/issues/74"},
        }
    ]
    issues_resp = [
        {
            "number": 74,
            "title": "feat(ai): Tree-sitter AST Graph",
            "url": "https://example.com/owner/repo/issues/74",
            "state": "OPEN",
            "labels": [{"name": "priority/p1-high"}, {"name": "status/in-progress"}],
        }
    ]

    def mock_run_subprocess(cmd: list[str], **kwargs: object) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        cmd_str = " ".join(cmd)
        if "item-list" in cmd_str:
            res.stdout = json.dumps(existing_items_resp)
        elif "repos/owner/repo/issues" in cmd_str:
            res.stdout = json.dumps(issues_resp)
        elif "repos/owner/repo/pulls" in cmd_str:
            res.stdout = json.dumps([])
        else:
            res.stdout = ""
        return res

    with (
        patch("devops_cli.github.projects._is_graphql_quota_exhausted", return_value=False),
        patch("devops_cli.github.projects._get_authenticated_user", return_value="owner"),
        patch("devops_cli.github.projects.run_gh", side_effect=mock_run_subprocess) as mock_cmd,
    ):
        res = reconcile_project_custom_fields(
            owner="owner",
            repo="owner/repo",
            project_number=2,
            dry_run=False,
        )
        edited = [
            c[0][0][c[0][0].index("--field") + 1]
            for c in mock_cmd.call_args_list
            if "item-edit" in c[0][0]
        ]
        assert (res["dry_run"], res["items_reconciled"], edited, res["changes"]) == (
            False,
            1,
            ["Status", "Priority"],
            [
                {
                    "url": "https://example.com/owner/repo/issues/74",
                    "field": "Status",
                    "old": None,
                    "new": "In Progress",
                    "source": "label status/in-progress",
                },
                {
                    "url": "https://example.com/owner/repo/issues/74",
                    "field": "Priority",
                    "old": None,
                    "new": "P1-High",
                    "source": "label priority/p1-high",
                },
            ],
        )


def test_is_graphql_quota_exhausted() -> None:
    import time

    from devops_cli.github.projects import _is_graphql_quota_exhausted
    from devops_cli.github.rate_limiter import QuotaState

    mock_limiter = MagicMock()
    # When remaining is None (quota unknown), exhausted = True (must not run)
    mock_limiter.get_quota.return_value = QuotaState(remaining=None, last_updated=0.0)
    with patch("devops_cli.github.projects.get_github_rate_limiter", return_value=mock_limiter):
        assert _is_graphql_quota_exhausted(threshold=25) is True

    # When quota is expired or reset_epoch in the past, exhausted = True (must not run)
    mock_limiter.get_quota.return_value = QuotaState(
        remaining=100, reset_epoch=time.time() - 10, last_updated=100.0
    )
    with patch("devops_cli.github.projects.get_github_rate_limiter", return_value=mock_limiter):
        assert _is_graphql_quota_exhausted(threshold=25) is True

    # When remaining < threshold and valid, exhausted = True
    future_epoch = time.time() + 3600
    mock_limiter.get_quota.return_value = QuotaState(
        remaining=10, reset_epoch=future_epoch, last_updated=100.0
    )
    with patch("devops_cli.github.projects.get_github_rate_limiter", return_value=mock_limiter):
        assert _is_graphql_quota_exhausted(threshold=25) is True

    # When remaining >= threshold and valid, not exhausted
    mock_limiter.get_quota.return_value = QuotaState(
        remaining=100, reset_epoch=future_epoch, last_updated=100.0
    )
    with patch("devops_cli.github.projects.get_github_rate_limiter", return_value=mock_limiter):
        assert _is_graphql_quota_exhausted(threshold=25) is False


def test_reconcile_project_custom_fields_quota_exhausted() -> None:
    with patch("devops_cli.github.projects._is_graphql_quota_exhausted", return_value=True):
        res = reconcile_project_custom_fields(
            owner="owner",
            repo="owner/repo",
            project_number=2,
            dry_run=False,
        )
        assert res["items_evaluated"] == 0
        assert res["items_reconciled"] == 0


def test_a_failed_fetch_raises_rather_than_reading_as_empty() -> None:
    """A failed read must stay distinct from a board or repository with nothing in it."""
    failed = MagicMock(returncode=1, stdout="", stderr="HTTP 502")
    with (
        patch("devops_cli.github.projects._is_graphql_quota_exhausted", return_value=False),
        patch("devops_cli.github.projects._get_authenticated_user", return_value="owner"),
        patch("devops_cli.github.projects.run_gh", return_value=failed),
        pytest.raises(GitHubOperationError),
    ):
        reconcile_project_custom_fields(
            owner="owner",
            repo="owner/repo",
            project_number=2,
            dry_run=False,
        )


def test_reconcile_project_custom_fields_empty_project_provisions_candidates() -> None:
    mock_issues = [
        {
            "html_url": "https://github.com/owner/repo/issues/1",
            "title": "Issue 1",
            "state": "open",
            "labels": [],
        }
    ]
    with (
        patch("devops_cli.github.projects._is_graphql_quota_exhausted", return_value=False),
        patch("devops_cli.github.projects._fetch_project_items_data", return_value={}),
        patch("devops_cli.github.projects._fetch_repository_issues", return_value=mock_issues),
        patch("devops_cli.github.projects._fetch_repository_prs", return_value=[]),
        patch("devops_cli.github.projects._provision_missing_candidates") as mock_prov,
        patch("devops_cli.github.projects._reconcile_candidate_items", return_value=[]),
    ):
        res = reconcile_project_custom_fields(
            owner="owner",
            repo="owner/repo",
            project_number=2,
            dry_run=False,
        )
        assert (res["items_evaluated"], res["items_reconciled"]) == (1, 0)
        mock_prov.assert_called_once()


def test_reconcile_project_custom_fields_skips_when_quota_unknown() -> None:
    """Verify reconcile_project_custom_fields never runs if quota is unknown for any reason."""
    from devops_cli.github.rate_limiter import QuotaState

    mock_limiter = MagicMock()
    mock_limiter.get_quota.return_value = QuotaState(remaining=None, last_updated=0.0)
    with patch("devops_cli.github.projects.get_github_rate_limiter", return_value=mock_limiter):
        res = reconcile_project_custom_fields(
            owner="owner",
            repo="owner/repo",
            project_number=2,
            dry_run=False,
        )
        assert (res["items_evaluated"], res["items_reconciled"]) == (0, 0)


def test_sync_project_items_skips_when_quota_unknown() -> None:
    """Verify sync_repository_issues_to_project never runs if quota is unknown for any reason."""
    from devops_cli.github.projects import sync_repository_issues_to_project
    from devops_cli.github.rate_limiter import QuotaState

    mock_limiter = MagicMock()
    mock_limiter.get_quota.return_value = QuotaState(remaining=None, last_updated=0.0)
    with patch("devops_cli.github.projects.get_github_rate_limiter", return_value=mock_limiter):
        added = sync_repository_issues_to_project(
            owner="owner",
            repo="owner/repo",
            project_number=2,
            dry_run=False,
        )
        assert added == 0


def test_reconcile_project_custom_fields_dry_run_filters_offboard_candidates() -> None:
    """Assert that off-board items are excluded in dry_run=True and evaluated in dry_run=False."""
    active_items = {
        "https://example.com/owner/repo/issues/1": {"id": "item_1", "status": "Ready"},
    }
    mock_issues = [
        {
            "html_url": "https://example.com/owner/repo/issues/1",
            "title": "On Board Issue",
            "state": "open",
            "labels": [],
        },
        {
            "html_url": "https://example.com/owner/repo/issues/2",
            "title": "Off Board Issue",
            "state": "open",
            "labels": [],
        },
    ]

    with (
        patch("devops_cli.github.projects._is_graphql_quota_exhausted", return_value=False),
        patch("devops_cli.github.projects._fetch_project_items_data", return_value=active_items),
        patch("devops_cli.github.projects._fetch_repository_issues", return_value=mock_issues),
        patch("devops_cli.github.projects._fetch_repository_prs", return_value=[]),
        patch("devops_cli.github.projects._provision_missing_candidates") as mock_prov,
        patch("devops_cli.github.projects._reconcile_candidate_items", return_value=[]),
    ):
        res_dry = reconcile_project_custom_fields(
            owner="owner",
            repo="owner/repo",
            project_number=2,
            dry_run=True,
        )
        assert (res_dry["dry_run"], res_dry["items_evaluated"]) == (True, 1)
        mock_prov.assert_not_called()

        res_live = reconcile_project_custom_fields(
            owner="owner",
            repo="owner/repo",
            project_number=2,
            dry_run=False,
        )
        assert (res_live["dry_run"], res_live["items_evaluated"]) == (False, 2)
        mock_prov.assert_called_once()


def test_the_issue_fetch_leaves_pull_requests_to_the_pulls_fetch() -> None:
    """Read as issues, pull requests lack their merge state and would be reconciled twice."""
    from devops_cli.github.projects import _fetch_repository_issues

    listing = [{"number": 1, "html_url": "u1"}, {"number": 2, "html_url": "u2", "pull_request": {}}]
    with patch(
        "devops_cli.github.projects.run_gh",
        return_value=MagicMock(returncode=0, stdout=json.dumps(listing), stderr=""),
    ):
        assert [it["number"] for it in _fetch_repository_issues("owner/repo")] == [1]
