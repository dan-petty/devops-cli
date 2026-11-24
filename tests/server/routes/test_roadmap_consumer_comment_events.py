"""The roadmap consumer refuses an `issue_comment` delivery that it does not trust, before it
reaches a lane and before it spends a GitHub request (#4415).

Verifies:
1. A comment whose action is not `created` is refused.
2. A comment of a bot is refused.
3. A comment on a pull request is refused.
4. A comment of an author outside `CONST_ROADMAP_TRUSTED_AUTHORS` is refused and counts as
   ignored.
5. Each refusal answers its status, reaches no lane and records no GitHub request.
6. A trusted comment runs the row that its text wakes, on the lane of that row, for the issue that
   the delivery names, and queues no whole round.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from devops_cli.config.constants import (
    CONST_GH_WEBHOOK_DELIVERY_HEADER,
    CONST_GH_WEBHOOK_EVENT_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_PREFIX,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES,
    CONST_SERVICE_OUTCOME_ACCEPTED,
    CONST_SERVICE_OUTCOME_IGNORED,
    CONST_SERVICE_STATUS_COMMENT_REFUSED,
    CONST_SERVICE_STATUS_UNTRUSTED_COMMENT,
)
from devops_cli.roadmap.run import WebhookDelivery
from devops_cli.server.routes.webhooks import (
    DeliveryLRUCache,
    create_webhook_router,
    roadmap_consumer,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.github import GitHubApiFake
from tests.support.roadmap_run import REPO

pytestmark = pytest.mark.usefixtures("keyring_store", "cluster")

SECRET = "secret-1"
"""The webhook secret of the repository, as the fake Service holds it."""

BOT = "devops-cli-service[bot]"
"""The login of the GitHub App's own bot."""

COMMENT_EVENT = "issue_comment"
"""The event that GitHub sends for a comment on an issue."""

IMPLEMENT_LANE = "code"
"""The lane of the `implement` row, as the setting `service.lanes` of the fake Service puts it."""

REFINE_LANE = "model"
"""The lane of the `refine` row, which calls the model."""

RETRY = "implement: retry"
"""The comment that asks the `implement` row to clear the stop of an item."""

REPLY = "Which option do you prefer?"
"""A trusted reply that wakes the `refine` row of the issue it is on."""

COMMENTED_AT = datetime(2026, 11, 23, 22, 18, tzinfo=UTC)
"""The time that the payload says the comment was written."""


@dataclass
class _ServiceConfig:
    """The setting `service.lanes` of the fake Service: the `implement` row runs in the code lane
    and the `refine` row in the model lane."""

    lanes: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: {IMPLEMENT_LANE: ("implement",), REFINE_LANE: ("refine",)}
    )


@dataclass
class _Service:
    """The Service as the webhook route reaches it: the repository, its secret, the login of the
    App's own bot, the lanes of its rows and the delivery cache. The fake Service records the
    whole-round triggers and the scoped updates that a delivered event queues, and runs neither, so
    a test sees which row the route picked for which lane without starting a roadmap round."""

    bot_login: str | None = BOT
    secrets: Mapping[str, str] = field(default_factory=lambda: {REPO: SECRET})
    managed_repos: tuple[str, ...] = (REPO,)
    config: _ServiceConfig = field(default_factory=_ServiceConfig)
    delivery_cache: DeliveryLRUCache = field(default_factory=DeliveryLRUCache)
    command_token: str | None = None
    triggers: list[tuple[str, str, str, int | None]] = field(default_factory=list)
    scoped: list[tuple[str, str]] = field(default_factory=list)
    updates: list[Callable[[], None]] = field(default_factory=list)

    def is_draining(self) -> bool:
        """Whether the Service drains: it does not, so the route reads the body."""
        return False

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

    def enqueue_scoped(self, repo: str, lane: str, scoped: Callable[[], None]) -> bool:
        """Record a scoped update of `lane`, which the fake Service does not run."""
        self.scoped.append((repo, lane))
        self.updates.append(scoped)
        return True


def _app(service: _Service) -> FastAPI:
    """The Service's webhook route over `service`, with the roadmap consumer alone."""
    app = FastAPI()
    app.include_router(create_webhook_router(service, consumers=(roadmap_consumer(service),)))
    return app


def _sign(body: bytes, secret: str) -> str:
    """The signature header of `body` under `secret`."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"{CONST_GH_WEBHOOK_SIGNATURE_PREFIX}{digest}"


def _comment_payload(
    action: str = "created",
    *,
    sender: str = "alice",
    association: str = "MEMBER",
    body: str = RETRY,
    number: int = 7,
    pull_request: bool = False,
) -> dict[str, Any]:
    """What GitHub sends for a comment of `sender` on issue `number` of `REPO`, marked as a pull
    request comment when `pull_request`."""
    issue: dict[str, Any] = {"number": number}
    if pull_request:
        issue["pull_request"] = {"url": f"https://api.example.com/repos/{REPO}/pulls/42"}
    return {
        "repository": {"full_name": REPO},
        "action": action,
        "sender": {"login": sender},
        "issue": issue,
        "comment": {
            "body": body,
            "author_association": association,
            "created_at": "2026-11-23T22:18:00Z",
        },
    }


def _deliver(client: TestClient, payload: dict[str, Any], delivery: str) -> Any:
    """Deliver `payload` as an `issue_comment` event, signed with the secret of `REPO`."""
    body = json.dumps(payload).encode("utf-8")
    return client.post(
        "/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            CONST_GH_WEBHOOK_EVENT_HEADER: COMMENT_EVENT,
            CONST_GH_WEBHOOK_DELIVERY_HEADER: delivery,
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(body, SECRET),
        },
    )


def _ignored_comments() -> float:
    """How many comment deliveries counted as ignored, over every test of the process."""
    return GLOBAL_METRICS.get_counter(
        CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES,
        labels={
            "provider": "github",
            "event": COMMENT_EVENT,
            "outcome": CONST_SERVICE_OUTCOME_IGNORED,
        },
    )


def _delivery_of(scoped: Callable[[], None]) -> WebhookDelivery:
    """The delivery that the route handed to the scoped update `scoped`: the route closes over it,
    so the fake Service reads it back to see the row's input without starting the row."""
    cells = [cell.cell_contents for cell in scoped.__closure__ or ()]
    deliveries = [cell for cell in cells if isinstance(cell, WebhookDelivery)]
    assert len(deliveries) == 1
    return deliveries[0]


def test_a_bot_an_edited_action_an_untrusted_author_or_a_pull_request_comment_is_refused_with_no_request(
    github_api: GitHubApiFake,
) -> None:
    """A comment that is not a `created` comment, one of a bot, one on a pull request and one of
    an author without write access are each refused before `deliver`: the action, the bot and the
    pull request marker answer `CONST_SERVICE_STATUS_COMMENT_REFUSED`, and the untrusted author
    answers `CONST_SERVICE_STATUS_UNTRUSTED_COMMENT`, which counts as ignored. No refusal queues
    a trigger or a scoped update, and none records a GitHub request (#4415)."""
    service = _Service()
    before = _ignored_comments()

    with TestClient(_app(service)) as client:
        replies = {
            "edited": _deliver(client, _comment_payload("edited"), "comment-edited"),
            "deleted": _deliver(client, _comment_payload("deleted"), "comment-deleted"),
            "bot": _deliver(client, _comment_payload(sender="dependabot[bot]"), "comment-bot"),
            "pull_request": _deliver(
                client, _comment_payload(pull_request=True), "comment-pull-request"
            ),
            "untrusted": _deliver(
                client, _comment_payload(association="NONE"), "comment-untrusted"
            ),
        }

    assert {name: (reply.status_code, reply.json()) for name, reply in replies.items()} == {
        "edited": (200, {"status": CONST_SERVICE_STATUS_COMMENT_REFUSED}),
        "deleted": (200, {"status": CONST_SERVICE_STATUS_COMMENT_REFUSED}),
        "bot": (200, {"status": CONST_SERVICE_STATUS_COMMENT_REFUSED}),
        "pull_request": (200, {"status": CONST_SERVICE_STATUS_COMMENT_REFUSED}),
        "untrusted": (200, {"status": CONST_SERVICE_STATUS_UNTRUSTED_COMMENT}),
    }
    assert (service.triggers, service.scoped, github_api.requested) == ([], [], [])
    assert _ignored_comments() - before == 5.0


def test_a_trusted_retry_comment_runs_the_implement_row_and_a_trusted_reply_runs_the_refine_row() -> (
    None
):
    """Test first for #4415: a trusted `implement: retry` comment on issue 7 runs the scoped
    update of the `implement` row on the lane of that row, and a trusted reply on issue 9 runs the
    scoped update of the `refine` row on the lane of its own. Each delivery carries the text and
    the time of the comment and the number of the issue that it is about, and neither queues a
    whole round."""
    service = _Service()

    with TestClient(_app(service)) as client:
        retry = _deliver(client, _comment_payload(body=RETRY, number=7), "comment-retry")
        reply = _deliver(
            client, _comment_payload(body=REPLY, number=9, sender="bob"), "comment-reply"
        )

    assert (
        retry.status_code,
        retry.json(),
        reply.status_code,
        reply.json(),
    ) == (
        202,
        {"status": CONST_SERVICE_OUTCOME_ACCEPTED},
        202,
        {"status": CONST_SERVICE_OUTCOME_ACCEPTED},
    )
    assert (service.scoped, service.triggers) == (
        [(REPO, IMPLEMENT_LANE), (REPO, REFINE_LANE)],
        [],
    )
    assert [
        (delivery.event, delivery.action, delivery.number, delivery.comment, delivery.comment_at)
        for delivery in map(_delivery_of, service.updates)
    ] == [
        (COMMENT_EVENT, "created", 7, RETRY, COMMENTED_AT),
        (COMMENT_EVENT, "created", 9, REPLY, COMMENTED_AT),
    ]
