"""GitHub webhook signature verification and event dispatch."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.exceptions.git import GitHubWebhookVerificationError

logger = logging.getLogger(__name__)


class WebhookEvent(BaseModel):
    """Normalized GitHub Webhook event dispatch payload."""

    event_type: str
    action: str | None = None
    repository: str | None = None
    sender: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


# ── Webhook Signature Verification & Event Dispatcher ────────────────────────


def verify_webhook_signature(
    payload: bytes | str,
    signature_header: str | None,
    secret: str,
) -> bool:
    """Verify GitHub webhook payload against HMAC-SHA256 signature using constant-time comparison."""
    if not signature_header or not secret:
        return False
    if not signature_header.startswith("sha256="):
        return False
    received_hash = signature_header[len("sha256=") :]
    payload_bytes = payload.encode("utf-8") if isinstance(payload, str) else payload
    secret_bytes = secret.encode("utf-8")
    computed_hash = hmac.new(secret_bytes, payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(received_hash, computed_hash)


class WebhookEventDispatcher:
    """Observer pattern event dispatcher for verified GitHub webhook events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[WebhookEvent], None]]] = {}

    def register(self, event_type: str, handler: Callable[[WebhookEvent], None]) -> None:
        """Register a handler for a specific event type (or '*' for all events)."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def dispatch(
        self,
        event_type: str,
        payload: dict[str, Any],
        signature_header: str | None = None,
        secret: str | None = None,
        raw_body: bytes | str | None = None,
    ) -> bool:
        """Verify signature if secret is provided and dispatch event to registered handlers."""
        if secret is not None:
            body_to_verify = (
                raw_body
                if raw_body is not None
                else json.dumps(payload, separators=(",", ":")).encode("utf-8")
            )
            if not verify_webhook_signature(body_to_verify, signature_header, secret):
                raise GitHubWebhookVerificationError(
                    "GitHub webhook HMAC-SHA256 signature validation failed",
                    details={"event_type": event_type[:256]},
                )

        repo_name: str | None = None
        repo_data = payload.get("repository")
        if isinstance(repo_data, dict):
            repo_name = repo_data.get("full_name") or repo_data.get("name")

        sender_login: str | None = None
        sender_data = payload.get("sender")
        if isinstance(sender_data, dict):
            sender_login = sender_data.get("login")

        event = WebhookEvent(
            event_type=event_type,
            action=payload.get("action"),
            repository=repo_name,
            sender=sender_login,
            payload=payload,
        )

        matched = self._handlers.get(event_type, []) + self._handlers.get("*", [])
        for handler in matched:
            try:
                handler(event)
            except Exception as exc:
                logger.error("Handler error on webhook event %s: %s", event_type, exc)

        return True
