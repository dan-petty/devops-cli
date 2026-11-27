"""The `watch` row takes a pull request as the plan of an item only when its head branch is the
branch that the record of the item holds (#7347).

The record of an item names its plan pull request by number (`stage.pr`) and by branch
(`stage.branch`). A number alone names no pull request of the item: the row compares the head
branch of the pull request with the recorded branch before it writes for the item. The cases run
the reconciling round over GraphQL, the REST fallback, the scoped round and the read of the plans
that are no more open.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import CONST_ROADMAP_WATCH_LEDGER_FILENAME
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap.stores.store import ItemField, StageRecordKey
from devops_cli.roadmap.watch_row import watch_round
from tests.support.fakes.github import (
    API,
    GitHubApiFake,
    github_json,
    route_compare_files,
)
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.gh_process import gh_argv
from tests.support.roadmap_run import NOW, REPO

pytestmark = pytest.mark.usefixtures("keyring_store", "cluster")

HEAD = "3" * 40
OTHER_BRANCH = "feat/4107-add-the-rows"
"""The head branch of a pull request that is not the plan of the item."""


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=REPO)


@pytest.fixture
def process(github_api_and_gh: tuple[GitHubApiFake, ProcessFake]) -> ProcessFake:
    _, fake = github_api_and_gh
    fake.answer("gh pr ready", ProcessAnswer(stdout="", returncode=0))
    return fake


@pytest.fixture
def github_api(github_api_and_gh: tuple[GitHubApiFake, ProcessFake]) -> GitHubApiFake:
    api, _ = github_api_and_gh
    return api


@contextmanager
def graphql_on_hold() -> Iterator[None]:
    """The GraphQL quota is below its floor, so a round in the block reads over REST."""
    limiter = get_github_rate_limiter()
    limiter.update_quota("graphql", remaining=0, limit=5000, reset_epoch=time.time() + 600.0)
    try:
        yield
    finally:
        limiter.update_quota("graphql", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0)


def _staged(store: InMemoryRoadmapStore, *, head_ref: str | None = None) -> tuple[int, int, str]:
    """An open item whose record names a plan pull request and its branch, the pull request, and
    the recorded branch. The pull request has the head branch `head_ref`, the recorded branch by
    default."""
    issue = store.seed_issue("Plan the rows", fields={ItemField.PRIORITY: "P2-Medium"})
    branch = f"feat/{issue}-plan-the-rows"
    pull = store.seed_pull("docs(spec): plan the rows", head_ref=head_ref or branch, draft=True)
    item = store.item(issue)
    assert item is not None
    store.set_marks(item, {StageRecordKey.PR: str(pull), StageRecordKey.BRANCH: branch})
    return issue, pull, branch


def _node(pull: int, head_ref: str) -> dict[str, Any]:
    """The GraphQL node of the green draft `pull` of the bot on the branch `head_ref`."""
    check = {"__typename": "CheckRun", "name": "Tests", "status": "COMPLETED"}
    rollup = {"state": "SUCCESS", "contexts": {"nodes": [check | {"conclusion": "SUCCESS"}]}}
    return {
        "number": pull,
        "title": "docs(spec): plan the rows",
        "body": "The plan of the item.",
        "isDraft": True,
        "labels": {"nodes": []},
        "mergeable": "MERGEABLE",
        "headRefOid": HEAD,
        "headRefName": head_ref,
        "baseRefName": "main",
        "author": {"login": "devops-cli-service[bot]"},
        "commits": {"nodes": [{"commit": {"oid": HEAD, "statusCheckRollup": rollup}}]},
    }


def _route_graphql(api: GitHubApiFake, *nodes: dict[str, Any]) -> None:
    pulls = {"nodes": list(nodes), "pageInfo": {"hasNextPage": False, "endCursor": None}}
    api.route("POST", "/graphql", github_json({"data": {"repository": {"pullRequests": pulls}}}))


def _route_pull(
    api: GitHubApiFake, pull: int, head_ref: str, *, state: str = "open", merged: bool = False
) -> None:
    """Answer the REST reads of pull request `pull` on the branch `head_ref`: a green draft while
    it is open."""
    api.route(
        "GET",
        f"/repos/{REPO}/pulls/{pull}",
        github_json(
            {
                "number": pull,
                "state": state,
                "merged": merged,
                "draft": state == "open",
                "title": "docs(spec): plan the rows",
                "body": "The plan of the item.",
                "head": {"sha": HEAD, "ref": head_ref},
                "base": {"ref": "main", "repo": {"default_branch": "main"}},
            }
        ),
    )
    api.route(
        "GET",
        f"/repos/{REPO}/commits/{HEAD}/check-runs?per_page=100",
        github_json(
            {"check_runs": [{"name": "Tests", "status": "completed", "conclusion": "success"}]}
        ),
    )
    changed = {"filename": "openspec/changes/1-plan-the-rows/proposal.md", "status": "added"}
    route_compare_files(api, REPO, "main", HEAD, changed, merge_base="c" * 40)


def _writes(api: GitHubApiFake, process: ProcessFake, store: InMemoryRoadmapStore) -> Any:
    """Each write of a round: the requests that are no read, the `gh` commands that are no read
    of the API, and the writes of the store."""
    sent = [line for line in api.requested if not line.startswith(("GET ", f"POST {API}/graphql"))]
    commands = [argv for argv in gh_argv(process) if argv[:2] != ["gh", "api"]]
    return sent, commands, store.job_writes()


def _ledger(tmp_path: Path) -> Path:
    return tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME


def test_a_draft_on_the_recorded_branch_is_the_plan_of_the_item_and_is_marked_ready(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, process: ProcessFake, tmp_path: Path
) -> None:
    issue, pull, branch = _staged(store)
    _route_graphql(github_api, _node(pull, branch))
    _route_pull(github_api, pull, branch)

    result = watch_round(store, repo=REPO, ledger_path=_ledger(tmp_path), now=NOW)

    item = store.item(issue)
    assert item is not None
    assert (result.marked_ready, item.job_record.get(StageRecordKey.READY)) == ((pull,), str(pull))


def test_a_draft_whose_head_branch_is_not_the_recorded_branch_is_not_the_plan_of_the_item(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, process: ProcessFake, tmp_path: Path
) -> None:
    """The record holds the number of a pull request whose head branch is not the recorded one.
    The row does not watch that pull request for the item, and the round sends no write."""
    issue, pull, _ = _staged(store, head_ref=OTHER_BRANCH)
    before = len(store.job_writes())
    _route_graphql(github_api, _node(pull, OTHER_BRANCH))
    _route_pull(github_api, pull, OTHER_BRANCH)

    result = watch_round(store, repo=REPO, ledger_path=_ledger(tmp_path), now=NOW)

    sent, commands, writes = _writes(github_api, process, store)
    item = store.item(issue)
    assert item is not None
    assert (result.watched, result.marked_ready) == (0, ())
    assert (sent, commands, writes[before:]) == ([], [], [])
    assert item.job_record.get(StageRecordKey.READY) is None


def test_of_two_items_that_record_one_number_only_the_item_of_the_head_branch_gets_the_plan(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, process: ProcessFake, tmp_path: Path
) -> None:
    """The first item records the number of the plan of the second item."""
    first = store.seed_issue("Another item", fields={ItemField.PRIORITY: "P2-Medium"})
    issue, pull, branch = _staged(store)
    held = store.item(first)
    assert held is not None
    store.set_marks(
        held,
        {StageRecordKey.PR: str(pull), StageRecordKey.BRANCH: f"feat/{first}-another-item"},
    )
    _route_graphql(github_api, _node(pull, branch))
    _route_pull(github_api, pull, branch)

    watch_round(store, repo=REPO, ledger_path=_ledger(tmp_path), now=NOW)

    records = [store.item(number) for number in (first, issue)]
    assert [item and item.job_record.get(StageRecordKey.READY) for item in records] == [
        None,
        str(pull),
    ]


def test_the_rest_round_takes_no_draft_on_another_branch_as_the_plan_of_the_item(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, process: ProcessFake, tmp_path: Path
) -> None:
    _, pull, _ = _staged(store, head_ref=OTHER_BRANCH)
    before = len(store.job_writes())
    _route_pull(github_api, pull, OTHER_BRANCH)

    with graphql_on_hold():
        result = watch_round(store, repo=REPO, ledger_path=_ledger(tmp_path), now=NOW)

    sent, commands, writes = _writes(github_api, process, store)
    assert (result.watched, result.marked_ready) == (0, ())
    assert (sent, commands, writes[before:]) == ([], [], [])


def test_the_rest_round_marks_the_draft_on_the_recorded_branch_ready(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, process: ProcessFake, tmp_path: Path
) -> None:
    _, pull, branch = _staged(store)
    _route_pull(github_api, pull, branch)

    with graphql_on_hold():
        result = watch_round(store, repo=REPO, ledger_path=_ledger(tmp_path), now=NOW)

    assert result.marked_ready == (pull,)


@pytest.mark.parametrize("scoped", [False, True], ids=["poll", "scoped"])
def test_a_merged_pull_request_on_another_branch_is_not_the_merged_plan_of_the_item(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    process: ProcessFake,
    tmp_path: Path,
    scoped: bool,
) -> None:
    """The recorded number names a merged pull request of another branch: the round sends no
    write for the item."""
    _, pull, _ = _staged(store, head_ref=OTHER_BRANCH)
    before = len(store.job_writes())
    _route_graphql(github_api)
    _route_pull(github_api, pull, OTHER_BRANCH, state="closed", merged=True)

    watch_round(
        store,
        repo=REPO,
        ledger_path=_ledger(tmp_path),
        now=NOW,
        pull_numbers=(pull,) if scoped else (),
    )

    sent, commands, writes = _writes(github_api, process, store)
    assert (sent, commands, writes[before:]) == ([], [], [])


def test_a_merged_pull_request_on_the_recorded_branch_settles_the_plan(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, process: ProcessFake, tmp_path: Path
) -> None:
    issue, pull, branch = _staged(store)
    _route_graphql(github_api)
    _route_pull(github_api, pull, branch, state="closed", merged=True)

    watch_round(store, repo=REPO, ledger_path=_ledger(tmp_path), now=NOW)

    item = store.item(issue)
    assert item is not None
    assert item.job_record.get(StageRecordKey.READY) == str(pull)
