"""Unit tests for GitHub Issues subsystem."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import httpx2
import pytest

from devops_cli.exceptions.git import (
    GitHubNotFoundError,
    GitHubOperationError,
    GitHubUnreadError,
)
from devops_cli.github.issues import (
    GitHubIssue,
    IssueTriageAudit,
    _fetch_issues_rest,
    audit_issues_triage,
    create_repository_issue,
    get_issues_summary,
    get_repository_issues,
)
from tests.support.fakes.github import JSON_TYPE, GitHubApiFake, github_json, next_page


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
        issues_awaiting_intake=[3],
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
    with patch("devops_cli.github.issues.run_gh") as mock_proc:
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
    with patch("devops_cli.github.issues.run_gh") as mock_proc:
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


def test_triage_reports_an_issue_off_the_board_once_as_awaiting_intake() -> None:
    """A backlog item has no milestone, and an issue off the board has no Priority until intake
    gives it one, so neither is a triage finding (#742)."""
    issues = [
        GitHubIssue(
            number=1,
            title="Backlog item",
            state="open",
            milestone=None,
            labels=["type/feature", "scope/cli", "priority/p2-medium"],
        ),
        GitHubIssue(number=2, title="Not on the board yet", state="open", labels=[]),
    ]
    with patch("devops_cli.github.issues.get_repository_issues", return_value=issues):
        audit = audit_issues_triage("dan-petty/devops-cli", awaiting_intake={2})
    assert (
        audit.valid_count,
        audit.issues_awaiting_intake,
        audit.issues_missing_type,
        audit.issues_missing_scope,
        audit.issues_missing_priority,
    ) == (1, [2], [], [], [])


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
    with patch("devops_cli.github.issues.run_gh") as mock_proc:
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


def test_get_repository_issues_graphql_rate_limit_fallback_to_rest(
    github_api: GitHubApiFake,
) -> None:
    """Verify get_repository_issues falls back to REST API when gh issue list hits GraphQL rate limit."""
    mock_gh_cli_err = MagicMock(
        returncode=1,
        stderr="GraphQL: API rate limit already exceeded for user ID 7726889.",
        stdout="",
    )
    rest_issues_payload = [
        {
            "number": 180,
            "title": "fix(github): add REST API fallback",
            "state": "open",
            "milestone": {"title": "v0.2.17"},
            "labels": [{"name": "type/bug"}, {"name": "scope/github"}],
            "assignees": [{"login": "dan-petty"}],
            "html_url": "https://example.com/dan-petty/devops-cli/issues/180",
        },
        {
            "number": 182,
            "title": "A pull request item",
            "state": "open",
            "pull_request": {"url": "https://example.com/dan-petty/devops-cli/pulls/182"},
            "labels": [],
            "html_url": "https://example.com/dan-petty/devops-cli/pull/182",
        },
    ]
    github_api.route(
        "GET",
        "/repos/dan-petty/devops-cli/issues?state=open&per_page=100",
        github_json(rest_issues_payload),
    )

    with patch("devops_cli.github.issues.run_gh", side_effect=[mock_gh_cli_err]):
        issues = get_repository_issues("dan-petty/devops-cli", milestone="v0.2.17")
        assert len(issues) == 1
        assert issues[0].number == 180
        assert issues[0].title == "fix(github): add REST API fallback"
        assert issues[0].milestone == "v0.2.17"
        assert "type/bug" in issues[0].labels


def test_issue_triage_audit_empty_total_open() -> None:
    """compliance_rate returns 100.0 when total_open is 0."""
    audit = IssueTriageAudit(total_open=0, valid_count=0)
    assert audit.compliance_rate == 100.0


def test_issue_parsing_helpers_edge_cases() -> None:
    """Helper functions handle invalid types, string assignees/labels, and string milestones."""
    from devops_cli.github.issues import (
        _parse_issue_assignees,
        _parse_issue_labels,
        _parse_single_issue,
    )

    assert _parse_issue_labels(None) == []
    assert _parse_issue_labels(["plain_string_label", {"name": "dict_label"}]) == [
        "plain_string_label",
        "dict_label",
    ]

    assert _parse_issue_assignees(None) == []
    assert _parse_issue_assignees(["plain_user", {"login": "dict_user"}]) == [
        "plain_user",
        "dict_user",
    ]

    issue = _parse_single_issue(
        {
            "number": 99,
            "title": "Title",
            "milestone": "v0.2.17",
            "labels": ["type/bug"],
        }
    )
    assert issue.milestone == "v0.2.17"


_REST_ISSUES = "/repos/octo/repo/issues?state=open&per_page=100"


def _issue(number: int, milestone: str) -> dict[str, Any]:
    """An issue as the REST API lists it."""
    return {"number": number, "title": f"Issue {number}", "milestone": {"title": milestone}}


def test_fetch_issues_rest_reads_every_page_and_filters(github_api: GitHubApiFake) -> None:
    """The REST read follows the pages, asks for the labels, keeps the milestone's issues and
    leaves out pull requests."""
    second = "/repositories/1/issues?state=open&per_page=100&labels=type%2Fbug&page=2"
    pull = {"number": 4, "title": "A pull request", "pull_request": {}, "milestone": None}
    github_api.route(
        "GET",
        f"{_REST_ISSUES}&labels=type%2Fbug",
        github_json([_issue(1, "v0.2.17"), _issue(2, "v0.2.18"), pull], headers=next_page(second)),
    )
    github_api.route("GET", second, github_json([_issue(3, "v0.2.17")]))
    issues = _fetch_issues_rest("octo/repo", milestone="v0.2.17", labels=["type/bug"], limit=None)
    assert ([issue.number for issue in issues], len(github_api.sent)) == ([1, 3], 2)


def test_fetch_issues_rest_stops_reading_at_its_limit(github_api: GitHubApiFake) -> None:
    """Once `limit` issues are read, no further page is requested."""
    second = "/repositories/1/issues?state=open&per_page=100&page=2"
    github_api.route(
        "GET", _REST_ISSUES, github_json([_issue(1, "v0.2.17")], headers=next_page(second))
    )
    github_api.route("GET", second, github_json([_issue(2, "v0.2.17")]))
    issues = _fetch_issues_rest("octo/repo", limit=1)
    assert ([issue.number for issue in issues], len(github_api.sent)) == ([1], 1)


@pytest.mark.parametrize(
    ("answer", "error"),
    [
        pytest.param(
            github_json({"message": "Bad Gateway"}, status=502), GitHubUnreadError, id="5xx"
        ),
        pytest.param(
            github_json({"message": "Not Found"}, status=404), GitHubNotFoundError, id="404"
        ),
        pytest.param(github_json({}), GitHubUnreadError, id="not-a-list"),
        pytest.param(
            httpx2.Response(200, headers={"content-type": JSON_TYPE}, content=b"not-json"),
            GitHubUnreadError,
            id="not-json",
        ),
    ],
)
def test_fetch_issues_rest_fails_closed(
    github_api: GitHubApiFake, answer: httpx2.Response, error: type[Exception]
) -> None:
    """A read that fails, or an answer that is no list of issues, raises: it never reads as a
    repository with no issues."""
    github_api.route("GET", _REST_ISSUES, answer)
    with pytest.raises(GitHubOperationError) as raised:
        _fetch_issues_rest("octo/repo")
    assert type(raised.value) is error
