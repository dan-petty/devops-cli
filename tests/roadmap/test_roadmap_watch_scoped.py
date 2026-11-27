"""The scoped round of the `watch` row: a pull request, review or check suite delivery reads only
the pull requests that it names, and a number that neither the store nor the ledger holds sends
no request (#4413).

Verifies:
1. A scoped round reads the delivered pull request and no other.
2. A scoped round for an unknown pull request sends no request.
3. A round with no numbers reads the open pull requests with one GraphQL query.
4. A scoped round reads a pull request that only the ledger holds.
5. A scoped round settles a delivered plan pull request that closed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import CONST_ROADMAP_WATCH_LEDGER_FILENAME
from devops_cli.roadmap.stores.store import ItemField, StageRecordKey
from devops_cli.roadmap.watch_row import (
    WatchLedger,
    WatchLedgerEntry,
    WatchRoundResult,
    watch_round,
)
from tests.support.fakes.github import API, GitHubApiFake, github_json
from tests.support.fakes.process import ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_run import NOW, REPO

pytestmark = pytest.mark.usefixtures("keyring_store", "cluster")

HEAD = "4" * 40
INFRA_CHECK = "Semantic PR title"


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=REPO)


@pytest.fixture
def github_api(github_api_and_gh: tuple[GitHubApiFake, ProcessFake]) -> GitHubApiFake:
    api, _process = github_api_and_gh
    return api


def _plan_branch(pull: int) -> str:
    """The branch of the plan draft `pull`. The tests stage the draft 42 for issue #1 and the
    draft 43 for issue #2, and the branch of a plan names its issue."""
    return f"feat/{pull - 41}-plan"


def _staged_draft(store: InMemoryRoadmapStore, pull: int) -> int:
    """An open Item of `store` whose record names the staged draft `pull`."""
    issue = store.seed_issue(f"Plan {pull}", fields={ItemField.PRIORITY: "P1-High"})
    item = store.item(issue)
    assert item is not None
    store.set_marks(item, {StageRecordKey.PR: str(pull), StageRecordKey.BRANCH: _plan_branch(pull)})
    return issue


def _route_open_draft(api: GitHubApiFake, pull: int) -> None:
    """Answer the reads of the open plan draft `pull` whose `ci_infra` check fails, so that the
    row reads it and takes no repair unit and no ready path."""
    api.route(
        "GET",
        f"/repos/{REPO}/pulls/{pull}",
        github_json(
            {
                "number": pull,
                "state": "open",
                "merged": False,
                "draft": True,
                "body": f"The plan of pull {pull}.",
                "head": {"sha": HEAD, "ref": _plan_branch(pull)},
                "base": {"ref": "main", "repo": {"default_branch": "main"}},
            }
        ),
    )
    api.route(
        "GET",
        f"/repos/{REPO}/commits/{HEAD}/check-runs",
        github_json(
            {"check_runs": [{"name": INFRA_CHECK, "status": "completed", "conclusion": "failure"}]}
        ),
    )


def _route_closed_plan(api: GitHubApiFake, pull: int) -> None:
    """Answer the read of the plan pull request `pull`, closed and merged."""
    api.route(
        "GET",
        f"/repos/{REPO}/pulls/{pull}",
        github_json(
            {
                "number": pull,
                "state": "closed",
                "merged": True,
                "draft": False,
                "body": f"The plan of pull {pull}.",
                "head": {"sha": HEAD, "ref": _plan_branch(pull)},
                "base": {"ref": "main", "repo": {"default_branch": "main"}},
            }
        ),
    )


def _graphql_node(pull: int) -> dict[str, Any]:
    """The GraphQL node of the open plan draft `pull`."""
    return {
        "number": pull,
        "title": "feat(roadmap): Plan the sample",
        "body": f"The plan of pull {pull}.",
        "isDraft": True,
        "labels": {"nodes": []},
        "mergeable": "MERGEABLE",
        "headRefOid": HEAD,
        "headRefName": _plan_branch(pull),
        "baseRefName": "main",
        "author": {"login": "devops-cli-service[bot]"},
        "commits": {
            "nodes": [
                {
                    "commit": {
                        "oid": HEAD,
                        "message": "feat(roadmap): Plan the sample",
                        "statusCheckRollup": {
                            "state": "FAILURE",
                            "contexts": {
                                "nodes": [
                                    {
                                        "__typename": "CheckRun",
                                        "name": INFRA_CHECK,
                                        "status": "COMPLETED",
                                        "conclusion": "FAILURE",
                                    }
                                ]
                            },
                        },
                    }
                }
            ]
        },
    }


def _route_graphql(api: GitHubApiFake, nodes: list[dict[str, Any]]) -> None:
    api.route(
        "POST",
        "/graphql",
        github_json(
            {
                "data": {
                    "repository": {
                        "pullRequests": {
                            "nodes": nodes,
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            }
        ),
    )


def _requests_for(api: GitHubApiFake, pull: int) -> list[str]:
    """Each request of the fake that names pull request `pull`."""
    return [request for request in api.requested if f"/pulls/{pull}" in request]


def test_a_scoped_round_reads_only_the_delivered_pull_request(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """The store holds open staged drafts 42 and 43, and the delivery names 42: the round reads
    42 and sends no request for 43."""
    _staged_draft(store, 42)
    _staged_draft(store, 43)
    _route_open_draft(github_api, 42)
    ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME

    result = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW, pull_numbers=(42,))

    assert result.watched == 1
    assert _requests_for(github_api, 42)
    assert _requests_for(github_api, 43) == []


def test_a_scoped_round_for_an_unknown_pull_request_sends_no_request(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """The delivery names 99, and neither the store nor the ledger holds it: the round sends no
    request and returns the empty result."""
    _staged_draft(store, 42)
    ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME

    result = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW, pull_numbers=(99,))

    assert result == WatchRoundResult()
    assert github_api.sent == []


def test_a_round_with_no_numbers_reads_the_open_pulls_with_one_graphql_query(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """The poll reads the open pull requests of the repository with one GraphQL query."""
    _staged_draft(store, 42)
    _route_graphql(github_api, [_graphql_node(42)])
    _route_open_draft(github_api, 42)
    ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME

    result = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW)

    assert result.watched == 1
    assert [request for request in github_api.requested if request.endswith("/graphql")] == [
        f"POST {API}/graphql"
    ]


def test_a_scoped_round_reads_a_pull_request_that_the_ledger_holds(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """A delivered pull request that no Item records as `stage.pr`, but that the watch ledger
    holds, is read and evaluated."""
    issue = store.seed_issue("Delivered item", fields={ItemField.PRIORITY: "P1-High"})
    ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME
    WatchLedger(pulls={77: WatchLedgerEntry(head=HEAD, verdict="failed")}).write(ledger_path)
    github_api.route(
        "GET",
        f"/repos/{REPO}/pulls/77",
        github_json(
            {
                "number": 77,
                "state": "open",
                "merged": False,
                "draft": False,
                "body": f"Closes #{issue}",
                "head": {"sha": HEAD, "ref": "feat/77-sample"},
                "base": {"ref": "main", "repo": {"default_branch": "main"}},
            }
        ),
    )
    github_api.route(
        "GET",
        f"/repos/{REPO}/commits/{HEAD}/check-runs",
        github_json(
            {"check_runs": [{"name": INFRA_CHECK, "status": "completed", "conclusion": "failure"}]}
        ),
    )

    result = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW, pull_numbers=(77,))

    assert result.watched == 1
    assert _requests_for(github_api, 77)


def test_a_scoped_round_settles_a_delivered_closed_plan(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """A delivered plan pull request that closed settles its Item, and no other plan is read."""
    issue = _staged_draft(store, 42)
    _staged_draft(store, 43)
    _route_closed_plan(github_api, 42)
    ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME

    watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW, pull_numbers=(42,))

    item = store.item(issue)
    assert item is not None
    assert item.job_record.get(StageRecordKey.READY) == "42"
    assert _requests_for(github_api, 43) == []
