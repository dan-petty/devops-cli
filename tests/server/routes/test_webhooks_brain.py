"""The project-brain cache of GitHub issues written by webhook delivery (#6013, #7292).

The roadmap consumer writes the issue of each delivery of a public repository to the shared tier
before it wakes the lanes, so a row that runs for that delivery reads the new state with no
request. The visibility comes from the delivery (`repository.private`), else from the answer that
the process holds, and never from a GitHub read of the route. The issue of a private repository
reaches the shared tier only when the process sends the `sweep` ACL user.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from fakeredis import FakeServer, FakeValkey
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
    from devops_cli.valkey.cache import ValkeyCacheTier
    from tests.support.fakes.otlp import FakeCollector

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
    """The Service as the webhook route reaches it. With `reads_at_wake`, it reads the entry of
    the subject of each wake from the shared tier, as a row of a public repository does."""

    bot_login: str | None = "service-bot[bot]"
    secrets: Mapping[str, str] = field(default_factory=lambda: {REPO: SECRET})
    managed_repos: tuple[str, ...] = (REPO,)
    config: _ServiceConfig = field(default_factory=_ServiceConfig)
    delivery_cache: DeliveryLRUCache = field(default_factory=DeliveryLRUCache)
    command_token: str | None = None
    triggers: list[tuple[str, str, str, int | None]] = field(default_factory=list)
    cache_at_wake: dict[int, Any] = field(default_factory=dict)
    reads_at_wake: bool = True

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
        if subject is not None and self.reads_at_wake:
            self.cache_at_wake[subject] = cached_issue(repo, subject, private=False)
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
        "repository": {"full_name": REPO, "private": False},
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
    current = cached_issue(REPO, 42, private=False)
    assert current is not None
    assert current == cached_at_wake


def test_an_issue_event_with_int_repair_rounds_decodes_the_job_record(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """An issue webhook decodes integer record fields via `decode_job_record` without failing validation (#7110)."""
    service = _Service()
    app = _app(service)

    body = json.dumps(
        {
            "repository": {"full_name": REPO, "private": False},
            "action": "labeled",
            "sender": {"login": "alice"},
            "issue": {
                "number": 43,
                "title": "Issue with int repair rounds",
                "body": 'Body text\n\n<!-- devops-roadmap-record {"implement.repair_rounds": 0, "Status": "Ready", "unknown.future_key": 7} -->',
                "state": "open",
                "updated_at": "2026-11-25T06:00:00Z",
                "labels": [{"name": "status/ready"}],
            },
        }
    ).encode("utf-8")
    with TestClient(app) as client:
        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "Content-Type": "application/json",
                CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
                CONST_GH_WEBHOOK_DELIVERY_HEADER: "delivery-43",
                CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(body, SECRET),
            },
        )

    assert response.status_code == 202
    entry = cached_issue(REPO, 43, private=False)
    assert entry is not None
    assert entry.record.job_record == {"implement.repair_rounds": "0", "Status": "Ready"}


def test_a_comment_event_with_int_repair_rounds_and_malformed_field_decodes_cleanly(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """An issue_comment webhook decodes integer repair rounds and drops non-string record fields (#7110)."""
    service = _Service()
    app = _app(service)

    body = json.dumps(
        {
            "repository": {"full_name": REPO, "private": False},
            "action": "created",
            "sender": {"login": "alice"},
            "issue": {
                "number": 44,
                "title": "Comment on issue with malformed field",
                "body": 'Body text\n\n<!-- devops-roadmap-record {"implement.repair_rounds": 2, "refine.next_step": 999} -->',
                "state": "open",
                "updated_at": "2026-11-25T06:05:00Z",
            },
            "comment": {
                "body": "Person note",
                "author_association": "COLLABORATOR",
                "created_at": "2026-11-25T06:05:00Z",
            },
        }
    ).encode("utf-8")
    with TestClient(app) as client:
        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "Content-Type": "application/json",
                CONST_GH_WEBHOOK_EVENT_HEADER: "issue_comment",
                CONST_GH_WEBHOOK_DELIVERY_HEADER: "delivery-44",
                CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(body, SECRET),
            },
        )

    assert response.status_code == 202
    entry = cached_issue(REPO, 44, private=False)
    assert entry is not None
    assert entry.record.job_record == {"implement.repair_rounds": "2"}


def test_newer_own_write_issue_webhook_updates_cache_without_waking_lane(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """A newer App-bot `issues` webhook refreshes `brain-issue` without waking a lane (#7063)."""
    from devops_cli.config.constants import CONST_SERVICE_STATUS_OWN_WRITE
    from devops_cli.roadmap.stores.brain_issues import CachedIssue, remember_issue
    from devops_cli.roadmap.stores.store import IssueRecord

    service = _Service()
    app = _app(service)
    older_time = datetime(2026, 11, 23, 22, 18, 0, tzinfo=UTC)
    newer_time = datetime(2026, 11, 23, 22, 20, 0, tzinfo=UTC)
    remember_issue(
        REPO,
        CachedIssue(
            record=IssueRecord(
                number=42,
                title="Tracked work",
                url=f"https://github.com/{REPO}/issues/42",
                labels=("priority/p1-high", "status/in-progress", "owner/service"),
                updated_at=older_time,
            ),
            etag='W/"etag-1"',
            checked_at=older_time,
        ),
        private=False,
    )

    payload = {
        "repository": {"full_name": REPO, "private": False},
        "action": "labeled",
        "sender": {"login": "service-bot[bot]"},
        "issue": {
            "number": 42,
            "title": "Tracked work",
            "body": "Done by runner pod.",
            "state": "open",
            "updated_at": "2026-11-23T22:20:00Z",
            "labels": [{"name": "priority/p1-high"}, {"name": "status/in-review"}],
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
                CONST_GH_WEBHOOK_DELIVERY_HEADER: "delivery-own-new",
                CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(body, SECRET),
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": CONST_SERVICE_STATUS_OWN_WRITE}
    assert service.triggers == []

    current = cached_issue(REPO, 42, private=False)
    assert current is not None
    assert current.record.labels == ("priority/p1-high", "status/in-review")
    assert current.record.updated_at == newer_time


def test_stale_or_comment_own_write_webhook_keeps_newer_cache_entry(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer
) -> None:
    """An own-write webhook with an equal or older `updated_at`, or with a comment, does not
    overwrite a fresher cached entry (#7063)."""
    from devops_cli.config.constants import CONST_SERVICE_STATUS_OWN_WRITE
    from devops_cli.roadmap.stores.brain_issues import CachedIssue, remember_issue
    from devops_cli.roadmap.stores.store import IssueRecord

    service = _Service()
    app = _app(service)
    current_time = datetime(2026, 11, 23, 22, 20, 0, tzinfo=UTC)
    kept = CachedIssue(
        record=IssueRecord(
            number=42,
            title="Tracked work",
            url=f"https://github.com/{REPO}/issues/42",
            labels=("priority/p1-high", "status/in-review"),
            updated_at=current_time,
        ),
        etag='W/"keep-etag"',
        checked_at=current_time,
    )
    remember_issue(REPO, kept, private=False)

    with TestClient(app) as client:
        for delivery_id, extra, stamp in (
            ("delivery-same-second", {}, "2026-11-23T22:20:00Z"),
            ("delivery-older", {}, "2026-11-23T22:19:00Z"),
            (
                "delivery-comment",
                {
                    "comment": {
                        "body": "Job ended",
                        "author_association": "NONE",
                        "created_at": "2026-11-23T22:21:00Z",
                    }
                },
                "2026-11-23T22:21:00Z",
            ),
        ):
            payload = {
                "repository": {"full_name": REPO, "private": False},
                "action": "edited" if not extra else "created",
                "sender": {"login": "service-bot[bot]"},
                "issue": {
                    "number": 42,
                    "title": "Tracked work",
                    "body": "Stale payload",
                    "state": "open",
                    "updated_at": stamp,
                    "labels": [{"name": "priority/p1-high"}, {"name": "status/in-progress"}],
                },
                **extra,
            }
            event_name = "issue_comment" if extra else "issues"
            raw = json.dumps(payload).encode("utf-8")
            reply = client.post(
                "/webhooks/github",
                content=raw,
                headers={
                    "Content-Type": "application/json",
                    CONST_GH_WEBHOOK_EVENT_HEADER: event_name,
                    CONST_GH_WEBHOOK_DELIVERY_HEADER: delivery_id,
                    CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(raw, SECRET),
                },
            )
            assert reply.status_code == 200
            assert reply.json() == {"status": CONST_SERVICE_STATUS_OWN_WRITE}

    current = cached_issue(REPO, 42, private=False)
    assert current == kept


def _keys(server: FakeServer) -> list[str]:
    return sorted(FakeValkey(server=server, decode_responses=True).keys("*"))


def _issue_writes(otlp: FakeCollector) -> dict[str, float]:
    """The writes of the issue store to the shared tier that the process counted, by result."""
    from devops_cli.telemetry.instruments import BRAIN_WRITES_TOTAL

    counted: dict[str, float] = {}
    for attributes, value in otlp.points(BRAIN_WRITES_TOTAL.name):
        if attributes["store"] == "issue":
            counted[attributes["result"]] = counted.get(attributes["result"], 0) + value
    return counted


def _deliver(service: _Service, repository: Mapping[str, Any], *, sender: str = "alice") -> int:
    """Send one signed `issues` delivery about issue 42 of `repository`, and give the status."""
    body = json.dumps(
        {
            "repository": repository,
            "action": "labeled",
            "sender": {"login": sender},
            "issue": {
                "number": 42,
                "title": "Issue of the delivery",
                "body": "Issue body content",
                "state": "open",
                "updated_at": "2026-11-23T22:18:00Z",
                "labels": [{"name": "status/ready"}],
            },
        }
    ).encode("utf-8")
    with TestClient(_app(service)) as client:
        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "Content-Type": "application/json",
                CONST_GH_WEBHOOK_EVENT_HEADER: "issues",
                CONST_GH_WEBHOOK_DELIVERY_HEADER: f"delivery-of-{sender}",
                CONST_GH_WEBHOOK_SIGNATURE_HEADER: _sign(body, SECRET),
            },
        )
    return response.status_code


def test_a_delivery_of_a_private_repository_writes_no_key(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """A delivery of a private repository, and an own-write delivery of it, wake the row as
    before and write no key to the shared tier, while the process sends no ACL user. Each counts
    one write with the result `private` (#7292)."""
    service = _Service(reads_at_wake=False)

    statuses = (
        _deliver(service, {"full_name": REPO, "private": True}),
        _deliver(service, {"full_name": REPO, "private": True}, sender="service-bot[bot]"),
    )

    assert (statuses, service.triggers, _keys(valkey_server), _issue_writes(otlp)) == (
        (202, 200),
        [(REPO, "issues", "labeled", 42)],
        [],
        {"private": 2.0},
    )


def test_a_delivery_of_a_private_repository_is_shared_under_the_sweep_user(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, config: Callable[..., Path]
) -> None:
    """While the process sends the `sweep` ACL user, the issue of a delivery of a private
    repository reaches the shared tier, under the roadmap prefix."""
    from devops_cli.roadmap.stores.visibility import SWEEP_USER

    config(valkey={"username": SWEEP_USER})

    status = _deliver(_Service(reads_at_wake=False), {"full_name": REPO, "private": True})

    assert (status, _keys(valkey_server)) == (202, ["valkey:roadmap:v1:issue:owner/repo:42"])


def test_a_delivery_with_no_visibility_uses_the_answer_that_the_process_holds(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """A delivery that does not carry the visibility of its repository sends no GitHub read. It
    writes no key while the process holds no answer of the visibility check, and counts
    `unknown`. After a public answer of the check, the next delivery writes the issue."""
    from devops_cli.roadmap.stores.visibility import visibility_of

    service = _Service(reads_at_wake=False)
    with_no_answer = (_deliver(service, {"full_name": REPO}), _keys(valkey_server))

    visibility_of(REPO, lambda: False)
    with_a_public_answer = (
        _deliver(service, {"full_name": REPO}, sender="bob"),
        _keys(valkey_server),
    )

    assert (with_no_answer, with_a_public_answer, _issue_writes(otlp)) == (
        (202, []),
        (202, ["valkey:roadmap:v1:issue:owner/repo:42"]),
        {"unknown": 1.0, "shared": 1.0},
    )
