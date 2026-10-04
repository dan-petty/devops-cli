"""Unit tests for GitHub webhook signature verification and event dispatch."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from devops_cli.exceptions.git import GitHubWebhookVerificationError
from devops_cli.github.graphql import (
    WebhookEvent,
    WebhookEventDispatcher,
    verify_webhook_signature,
)


def test_verify_webhook_signature() -> None:
    """Verify constant-time HMAC-SHA256 signature verification."""
    secret = "my-secret-key-12345"
    payload = b'{"action":"opened","issue":{"number":1}}'

    valid_hex = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    valid_sig = f"sha256={valid_hex}"
    invalid_sig = "sha256=badbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadb"

    assert (
        verify_webhook_signature(payload, valid_sig, secret),
        verify_webhook_signature(payload, invalid_sig, secret),
        verify_webhook_signature(payload, None, secret),
        verify_webhook_signature(payload, "invalid_prefix", secret),
        verify_webhook_signature(payload, valid_sig, ""),
    ) == (True, False, False, False, False)


def test_webhook_event_dispatcher() -> None:
    """Verify webhook event dispatching to type-specific and wildcard handlers."""
    dispatcher = WebhookEventDispatcher()
    received_issues: list[WebhookEvent] = []
    received_all: list[WebhookEvent] = []

    dispatcher.register("issues", received_issues.append)
    dispatcher.register("*", received_all.append)

    secret = "webhook-secret"
    payload = {
        "action": "labeled",
        "issue": {"number": 15},
        "repository": {"full_name": "example/repo"},
        "sender": {"login": "octocat"},
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    success = dispatcher.dispatch(
        "issues",
        payload,
        signature_header=sig,
        secret=secret,
        raw_body=raw_body,
    )

    assert (success, len(received_issues), len(received_all)) == (True, 1, 1)
    ev = received_issues[0]
    assert (ev.event_type, ev.action, ev.repository, ev.sender) == (
        "issues",
        "labeled",
        "example/repo",
        "octocat",
    )


def test_webhook_event_dispatcher_invalid_signature() -> None:
    """Verify dispatch raises GitHubWebhookVerificationError on invalid signature."""
    dispatcher = WebhookEventDispatcher()
    with pytest.raises(GitHubWebhookVerificationError):
        dispatcher.dispatch(
            "issues",
            {"action": "opened"},
            signature_header="sha256=invalid",
            secret="correct-secret",
            raw_body=b'{"action":"opened"}',
        )


def test_webhook_dispatcher_handler_exception_handling() -> None:
    """Verify dispatcher catches handler exceptions and continues dispatching."""
    dispatcher = WebhookEventDispatcher()

    def buggy_handler(event: WebhookEvent) -> None:
        raise RuntimeError("boom")

    delivered: list[WebhookEvent] = []
    dispatcher.register("push", buggy_handler)
    dispatcher.register("push", delivered.append)

    res = dispatcher.dispatch("push", {"ref": "refs/heads/main"})
    assert (res, len(delivered)) == (True, 1)
