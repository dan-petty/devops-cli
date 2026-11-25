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
    CONST_ISSUE_STATE_CLOSED,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_ROADMAP_PRIORITY_LABEL_PREFIX,
    CONST_ROADMAP_TRUSTED_AUTHORS,
    CONST_ROADMAP_WEBHOOK_EVENTS,
    CONST_SERVICE_CHAT_COMMAND_ROADMAP,
    CONST_SERVICE_CHAT_RESULT_ERROR,
    CONST_SERVICE_CHAT_RESULT_STATUS,
    CONST_SERVICE_CHAT_RESULT_UNKNOWN_REPO,
    CONST_SERVICE_CHAT_RESULT_USAGE,
    CONST_SERVICE_DELIVERY_LRU_CAPACITY,
    CONST_SERVICE_EVENT_OTHER,
    CONST_SERVICE_MAX_BODY_BYTES,
    CONST_SERVICE_METRIC_CHAT_COMMANDS,
    CONST_SERVICE_METRIC_ROADMAP_ITEMS_CLOSED,
    CONST_SERVICE_METRIC_TRIGGERS,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES,
    CONST_SERVICE_OUTCOME_ACCEPTED,
    CONST_SERVICE_OUTCOME_IGNORED,
    CONST_SERVICE_OUTCOME_NO_SUBSCRIBER,
    CONST_SERVICE_OUTCOME_REJECTED,
    CONST_SERVICE_OUTCOME_SELF,
    CONST_SERVICE_PING_EVENT,
    CONST_SERVICE_ROADMAP_CLOSE_REASON_UNKNOWN,
    CONST_SERVICE_ROADMAP_CLOSE_REASONS,
    CONST_SERVICE_SOURCE_WEBHOOK,
    CONST_SERVICE_STATUS_COMMENT_REFUSED,
    CONST_SERVICE_STATUS_OWN_WRITE,
    CONST_SERVICE_STATUS_RELEASE_REFUSED,
    CONST_SERVICE_STATUS_UNTRUSTED_COMMENT,
    WebhookExposure,
    WebhookProviderName,
)
from devops_cli.config.settings import load_settings
from devops_cli.github.repo_ref import RepoRef
from devops_cli.lang import MESSAGES
from devops_cli.models.webhooks import GitHubWebhookPayload, WebhookComment
from devops_cli.telemetry.metrics import GLOBAL_METRICS

if TYPE_CHECKING:
    from devops_cli.server.service import ServiceManager

logger = logging.getLogger(__name__)

_COMMENT_CREATED_ACTION: Final[str] = "created"
"""The one action of a comment delivery that the roadmap consumer takes (#4415)."""

_BOT_SUFFIX: Final[str] = "[bot]"
"""How GitHub ends the login of every bot account, the App's own bot included (#4415)."""

_RELEASE_PUBLISHED_ACTION: Final[str] = "published"
"""The one action of a release delivery that the roadmap consumer takes (#4416)."""

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


def _refuses_comment(payload: GitHubWebhookPayload) -> bool:
    """Whether a comment delivery is one that the roadmap consumer never takes: a comment whose
    action is not `created`, a comment on a pull request, or a comment of a bot. GitHub reports a
    comment on a pull request as an `issue_comment` event whose issue carries the marker, so the
    marker alone tells the two apart, with no request (#4415)."""
    sender = payload.sender
    bot = sender is not None and sender.login.endswith(_BOT_SUFFIX)
    on_pull_request = payload.issue is not None and payload.issue.pull_request is not None
    return payload.action != _COMMENT_CREATED_ACTION or on_pull_request or bot


def _comment_refusal(payload: GitHubWebhookPayload, comment: WebhookComment | None) -> str | None:
    """The status of the comment that a delivery carries, or None when the delivery carries none
    or the comment is one the roadmap consumer takes. A comment whose author has no write access
    is refused under its own status, as the repository is public (#4415)."""
    if comment is None:
        return None
    if _refuses_comment(payload):
        return CONST_SERVICE_STATUS_COMMENT_REFUSED
    if comment.author_association not in CONST_ROADMAP_TRUSTED_AUTHORS:
        return CONST_SERVICE_STATUS_UNTRUSTED_COMMENT
    return None


def _release_refusal(payload: GitHubWebhookPayload) -> str | None:
    """The status of a release delivery that the roadmap consumer ignores, before any GitHub
    request: an action that is not `published`, a draft, a prerelease, or a release that holds no
    publication time. A delivery that carries no release object is not refused (#4416)."""
    release = payload.release
    if release is None:
        return None
    unwanted = (
        payload.action != _RELEASE_PUBLISHED_ACTION
        or release.draft
        or release.prerelease
        or release.published_at is None
    )
    return CONST_SERVICE_STATUS_RELEASE_REFUSED if unwanted else None


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


def _count_chat_command(result: str) -> None:
    """Count one `/roadmap` chat command under its `result` (#1395, #3495)."""
    GLOBAL_METRICS.increment_counter(
        CONST_SERVICE_METRIC_CHAT_COMMANDS,
        labels={"command": CONST_SERVICE_CHAT_COMMAND_ROADMAP, "result": result},
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
        _count_chat_command(CONST_SERVICE_CHAT_RESULT_USAGE)
        return {
            "response_type": "ephemeral",
            "text": MESSAGES.serve.chat_roadmap_usage,
        }

    try:
        if not args or args == ["status"]:
            statuses = service_manager.lane_statuses()
            lines = [_format_lane_status(s) for s in statuses]
            _count_chat_command(CONST_SERVICE_CHAT_RESULT_STATUS)
            return {"response_type": "ephemeral", "text": "\n".join(lines)}

        if len(args) == 2 and args[0] == "status":
            target_repo = args[1]
            if target_repo not in service_manager.managed_repos:
                known = ", ".join(service_manager.config.repos)
                _count_chat_command(CONST_SERVICE_CHAT_RESULT_UNKNOWN_REPO)
                return {
                    "response_type": "ephemeral",
                    "text": MESSAGES.serve.chat_roadmap_unknown_repo.format(
                        repo=target_repo, repos=known
                    ),
                }

            statuses = service_manager.lane_statuses(target_repo)
            lines = [_format_lane_status(s) for s in statuses]
            _count_chat_command(CONST_SERVICE_CHAT_RESULT_STATUS)
            return {"response_type": "ephemeral", "text": "\n".join(lines)}

        _count_chat_command(CONST_SERVICE_CHAT_RESULT_USAGE)
        return {
            "response_type": "ephemeral",
            "text": MESSAGES.serve.chat_roadmap_usage,
        }
    except Exception as exc:
        logger.error("Error executing /roadmap chat command: %s", exc, exc_info=True)
        _count_chat_command(CONST_SERVICE_CHAT_RESULT_ERROR)
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


def _handle_infra_plan_event(
    repo: str,
    event: str,
    action: str,
    payload: GitHubWebhookPayload | None,
    service_manager: ServiceManager,
) -> bool:
    """Launch an infra-plan Job on pull_request synchronize deliveries (#5129). Return True if event is consumed."""
    if event != "pull_request" or action != "synchronize":
        return False

    active_settings = load_settings()
    infra_repos = {r.repo for r in active_settings.infra.repos}
    if repo not in infra_repos:
        return False
    pr = payload.pull_request if payload is not None else None
    if pr is not None and pr.number is not None and pr.state == "open" and pr.head and pr.head.sha:
        launch_infra_plan(repo, pr.number, pr.head.sha)
    repos = getattr(service_manager.config, "repos", ())
    return repo not in repos


def _handle_infra_apply_event(
    repo: str,
    event: str,
    action: str,
    payload: GitHubWebhookPayload | None,
    service_manager: ServiceManager,
) -> bool:
    """Launch an infra apply job when a pull request of an infra repo merges (#5130). Return True if event is consumed."""
    if event != "pull_request" or action != "closed" or payload is None:
        return False
    pr = payload.pull_request
    if pr is None or not pr.merged or not pr.number:
        return False
    commit = pr.merge_commit_sha or (pr.head.sha if pr.head else None)
    if not commit:
        return False

    settings = load_settings()
    ref = RepoRef(repo)
    if not settings.infra.entry(ref):
        return False
    from devops_cli.roadmap.steps.infra_apply import launch_infra_apply

    launch_infra_apply(repo, pr.number, commit, settings=settings)
    repos = getattr(service_manager.config, "repos", ())
    return repo not in repos


def _build_delivery_and_subject(
    repo: str,
    event: str,
    action: str,
    payload: GitHubWebhookPayload | None,
) -> tuple[Any, int | None]:
    """Build the typed WebhookDelivery and determine the subject issue/PR number."""
    from devops_cli.roadmap.run import WebhookDelivery

    numbers = payload.delivery_numbers if payload is not None else ()
    issue = payload.issue.number if payload is not None and payload.issue else None
    comment = payload.comment if payload is not None else None
    release = payload.release if payload is not None else None
    subject = issue if issue is not None else next(iter(numbers), None)
    delivery = WebhookDelivery(
        repo=repo,
        event=event,
        action=action,
        number=issue,
        pull_numbers=numbers,
        comment=None if comment is None else comment.body,
        comment_at=None if comment is None else comment.created_at,
        release=release,
    )
    return delivery, subject


def _handle_and_filter_infra(
    repo: str,
    event: str,
    action: str,
    payload: GitHubWebhookPayload | None,
    service_manager: ServiceManager,
) -> bool:
    """Launch infra plan or apply jobs if applicable; return True to skip roadmap delivery."""
    if _handle_infra_plan_event(repo, event, action, payload, service_manager):
        return True
    if _handle_infra_apply_event(repo, event, action, payload, service_manager):
        return True
    return False


def _remember_delivery_issue(repo: str, payload: GitHubWebhookPayload | None) -> None:
    """Remember the delivery issue if present."""
    if payload is not None and payload.issue and payload.issue.number is not None:
        from devops_cli.roadmap.stores.brain_issues import issue_from_event, remember_issue

        remember_issue(repo, issue_from_event(repo, payload.issue))


def _remember_own_delivery_issue(repo: str, payload: GitHubWebhookPayload) -> None:
    """Refresh the cached issue from an App bot `issues` webhook only when its `updated_at` time
    is strictly newer than the stored entry, so stale or same-second hooks cannot replace newer
    writes (#7063)."""
    issue = payload.issue
    if (
        payload.comment is not None
        or issue is None
        or issue.number is None
        or issue.pull_request is not None
    ):
        return
    from devops_cli.roadmap.stores.brain_issues import (
        cached_issue,
        issue_from_event,
        remember_issue,
    )

    existing = cached_issue(repo, issue.number)
    if existing is not None and existing.record.updated_at is not None:
        if issue.updated_at is None or issue.updated_at <= existing.record.updated_at:
            return
    remember_issue(repo, issue_from_event(repo, issue))


def _own_write_refusal(bot: str | None, payload: GitHubWebhookPayload) -> str | None:
    """Refuse webhooks authored by the Service bot after refreshing newer `issues` payloads."""
    sender = payload.sender
    if not (bot and sender and sender.login.lower() == bot.lower()):
        return None
    _remember_own_delivery_issue(payload.repository.full_name, payload)
    return CONST_SERVICE_STATUS_OWN_WRITE


def roadmap_consumer(service_manager: ServiceManager) -> WebhookConsumer:
    """The roadmap jobs' consumer: each event their batch keys name runs a round in every lane of
    its repository, except the writes of the GitHub App's own bot. A subscribed event that can be
    scoped runs its scoped update on the lane of its job (`lane_of_row`), over the issue and the
    pull requests that the delivery names; another event, and a delivery that names no number,
    stays a hint (ADR 0017). Each trigger names the issue of the delivery, or its first pull
    request, as its subject (#5553, #4413). A comment delivery is taken only when a person with
    write access created it on an issue (#4415), and it runs the row that its text wakes: the
    `implement` row for a retry command and the `refine` row for another comment. A release
    delivery is taken only when it is a published release that carries its publication time
    (#4416). The handler only adds to the queues of the lanes and returns."""

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
        if _handle_and_filter_infra(repo, event, action, payload, service_manager):
            return
        from devops_cli.roadmap.run import (
            lane_of_row,
            lanes_to_wake,
            run_scoped_update,
            scoped_update_of,
            scoped_update_wakes_lanes,
        )
        from devops_cli.roadmap.stores.listing_snapshot import intake_listing
        from devops_cli.roadmap.stores.store import get_roadmap_store

        _remember_delivery_issue(repo, payload)
        delivery, subject = _build_delivery_and_subject(repo, event, action, payload)
        scoped = scoped_update_of(delivery)
        # A delivery that names no issue number and no pull request number stays a whole-round
        # hint, unless it carries a release, which its scoped update reads (#4416).
        if scoped is not None and (subject is not None or delivery.release is not None):
            lane = lane_of_row(scoped.job, service_manager.config.lanes)

            def run_scoped() -> None:
                # The scoped intake reads every issue through the snapshot that the intake
                # rounds of the same lane keep in the state directory (#3670).
                state_dir = service_manager.state_dir
                store = get_roadmap_store(repo, listing=intake_listing(state_dir))
                data_dir = state_dir.parent if state_dir else None
                outcome = run_scoped_update(delivery, store, data_dir=data_dir, lane=lane)
                if scoped_update_wakes_lanes(delivery, outcome):
                    groups = service_manager.config.lanes
                    for woken in lanes_to_wake(scoped.job, service_manager.jobs, groups):
                        service_manager.enqueue_trigger(
                            repo,
                            CONST_SERVICE_SOURCE_WEBHOOK,
                            event,
                            action,
                            lane=woken,
                            subject=subject,
                        )

            if service_manager.enqueue_scoped(repo, lane, run_scoped):
                return

        service_manager.enqueue_trigger(
            repo, CONST_SERVICE_SOURCE_WEBHOOK, event, action, subject=subject
        )

    def refuse_comment(payload: GitHubWebhookPayload) -> str | None:
        """The status of a delivery that the roadmap consumer ignores, before any GitHub request:
        the App bot's own write, else the refusal of the comment that the payload carries (#4415),
        else the refusal of the release that it carries (#4416)."""
        return (
            _own_write_refusal(service_manager.bot_login, payload)
            or _comment_refusal(payload, payload.comment)
            or _release_refusal(payload)
        )

    return WebhookConsumer(
        name="roadmap",
        provider=WebhookProviderName.GITHUB,
        events=CONST_ROADMAP_WEBHOOK_EVENTS,
        deliver=deliver,
        refusal=refuse_comment,
    )


def service_consumers(service_manager: ServiceManager) -> tuple[WebhookConsumer, ...]:
    """The consumers of the Service. Each event that a GitHub consumer takes must be an event
    that the repository hook sends: `devops repos onboard` requires the events of
    `CONST_ROADMAP_WEBHOOK_EVENTS` of the hook, and a test holds these consumers to them
    (#5035)."""
    return (roadmap_consumer(service_manager),)


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


def _count_closed_roadmap_item(payload: GitHubWebhookPayload) -> None:
    """Count a closed roadmap item by repository and reason (#4580). An issue that holds no
    `priority/` label is no roadmap item, so it counts nothing. The reason is GitHub's
    `state_reason` when it is a known value, and `unknown` otherwise. The count sits after the
    duplicate check, so a repeated delivery adds nothing, and it counts the closes that the
    roadmap jobs make as the App bot."""
    issue = payload.issue
    if payload.action != CONST_ISSUE_STATE_CLOSED or issue is None:
        return
    if not any(
        label.name.startswith(CONST_ROADMAP_PRIORITY_LABEL_PREFIX) for label in issue.labels
    ):
        return
    reason = (
        issue.state_reason
        if issue.state_reason in CONST_SERVICE_ROADMAP_CLOSE_REASONS
        else CONST_SERVICE_ROADMAP_CLOSE_REASON_UNKNOWN
    )
    GLOBAL_METRICS.increment_counter(
        CONST_SERVICE_METRIC_ROADMAP_ITEMS_CLOSED,
        labels={"repo": payload.repository.full_name, "reason": reason},
    )


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
    if delivery.event in CONST_ROADMAP_WEBHOOK_EVENTS:
        _count_closed_roadmap_item(payload)
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


def _declared_events(
    provider: WebhookProvider, consumers: Sequence[WebhookConsumer]
) -> frozenset[str]:
    """The events that `provider` declares: its ping event and the events of the consumers that
    take its events."""
    taking = [consumer for consumer in consumers if consumer.provider is provider.name]
    ping_events = {provider.ping_event} if provider.ping_event is not None else set()
    return frozenset(ping_events).union(*(c.events for c in taking))


_DELIVERY_OUTCOMES: Final[tuple[str, ...]] = (
    CONST_SERVICE_OUTCOME_ACCEPTED,
    CONST_SERVICE_OUTCOME_IGNORED,
    CONST_SERVICE_OUTCOME_REJECTED,
    CONST_SERVICE_OUTCOME_NO_SUBSCRIBER,
    CONST_SERVICE_OUTCOME_SELF,
)
"""The outcomes that a delivery of a provider counts, each under its declared event (#3495)."""


def _delivery_label_sets(
    provider: WebhookProvider, consumers: Sequence[WebhookConsumer]
) -> list[dict[str, str]]:
    """Each label set that a delivery of `provider` counts: each declared event and `other`, with
    each outcome. The Service creates each of them at zero when its routes are built (#3495)."""
    events = _declared_events(provider, consumers) | {CONST_SERVICE_EVENT_OTHER}
    return [
        {"provider": str(provider.name), "event": event, "outcome": outcome}
        for event in sorted(events)
        for outcome in _DELIVERY_OUTCOMES
    ]


def _receiver(
    provider: WebhookProvider,
    service_manager: ServiceManager,
    consumers: Sequence[WebhookConsumer],
) -> Callable[[Request], Awaitable[Response]]:
    """The route handler of one provider, over the consumers that take its events."""
    taking = [consumer for consumer in consumers if consumer.provider is provider.name]
    declared_events = _declared_events(provider, consumers)

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


def _closed_label_sets(service_manager: ServiceManager) -> list[dict[str, str]]:
    """Each label set that `CONST_SERVICE_METRIC_ROADMAP_ITEMS_CLOSED` counts: each managed
    repository and each reason. The Service creates each of them at zero when its routes are built
    (#4580)."""
    return [
        {"repo": repo, "reason": reason}
        for repo in sorted(service_manager.managed_repos)
        for reason in CONST_SERVICE_ROADMAP_CLOSE_REASONS
    ]


def create_webhook_router(
    service_manager: ServiceManager, consumers: Sequence[WebhookConsumer] | None = None
) -> APIRouter:
    """Construct the APIRouter with a POST route for each declared provider, delivering to
    `consumers`, or to the consumers of the Service when none are given."""
    active = service_consumers(service_manager) if consumers is None else tuple(consumers)
    router = APIRouter(tags=["webhooks"])
    GLOBAL_METRICS.prime_counter(
        CONST_SERVICE_METRIC_ROADMAP_ITEMS_CLOSED, _closed_label_sets(service_manager)
    )
    for provider in WEBHOOK_PROVIDERS.values():
        GLOBAL_METRICS.prime_counter(
            CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES, _delivery_label_sets(provider, active)
        )
        router.add_api_route(
            provider.path,
            _receiver(provider, service_manager, active),
            methods=["POST"],
            name=f"receive_{provider.name}_webhook",
        )
    return router


def launch_infra_plan(
    repo: str,
    pull: int,
    head: str,
    *,
    jobs: Any = None,
    playbook: str = "site.yaml",
) -> str:
    """Launch an infra-plan Job for `repo`, `pull` and `head`. Return the Job unit name."""
    from devops_cli.exceptions.k8s import ClusterJobExistsError
    from devops_cli.k8s.cluster_job_api import ClusterJobs
    from devops_cli.roadmap.job_launcher import launch
    from devops_cli.roadmap.steps.infra_plan import infra_plan_unit

    unit = infra_plan_unit(repo, pull, head, playbook=playbook)
    api = jobs or ClusterJobs()
    try:
        return launch(api, unit)
    except ClusterJobExistsError:
        return unit.name
