"""Tests of the findings that an open issue of the repository already names (#2346).

A recurring problem that a person filed an issue for is no new finding: the audit marks it as
tracked, and the report renders it apart from the problems that no issue holds yet.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devops_cli.ai.agent_audit.finding import Finding
    from devops_cli.roadmap.stores.store import IssueRecord
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

REPO = "example/project"
# The warning that every `uv run` of a worktree prints, as a signature reduces it: the paths of the
# line become placeholders, and the words around them are what an issue names.
_WARNING_SIGNATURE = (
    "warning: virtual_env <path> does not match the project environment path <path>"
)
# The line as a person pastes it into an issue: the paths are the real ones of the host.
_WARNING_LINE = (
    "uv run: warning: VIRTUAL_ENV=/home/me/.venv does not match the project environment path "
    "/repo/.venv"
)
# A failure that no issue names.
_FAILURE_SIGNATURE = "uv run devops ci test <path> | exit 1: failed <path>"


def _warning_finding() -> Finding:
    """The finding of the warning that every `uv run` of a worktree prints."""
    from devops_cli.ai.agent_audit.finding import Finding

    return Finding(
        signature=_WARNING_SIGNATURE,
        sessions=3,
        recurrences=5,
        elapsed_seconds=0.0,
        pointers=(),
    )


def _failure_finding() -> Finding:
    """The finding of a failed test run that no issue names yet."""
    from devops_cli.ai.agent_audit.finding import Finding

    return Finding(
        signature=_FAILURE_SIGNATURE,
        sessions=1,
        recurrences=1,
        elapsed_seconds=0.0,
        pointers=(),
    )


def _issue(title: str, *, body: str = "") -> IssueRecord:
    """An open issue of the repository, as the roadmap store reads it."""
    from devops_cli.roadmap.stores.store import IssueRecord

    return IssueRecord(number=1, title=title, url=f"https://github.com/{REPO}/issues/1", body=body)


def test_warning_named_by_an_open_issue_is_tracked(
    roadmap_store: InMemoryRoadmapStore, roadmap_store_repos: list[str]
) -> None:
    """A warning that the title of an open issue names is no new finding, and the report marks it
    as tracked (#2346)."""
    from devops_cli.ai.agent_audit.report import render_report
    from devops_cli.ai.agent_audit.tracked import GitHubTrackedIssues, mark_tracked

    roadmap_store.seed_issue(_WARNING_LINE)
    warning, failure = _warning_finding(), _failure_finding()

    marked = mark_tracked([warning, failure], GitHubTrackedIssues(REPO).open_issues())
    payload = json.loads(render_report(marked, "json"))

    assert roadmap_store_repos == [REPO]
    assert [each.signature for each in marked if each.tracked] == [warning.signature]
    assert [each["signature"] for each in payload["findings"]] == [failure.signature]
    assert [each["signature"] for each in payload["tracked"]] == [warning.signature]


def test_the_body_of_an_open_issue_names_a_warning(
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    """A warning that the body of an open issue quotes, under another title, is tracked (#2346)."""
    from devops_cli.ai.agent_audit.tracked import GitHubTrackedIssues, mark_tracked

    roadmap_store.seed_issue(
        "chore(dev): stop the virtual environment warning",
        body=f"The warning of every worktree run is:\n\n```\n{_WARNING_LINE}\n```\n",
    )

    marked = mark_tracked([_warning_finding()], GitHubTrackedIssues(REPO).open_issues())

    assert [each.tracked for each in marked] == [True]


def test_a_closed_issue_names_no_finding(roadmap_store: InMemoryRoadmapStore) -> None:
    """An issue that is closed no longer tracks its warning, so the audit reports it as new
    (#2346)."""
    from devops_cli.ai.agent_audit.tracked import GitHubTrackedIssues, mark_tracked
    from devops_cli.roadmap.stores.store import GitHubState

    roadmap_store.seed_issue(_WARNING_LINE, state=GitHubState.CLOSED)

    marked = mark_tracked([_warning_finding()], GitHubTrackedIssues(REPO).open_issues())

    assert [each.tracked for each in marked] == [False]


def test_a_finding_that_no_issue_names_stays_new(
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    """The audit reports a finding as new when no open issue names it (#2346)."""
    from devops_cli.ai.agent_audit.tracked import GitHubTrackedIssues, mark_tracked

    roadmap_store.seed_issue("feat(ai): add a command that audits the agent sessions")

    marked = mark_tracked(
        [_warning_finding(), _failure_finding()], GitHubTrackedIssues(REPO).open_issues()
    )

    assert [each.tracked for each in marked] == [False, False]


def test_the_masked_host_of_a_signature_matches_the_host_of_an_issue(
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    """A signature names a private host masked, and the issue names it as it is: both read as the
    same words, so the warning is tracked with no host in the signature (#2346)."""
    from devops_cli.ai.agent_audit.finding import Finding
    from devops_cli.ai.agent_audit.tracked import GitHubTrackedIssues, mark_tracked

    roadmap_store.seed_issue("error: cannot reach build-box.internal: connect: connection refused")
    finding = Finding(
        signature="error: cannot reach <masked-host>: connect: connection refused",
        sessions=2,
        recurrences=2,
        elapsed_seconds=0.0,
        pointers=(),
    )

    marked = mark_tracked([finding], GitHubTrackedIssues(REPO).open_issues())

    assert [each.tracked for each in marked] == [True]


def test_marking_a_finding_keeps_its_counts() -> None:
    """Marking a finding tracked changes its `tracked` flag and nothing else (#2346)."""
    from devops_cli.ai.agent_audit.finding import Finding
    from devops_cli.ai.agent_audit.tracked import mark_tracked

    warning = _warning_finding()

    marked = mark_tracked([warning], [_issue(_WARNING_LINE)])

    assert marked[0] == Finding(
        signature=warning.signature,
        sessions=warning.sessions,
        recurrences=warning.recurrences,
        elapsed_seconds=warning.elapsed_seconds,
        pointers=warning.pointers,
        tracked=True,
    )
