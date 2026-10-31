"""The webhook router (#1386): one route per declared provider, each verified its own way, its body
parsed into a typed payload and delivered to the consumers subscribed to its event."""

from __future__ import annotations

import hashlib
import hmac
import inspect
import logging
import secrets
import shlex
import threading
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC
from typing import TYPE_CHECKING, Any, Final, cast

from cachetools import LRUCache
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security.utils import get_authorization_scheme_param
from pydantic import BaseModel, ConfigDict, ValidationError

from devops_cli.config.constants import (
    CONST_GH_WEBHOOK_DELIVERY_HEADER,
    CONST_GH_WEBHOOK_EVENT_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_HEADER,
    CONST_GH_WEBHOOK_SIGNATURE_PREFIX,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_ROADMAP_WEBHOOK_EVENTS,
    CONST_SERVICE_DELIVERY_LRU_CAPACITY,
    CONST_SERVICE_EVENT_OTHER,
    CONST_SERVICE_MAX_BODY_BYTES,
    CONST_SERVICE_METRIC_CHAT_COMMANDS,
    CONST_SERVICE_METRIC_TRIGGERS,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES,
    CONST_SERVICE_OUTCOME_ACCEPTED,
    CONST_SERVICE_OUTCOME_IGNORED,
    CONST_SERVICE_OUTCOME_NO_SUBSCRIBER,
    CONST_SERVICE_OUTCOME_REJECTED,
    CONST_SERVICE_OUTCOME_SELF,
    CONST_SERVICE_PING_EVENT,
    CONST_SERVICE_SOURCE_WEBHOOK,
    CONST_SERVICE_STATUS_OWN_WRITE,
    WebhookExposure,
    WebhookProviderName,
)
from devops_cli.lang import MESSAGES
from devops_cli.models.webhooks import GitHubWebhookPayload
from devops_cli.telemetry.metrics import GLOBAL_METRICS

if TYPE_CHECKING:
    from devops_cli.server.service import ServiceManager

logger = logging.getLogger(__name__)

# The outcome each refusal status counts as; any other refusal counts as ignored (#2475).
_REFUSAL_OUTCOMES: Final[Mapping[str, str]] = {
    CONST_SERVICE_STATUS_OWN_WRITE: CONST_SERVICE_OUTCOME_SELF,
}


class HmacSha256(BaseModel):
    """Verifies a body against the hex HMAC-SHA256 digest that a request header carries after an
    optional prefix, with one secret per subject (a repository, for GitHub)."""

    model_config = ConfigDict(frozen=True)

    header: str
    prefix: str = ""

    def verify(self, body: bytes, signature: str | None, secret: str) -> bool:
        """Whether `signature` is the digest of `body` under `secret`, compared in constant
        time. The digest is hex, so text that is not ASCII can't match."""
        if not signature or not secret or not signature.startswith(self.prefix):
            return False
        received = signature[len(self.prefix) :]
        computed = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(received.encode("utf-8"), computed.encode("utf-8"))

    def signers(
        self, body: bytes, signature: str | None, secrets: Mapping[str, str]
    ) -> frozenset[str]:
        """The subjects whose secret `signature` is the digest of `body` under."""
        return frozenset(
            subject for subject, secret in secrets.items() if self.verify(body, signature, secret)
        )


class AuthorizationToken(BaseModel):
    """Verifies a request carries an Authorization header matching `scheme` and the configured
    token, compared in constant time (#1395)."""

    model_config = ConfigDict(frozen=True)

    scheme: str

    def verify(self, auth_header: str | None, expected_token: str | None) -> bool:
        """Whether `auth_header` carries `self.scheme` and matches `expected_token` in constant time."""
        if not auth_header or not expected_token:
            return False
        scheme, token = get_authorization_scheme_param(auth_header)
        if scheme.lower() != self.scheme.lower() or not token:
            return False
        return secrets.compare_digest(token, expected_token)


class WebhookProvider(BaseModel):
    """What the router knows of one sender: how its requests prove who sent them, where their
    event name and delivery id are, the payload model its bodies validate into, the event that
    only asks whether the Service is listening, and how it is reached."""

    model_config = ConfigDict(frozen=True)

    name: WebhookProviderName
    exposure: WebhookExposure
    verifier: HmacSha256 | AuthorizationToken
    event_header: str = ""
    delivery_header: str = ""
    ping_event: str = ""
    payload_model: type[GitHubWebhookPayload] | None = None
    content_type: str = "application/json"
    responder: Callable[[Request, Any, bytes], Awaitable[Response | dict[str, Any]]] | None = None

    @property
    def path(self) -> str:
        """The route the provider's requests are posted to."""
        return f"/webhooks/{self.name}"


def _takes_every_payload(_payload: GitHubWebhookPayload) -> str | None:
    """The refusal of a consumer that narrows its events no further."""
    return None


class WebhookConsumer(BaseModel):
    """What takes a provider's events: the `events` it subscribes to, a `refusal` that narrows
    them by their payload (the status that says why the consumer ignores a payload, or None to
    take it), and the `deliver` target that receives the repository, event and action of each
    event it takes."""

    model_config = ConfigDict(frozen=True)

    name: str
    provider: WebhookProviderName
    events: frozenset[str]
    deliver: Callable[..., None]
    refusal: Callable[[GitHubWebhookPayload], str | None] = _takes_every_payload


def _format_lane_status(status: Any) -> str:
    state = "running" if status.active else "idle"
    if status.last_round is not None:
        start_str = status.last_round.start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = status.last_round.end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return MESSAGES.serve.chat_roadmap_status_round.format(
            repo=status.repo,
            lane=status.lane,
            state=state,
            pending=status.pending_triggers,
            start=start_str,
            end=end_str,
            result=status.last_round.result,
        )
    return MESSAGES.serve.chat_roadmap_status_no_round.format(
        repo=status.repo,
        lane=status.lane,
        state=state,
        pending=status.pending_triggers,
    )


async def mattermost_roadmap_responder(
    request: Request,
    service_manager: ServiceManager,
    body: bytes,
) -> dict[str, Any]:
    """Execute the /roadmap chat command synchronously and return an ephemeral response (#1395)."""
    request._body = body
    form = await request.form()
    raw_text = str(form.get("text", "")).strip()

    try:
        args = shlex.split(raw_text)
    except ValueError:
        GLOBAL_METRICS.increment_counter(
            CONST_SERVICE_METRIC_CHAT_COMMANDS, labels={"command": "/roadmap", "result": "usage"}
        )
        return {
            "response_type": "ephemeral",
            "text": MESSAGES.serve.chat_roadmap_usage,
        }

    try:
        if not args or args == ["status"]:
            statuses = service_manager.lane_statuses()
            lines = [_format_lane_status(s) for s in statuses]
            GLOBAL_METRICS.increment_counter(
                CONST_SERVICE_METRIC_CHAT_COMMANDS,
                labels={"command": "/roadmap", "result": "status"},
            )
            return {"response_type": "ephemeral", "text": "\n".join(lines)}

        if len(args) == 2 and args[0] == "status":
            target_repo = args[1]
            if target_repo not in service_manager.managed_repos:
                known = ", ".join(service_manager.config.repos)
                GLOBAL_METRICS.increment_counter(
                    CONST_SERVICE_METRIC_CHAT_COMMANDS,
                    labels={"command": "/roadmap", "result": "unknown_repo"},
                )
                return {
                    "response_type": "ephemeral",
                    "text": MESSAGES.serve.chat_roadmap_unknown_repo.format(
                        repo=target_repo, repos=known
                    ),
                }

            statuses = service_manager.lane_statuses(target_repo)
            lines = [_format_lane_status(s) for s in statuses]
            GLOBAL_METRICS.increment_counter(
                CONST_SERVICE_METRIC_CHAT_COMMANDS,
                labels={"command": "/roadmap", "result": "status"},
            )
            return {"response_type": "ephemeral", "text": "\n".join(lines)}

        GLOBAL_METRICS.increment_counter(
            CONST_SERVICE_METRIC_CHAT_COMMANDS, labels={"command": "/roadmap", "result": "usage"}
        )
        return {
            "response_type": "ephemeral",
            "text": MESSAGES.serve.chat_roadmap_usage,
        }
    except Exception as exc:
        logger.error("Error executing /roadmap chat command: %s", exc, exc_info=True)
        GLOBAL_METRICS.increment_counter(
            CONST_SERVICE_METRIC_CHAT_COMMANDS, labels={"command": "/roadmap", "result": "error"}
        )
        return {
            "response_type": "ephemeral",
            "text": f"Error executing roadmap command: {exc}",
        }


WEBHOOK_PROVIDERS: Final[Mapping[WebhookProviderName, WebhookProvider]] = {
    WebhookProviderName.GITHUB: WebhookProvider(
        name=WebhookProviderName.GITHUB,
        exposure=WebhookExposure.TUNNEL,
        verifier=HmacSha256(
            header=CONST_GH_WEBHOOK_SIGNATURE_HEADER, prefix=CONST_GH_WEBHOOK_SIGNATURE_PREFIX
        ),
        event_header=CONST_GH_WEBHOOK_EVENT_HEADER,
        delivery_header=CONST_GH_WEBHOOK_DELIVERY_HEADER,
        ping_event=CONST_SERVICE_PING_EVENT,
        payload_model=GitHubWebhookPayload,
    ),
    WebhookProviderName.MATTERMOST: WebhookProvider(
        name=WebhookProviderName.MATTERMOST,
        exposure=WebhookExposure.CLUSTER,
        verifier=AuthorizationToken(scheme="Token"),
        content_type="application/x-www-form-urlencoded",
        responder=mattermost_roadmap_responder,
    ),
}


def roadmap_consumer(service_manager: ServiceManager) -> WebhookConsumer:
    """The roadmap jobs' consumer: each event their batch keys name runs a round in every lane of
    its repository, except the writes of the GitHub App's own bot. A subscribed event that can be
    scoped runs its scoped update on the lane that the table names; another event stays a hint
    (ADR 0017)."""

    def deliver(
        repo: str,
        event: str,
        action: str,
        payload: GitHubWebhookPayload | None = None,
    ) -> None:
        GLOBAL_METRICS.increment_counter(
            CONST_SERVICE_METRIC_TRIGGERS,
            labels={"repo": repo, "source": CONST_SERVICE_SOURCE_WEBHOOK},
        )
        from devops_cli.roadmap.run import SCOPED_UPDATES, WebhookDelivery, run_scoped_update
        from devops_cli.roadmap.store import get_roadmap_store

        scoped = SCOPED_UPDATES.get((event, action))
        if (
            scoped is not None
            and payload is not None
            and payload.issue is not None
            and payload.issue.number is not None
        ):
            delivery = WebhookDelivery(
                repo=repo,
                event=event,
                action=action,
                number=payload.issue.number,
            )

            def run_scoped() -> None:
                store = get_roadmap_store(repo)
                data_dir = service_manager.state_dir.parent if service_manager.state_dir else None
                run_scoped_update(delivery, store, data_dir=data_dir)

            if service_manager.enqueue_scoped(repo, scoped.lane, run_scoped):
                return

        service_manager.enqueue_trigger(repo, CONST_SERVICE_SOURCE_WEBHOOK, event, action)

    def refuse_own_write(payload: GitHubWebhookPayload) -> str | None:
        bot, sender = service_manager.bot_login, payload.sender
        own_write = bot and sender and sender.login.lower() == bot.lower()
        return CONST_SERVICE_STATUS_OWN_WRITE if own_write else None

    return WebhookConsumer(
        name="roadmap",
        provider=WebhookProviderName.GITHUB,
        events=CONST_ROADMAP_WEBHOOK_EVENTS,
        deliver=deliver,
        refusal=refuse_own_write,
    )


class DeliveryLRUCache:
    """Thread-safe LRU cache for tracking recent delivery IDs to eliminate duplicate replays."""

    def __init__(self, capacity: int = CONST_SERVICE_DELIVERY_LRU_CAPACITY) -> None:
        self._seen: LRUCache[str, bool] = LRUCache(maxsize=capacity)
        self._lock = threading.Lock()

    def check_and_add(self, delivery_id: str) -> bool:
        """Return True if delivery_id is already seen (duplicate), False otherwise. A seen id
        becomes the most recent; at capacity, a new id drops the least recently used one."""
        with self._lock:
            if self._seen.get(delivery_id, False):
                return True
            self._seen[delivery_id] = True
            return False


@dataclass(frozen=True)
class _Reply:
    """What a delivery is answered with, and the outcome it counts as."""

    status: int
    body: dict[str, str]
    outcome: str


def _rejected(status: int, error: str) -> _Reply:
    return _Reply(status, {"error": error}, CONST_SERVICE_OUTCOME_REJECTED)


def _acknowledged(status: str, outcome: str) -> _Reply:
    return _Reply(200, {"status": status}, outcome)


@dataclass
class _Delivery:
    """What one request is known by, filled in as it is read, and written to its record and its
    count. The event and delivery id are the sender's text until the signature checks out."""

    provider: WebhookProviderName
    event: str
    delivery: str
    declared_events: frozenset[str]
    repo: str | None = None
    action: str | None = None

    def conclude(self, outcome: str) -> None:
        """Count the delivery and write its one record. An event no consumer subscribes to counts
        as "other", and the sender's text is cut to the bound on error details."""
        event = self.event if self.event in self.declared_events else CONST_SERVICE_EVENT_OTHER
        GLOBAL_METRICS.increment_counter(
            CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES,
            labels={"provider": str(self.provider), "event": event, "outcome": outcome},
        )
        logger.info(
            MESSAGES.serve.webhook_delivery,
            extra={
                "provider": str(self.provider),
                "event": self.event[:CONST_MAX_ERROR_DETAIL_LENGTH],
                "action": self.action,
                "delivery": self.delivery[:CONST_MAX_ERROR_DETAIL_LENGTH],
                "repo": self.repo,
                "outcome": outcome,
            },
        )


def _declares_more_than_the_cap(declared: str) -> bool:
    """Whether a Content-Length value is a number above the size cap. Python converts no more
    than 4300 digits to an integer, so a number with more significant digits than the cap has is
    above it without being converted. Leading zeros are not significant."""
    if not (declared.isascii() and declared.isdecimal()):
        return False
    significant = declared.lstrip("0")
    return len(significant) > len(str(CONST_SERVICE_MAX_BODY_BYTES)) or (
        int(significant or "0") > CONST_SERVICE_MAX_BODY_BYTES
    )


async def _read_capped_body(request: Request) -> bytes | None:
    """Read the request body, or None once the bytes it streams pass the size cap."""
    body_chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in request.stream():
        total_bytes += len(chunk)
        if total_bytes > CONST_SERVICE_MAX_BODY_BYTES:
            return None
        body_chunks.append(chunk)
    return b"".join(body_chunks)


def _refuse_content_type(request: Request, provider: WebhookProvider) -> _Reply | None:
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith(provider.content_type):
        return _rejected(415, "unsupported media type")
    return None


def _refuse_verifier(
    request: Request,
    provider: WebhookProvider,
    service_manager: ServiceManager,
    delivery: _Delivery,
) -> _Reply | None:
    if isinstance(provider.verifier, HmacSha256):
        if not delivery.event or not delivery.delivery:
            return _rejected(400, "missing event or delivery header")
        if not request.headers.get(provider.verifier.header):
            return _rejected(401, "missing signature")
    elif isinstance(provider.verifier, AuthorizationToken):
        auth_header = request.headers.get("authorization")
        if not auth_header:
            return _rejected(401, "missing authorization header")
        scheme, token = get_authorization_scheme_param(auth_header)
        if scheme.lower() != provider.verifier.scheme.lower() or not token:
            logger.warning(
                "Refused %s webhook delivery: invalid authorization header scheme or missing token.",
                provider.name,
            )
            return _rejected(401, "invalid authorization")
        expected_token = service_manager.command_token
        if not expected_token:
            logger.warning(
                "Refused %s webhook delivery: setting mattermost.command_token is not configured.",
                provider.name,
            )
            return _rejected(401, "unauthorized")
        if not secrets.compare_digest(token, expected_token):
            logger.warning(
                "Refused %s webhook delivery: invalid authorization token.", provider.name
            )
            return _rejected(401, "invalid token")
    return None


def _refuse_before_reading(
    request: Request,
    provider: WebhookProvider,
    service_manager: ServiceManager,
    delivery: _Delivery,
) -> _Reply | None:
    """Refuse a delivery while draining, one that has an unsupported content type, one without
    its event name or signature, or one that declares a length above the size cap, before its body
    is read. An unsigned or oversized flood thus costs no read and no digest."""
    if service_manager.is_draining():
        return _rejected(503, "service is draining")
    if ct_reply := _refuse_content_type(request, provider):
        return ct_reply
    if verifier_reply := _refuse_verifier(request, provider, service_manager, delivery):
        return verifier_reply
    if _declares_more_than_the_cap(request.headers.get("content-length", "")):
        return _rejected(413, "payload too large")
    return None


def invalid_payload_detail(failure: ValidationError) -> str:
    """The paths and reasons of a payload's failed fields, within the bound on error details. It
    names no value from the body."""
    details = "; ".join(
        f"{'.'.join(map(str, error['loc'])) or 'body'}: {error['msg']}"
        for error in failure.errors(include_url=False, include_context=False, include_input=False)
    )
    return f"invalid payload: {details}"[:CONST_MAX_ERROR_DETAIL_LENGTH]


def _authenticated_payload(
    request: Request, provider: WebhookProvider, service_manager: ServiceManager, body: bytes
) -> GitHubWebhookPayload | _Reply:
    """The body's typed payload once its signature matches the secret of the repository it names,
    or the 401 or 400 that refuses it. It validates only a body that was signed, so a sender
    without a secret learns nothing of the schema."""
    verifier = cast(HmacSha256, provider.verifier)
    payload_model = cast(type[GitHubWebhookPayload], provider.payload_model)
    signature = request.headers.get(verifier.header)
    signers = verifier.signers(body, signature, service_manager.secrets)
    if not signers:
        return _rejected(401, "invalid signature")
    try:
        payload = payload_model.model_validate_json(body)
    except ValidationError as failure:
        return _rejected(400, invalid_payload_detail(failure))
    repo = payload.repository.full_name
    if repo not in service_manager.managed_repos or repo not in signers:
        return _rejected(401, "unmanaged repository or signature mismatch")
    return payload


def _hand_to_consumers(
    delivery: _Delivery, payload: GitHubWebhookPayload, subscribed: Sequence[WebhookConsumer]
) -> _Reply:
    """Deliver the event to each subscribed consumer that takes this payload. When none does,
    the answer is the first refusal's status, and the outcome is `self` for the App bot's own
    write, else `ignored`."""
    verdicts = [(consumer, consumer.refusal(payload)) for consumer in subscribed]
    takers = [consumer for consumer, refusal in verdicts if refusal is None]
    refusals = [refusal for _consumer, refusal in verdicts if refusal is not None]
    for consumer in takers:
        sig = inspect.signature(consumer.deliver)
        if len(sig.parameters) >= 4 or any(
            p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            for p in sig.parameters.values()
        ):
            consumer.deliver(
                payload.repository.full_name, delivery.event, payload.action or "", payload
            )
        else:
            consumer.deliver(payload.repository.full_name, delivery.event, payload.action or "")
    if takers:
        return _Reply(202, {"status": "accepted"}, CONST_SERVICE_OUTCOME_ACCEPTED)
    first = refusals[0]
    return _acknowledged(first, _REFUSAL_OUTCOMES.get(first, CONST_SERVICE_OUTCOME_IGNORED))


def _route(
    delivery: _Delivery,
    provider: WebhookProvider,
    payload: GitHubWebhookPayload,
    service_manager: ServiceManager,
    consumers: Sequence[WebhookConsumer],
) -> _Reply:
    """Answer a ping, acknowledge an event nothing subscribes to, drop a repeated delivery id,
    and deliver any other event to its subscribers."""
    if delivery.event == provider.ping_event:
        return _acknowledged("pong", CONST_SERVICE_OUTCOME_IGNORED)
    subscribed = [consumer for consumer in consumers if delivery.event in consumer.events]
    if not subscribed:
        return _acknowledged("no_subscriber", CONST_SERVICE_OUTCOME_NO_SUBSCRIBER)
    if service_manager.delivery_cache.check_and_add(delivery.delivery):
        return _acknowledged("duplicate", CONST_SERVICE_OUTCOME_IGNORED)
    return _hand_to_consumers(delivery, payload, subscribed)


async def _read_and_route(
    request: Request,
    provider: WebhookProvider,
    service_manager: ServiceManager,
    consumers: Sequence[WebhookConsumer],
    delivery: _Delivery,
) -> _Reply:
    """Read the body, authenticate and validate it, and route the event."""
    body = await _read_capped_body(request)
    if body is None:
        return _rejected(413, "payload too large")
    payload = _authenticated_payload(request, provider, service_manager, body)
    if isinstance(payload, _Reply):
        return payload
    delivery.repo, delivery.action = payload.repository.full_name, payload.action
    return _route(delivery, provider, payload, service_manager, consumers)


def _receiver(
    provider: WebhookProvider,
    service_manager: ServiceManager,
    consumers: Sequence[WebhookConsumer],
) -> Callable[[Request], Awaitable[Response]]:
    """The route handler of one provider, over the consumers that take its events."""
    taking = [consumer for consumer in consumers if consumer.provider is provider.name]
    ping_events = {provider.ping_event} if provider.ping_event is not None else set()
    declared_events = frozenset(ping_events).union(*(c.events for c in taking))

    async def receive(request: Request) -> Response:
        event = request.headers.get(provider.event_header, "") if provider.event_header else ""
        delivery_id = (
            request.headers.get(provider.delivery_header, "") if provider.delivery_header else ""
        )
        delivery = _Delivery(
            provider=provider.name,
            event=event,
            delivery=delivery_id,
            declared_events=declared_events,
        )
        reply = _refuse_before_reading(request, provider, service_manager, delivery)
        if reply is not None:
            delivery.conclude(reply.outcome)
            return JSONResponse(status_code=reply.status, content=reply.body)

        if provider.responder is not None:
            body = await _read_capped_body(request)
            if body is None:
                reply = _rejected(413, "payload too large")
                delivery.conclude(reply.outcome)
                return JSONResponse(status_code=reply.status, content=reply.body)
            result = await provider.responder(request, service_manager, body)
            delivery.conclude(CONST_SERVICE_OUTCOME_ACCEPTED)
            return JSONResponse(status_code=200, content=result)

        reply = await _read_and_route(request, provider, service_manager, taking, delivery)
        delivery.conclude(reply.outcome)
        return JSONResponse(status_code=reply.status, content=reply.body)

    return receive


def create_webhook_router(
    service_manager: ServiceManager, consumers: Sequence[WebhookConsumer] | None = None
) -> APIRouter:
    """Construct the APIRouter with a POST route for each declared provider, delivering to
    `consumers`, or to the roadmap consumer when none are given."""
    active = (roadmap_consumer(service_manager),) if consumers is None else tuple(consumers)
    router = APIRouter(tags=["webhooks"])
    for provider in WEBHOOK_PROVIDERS.values():
        router.add_api_route(
            provider.path,
            _receiver(provider, service_manager, active),
            methods=["POST"],
            name=f"receive_{provider.name}_webhook",
        )
    return router
