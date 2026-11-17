"""The loopback gateway broker of an implement step (#3820).

The shell of a step has no AI key: the job process holds it and is not dumpable, while the shell
runs as the same user and would expose a key that it reads. So the job process runs this broker on
the loopback interface for the length of one step, mints a token for that step, and forwards only
the two model endpoints of the gateway. The token dies when the step ends, and the shell gets the
address and the token and no key.

The broker forwards only the exact pairs of `ALLOWED_REQUESTS`, under the path prefix of
`ai.gateway_url`. Its upstream client is `http_client` of `devops_cli.http.entry` at the level of
`configured_level`, so the connect is vetted as the agent's is and a test records the request.
`StepBroker.record` adds the new tokens of a forwarded answer to the budget of the step and its
requests and tokens to the record of the tier that served the call, so a shell call counts as a
model call of the agent.
"""

from __future__ import annotations

import ipaddress
import json
import secrets
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import httpx2

from devops_cli.config.constants import CONST_AI_GATEWAY_PROVIDER
from devops_cli.config.settings import get_ai_api_key, load_settings
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.http.egress import configured_level
from devops_cli.http.entry import http_client, request_headers
from devops_cli.roadmap.implement.implement_limits import StepBudget, new_tokens

if TYPE_CHECKING:
    from collections.abc import Callable

    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import Response

# The exact method and path pairs that the broker forwards, under the prefix of `ai.gateway_url`:
# the endpoints of the model of the agent and of the query embedding of `devops ai rag-query`.
ALLOWED_REQUESTS: tuple[tuple[str, str], ...] = (
    ("POST", "/chat/completions"),
    ("POST", "/embeddings"),
)

_DEFAULT_HOST = "127.0.0.1"
_BACKLOG = 128
_TOKEN_BYTES = 32
_START_TIMEOUT_SECONDS = 30.0
_START_POLL_SECONDS = 0.01
_STOP_TIMEOUT_SECONDS = 30.0
_NON_LOOPBACK = (
    "The step broker refuses host {host!r}: it binds only a loopback address, such as 127.0.0.1."
)
_NO_GATEWAY_URL = (
    "The step broker needs ai.gateway_url: the gateway serves the two model endpoints of the step "
    "shell."
)
_NOT_STARTED = (
    "The step broker did not start within {seconds} s: uvicorn ended before it served the loopback "
    "port."
)
_REFUSED_TOKEN = "The step broker refuses this request: it holds no valid token of the step."
_REFUSED = 401

_LIVE: StepBroker | None = None
_LIVE_LOCK = threading.Lock()


@dataclass(frozen=True)
class BrokerSpend:
    """What the shell calls of a step spent under one tier: the requests, the input tokens (the
    cache-read part included), the cache-read tokens and the output tokens."""

    requests: int = 0
    input_tokens: int = 0
    cache_read_tokens: int = 0
    output_tokens: int = 0

    def plus(self, other: BrokerSpend) -> BrokerSpend:
        """This spend and `other`."""
        return BrokerSpend(
            requests=self.requests + other.requests,
            input_tokens=self.input_tokens + other.input_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


@dataclass(frozen=True)
class _Usage:
    """The token usage of one forwarded answer, as the gateway reports it: `input_tokens` includes
    the part that the provider read from its cache."""

    input_tokens: int = 0
    cache_read_tokens: int = 0
    output_tokens: int = 0

    @property
    def counted(self) -> int:
        """The new tokens that the budget of the step counts."""
        return new_tokens(self)


@dataclass
class StepBroker:
    """The live broker of one step: the token that the step holds, its base URL (the gateway prefix
    included, so a client appends the same path that it appends to `ai.gateway_url`), the gateway URL,
    the AI key, the upstream client, the budget of the step, the tier that the current attempt runs
    on, and the spend of each tier.

    `app` is the FastAPI app that the server runs, which a test also calls directly. `server` and
    `thread` hold the uvicorn server and its thread until `stop_step_broker` ends them."""

    key: str = field(repr=False)
    token: str = field(repr=False)
    url: str
    gateway_url: str
    client: httpx2.Client = field(repr=False)
    budget: StepBudget = field(repr=False)
    tier: str = ""
    spends: dict[str, BrokerSpend] = field(default_factory=dict, repr=False)
    server: uvicorn.Server | None = field(default=None, repr=False)
    thread: threading.Thread | None = field(default=None, repr=False)
    app: FastAPI = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.app = broker_app(self)

    def record(self, usage: _Usage) -> None:
        """Count one forwarded answer: its new tokens in the budget of the step, and the request
        and its tokens in the record of the tier that served it."""
        self.budget.add(usage.counted)
        spend = BrokerSpend(
            requests=1,
            input_tokens=usage.input_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            output_tokens=usage.output_tokens,
        )
        self.spends[self.tier] = self.spends.get(self.tier, BrokerSpend()).plus(spend)

    def spend_by_tier(self) -> dict[str, BrokerSpend]:
        """The spend of each tier, by tier name, as a copy."""
        return dict(self.spends)


def live_broker() -> StepBroker | None:
    """The broker of the step that runs now, or None."""
    with _LIVE_LOCK:
        return _LIVE


def _set_live(broker: StepBroker | None) -> None:
    """Make `broker` the live one, or clear it with None."""
    global _LIVE
    with _LIVE_LOCK:
        _LIVE = broker


def loopback_broker_url(host: str, port: int, prefix: str = "") -> str:
    """The URL of a broker on `host:port`, with the gateway path `prefix`, or
    `RoadmapImplementError` when `host` is not loopback.

    The broker holds the AI key, so only a loopback address keeps it on this pod: another address
    is reachable by every pod of the cluster.
    """
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise RoadmapImplementError(_NON_LOOPBACK.format(host=host)) from exc
    if not address.is_loopback:
        raise RoadmapImplementError(_NON_LOOPBACK.format(host=host))
    url = httpx2.URL(scheme="http", host=host, port=port)
    return str(url.copy_with(path=prefix) if prefix else url)


def _gateway_prefix(gateway_url: str) -> str:
    """The path prefix of `gateway_url`, such as `/v1`, or an empty string."""
    return urlsplit(gateway_url).path.rstrip("/")


def broker_app(broker: StepBroker) -> FastAPI:
    """The FastAPI app of `broker`: one route for each pair of `ALLOWED_REQUESTS`, under the path
    prefix of the gateway URL, behind the token of the step.

    A request to another path, a method other than POST, or a request with another token gets a
    refusal and reaches no gateway. Each route is a sync function, so FastAPI runs the blocking
    upstream call in its threadpool, off the event loop, and reads the JSON body of the step.
    """
    from fastapi import Body, FastAPI, Header, HTTPException

    app = FastAPI(title="devops-cli step broker", docs_url=None, redoc_url=None, openapi_url=None)
    prefix = _gateway_prefix(broker.gateway_url)

    def route(suffix: str) -> Callable[..., Any]:
        """The handler of the allowed pair with `suffix`."""

        def forward(
            payload: Any = Body(...),  # noqa: B008 - FastAPI's marker, not a mutable default
            authorization: str | None = Header(default=None),
        ) -> Any:
            if not _carries_token(broker, authorization):
                raise HTTPException(status_code=_REFUSED, detail=_REFUSED_TOKEN)
            return _forward(broker, suffix, _body(payload))

        return forward

    for method, suffix in ALLOWED_REQUESTS:
        app.add_api_route(
            prefix + suffix,
            route(suffix),
            methods=[method],
            name=f"broker{suffix.replace('/', '-')}",
            include_in_schema=False,
        )
    return app


def _carries_token(broker: StepBroker, authorization: str | None) -> bool:
    """Whether `authorization` carries the current token of the step."""
    scheme, _, token = (authorization or "").partition(" ")
    expected = broker.token
    if not expected or scheme.lower() != "bearer":
        return False
    return secrets.compare_digest(token.encode("utf-8"), expected.encode("utf-8"))


def _forward(broker: StepBroker, suffix: str, body: bytes) -> Response:
    """Send one allowed request to the gateway with the AI key, and return its answer."""
    from fastapi.responses import Response

    url = f"{broker.gateway_url.rstrip('/')}{suffix}"
    headers = request_headers(
        {"Content-Type": "application/json", "Authorization": f"Bearer {broker.key}"}
    )
    answer = broker.client.post(url, content=body, headers=headers)
    broker.record(_usage(answer.content))
    content_type = answer.headers.get("content-type")
    return Response(
        content=answer.content,
        status_code=answer.status_code,
        headers={"content-type": content_type} if content_type else None,
    )


def _body(payload: Any) -> bytes:
    """The bytes of a request body: the raw bytes when FastAPI gives them, else their JSON."""
    if isinstance(payload, bytes):
        return payload
    return json.dumps(payload).encode()


def _int(value: Any) -> int:
    """`value` as a count of zero or more, or 0 for a value that is no count."""
    try:
        return max(int(value), 0)
    except TypeError, ValueError:
        return 0


def _usage(body: bytes) -> _Usage:
    """The token usage of a gateway answer, or zeros for a body that holds none."""
    try:
        payload = json.loads(body)
    except ValueError:
        return _Usage()
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return _Usage()
    details = usage.get("prompt_tokens_details")
    cached = details.get("cached_tokens") if isinstance(details, dict) else None
    return _Usage(
        input_tokens=_int(usage.get("prompt_tokens") or usage.get("input_tokens")),
        cache_read_tokens=_int(cached or usage.get("cache_read_input_tokens")),
        output_tokens=_int(usage.get("completion_tokens") or usage.get("output_tokens")),
    )


def _listening_socket(host: str, port: int) -> socket.socket:
    """A listening socket on `host:port`; port 0 takes a port of the kernel's choosing."""
    family = (
        socket.AF_INET6
        if isinstance(ipaddress.ip_address(host), ipaddress.IPv6Address)
        else socket.AF_INET
    )
    sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(_BACKLOG)
    except OSError:
        sock.close()
        raise
    return sock


def _await_started(server: uvicorn.Server, thread: threading.Thread) -> None:
    """Wait until uvicorn serves the app, or raise `RoadmapImplementError` when it does not.

    The wait joins the thread for a poll interval rather than sleeping on the clock seam, so a
    test that fakes the clock does not spin here and does not move its wall clock (#3820)."""
    deadline = time.monotonic() + _START_TIMEOUT_SECONDS
    while not server.started:
        if not thread.is_alive() or time.monotonic() >= deadline:
            raise RoadmapImplementError(_NOT_STARTED.format(seconds=_START_TIMEOUT_SECONDS))
        thread.join(_START_POLL_SECONDS)


def _serve(broker: StepBroker, sock: socket.socket) -> None:
    """Run the app of `broker` in a thread on `sock` until `stop_step_broker` ends it."""
    import uvicorn

    config = uvicorn.Config(
        broker.app,
        log_config=None,
        access_log=False,
        lifespan="off",
        server_header=False,
        date_header=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [sock]},
        name="implement-step-broker",
        daemon=True,
    )
    broker.server, broker.thread = server, thread
    thread.start()
    _await_started(server, thread)


def start_step_broker(
    budget: StepBudget, *, host: str = _DEFAULT_HOST, port: int = 0
) -> StepBroker | None:
    """Run the broker of one step on `host:port`, an ephemeral port by default, and return it.

    No broker runs when `ai.provider` is not the gateway or the process holds no AI key: such a
    step has no model endpoint to reach, and its shell gets no broker variable. A gateway provider
    with no `ai.gateway_url` raises `RoadmapImplementError`. A `host` that is not a loopback
    address raises it too, and no port is bound then. `budget` takes the new tokens of each shell
    call.
    """
    settings = load_settings()
    if settings.ai.provider != CONST_AI_GATEWAY_PROVIDER:
        return None
    key = get_ai_api_key(settings)
    if not key:
        return None
    gateway_url = settings.ai.gateway_url
    if not gateway_url:
        raise RoadmapImplementError(_NO_GATEWAY_URL)
    loopback_broker_url(host, port)
    stop_step_broker(live_broker())
    client = http_client(configured_level(settings.ai))
    sock = _listening_socket(host, port)
    prefix = _gateway_prefix(str(gateway_url))
    broker: StepBroker | None = None
    try:
        broker = StepBroker(
            key=key,
            token=secrets.token_urlsafe(_TOKEN_BYTES),
            url=loopback_broker_url(host, sock.getsockname()[1], prefix),
            gateway_url=str(gateway_url),
            client=client,
            budget=budget,
        )
        _set_live(broker)
        _serve(broker, sock)
    except BaseException:
        stop_step_broker(broker)
        client.close()
        sock.close()
        raise
    return broker


def stop_step_broker(broker: StepBroker | None) -> None:
    """End the broker of a step: refuse its token, stop its server, close its client and clear the
    live broker, so a request with the token that the step held reaches no gateway."""
    if broker is None:
        return
    broker.token = ""
    if live_broker() is broker:
        _set_live(None)
    if broker.server is not None:
        broker.server.should_exit = True
    if broker.thread is not None:
        broker.thread.join(_STOP_TIMEOUT_SECONDS)
    broker.client.close()


def reset_step_broker() -> None:
    """Stop the live broker, so a test or a new step starts from no broker."""
    stop_step_broker(live_broker())


__all__ = [
    "ALLOWED_REQUESTS",
    "BrokerSpend",
    "StepBroker",
    "broker_app",
    "live_broker",
    "loopback_broker_url",
    "reset_step_broker",
    "start_step_broker",
    "stop_step_broker",
]
