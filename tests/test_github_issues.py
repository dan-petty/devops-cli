"""Unit tests for GitHub Issues subsystem."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.issues import (
    GitHubIssue,
    IssueTriageAudit,
    audit_issues_triage,
    create_repository_issue,
    get_issues_summary,
    get_repository_issues,
)


def test_github_issue_model() -> None:
    """GitHubIssue model validates correctly."""
    issue = GitHubIssue(
        number=77,
        title="feat(rag): dedicated library vector tier",
        state="open",
        milestone="v0.2.14",
        labels=["type/feature", "scope/ai", "priority/p2-medium"],
        assignees=["dan-petty"],
        url="https://github.com/dan-petty/devops-cli/issues/77",
    )
    assert issue.number == 77
    assert issue.milestone == "v0.2.14"
    assert "type/feature" in issue.labels


def test_issue_triage_audit_model() -> None:
    """IssueTriageAudit records triage metrics accurately."""
    audit = IssueTriageAudit(
        total_open=10,
        valid_count=8,
        issues_missing_type=[1, 2],
        issues_missing_scope=[2],
        issues_missing_priority=[1],
        issues_missing_milestone=[3],
    )
    assert audit.total_open == 10
    assert audit.valid_count == 8
    assert len(audit.issues_missing_type) == 2
    assert audit.compliance_rate == 80.0


def test_get_repository_issues_success() -> None:
    """get_repository_issues parses JSON from gh CLI."""
    payload = [
        {
            "number": 77,
            "title": "feat(rag): dedicated library vector tier",
            "state": "OPEN",
            "milestone": {"title": "v0.2.14"},
            "labels": [{"name": "type/feature"}, {"name": "scope/ai"}],
            "assignees": [{"login": "dan-petty"}],
            "url": "https://github.com/dan-petty/devops-cli/issues/77",
        }
    ]
    with patch("devops_cli.github.issues.run_subprocess") as mock_proc:
        mock_proc.return_value = MagicMock(returncode=0, stdout=json.dumps(payload))
        issues = get_repository_issues("dan-petty/devops-cli")
        assert len(issues) == 1
        assert issues[0].number == 77
        assert issues[0].milestone == "v0.2.14"
        assert "type/feature" in issues[0].labels


def test_create_repository_issue_success() -> None:
    """create_repository_issue creates issue with proper command arguments."""
    payload = {
        "number": 84,
        "title": "fix(ci): improve timeout",
        "state": "OPEN",
        "milestone": {"title": "v0.2.14"},
        "labels": [{"name": "type/bug"}, {"name": "scope/ci"}, {"name": "priority/p1-high"}],
        "assignees": [],
        "url": "https://github.com/dan-petty/devops-cli/issues/84",
    }
    with patch("devops_cli.github.issues.run_subprocess") as mock_proc:
        mock_proc.return_value = MagicMock(returncode=0, stdout=json.dumps(payload))
        issue = create_repository_issue(
            repo="dan-petty/devops-cli",
            title="fix(ci): improve timeout",
            body="Description",
            milestone="v0.2.14",
            labels=["type/bug", "scope/ci", "priority/p1-high"],
        )
        assert issue.number == 84
        assert issue.title == "fix(ci): improve timeout"


def test_audit_issues_triage() -> None:
    """audit_issues_triage categorizes missing taxonomy labels."""
    issues = [
        GitHubIssue(
            number=1,
            title="Properly labeled issue",
            state="open",
            milestone="v0.2.14",
            labels=["type/feature", "scope/ai", "priority/p2-medium"],
        ),
        GitHubIssue(
            number=2,
            title="Missing scope and priority",
            state="open",
            milestone="v0.2.14",
            labels=["type/bug"],
        ),
        GitHubIssue(
            number=3,
            title="Missing all taxonomy labels and milestone",
            state="open",
            milestone=None,
            labels=[],
        ),
    ]
    with patch("devops_cli.github.issues.get_repository_issues", return_value=issues):
        audit = audit_issues_triage("dan-petty/devops-cli")
        assert audit.total_open == 3
        assert audit.valid_count == 1
        assert 3 in audit.issues_missing_type
        assert 2 in audit.issues_missing_scope
        assert 3 in audit.issues_missing_scope
        assert 2 in audit.issues_missing_priority
        assert 3 in audit.issues_missing_milestone


def test_get_issues_summary() -> None:
    """get_issues_summary produces breakdown aggregates."""
    issues = [
        GitHubIssue(
            number=1,
            title="Bug 1",
            state="open",
            milestone="v0.2.14",
            labels=["type/bug", "scope/ai", "priority/p0-critical"],
        ),
        GitHubIssue(
            number=2,
            title="Feature 1",
            state="open",
            milestone="v0.2.14",
            labels=["type/feature", "scope/k8s", "priority/p2-medium"],
        ),
    ]
    with patch("devops_cli.github.issues.get_repository_issues", return_value=issues):
        summary = get_issues_summary("dan-petty/devops-cli")
        assert summary["total_open"] == 2
        assert summary["by_priority"]["priority/p0-critical"] == 1
        assert summary["by_type"]["type/bug"] == 1
        assert summary["by_milestone"]["v0.2.14"] == 2


def test_create_repository_issue_failure_bounds_title_in_error_details() -> None:
    """Verify that GitHubOperationError details truncates unbounded title to max 256 chars."""
    huge_title = "fix(security): " + ("A" * 1500)
    with patch("devops_cli.github.issues.run_subprocess") as mock_proc:
        mock_proc.return_value = MagicMock(returncode=1, stderr="GraphQL mutation error", stdout="")
        with pytest.raises(GitHubOperationError) as exc_info:
            create_repository_issue(
                repo="dan-petty/devops-cli",
                title=huge_title,
                body="Issue description",
            )
        err = exc_info.value
        assert err.details is not None
        assert "title" in err.details
        assert len(err.details["title"]) <= 256
        assert err.details["title"] == huge_title[:256]
