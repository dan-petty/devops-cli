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
    _parse_single_issue,
    audit_issues_triage,
    create_repository_issue,
    get_issues_summary,
    get_repository_issue,
    get_repository_issues,
    render_issue,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import ItemField
from tests.support.fakes.github import JSON_TYPE, GitHubApiFake, github_json, next_page


def test_github_issue_model() -> None:
    """GitHubIssue model validates correctly."""
    issue = GitHubIssue(
        number=77,
        title="feat(rag): dedicated library vector tier",
        state="open",
        milestone="2026-11",
        labels=["type/feature", "scope/ai"],
        assignees=["dan-petty"],
        url="https://github.com/dan-petty/devops-cli/issues/77",
    )
    assert issue.number == 77
    assert issue.milestone == "2026-11"
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
            "milestone": {"title": "2026-11"},
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
        assert issues[0].milestone == "2026-11"
        assert "type/feature" in issues[0].labels


def test_create_repository_issue_success() -> None:
    """create_repository_issue creates issue with proper command arguments."""
    payload = {
        "number": 84,
        "title": "fix(ci): improve timeout",
        "state": "OPEN",
        "milestone": {"title": "2026-11"},
        "labels": [{"name": "type/bug"}, {"name": "scope/ci"}],
        "assignees": [],
        "url": "https://github.com/dan-petty/devops-cli/issues/84",
    }
    with patch("devops_cli.github.issues.run_gh") as mock_proc:
        mock_proc.return_value = MagicMock(returncode=0, stdout=json.dumps(payload))
        issue = create_repository_issue(
            repo="dan-petty/devops-cli",
            title="fix(ci): improve timeout",
            body="Description",
            milestone="2026-11",
            labels=["type/bug", "scope/ci"],
        )
        assert issue.number == 84
        assert issue.title == "fix(ci): improve timeout"


def test_audit_issues_triage() -> None:
    """audit_issues_triage categorizes missing taxonomy labels and board Priority."""
    store = InMemoryRoadmapStore(
        board_options={ItemField.PRIORITY: ["P0-Critical", "P1-High", "P2-Medium", "P3-Low"]}
    )
    store.seed_milestone("2026-11")
    i1 = store.seed_issue(
        "Properly labeled and prioritized issue",
        on_board=True,
        milestone="2026-11",
        labels=["type/feature", "scope/ai"],
    )
    store.set_field(store.item(i1), ItemField.PRIORITY, "P2-Medium")

    i2 = store.seed_issue(
        "Missing scope and priority",
        on_board=True,
        milestone="2026-11",
        labels=["type/bug"],
    )
    i3 = store.seed_issue(
        "Missing all taxonomy labels and priority",
        on_board=True,
        milestone=None,
        labels=[],
    )

    audit = audit_issues_triage("dan-petty/devops-cli", store=store)
    assert audit.total_open == 3
    assert audit.valid_count == 1
    assert i3 in audit.issues_missing_type
    assert i2 in audit.issues_missing_scope
    assert i3 in audit.issues_missing_scope
    assert i2 in audit.issues_missing_priority
    assert i3 in audit.issues_missing_priority
    assert i1 not in audit.issues_missing_priority


def test_triage_reports_an_issue_off_the_board_once_as_awaiting_intake() -> None:
    """A backlog item has no milestone, and an issue off the board has no Priority until intake
    gives it one, so neither is a triage finding (#742)."""
    store = InMemoryRoadmapStore(
        board_options={ItemField.PRIORITY: ["P0-Critical", "P1-High", "P2-Medium", "P3-Low"]}
    )
    i1 = store.seed_issue(
        "Backlog item",
        on_board=True,
        milestone=None,
        labels=["type/feature", "scope/cli"],
    )
    store.set_field(store.item(i1), ItemField.PRIORITY, "P2-Medium")
    i2 = store.seed_issue("Not on the board yet", on_board=False, labels=[])

    audit = audit_issues_triage("dan-petty/devops-cli", store=store)
    assert (
        audit.valid_count,
        audit.issues_awaiting_intake,
        audit.issues_missing_type,
        audit.issues_missing_scope,
        audit.issues_missing_priority,
    ) == (1, [i2], [], [], [])


def test_triage_flags_open_item_with_priority_label_but_no_board_priority() -> None:
    """Criterion 2: An issue with a priority/* label but no Priority field value on the board
    counts as unprioritized in triage."""
    store = InMemoryRoadmapStore(
        board_options={ItemField.PRIORITY: ["P0-Critical", "P1-High", "P2-Medium", "P3-Low"]}
    )
    i1 = store.seed_issue(
        "Stray label item",
        on_board=True,
        milestone=None,
        labels=["type/feature", "scope/cli", "priority/stray-label"],
    )
    audit = audit_issues_triage("dan-petty/devops-cli", store=store)
    assert audit.total_open == 1
    assert audit.valid_count == 0
    assert i1 in audit.issues_missing_priority


def test_triage_and_status_count_over_100_open_issues() -> None:
    """Criterion 3: With more than 100 open issues, every one is counted."""
    store = InMemoryRoadmapStore(
        board_options={ItemField.PRIORITY: ["P0-Critical", "P1-High", "P2-Medium", "P3-Low"]}
    )
    for i in range(120):
        store.seed_issue(f"Open item {i}", on_board=True, labels=["type/feature", "scope/cli"])
    for i in range(15):
        store.seed_issue(f"Candidate {i}", on_board=False, labels=["type/bug", "scope/cli"])

    audit = audit_issues_triage("dan-petty/devops-cli", store=store)
    summary = get_issues_summary("dan-petty/devops-cli", store=store)
    assert audit.total_open == 135
    assert summary["total_open"] == 135
    assert len(audit.issues_awaiting_intake) == 15


def test_triage_backlog_item_without_milestone_is_not_flagged() -> None:
    """Criterion 4: A backlog item without a milestone is not flagged."""
    store = InMemoryRoadmapStore(
        board_options={ItemField.PRIORITY: ["P0-Critical", "P1-High", "P2-Medium", "P3-Low"]}
    )
    i1 = store.seed_issue(
        "Backlog feature",
        on_board=True,
        milestone=None,
        labels=["type/feature", "scope/cli"],
    )
    store.set_field(store.item(i1), ItemField.PRIORITY, "P3-Low")

    audit = audit_issues_triage("dan-petty/devops-cli", store=store)
    assert audit.total_open == 1
    assert audit.valid_count == 1
    assert audit.issues_missing_type == []
    assert audit.issues_missing_scope == []
    assert audit.issues_missing_priority == []


def test_get_issues_summary() -> None:
    """get_issues_summary produces breakdown aggregates using board Priority."""
    store = InMemoryRoadmapStore(
        board_options={ItemField.PRIORITY: ["P0-Critical", "P1-High", "P2-Medium", "P3-Low"]}
    )
    store.seed_milestone("2026-11")
    i1 = store.seed_issue(
        "Bug 1",
        on_board=True,
        milestone="2026-11",
        labels=["type/bug", "scope/ai"],
    )
    store.set_field(store.item(i1), ItemField.PRIORITY, "P0-Critical")

    i2 = store.seed_issue(
        "Feature 1",
        on_board=True,
        milestone="2026-11",
        labels=["type/feature", "scope/k8s"],
    )
    store.set_field(store.item(i2), ItemField.PRIORITY, "P2-Medium")

    summary = get_issues_summary("dan-petty/devops-cli", store=store)
    assert summary["total_open"] == 2
    assert summary["by_priority"]["P0-Critical"] == 1
    assert summary["by_priority"]["P2-Medium"] == 1
    assert summary["by_type"]["type/bug"] == 1
    assert summary["by_type"]["type/feature"] == 1
    assert summary["by_milestone"]["2026-11"] == 2


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
            "milestone": {"title": "2026-12"},
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
        issues = get_repository_issues("dan-petty/devops-cli", milestone="2026-12")
        assert len(issues) == 1
        assert issues[0].number == 180
        assert issues[0].title == "fix(github): add REST API fallback"
        assert issues[0].milestone == "2026-12"
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
            "milestone": "2026-12",
            "labels": ["type/bug"],
        }
    )
    assert issue.milestone == "2026-12"


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
        github_json([_issue(1, "2026-12"), _issue(2, "2027-01"), pull], headers=next_page(second)),
    )
    github_api.route("GET", second, github_json([_issue(3, "2026-12")]))
    issues = _fetch_issues_rest("octo/repo", milestone="2026-12", labels=["type/bug"], limit=None)
    assert ([issue.number for issue in issues], len(github_api.sent)) == ([1, 3], 2)


def test_fetch_issues_rest_stops_reading_at_its_limit(github_api: GitHubApiFake) -> None:
    """Once `limit` issues are read, no further page is requested."""
    second = "/repositories/1/issues?state=open&per_page=100&page=2"
    github_api.route(
        "GET", _REST_ISSUES, github_json([_issue(1, "2026-12")], headers=next_page(second))
    )
    github_api.route("GET", second, github_json([_issue(2, "2026-12")]))
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


_REST_ISSUE = "/repos/octo/repo/issues/9999"


def _full_issue() -> dict[str, Any]:
    """An issue as the REST API sends one, with every field the command prints."""
    return {
        "number": 9999,
        "title": "feat(github): a title that is longer than the fifty characters of a list row",
        "state": "open",
        "url": "https://api.github.com/repos/octo/repo/issues/9999",
        "html_url": "https://github.com/octo/repo/issues/9999",
        "milestone": {"title": "2026-12"},
        "labels": [{"name": "type/feature"}, {"name": "source/agent"}],
        "assignees": [{"login": "octocat"}],
        "created_at": "2026-10-27T10:00:00Z",
        "updated_at": "2026-10-28T11:30:00Z",
        "body": "First line.\n\nSecond line.",
    }


def test_get_repository_issue_reads_one_issue_with_one_request(github_api: GitHubApiFake) -> None:
    """The reader sends one request for the number and returns the whole issue."""
    github_api.route("GET", _REST_ISSUE, github_json(_full_issue()))
    issue = get_repository_issue("octo/repo", 9999)
    assert (issue.number, issue.title, issue.body, issue.labels, len(github_api.sent)) == (
        9999,
        _full_issue()["title"],
        "First line.\n\nSecond line.",
        ["type/feature", "source/agent"],
        1,
    )


def test_a_rest_issue_has_its_web_address_not_its_api_address() -> None:
    """GitHub's REST answer holds the API address in `url` and the web address in `html_url`;
    `gh issue list --json` holds the web address in `url`. The issue gets the web address."""
    rest = _parse_single_issue(_full_issue())
    gh_json = _parse_single_issue({"number": 1, "url": "https://github.com/octo/repo/issues/1"})
    assert (rest.url, gh_json.url) == (
        "https://github.com/octo/repo/issues/9999",
        "https://github.com/octo/repo/issues/1",
    )


def test_get_repository_issue_names_the_repository_and_number_of_a_missing_issue(
    github_api: GitHubApiFake,
) -> None:
    """A 404 raises the not-found error, which names the repository and the number."""
    github_api.route("GET", _REST_ISSUE, github_json({"message": "Not Found"}, status=404))
    with pytest.raises(GitHubNotFoundError) as raised:
        get_repository_issue("octo/repo", 9999)
    message = str(raised.value)
    assert ("octo/repo" in message, "9999" in message) == (True, True)


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(github_json({"message": "Bad Gateway"}, status=502), id="5xx"),
        pytest.param(github_json([_full_issue()]), id="a-list"),
        pytest.param(github_json({"message": "no number"}), id="no-number"),
    ],
)
def test_get_repository_issue_fails_closed(
    github_api: GitHubApiFake, answer: httpx2.Response
) -> None:
    """A failed read, and an answer that is no issue, raise the unread error: they never read as
    an empty issue."""
    github_api.route("GET", _REST_ISSUE, answer)
    with pytest.raises(GitHubUnreadError):
        get_repository_issue("octo/repo", 9999)


def test_get_repository_issue_refuses_a_pull_request(github_api: GitHubApiFake) -> None:
    """The issues endpoint answers for a pull request; the reader names the command that shows
    one."""
    pull = {**_full_issue(), "number": 12, "pull_request": {"url": "https://example.com/pull/12"}}
    github_api.route("GET", "/repos/octo/repo/issues/12", github_json(pull))
    with pytest.raises(GitHubOperationError, match=r"devops pr view 12"):
        get_repository_issue("octo/repo", 12)


def test_render_issue_prints_every_field_and_the_whole_body() -> None:
    """The text holds the full title, each field and the body after an empty line, with a dash
    for each empty field."""
    full = GitHubIssue(
        number=9999,
        title="x" * 80,
        body="First line.\n\nSecond line.",
        state="open",
        milestone="2026-12",
        labels=["type/feature", "source/agent"],
        assignees=["octocat"],
        created_at="2026-10-27T10:00:00Z",
        updated_at="2026-10-28T11:30:00Z",
        url="https://github.com/octo/repo/issues/9999",
    )
    empty = GitHubIssue(number=5, title="Bare")
    text = render_issue(full).splitlines()
    bare = render_issue(empty).splitlines()
    assert (
        text[0],
        "State: open" in text,
        "Milestone: 2026-12" in text,
        "Labels: type/feature, source/agent" in text,
        "Assignees: octocat" in text,
        text[-3:],
        "Milestone: —" in bare,
        "Labels: —" in bare,
        "Assignees: —" in bare,
        bare[-1],
    ) == (
        f"#9999 {'x' * 80}",
        True,
        True,
        True,
        True,
        ["First line.", "", "Second line."],
        True,
        True,
        True,
        "—",
    )
