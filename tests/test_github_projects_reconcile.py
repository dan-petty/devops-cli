"""Unit tests for GitHub Projects v2 custom field reconciler."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from devops_cli.github.projects import (
    infer_item_category_value_effort,
    infer_item_priority,
    infer_item_status,
    reconcile_project_custom_fields,
)


def test_infer_item_priority() -> None:
    assert infer_item_priority(["priority/p0-critical", "type/bug"]) == "P0-Critical"
    assert infer_item_priority([{"name": "priority/p1-high"}]) == "P1-High"
    assert infer_item_priority(["priority/p2-medium"]) == "P2-Medium"
    assert infer_item_priority(["priority/p3-low"]) == "P3-Low"
    assert infer_item_priority([]) == "P2-Medium"


def test_infer_item_status() -> None:
    results = (
        infer_item_status("CLOSED", []),
        infer_item_status("MERGED", []),
        infer_item_status("OPEN", ["status/in-progress"]),
        infer_item_status("OPEN", [{"name": "status/in-review"}]),
        infer_item_status("OPEN", ["status/ready"]),
        infer_item_status("OPEN", ["status/blocked"]),
        infer_item_status("OPEN", ["status/backlog"]),
        infer_item_status("OPEN", [], is_pr=True),
        infer_item_status("OPEN", [], is_pr=True, is_draft=True),
        infer_item_status("OPEN", [], is_pr=True, is_draft=False),
        infer_item_status("OPEN", [], has_open_pr=True),
        infer_item_status("OPEN", []),
    )
    expected = (
        "Done",
        "Done",
        "In Progress",
        "In Review",
        "Ready",
        "Blocked",
        "Backlog",
        "In Review",
        "In Progress",
        "In Review",
        "In Review",
        "Ready",
    )
    assert results == expected


def test_infer_item_category_value_effort() -> None:
    cat, val, eff = infer_item_category_value_effort("Tree-sitter AST parser", "P1-High")
    assert cat == "Major Project"
    assert val == "High"
    assert eff == "High"

    cat, val, eff = infer_item_category_value_effort("FastMCP Library Tools", "P0-Critical")
    assert cat == "Quick Win"
    assert val == "High"
    assert eff == "Low"

    cat, val, eff = infer_item_category_value_effort("Library Vector Store and Cache", "P1-High")
    assert cat == "Foundation"
    assert val == "High"
    assert eff == "Medium"


def test_infer_item_category_value_effort_from_labels() -> None:
    # type/security -> Quick Win, High, Low
    cat, val, eff = infer_item_category_value_effort(
        "Custom Secret Tool", "P2-Medium", labels=["type/security"]
    )
    assert cat == "Quick Win"
    assert val == "High"
    assert eff == "Low"

    # type/docs -> Fill-In, Medium, Low
    cat, val, eff = infer_item_category_value_effort(
        "Update User Manual", "P2-Medium", labels=["type/docs"]
    )
    assert cat == "Fill-In"
    assert val == "Medium"
    assert eff == "Low"

    # type/feature -> Major Project, High, High
    cat, val, eff = infer_item_category_value_effort(
        "Polyglot Engine", "P1-High", labels=[{"name": "type/feature"}]
    )
    assert cat == "Major Project"
    assert val == "High"
    assert eff == "High"


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
        assert (res["dry_run"], res["project_number"]) == (True, 2)
        assert "items_evaluated" in res


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
        assert (res["dry_run"], res["items_reconciled"] >= 1) == (False, True)
        # Verify item-edit was called
        edit_calls = [c for c in mock_cmd.call_args_list if "item-edit" in c[0][0]]
        assert len(edit_calls) >= 5  # Status, Priority, Category, Value, Effort


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


def test_reconcile_project_custom_fields_fetch_failure_skips_mutations() -> None:
    with (
        patch("devops_cli.github.projects._is_graphql_quota_exhausted", return_value=False),
        patch("devops_cli.github.projects._fetch_project_items_data", return_value=None),
    ):
        res = reconcile_project_custom_fields(
            owner="owner",
            repo="owner/repo",
            project_number=2,
            dry_run=False,
        )
        assert res["items_evaluated"] == 0
        assert res["items_reconciled"] == 0


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
        patch("devops_cli.github.projects._reconcile_candidate_items", return_value=1),
    ):
        res = reconcile_project_custom_fields(
            owner="owner",
            repo="owner/repo",
            project_number=2,
            dry_run=False,
        )
        assert (res["items_evaluated"], res["items_reconciled"]) == (1, 1)
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
        patch("devops_cli.github.projects._reconcile_candidate_items", return_value=1),
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
