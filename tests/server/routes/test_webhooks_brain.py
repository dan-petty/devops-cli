"""The project-brain cache of GitHub issues written by webhook delivery (#6013).

The roadmap consumer writes the issue of each delivery to the shared tier before it wakes the
lanes, so a row that runs for that delivery reads the new state with no request.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from devops_cli.config.constants import (
    CONST_GH_WEBHOOK_DELIVERY_HEADER,
    CONST_GH_WEBHOOK_EVENT_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_PREFIX,
)
from devops_cli.roadmap.stores.brain_issues import cached_issue
from devops_cli.server.routes.webhooks import (
    DeliveryLRUCache,
    create_webhook_router,
    roadmap_consumer,
)

if TYPE_CHECKING:
    from fakeredis import FakeServer

    from devops_cli.valkey.cache import ValkeyCacheTier

pytestmark = pytest.mark.usefixtures("keyring_store", "cluster")

REPO = "owner/repo"
SECRET = "secret-1"


@dataclass
class _ServiceConfig:
    lanes: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: {"status": ("triage",), "model": ("refine",)}
    )


@dataclass
class _Service:
    """The Service as the webhook route reaches it."""

    bot_login: str | None = "service-bot[bot]"
    secrets: Mapping[str, str] = field(default_factory=lambda: {REPO: SECRET})
    managed_repos: tuple[str, ...] = (REPO,)
    config: _ServiceConfig = field(default_factory=_ServiceConfig)
    delivery_cache: DeliveryLRUCache = field(default_factory=DeliveryLRUCache)
    command_token: str | None = None
    triggers: list[tuple[str, str, str, int | None]] = field(default_factory=list)
    cache_at_wake: dict[int, Any] = field(default_factory=dict)

    def is_draining(self) -> bool:
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
        if subject is not None:
            self.cache_at_wake[subject] = cached_issue(repo, subject)
        self.triggers.append((repo, event, action, subject))
        return True

    def enqueue_scoped(self, repo: str, lane: str, scoped: Callable[[], None]) -> bool:
        return False


def _app(service: _Service) -> FastAPI:
    app = FastAPI()
    app.include_router(create_webhook_router(service, consumers=(roadmap_consumer(service),)))
    return app


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"{CONST_GH_WEBHOOK_SIGNATURE_PREFIX}{digest}"


def test_a_labeled_issue_event_writes_the_entry_before_the_wake(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """A labeled issue event writes the entry and wakes the row."""
    service = _Service()
    app = _app(service)

    updated_at_str = "2026-11-23T22:18:00Z"
    expected_updated_at = datetime(2026, 11, 23, 22, 18, 0, tzinfo=UTC)

    payload = {
        "repository": {"full_name": REPO},
        "action": "labeled",
        "sender": {"login": "alice"},
        "issue": {
            "number": 42,
            "title": "Cached issue from webhook",
            "body": "Issue body content",
            "state": "open",
            "updated_at": updated_at_str,
            "labels": [{"name": "status/ready"}, {"name": "type/feature"}],
        },
    }

    body = json.dumps(payload).encode("utf-8")
    with TestClient(app) as client:
        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "Content-Type": "application/json",
                CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
                CONST_GH_WEBHOOK_DELIVERY_HEADER: "delivery-42",
                CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(body, SECRET),
            },
        )

    assert response.status_code == 202
    assert (REPO, "issues", "labeled", 42) in service.triggers

    # The entry must have been written before the wake was enqueued
    cached_at_wake = service.cache_at_wake.get(42)
    assert cached_at_wake is not None, "cache was not written before enqueue_trigger"
    assert cached_at_wake.record.number == 42
    assert "status/ready" in cached_at_wake.record.labels
    assert "type/feature" in cached_at_wake.record.labels
    assert cached_at_wake.record.title == "Cached issue from webhook"
    assert cached_at_wake.record.body == "Issue body content"
    assert cached_at_wake.record.updated_at == expected_updated_at

    # The entry in the tier matches
    current = cached_issue(REPO, 42)
    assert current is not None
    assert current == cached_at_wake
