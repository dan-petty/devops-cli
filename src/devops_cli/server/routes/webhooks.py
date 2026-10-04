"""GitHub webhook endpoint and HMAC signature verification."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from devops_cli.config.constants import (
    CONST_GH_WEBHOOK_DELIVERY_HEADER,
    CONST_GH_WEBHOOK_EVENT_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_HEADER,
    CONST_SERVICE_DELIVERY_LRU_CAPACITY,
    CONST_SERVICE_MAX_BODY_BYTES,
    CONST_SERVICE_METRIC_TRIGGERS,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES,
    CONST_SERVICE_PING_EVENT,
    CONST_SERVICE_SOURCE_WEBHOOK,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS

if TYPE_CHECKING:
    from devops_cli.server.service import ServiceManager

logger = logging.getLogger(__name__)


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


class DeliveryLRUCache:
    """Thread-safe LRU cache for tracking recent delivery IDs to eliminate duplicate replays."""

    def __init__(self, capacity: int = CONST_SERVICE_DELIVERY_LRU_CAPACITY) -> None:
        self._capacity = capacity
        self._cache: OrderedDict[str, None] = OrderedDict()
        self._lock = threading.Lock()

    def check_and_add(self, delivery_id: str) -> bool:
        """Return True if delivery_id is already seen (duplicate), False otherwise."""
        with self._lock:
            if delivery_id in self._cache:
                self._cache.move_to_end(delivery_id)
                return True
            self._cache[delivery_id] = None
            if len(self._cache) > self._capacity:
                self._cache.popitem(last=False)
            return False


async def _read_and_cap_body(request: Request) -> tuple[bytes | None, Response | None]:
    """Read the incoming request body while enforcing the 25 MiB size cap."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > CONST_SERVICE_MAX_BODY_BYTES:
                return None, JSONResponse(status_code=413, content={"error": "payload too large"})
        except ValueError:
            pass

    body_chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in request.stream():
        total_bytes += len(chunk)
        if total_bytes > CONST_SERVICE_MAX_BODY_BYTES:
            return None, JSONResponse(status_code=413, content={"error": "payload too large"})
        body_chunks.append(chunk)

    return b"".join(body_chunks), None


def _check_headers_and_type(request: Request) -> tuple[str | None, str | None, Response | None]:
    """Validate Content-Type and presence of required delivery headers."""
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("application/json"):
        return (
            None,
            None,
            JSONResponse(status_code=415, content={"error": "unsupported media type"}),
        )

    event = request.headers.get(CONST_GH_WEBHOOK_EVENT_HEADER)
    delivery_id = request.headers.get(CONST_GH_WEBHOOK_DELIVERY_HEADER)
    if not event or not delivery_id:
        return (
            None,
            None,
            JSONResponse(status_code=400, content={"error": "missing event or delivery header"}),
        )

    return event, delivery_id, None


def _verify_signature_and_extract_payload(
    raw_body: bytes,
    signature_header: str | None,
    service_manager: ServiceManager,
) -> tuple[dict[str, Any] | None, str | None, Response | None]:
    """Authenticate HMAC signature across managed repo secrets and parse payload body."""
    if not signature_header:
        return None, None, JSONResponse(status_code=401, content={"error": "missing signature"})

    matching_repos = [
        repo
        for repo in service_manager.managed_repos
        if repo in service_manager.secrets
        and verify_webhook_signature(raw_body, signature_header, service_manager.secrets[repo])
    ]
    if not matching_repos:
        return None, None, JSONResponse(status_code=401, content={"error": "invalid signature"})

    try:
        payload = json.loads(raw_body.decode("utf-8"))
        if not isinstance(payload, dict):
            return (
                None,
                None,
                JSONResponse(status_code=400, content={"error": "body must be a json object"}),
            )
    except Exception:
        return None, None, JSONResponse(status_code=400, content={"error": "invalid json body"})

    repo_obj = payload.get("repository")
    repo_name = repo_obj.get("full_name") if isinstance(repo_obj, dict) else None
    if (
        not repo_name
        or repo_name not in service_manager.managed_repos
        or repo_name not in matching_repos
    ):
        return (
            None,
            None,
            JSONResponse(
                status_code=401, content={"error": "unmanaged repository or signature mismatch"}
            ),
        )

    return payload, repo_name, None


def _check_ignored_delivery(
    payload: dict[str, Any],
    event: str,
    delivery_id: str,
    service_manager: ServiceManager,
) -> Response | None:
    """Filter out ping events, machine account actions, and duplicate deliveries."""
    if event == CONST_SERVICE_PING_EVENT:
        return JSONResponse(status_code=200, content={"status": "pong"})

    if service_manager.machine_account:
        sender_obj = payload.get("sender")
        sender_login = sender_obj.get("login") if isinstance(sender_obj, dict) else None
        if sender_login and sender_login.lower() == service_manager.machine_account.lower():
            return JSONResponse(status_code=200, content={"status": "ignored_machine_account"})

    if service_manager.delivery_cache.check_and_add(delivery_id):
        return JSONResponse(status_code=200, content={"status": "duplicate"})

    return None


def create_webhook_router(service_manager: ServiceManager) -> APIRouter:
    """Construct APIRouter for GitHub webhook receiver."""
    router = APIRouter(tags=["webhooks"])

    @router.post("/webhooks/github")
    async def receive_github_webhook(request: Request) -> Response:
        if service_manager.is_draining():
            GLOBAL_METRICS.increment_counter(
                CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES, labels={"outcome": "rejected"}
            )
            return JSONResponse(status_code=503, content={"error": "service is draining"})

        event, delivery_id, err_resp = _check_headers_and_type(request)
        if err_resp is not None:
            GLOBAL_METRICS.increment_counter(
                CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES, labels={"outcome": "rejected"}
            )
            return err_resp

        raw_body, body_err = await _read_and_cap_body(request)
        if body_err is not None or raw_body is None:
            GLOBAL_METRICS.increment_counter(
                CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES, labels={"outcome": "rejected"}
            )
            return body_err or JSONResponse(status_code=413, content={"error": "payload too large"})

        signature_header = request.headers.get(CONST_GH_WEBHOOK_SIGNATURE_HEADER)
        payload, repo_name, auth_err = _verify_signature_and_extract_payload(
            raw_body, signature_header, service_manager
        )
        if auth_err is not None or payload is None or repo_name is None:
            GLOBAL_METRICS.increment_counter(
                CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES, labels={"outcome": "rejected"}
            )
            return auth_err or JSONResponse(
                status_code=401, content={"error": "authentication failed"}
            )

        ignored_resp = _check_ignored_delivery(
            payload, str(event), str(delivery_id), service_manager
        )
        if ignored_resp is not None:
            GLOBAL_METRICS.increment_counter(
                CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES, labels={"outcome": "ignored"}
            )
            return ignored_resp

        action = str(payload.get("action", ""))
        service_manager.enqueue_trigger(
            repo=repo_name,
            source=CONST_SERVICE_SOURCE_WEBHOOK,
            event=str(event),
            action=action,
        )
        GLOBAL_METRICS.increment_counter(
            CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES, labels={"outcome": "accepted"}
        )
        GLOBAL_METRICS.increment_counter(
            CONST_SERVICE_METRIC_TRIGGERS,
            labels={"repo": repo_name, "source": CONST_SERVICE_SOURCE_WEBHOOK},
        )
        return JSONResponse(status_code=202, content={"status": "accepted"})

    return router
