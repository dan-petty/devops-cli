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
    assert infer_item_status("CLOSED", []) == "Done"
    assert infer_item_status("MERGED", []) == "Done"
    assert infer_item_status("OPEN", ["status/in-progress"]) == "In Progress"
    assert infer_item_status("OPEN", [{"name": "status/in-review"}]) == "In Review"
    assert infer_item_status("OPEN", ["status/ready"]) == "Ready"
    assert infer_item_status("OPEN", ["status/blocked"]) == "Blocked"
    assert infer_item_status("OPEN", ["status/backlog"]) == "Backlog"
    assert infer_item_status("OPEN", [], is_pr=True) == "In Review"
    assert infer_item_status("OPEN", [], has_open_pr=True) == "In Review"
    assert infer_item_status("OPEN", []) == "Ready"


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
    res = reconcile_project_custom_fields(
        owner="owner",
        repo="owner/repo",
        project_number=2,
        dry_run=True,
    )
    assert res["dry_run"] is True
    assert res["project_number"] == 2
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
        if "items" in cmd_str:
            res.stdout = json.dumps(existing_items_resp)
        elif "repos/owner/repo/issues" in cmd_str:
            res.stdout = json.dumps(issues_resp)
        elif "repos/owner/repo/pulls" in cmd_str:
            res.stdout = json.dumps([])
        else:
            res.stdout = ""
        return res

    with (
        patch("devops_cli.github.projects._get_authenticated_user", return_value="owner"),
        patch(
            "devops_cli.github.projects.run_subprocess", side_effect=mock_run_subprocess
        ) as mock_cmd,
    ):
        res = reconcile_project_custom_fields(
            owner="owner",
            repo="owner/repo",
            project_number=2,
            dry_run=False,
        )
        assert res["dry_run"] is False
        assert res["items_reconciled"] >= 1
        # Verify item-edit was called
        edit_calls = [c for c in mock_cmd.call_args_list if "item-edit" in c[0][0]]
        assert len(edit_calls) >= 5  # Status, Priority, Category, Value, Effort
