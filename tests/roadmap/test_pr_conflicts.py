"""The row `pr_conflicts` of the Service's status lane: a ready delivery pull request that GitHub
reports with merge conflicts gets one comment, and a clean pull request that is behind the default
branch gets no action (#4027).

GitHub's REST API is faked at the session, and the store is the in-memory store. The row reads
the open pull requests from the store, and reads and comments on each one that is not a draft
through the session.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import CONST_ROADMAP_PR_CONFLICTS_LEDGER_FILENAME
from devops_cli.exceptions import RoadmapRunError
from devops_cli.exceptions.git import GitHubNotFoundError
from devops_cli.github.merge_readiness import merge_conflict
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.run import STATUS_LANE_ROWS, JobOutcome, JobRow
from devops_cli.roadmap.stores.store import GitHubState, ItemField
from devops_cli.telemetry.instruments import ROADMAP_CONFLICTED_PULLS
from tests.support.fakes.github import API, GitHubApiFake, github_json
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_run import NOW, REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

HEAD = "a" * 40
OTHER_HEAD = "b" * 40
DIRTY: dict[str, Any] = {"mergeable": False, "mergeable_state": "dirty"}
CLEAN: dict[str, Any] = {"mergeable": True, "mergeable_state": "clean"}
BEHIND: dict[str, Any] = {"mergeable": True, "mergeable_state": "behind"}
UNKNOWN: dict[str, Any] = {"mergeable": None, "mergeable_state": "unknown"}


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=REPO)


def _row() -> JobRow:
    """The row `pr_conflicts` of the status lane, or a failed assertion."""
    for row in STATUS_LANE_ROWS:
        if row.name == "pr_conflicts":
            return row
    raise AssertionError("The status lane has no row pr_conflicts.")


def _round(store: InMemoryRoadmapStore, repo_dir: Path) -> JobOutcome:
    """One round of the row, as the status lane runs it."""
    return _row().runner(
        store=store,
        clone_path=None,
        changes=[],
        batch={},
        repo=REPO,
        repo_dir=repo_dir,
        now=NOW,
    )


def _item(store: InMemoryRoadmapStore, *, priority: str | None = "P2-Medium") -> int:
    """An open issue, an Item when it holds a Priority."""
    fields = {ItemField.PRIORITY: priority} if priority else {}
    return store.seed_issue("Detect the conflicts", fields=fields)


def _pull(
    store: InMemoryRoadmapStore,
    api: GitHubApiFake,
    *states: dict[str, Any],
    body: str,
    draft: bool = False,
    head: str = HEAD,
    base: str = "main",
) -> int:
    """An open pull request in the store, and GitHub's answers, in turn, to its reads."""
    number = store.seed_pull("feat(roadmap): detect", head_ref="feat/1-detect", draft=draft)
    answers = [
        github_json(
            {
                "state": "open",
                "draft": draft,
                "body": body,
                "head": {"sha": head, "ref": "feat/1-detect"},
                "base": {"ref": base, "repo": {"default_branch": "main"}},
                **state,
            }
        )
        for state in states
    ]
    api.route("GET", f"/repos/{REPO}/pulls/{number}", *answers)
    _commentable(api, number)
    return number


def _commentable(api: GitHubApiFake, number: int) -> None:
    """GitHub's answer to a comment on pull request `number`."""
    api.route("POST", f"/repos/{REPO}/issues/{number}/comments", github_json({"id": 1}, status=201))


def _comments(api: GitHubApiFake, number: int) -> list[str]:
    """The bodies of the comments that the row posted on pull request `number`, in turn."""
    path = f"/repos/{REPO}/issues/{number}/comments"
    return [
        json.loads(sent.content)["body"]
        for sent in api.sent
        if sent.method == "POST" and sent.url.path == path
    ]


def _note(number: int, head: str = HEAD) -> str:
    return MESSAGES.roadmap.pr_conflicts_comment.format(number=number, base="main", head=head[:12])


def test_pr_conflicts_runs_last_in_the_status_lane_with_no_clone() -> None:
    """The row follows `cloudflare_status`, needs no clone and is due on a first run."""
    assert (
        [row.name for row in STATUS_LANE_ROWS][-2:],
        _row().needs_clone,
        _row().first_run_due,
    ) == (["cloudflare_status", "pr_conflicts"], False, True)


def test_a_conflicted_delivery_pull_request_gets_one_comment_that_names_the_default_branch(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    issue = _item(store)
    pull = _pull(store, github_api, DIRTY, body=f"Detect the conflicts.\n\nCloses #{issue}")

    _round(store, tmp_path)

    assert (_comments(github_api, pull), _comments(github_api, issue)) == ([_note(pull)], [])


def test_a_conflict_that_persists_at_the_same_head_gets_no_second_comment(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    issue = _item(store)
    pull = _pull(store, github_api, DIRTY, DIRTY, body=f"Closes #{issue}")

    _round(store, tmp_path)
    _round(store, tmp_path)

    assert _comments(github_api, pull) == [_note(pull)]


def test_a_conflict_at_a_new_head_gets_a_comment_for_that_head(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    issue = _item(store)
    pull = store.seed_pull("feat(roadmap): detect", head_ref="feat/1-detect")
    reads = [
        github_json(
            {
                "state": "open",
                "draft": False,
                "body": f"Closes #{issue}",
                "head": {"sha": head},
                "base": {"ref": "main", "repo": {"default_branch": "main"}},
                **DIRTY,
            }
        )
        for head in (HEAD, OTHER_HEAD)
    ]
    github_api.route("GET", f"/repos/{REPO}/pulls/{pull}", *reads)
    _commentable(github_api, pull)

    _round(store, tmp_path)
    _round(store, tmp_path)

    assert _comments(github_api, pull) == [_note(pull), _note(pull, OTHER_HEAD)]


def test_a_conflict_that_returns_after_a_clean_round_gets_the_comment_again(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    issue = _item(store)
    pull = _pull(store, github_api, DIRTY, CLEAN, DIRTY, body=f"Closes #{issue}")

    for _ in range(3):
        _round(store, tmp_path)

    assert _comments(github_api, pull) == [_note(pull), _note(pull)]


def test_an_unknown_mergeable_state_leaves_the_pull_request_and_the_ledger_unchanged(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """An unknown state posts nothing, and the record of the conflict stays, so the conflict that
    GitHub reports again at the same head gets no second comment."""
    issue = _item(store)
    pull = _pull(store, github_api, UNKNOWN, DIRTY, UNKNOWN, DIRTY, body=f"Closes #{issue}")

    _round(store, tmp_path)
    after_unknown = _comments(github_api, pull)
    for _ in range(3):
        _round(store, tmp_path)

    assert (after_unknown, _comments(github_api, pull)) == ([], [_note(pull)])


def test_a_clean_pull_request_behind_the_default_branch_gets_no_action(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """The row sends no update-branch request and posts no comment: an open pull request gets
    no catch-up update (docs/SDLC.md, Phase 1)."""
    issue = _item(store)
    pull = _pull(store, github_api, BEHIND, body=f"Closes #{issue}")

    _round(store, tmp_path)

    assert (github_api.requested, _comments(github_api, pull)) == (
        [f"GET {API}/repos/{REPO}/pulls/{pull}"],
        [],
    )


@pytest.mark.parametrize(
    ("body", "draft", "base", "priority", "reads"),
    [
        pytest.param("Plans #{issue}", False, "main", "P2-Medium", 1, id="plan"),
        pytest.param("Closes #{issue}", True, "main", "P2-Medium", 0, id="draft"),
        pytest.param("Closes #{issue}", False, "release", "P2-Medium", 1, id="other-base"),
        pytest.param("Closes #{issue}", False, "main", None, 1, id="no-item"),
        pytest.param("Closes #{issue}\nCloses #99", False, "main", "P2-Medium", 1, id="two"),
    ],
)
def test_a_pull_request_that_delivers_no_one_open_item_into_the_default_branch_is_skipped(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    tmp_path: Path,
    body: str,
    draft: bool,
    base: str,
    priority: str | None,
    reads: int,
) -> None:
    """A plan, a draft, a pull request into another branch, one that closes an issue with no
    Priority and one that closes two issues get no comment. A draft is not read at all."""
    issue = _item(store, priority=priority)
    pull = _pull(store, github_api, DIRTY, body=body.format(issue=issue), draft=draft, base=base)

    _round(store, tmp_path)

    assert (len(github_api.requested), _comments(github_api, pull)) == (reads, [])


def test_a_pull_request_that_closes_a_closed_item_is_skipped(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    issue = store.seed_issue(
        "Done", state=GitHubState.CLOSED, fields={ItemField.PRIORITY: "P2-Medium"}
    )
    pull = _pull(store, github_api, DIRTY, body=f"Closes #{issue}")

    _round(store, tmp_path)

    assert _comments(github_api, pull) == []


def test_the_gauge_counts_the_conflicted_delivery_pull_requests_by_repo(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path, otlp: FakeCollector
) -> None:
    for state in (DIRTY, DIRTY, CLEAN, UNKNOWN):
        _pull(store, github_api, state, body=f"Closes #{_item(store)}")

    _round(store, tmp_path)

    assert otlp.points(ROADMAP_CONFLICTED_PULLS.name) == [({"repo": REPO}, 2.0)]


def test_a_failed_read_fails_the_row(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """GitHub answers 404 for the read of the pull request: the row raises."""
    store.seed_pull("feat(roadmap): detect", head_ref="feat/1-detect")

    with pytest.raises(GitHubNotFoundError) as raised:
        _round(store, tmp_path)

    assert (raised.value.exit_code, raised.value.error_code) == (
        GitHubNotFoundError.exit_code,
        GitHubNotFoundError.error_code,
    )


def test_an_unreadable_ledger_fails_the_row_and_names_the_file(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    ledger = tmp_path / CONST_ROADMAP_PR_CONFLICTS_LEDGER_FILENAME
    ledger.write_text("{not json", encoding="utf-8")

    store.seed_pull("feat(roadmap): detect", head_ref="feat/1-detect")

    with pytest.raises(RoadmapRunError) as raised:
        _round(store, tmp_path)

    assert (
        raised.value.exit_code,
        raised.value.error_code,
        raised.value.details["path"],
        github_api.requested,
    ) == (RoadmapRunError.exit_code, RoadmapRunError.error_code, str(ledger), [])


@pytest.mark.parametrize(
    ("state", "conflict"),
    [
        pytest.param(DIRTY, True, id="dirty"),
        pytest.param(
            {"mergeable": False, "mergeable_state": "conflicting"}, True, id="conflicting"
        ),
        pytest.param(CLEAN, False, id="clean"),
        pytest.param(BEHIND, False, id="behind"),
        pytest.param({"mergeable": True, "mergeable_state": "blocked"}, False, id="blocked"),
        pytest.param(UNKNOWN, None, id="unknown"),
        pytest.param({"mergeable": None, "mergeable_state": ""}, None, id="empty"),
    ],
)
def test_the_row_and_check_readiness_judge_one_conflict(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    tmp_path: Path,
    state: dict[str, Any],
    conflict: bool | None,
) -> None:
    """The row comments exactly when the judgment of `devops pr check-readiness` reports a
    conflict."""
    issue = _item(store)
    pull = _pull(store, github_api, state, body=f"Closes #{issue}")

    _round(store, tmp_path)

    assert (
        merge_conflict(state["mergeable"], state["mergeable_state"]),
        _comments(github_api, pull),
    ) == (
        conflict,
        [_note(pull)] if conflict else [],
    )
