"""The Status label follows the pull request that delivers an item, and leaves with the close (#2717).

`devops pr create` sets In Progress and `devops pr ready` sets In Review on the issue the pull
request closes. A workflow removes the `status/*` and `owner/*` labels of an issue when it closes. No case runs
`gh` or reaches GitHub: the closing issues come from a fake read and the roadmap is in memory.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.pr import app
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.merge_readiness import ClosingRead
from devops_cli.roadmap.grounding import ClosingIssue
from devops_cli.roadmap.stores.store import GitHubState, ImplementRecordKey, ItemField
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.gh_process import mentions

if TYPE_CHECKING:
    from tests.support.fakes.clock import ClockFake

REPO = "example/roadmap"


TITLE = "fix(cli): set the status of the item"
BODY = (
    "A pull request moves the item it closes forward, so the board shows the work.\n\n"
    "Closes #1\n\nChange: `openspec/changes/archive/2026-11-02-1-set-the-status/`"
)
LABELS = "".join(
    f'- name: "{name}"\n  color: "ededed"\n' for name in ("type/bug", "scope/cli", "type/fix")
)


@pytest.fixture(autouse=True)
def labels_file(roadmap_store: InMemoryRoadmapStore) -> None:
    """The labels file of the repository, which `pr create` reads to check the scope of a title
    (#3198)."""
    roadmap_store.seed_file(".github/labels.yml", LABELS)


def _closing(number: int, *, repo: str = REPO, state: str = "OPEN") -> ClosingIssue:
    return ClosingIssue.model_validate(
        {"number": number, "state": state, "repository": {"nameWithOwner": repo}}
    )


def _status(roadmap_store: InMemoryRoadmapStore, number: int) -> str | None:
    item = roadmap_store.item(number)
    return item.status if item else None


def _closing_reply(read: ClosingRead) -> ProcessAnswer:
    """The answer of `gh api graphql` to the read of the issues a pull request closes."""
    if read.error:
        return ProcessAnswer(returncode=1, stderr=read.error)
    nodes = [
        {
            "number": issue.number,
            "state": issue.state,
            "repository": {"nameWithOwner": issue.repository.name_with_owner},
            "labels": {"nodes": []},
        }
        for issue in read.issues
    ]
    reply = {
        "data": {
            "repository": {
                "pullRequest": {
                    "closingIssuesReferences": {"totalCount": read.total, "nodes": nodes}
                }
            }
        }
    }
    return ProcessAnswer(stdout=json.dumps(reply))


def _set(
    roadmap_store: InMemoryRoadmapStore,
    gh_edge: ProcessFake,
    status: str,
    read: ClosingRead,
    *,
    number: int = 7,
) -> int | None:
    from devops_cli.roadmap import pull_status

    gh_edge.answer(mentions("closingIssuesReferences"), _closing_reply(read))
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
def test_the_status_moves_forward_and_never_leaves_a_blocked_that_a_person_set(
    roadmap_store: InMemoryRoadmapStore,
    gh_edge: ProcessFake,
    before: str | None,
    target: str,
    after: str,
) -> None:
    number = _item(roadmap_store, before)
    _set(roadmap_store, gh_edge, target, ClosingRead((_closing(number),), 1))
    assert _status(roadmap_store, number) == after


def _recorded_blocked(roadmap_store: InMemoryRoadmapStore, *, stopped: bool) -> int:
    """An item that a job set Blocked and recorded, with `implement.stopped` when `stopped`."""
    number = _item(roadmap_store, None)
    item = roadmap_store.item(number)
    assert item is not None
    marks = {ImplementRecordKey.STOPPED: "group 1"} if stopped else {}
    roadmap_store.set_field(item, ItemField.STATUS, "Blocked", marks=marks)
    return number


@pytest.mark.parametrize(
    ("target", "after"), [("In Progress", "In Progress"), ("In Review", "In Review")]
)
def test_a_blocked_item_that_a_stop_recorded_moves_on(
    roadmap_store: InMemoryRoadmapStore, gh_edge: ProcessFake, target: str, after: str
) -> None:
    number = _recorded_blocked(roadmap_store, stopped=True)
    changed = _set(roadmap_store, gh_edge, target, ClosingRead((_closing(number),), 1))
    assert (changed, _status(roadmap_store, number)) == (number, after)


def test_a_blocked_item_with_no_stop_on_record_stays(
    roadmap_store: InMemoryRoadmapStore, gh_edge: ProcessFake
) -> None:
    number = _recorded_blocked(roadmap_store, stopped=False)
    assert _set(roadmap_store, gh_edge, "In Progress", ClosingRead((_closing(number),), 1)) is None
    assert _status(roadmap_store, number) == "Blocked"


def test_a_pull_request_that_closes_no_issue_changes_nothing(
    roadmap_store: InMemoryRoadmapStore,
    gh_edge: ProcessFake,
) -> None:
    number = _item(roadmap_store, "Ready")
    assert (
        _set(roadmap_store, gh_edge, "In Progress", ClosingRead()),
        _status(roadmap_store, number),
    ) == (
        None,
        "Ready",
    )


def test_an_issue_of_another_repository_or_a_closed_issue_changes_nothing(
    roadmap_store: InMemoryRoadmapStore,
    gh_edge: ProcessFake,
) -> None:
    number = _item(roadmap_store, "Ready")
    read = ClosingRead(
        (_closing(number, repo="example/other"), _closing(number, state="CLOSED")), 2
    )
    _set(roadmap_store, gh_edge, "In Progress", read)
    assert _status(roadmap_store, number) == "Ready"


def test_an_issue_that_is_no_item_changes_nothing(
    roadmap_store: InMemoryRoadmapStore, gh_edge: ProcessFake
) -> None:
    number = roadmap_store.seed_issue("A candidate", state=GitHubState.OPEN)
    assert _set(roadmap_store, gh_edge, "In Progress", ClosingRead((_closing(number),), 1)) is None


def test_a_read_that_fails_stops_with_the_reason(
    roadmap_store: InMemoryRoadmapStore, gh_edge: ProcessFake
) -> None:
    with pytest.raises(GitHubOperationError, match="HTTP 502"):
        _set(roadmap_store, gh_edge, "In Progress", ClosingRead(error="HTTP 502"))


# ── The commands ───────────────────────────────────────────────────────────────


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _delivery(roadmap_store: InMemoryRoadmapStore, gh_edge: ProcessFake) -> tuple[int, int]:
    """An item in Ready, and the open pull request that closes it, with gh answering the read of
    the closing issues and the pull request."""
    item = _item(roadmap_store, "Ready")
    pull = roadmap_store.seed_issue("fix(cli): a pull request", pull_request=True)
    closing = ClosingRead((_closing(item),), 1)
    gh_edge.answer(mentions("closingIssuesReferences"), _closing_reply(closing))
    return item, pull


def test_create_sets_the_status_of_the_issue_the_pull_request_closes(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, gh_edge: ProcessFake
) -> None:
    item, pull = _delivery(roadmap_store, gh_edge)
    gh_edge.answer(
        ["gh", "pr", "create"],
        ProcessAnswer(stdout=f"https://example.com/org/repo/pull/{pull}\n"),
    )
    result = runner.invoke(
        app, ["create", "--title", TITLE, "--body", BODY.replace("#1", f"#{item}"), "--repo", REPO]
    )
    assert (result.exit_code, _status(roadmap_store, item)) == (0, "In Progress")


def test_ready_sets_the_status_of_the_issue_the_pull_request_closes(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, gh_edge: ProcessFake
) -> None:
    item, pull = _delivery(roadmap_store, gh_edge)
    reads: list[bool] = []

    def pull_request(call: ProcessCall) -> ProcessAnswer:
        reads.append(True)
        return ProcessAnswer(stdout=json.dumps({"draft": len(reads) == 1}))

    gh_edge.answer(["gh", "api", f"repos/{REPO}/pulls/{pull}"], pull_request)
    result = runner.invoke(app, ["ready", str(pull), "--repo", REPO, "--force"])
    assert (result.exit_code, _status(roadmap_store, item)) == (0, "In Review")


def test_a_status_write_that_fails_exits_1_after_the_pull_request_opened(
    runner: CliRunner, roadmap_store: InMemoryRoadmapStore, gh_edge: ProcessFake, clock: ClockFake
) -> None:
    gh_edge.answer(
        mentions("closingIssuesReferences"), _closing_reply(ClosingRead(error="HTTP 502"))
    )
    gh_edge.answer(
        ["gh", "pr", "create"], ProcessAnswer(stdout="https://example.com/org/repo/pull/14\n")
    )
    result = runner.invoke(app, ["create", "--title", TITLE, "--body", BODY, "--repo", REPO])
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


def test_the_workflow_removes_only_the_status_and_owner_labels() -> None:
    """The filter of the workflow picks the `status/*` and `owner/*` labels of the closed issue
    (#2910), and no other label (a test cannot start jq: the process edge is closed)."""
    script = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["clear-status"]["steps"][
        0
    ]["run"]
    filter_ = re.search(r"--jq '([^']*)'", script)
    assert filter_ is not None
    assert re.findall(r'startswith\("([^"]*)"\)', filter_.group(1)) == ["status/", "owner/"]
    assert " or " in filter_.group(1)
