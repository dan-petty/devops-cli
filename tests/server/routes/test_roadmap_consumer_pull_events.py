"""The roadmap consumer routes a pull request, review or check suite delivery to the `watch` row,
scoped to the pull requests that the delivery names (#4413). A delivery of the App's own bot starts
nothing, and an event with no scoped update keeps a whole-round hint.

Verifies:
1. A signed pull request delivery runs the scoped watch update on the status lane.
2. An unsigned delivery is refused.
3. A delivery of the App's own bot runs no scoped update.
4. An unscopeable check suite event keeps a whole-round hint.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from devops_cli.config.constants import (
    CONST_GH_WEBHOOK_DELIVERY_HEADER,
    CONST_GH_WEBHOOK_EVENT_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_PREFIX,
    CONST_SERVICE_STATUS_OWN_WRITE,
)
from devops_cli.roadmap.stores.store import ItemField, StageRecordKey
from devops_cli.server.routes.webhooks import (
    DeliveryLRUCache,
    create_webhook_router,
    roadmap_consumer,
)
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.process import ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_run import REPO

pytestmark = pytest.mark.usefixtures("keyring_store", "cluster")

SECRET = "secret-1"
"""The webhook secret of the repository, as the fake Service holds it."""

BOT = "devops-cli-service[bot]"
"""The login of the GitHub App's own bot."""

STATUS_LANE = "status"
"""The lane of the status rows, the `watch` row among them (#5553)."""

HEAD = "4" * 40

INFRA_CHECK = "Semantic PR title"


@dataclass
class _ServiceConfig:
    """The setting `service.lanes` of the fake Service: the status lane holds the `watch` row."""

    lanes: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: {STATUS_LANE: ("metrics", "watch")}
    )


@dataclass
class _Lanes:
    """The lanes of the Service, as the roadmap consumer and the webhook route reach them: a
    scoped update runs at once on the worker of its lane, as an idle worker runs it, and each
    whole-round trigger is recorded. The repository, its secret and the delivery cache are here
    too, so a delivery is routed as the Service routes it."""

    state_dir: Path
    bot_login: str | None = None
    secrets: Mapping[str, str] = field(default_factory=lambda: {REPO: SECRET})
    managed_repos: tuple[str, ...] = (REPO,)
    jobs: Mapping[str, str] = field(default_factory=lambda: {STATUS_LANE: "watch"})
    config: _ServiceConfig = field(default_factory=_ServiceConfig)
    delivery_cache: DeliveryLRUCache = field(default_factory=DeliveryLRUCache)
    command_token: str | None = None
    scoped: list[tuple[str, str]] = field(default_factory=list)
    triggers: list[tuple[str, str, str, int | None]] = field(default_factory=list)

    def is_draining(self) -> bool:
        """Whether the Service drains: it does not, so the route reads the body."""
        return False

    def enqueue_scoped(self, repo: str, lane: str, scoped: Callable[[], None]) -> bool:
        """Run the scoped update at once on the worker of `lane`, and record its lane."""
        self.scoped.append((repo, lane))
        scoped()
        return True

    def enqueue_trigger(
        self,
        repo: str,
        source: str,
        event: str,
        action: str,
        *,
        lane: str | None = None,
        subject: int | None = None,
    ) -> bool:
        """Record a whole-round trigger of `repo`, which the fake Service runs nowhere."""
        self.triggers.append((repo, event, action, subject))
        return True


@pytest.fixture
def github_api(github_api_and_gh: tuple[GitHubApiFake, ProcessFake]) -> GitHubApiFake:
    """GitHub's API faked for every GitHub session."""
    api, _process = github_api_and_gh
    return api


def _staged_draft(store: InMemoryRoadmapStore, pull: int) -> int:
    """An open Item of `store` whose record names the staged draft `pull`."""
    issue = store.seed_issue(f"Plan {pull}", fields={ItemField.PRIORITY: "P1-High"})
    item = store.item(issue)
    assert item is not None
    store.set_marks(item, {StageRecordKey.PR: str(pull)})
    return issue


def _route_open_draft(api: GitHubApiFake, pull: int) -> None:
    """Answer the reads of the open plan draft `pull`, whose infra check fails, so that the round
    reads it and takes no ready path."""
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
                "head": {"sha": HEAD, "ref": f"feat/{pull}-plan"},
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


def _app(lanes: _Lanes) -> FastAPI:
    """The Service's webhook route over `lanes`, with the roadmap consumer alone."""
    app = FastAPI()
    app.include_router(create_webhook_router(lanes, consumers=(roadmap_consumer(lanes),)))
    return app


def _sign(body: bytes, secret: str) -> str:
    """The signature header of `body` under `secret`."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"{CONST_GH_WEBHOOK_SIGNATURE_PREFIX}{digest}"


def _payload(action: str, *, sender: str = "alice", **extra: Any) -> dict[str, Any]:
    """What GitHub sends for repository `REPO`, with the fields the Service reads."""
    return {
        "repository": {"full_name": REPO, "default_branch": "main"},
        "action": action,
        "sender": {"login": sender},
        **extra,
    }


def _deliver(
    client: TestClient, event: str, payload: dict[str, Any], delivery: str, *, signed: bool = True
) -> Any:
    """Deliver `payload` as `event`, signed with the secret of the repository unless `signed`."""
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        CONST_GH_WEBHOOK_EVENT_HEADER: event,
        CONST_GH_WEBHOOK_DELIVERY_HEADER: delivery,
    }
    if signed:
        headers[CONST_GH_WEBHOOK_SIGNATURE_HEADER] = _sign(body, SECRET)
    return client.post("/webhooks/github", content=body, headers=headers)


def _requests_for(api: GitHubApiFake, pull: int) -> list[str]:
    """Each request of the fake that names pull request `pull`."""
    return [request for request in api.requested if f"/pulls/{pull}" in request]


def test_a_signed_pull_request_delivery_runs_the_scoped_update(
    roadmap_store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """A signed `pull_request` `synchronize` delivery of pull request 42 runs the watch row on the
    status lane, scoped to 42: the round reads pull request 42 and no other, and the delivery
    queues no full round on any lane. An unsigned delivery is refused, the App bot's own delivery
    runs no scoped update, and a `check_suite` `requested` delivery stays a whole-round hint
    (#4413)."""
    _staged_draft(roadmap_store, 42)
    _staged_draft(roadmap_store, 43)
    _route_open_draft(github_api, 42)
    lanes = _Lanes(state_dir=tmp_path / "state")
    lanes.bot_login = BOT

    with TestClient(_app(lanes)) as client:
        delivered = _deliver(
            client, "pull_request", _payload("synchronize", pull_request={"number": 42}), "pull-42"
        )
        unsigned = _deliver(
            client,
            "pull_request",
            _payload("synchronize", pull_request={"number": 42}),
            "pull-unsigned",
            signed=False,
        )
        own_write = _deliver(
            client,
            "pull_request",
            _payload("synchronize", sender=BOT, pull_request={"number": 43}),
            "pull-own",
        )
        hint = _deliver(
            client,
            "check_suite",
            _payload("requested", check_suite={"pull_requests": [{"number": 42}]}),
            "suite-requested",
        )

    assert (
        delivered.status_code,
        delivered.json(),
        unsigned.status_code,
        own_write.status_code,
        own_write.json(),
        hint.status_code,
        hint.json(),
    ) == (
        202,
        {"status": "accepted"},
        401,
        200,
        {"status": CONST_SERVICE_STATUS_OWN_WRITE},
        202,
        {"status": "accepted"},
    )
    assert (lanes.scoped, lanes.triggers) == (
        [(REPO, STATUS_LANE)],
        [(REPO, "check_suite", "requested", 42)],
    )
    assert (bool(_requests_for(github_api, 42)), _requests_for(github_api, 43)) == (True, [])
