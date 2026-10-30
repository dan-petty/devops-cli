"""The Status label follows the pull request that delivers an item, and leaves with the close (#2717).

`devops pr create` sets In Progress and `devops pr ready` sets In Review on the issue the pull
request closes. A workflow removes the `status/*` labels of an issue when it closes. No case runs
`gh` or reaches GitHub: the closing issues come from a fake read and the roadmap is in memory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.pr import app
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.merge_readiness import ClosingRead
from devops_cli.roadmap.grounding import ClosingIssue
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import GitHubState, ItemField

REPO = "example/roadmap"


def _closing(number: int, *, repo: str = REPO, state: str = "OPEN") -> ClosingIssue:
    return ClosingIssue.model_validate(
        {"number": number, "state": state, "repository": {"nameWithOwner": repo}}
    )


def _status(roadmap_store: InMemoryRoadmapStore, number: int) -> str | None:
    item = roadmap_store.item(number)
    return item.status if item else None


def _set(
    roadmap_store: InMemoryRoadmapStore, status: str, read: ClosingRead, *, number: int = 7
) -> int | None:
    from devops_cli.roadmap import pull_status

    with patch.object(pull_status, "read_closing_issues", return_value=read):
        return pull_status.set_delivered_status(REPO, number, status)


def _item(roadmap_store: InMemoryRoadmapStore, status: str | None) -> int:
    fields = {ItemField.PRIORITY: "P2-Medium"}
    if status:
        fields[ItemField.STATUS] = status
    return roadmap_store.seed_issue("fix(cli): one", fields=fields)


@pytest.mark.parametrize(
    ("before", "target", "after"),
    [
        ("New", "In Progress", "In Progress"),
        ("Ready", "In Progress", "In Progress"),
        (None, "In Progress", "In Progress"),
        ("In Progress", "In Review", "In Review"),
        ("Ready", "In Review", "In Review"),
        ("In Review", "In Progress", "In Review"),
        ("Blocked", "In Progress", "Blocked"),
        ("Blocked", "In Review", "Blocked"),
    ],
)
def test_the_status_moves_forward_and_never_leaves_blocked(
    roadmap_store: InMemoryRoadmapStore, before: str | None, target: str, after: str
) -> None:
    number = _item(roadmap_store, before)
    _set(roadmap_store, target, ClosingRead((_closing(number),), 1))
    assert _status(roadmap_store, number) == after


def test_a_pull_request_that_closes_no_issue_changes_nothing(
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    number = _item(roadmap_store, "Ready")
    assert (_set(roadmap_store, "In Progress", ClosingRead()), _status(roadmap_store, number)) == (
        None,
        "Ready",
    )


def test_an_issue_of_another_repository_or_a_closed_issue_changes_nothing(
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    number = _item(roadmap_store, "Ready")
    read = ClosingRead(
        (_closing(number, repo="example/other"), _closing(number, state="CLOSED")), 2
    )
    _set(roadmap_store, "In Progress", read)
    assert _status(roadmap_store, number) == "Ready"


def test_an_issue_that_is_no_item_changes_nothing(roadmap_store: InMemoryRoadmapStore) -> None:
    number = roadmap_store.seed_issue("A candidate", state=GitHubState.OPEN)
    assert _set(roadmap_store, "In Progress", ClosingRead((_closing(number),), 1)) is None


def test_a_read_that_fails_stops_with_the_reason(roadmap_store: InMemoryRoadmapStore) -> None:
    with pytest.raises(GitHubOperationError, match="HTTP 502"):
        _set(roadmap_store, "In Progress", ClosingRead(error="HTTP 502"))


# ── The commands ───────────────────────────────────────────────────────────────


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _gh(**_: Any) -> MagicMock:
    return MagicMock(returncode=0, stdout="https://example.com/org/repo/pull/14\n", stderr="")


def test_create_sets_the_status_of_the_issue_the_pull_request_closes(runner: CliRunner) -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.commands.pr.run_gh", return_value=_gh()),
        patch("devops_cli.commands.pr.set_delivered_status") as record,
    ):
        result = runner.invoke(app, ["create", "--title", "fix: a", "--body", "Closes #7"])
    assert (result.exit_code, record.call_args.args[1:]) == (0, (14, "In Progress"))


def test_ready_sets_the_status_of_the_issue_the_pull_request_closes(runner: CliRunner) -> None:
    drafts = [{"draft": True}, {"draft": False}]
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.commands.pr.run_gh", return_value=_gh()),
        patch("devops_cli.commands.pr.fetch_pr_details", side_effect=drafts),
        patch("devops_cli.commands.pr.set_delivered_status") as record,
    ):
        result = runner.invoke(app, ["ready", "14", "--repo", REPO, "--force"])
    assert (result.exit_code, record.call_args.args) == (0, (REPO, 14, "In Review"))


def test_a_status_write_that_fails_exits_1_after_the_pull_request_opened(
    runner: CliRunner,
) -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.commands.pr.run_gh", return_value=_gh()),
        patch(
            "devops_cli.commands.pr.set_delivered_status",
            side_effect=GitHubOperationError("HTTP 502"),
        ),
    ):
        result = runner.invoke(app, ["create", "--title", "fix: a", "--body", "Closes #7"])
    assert (result.exit_code, "pull/14" in result.output, "HTTP 502" in result.output) == (
        1,
        True,
        True,
    )


# ── The close ──────────────────────────────────────────────────────────────────

WORKFLOW = Path(".github/workflows/clear-status.yml")


def test_a_workflow_removes_the_status_labels_when_an_issue_closes() -> None:
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = document.get("on", document.get(True))
    job = next(iter(document["jobs"].values()))
    assert (triggers, job["permissions"], "status/" in WORKFLOW.read_text(encoding="utf-8")) == (
        {"issues": {"types": ["closed"]}},
        {"issues": "write"},
        True,
    )
