"""The roadmap consumer refuses a `release` delivery that it does not take, before it reaches a
lane and before it spends a GitHub request (#4416).

Verifies:
1. A release delivery whose action is not `published` is refused.
2. A draft release is refused.
3. A prerelease is refused.
4. A release that holds no publication time is refused.
5. Each refusal answers `CONST_SERVICE_STATUS_RELEASE_REFUSED`, reaches no lane and records no
   GitHub request.
6. A release delivery whose payload holds no release object is not refused.
7. A published release delivery runs the scoped update of the `release_comments` row on the lane
   of that row, at once, and queues no whole round.
8. A release delivery whose payload holds no release object keeps a whole-round hint.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from devops_cli.config.constants import (
    CONST_GH_WEBHOOK_DELIVERY_HEADER,
    CONST_GH_WEBHOOK_EVENT_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_PREFIX,
    CONST_SERVICE_OUTCOME_ACCEPTED,
)
from devops_cli.roadmap.run import WebhookDelivery
from devops_cli.server.routes.webhooks import (
    DeliveryLRUCache,
    create_webhook_router,
    roadmap_consumer,
)
from tests.support.fakes.github import GitHubApiFake
from tests.support.roadmap_run import REPO

pytestmark = pytest.mark.usefixtures("keyring_store", "cluster")

SECRET = "secret-1"
"""The webhook secret of the repository, as the fake Service holds it."""

BOT = "devops-cli-service[bot]"
"""The login of the GitHub App's own bot."""

RELEASE_EVENT = "release"
"""The event that GitHub sends for a release."""

TAG = "v1.2.3"
"""The tag of the release that a delivery is about."""

PUBLISHED_AT = "2026-11-24T12:00:00Z"
"""The publication time that a published release carries."""

RELEASE_LANE = "model"
"""The lane that the `release_comments` row runs in, as the fake Service puts its rows."""

REFUSED = "ignored_release_refused"
"""The status that the roadmap consumer answers for a release delivery that it ignores, which
`CONST_SERVICE_STATUS_RELEASE_REFUSED` of `devops_cli.config.constants` holds. The test spells it
out, so that it fails on an assertion of a base that knows no release refusal."""


@dataclass
class _ServiceConfig:
    """The setting `service.lanes` of the fake Service: the `release_comments` row runs in the
    model lane."""

    lanes: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: {RELEASE_LANE: ("release_comments",)}
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


def _release_payload(
    action: str = "published",
    *,
    draft: bool = False,
    prerelease: bool = False,
    published_at: str | None = PUBLISHED_AT,
) -> dict[str, Any]:
    """What GitHub sends for the release `TAG` of `REPO`, as a draft, as a prerelease, with no
    publication time when `published_at` is None, and under `action`."""
    release: dict[str, Any] = {
        "tag_name": TAG,
        "html_url": f"https://github.com/{REPO}/releases/tag/{TAG}",
        "body": "Closes #123",
        "draft": draft,
        "prerelease": prerelease,
    }
    if published_at is not None:
        release["published_at"] = published_at
    return {
        "repository": {"full_name": REPO},
        "action": action,
        "sender": {"login": "release-please[bot]"},
        "release": release,
    }


def _payload_without_release() -> dict[str, Any]:
    """What GitHub sends for a `release` event whose body carries no release object."""
    return {
        "repository": {"full_name": REPO},
        "action": "published",
        "sender": {"login": "alice"},
    }


def _deliver(client: TestClient, payload: dict[str, Any], delivery: str) -> Any:
    """Deliver `payload` as a `release` event, signed with the secret of `REPO`."""
    body = json.dumps(payload).encode("utf-8")
    return client.post(
        "/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            CONST_GH_WEBHOOK_EVENT_HEADER: RELEASE_EVENT,
            CONST_GH_WEBHOOK_DELIVERY_HEADER: delivery,
            CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(body, SECRET),
        },
    )


def _delivery_of(scoped: Callable[[], None]) -> WebhookDelivery:
    """The delivery that the route handed to the scoped update `scoped`: the route closes over it,
    so the fake Service reads it back to see the row's input without starting the row."""
    cells = [cell.cell_contents for cell in scoped.__closure__ or ()]
    deliveries = [cell for cell in cells if isinstance(cell, WebhookDelivery)]
    assert len(deliveries) == 1
    return deliveries[0]


def test_an_unwanted_release_is_refused_with_no_request(github_api: GitHubApiFake) -> None:
    """Test first for #4416: a release delivery of an action that is not `published`, one of a
    draft, one of a prerelease and one that holds no publication time are each refused before
    `deliver`: each answers `CONST_SERVICE_STATUS_RELEASE_REFUSED`, queues no whole round and no
    scoped update, and records no GitHub request. A published release delivery, and one whose
    payload carries no release object, are not refused, so the delivery without a release still
    queues its round."""
    service = _Service()

    with TestClient(_app(service)) as client:
        refused = {
            "created": _deliver(client, _release_payload("created"), "release-created"),
            "edited": _deliver(client, _release_payload("edited"), "release-edited"),
            "draft": _deliver(client, _release_payload(draft=True), "release-draft"),
            "prerelease": _deliver(client, _release_payload(prerelease=True), "release-prerelease"),
            "unpublished": _deliver(client, _release_payload(published_at=None), "release-unpub"),
        }

    assert {name: (reply.status_code, reply.json()) for name, reply in refused.items()} == {
        "created": (200, {"status": REFUSED}),
        "edited": (200, {"status": REFUSED}),
        "draft": (200, {"status": REFUSED}),
        "prerelease": (200, {"status": REFUSED}),
        "unpublished": (200, {"status": REFUSED}),
    }
    assert (service.triggers, service.scoped, github_api.requested) == ([], [], [])

    taken = _Service()

    with TestClient(_app(taken)) as client:
        published = _deliver(client, _release_payload(), "release-published")
        without_release = _deliver(client, _payload_without_release(), "release-no-object")

    assert (published.status_code, published.json(), without_release.status_code) == (
        202,
        {"status": CONST_SERVICE_OUTCOME_ACCEPTED},
        202,
    )
    assert (REPO, RELEASE_EVENT, "published", None) in taken.triggers


def test_a_published_release_delivery_runs_the_scoped_release_update() -> None:
    """Test first for #4416: a signed `release` `published` delivery that carries a release runs
    the scoped update of the `release_comments` row on the lane of that row, at once, and queues
    no whole round. The delivery carries the release of the payload, so the scoped update reads
    its tag without a second read of the release."""
    service = _Service()

    with TestClient(_app(service)) as client:
        reply = _deliver(client, _release_payload(), "release-published")

    assert (reply.status_code, reply.json()) == (202, {"status": CONST_SERVICE_OUTCOME_ACCEPTED})
    assert (service.scoped, service.triggers) == ([(REPO, RELEASE_LANE)], [])
    delivery = _delivery_of(service.updates[0])
    assert (delivery.event, delivery.action, delivery.number, delivery.pull_numbers) == (
        RELEASE_EVENT,
        "published",
        None,
        (),
    )
    assert delivery.release is not None
    assert (
        delivery.release.tag_name,
        delivery.release.html_url,
        delivery.release.body,
        delivery.release.draft,
        delivery.release.prerelease,
    ) == (
        TAG,
        f"https://github.com/{REPO}/releases/tag/{TAG}",
        "Closes #123",
        False,
        False,
    )


def test_a_release_delivery_with_no_release_keeps_a_whole_round_hint() -> None:
    """A signed `release` `published` delivery whose payload holds no release object has nothing
    to scope, so it queues one whole-round trigger, which every lane of the Service takes, and no
    scoped update (#4416)."""
    service = _Service()

    with TestClient(_app(service)) as client:
        reply = _deliver(client, _payload_without_release(), "release-no-object")

    assert (reply.status_code, reply.json()) == (202, {"status": CONST_SERVICE_OUTCOME_ACCEPTED})
    assert (service.scoped, service.triggers) == (
        [],
        [(REPO, RELEASE_EVENT, "published", None)],
    )
