"""`devops k8s crawl4ai-check`: the controls that keep the Crawl4AI service off internal addresses (#3894).

The command forwards a local port to the Service, sends each of five routes to each of five
internal targets with the token of the keyring, and checks that the service refuses each one. It
also checks that a request without the token is refused, and, from a throwaway pod that carries
the label of the service, that the NetworkPolicy blocks a private ClusterIP and the metadata
address. The tests fake the process edge, the HTTP edge and the keyring, and none skips on the
state of the host.
"""

from __future__ import annotations

import itertools
import json
import signal
from collections.abc import Callable, Sequence
from typing import Any
from urllib.parse import unquote, urlsplit

import httpx2
import pytest

from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import RecordedRequest, WebFake
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.kubectl_calls import (
    context_of,
    flag,
    kubectl_calls,
    namespace_of,
    verb,
)

_TOKEN = "c4a-secret-token"
_PORT = 18235
_BASE = f"http://127.0.0.1:{_PORT}"
_BLOCKED = b'{"detail":"URL blocked (SSRF protection): URL blocked"}'
_CLUSTER_IP = "192.0.2.10"

# The routes, as the command names them, with the method of each.
_ROUTES = {
    "/md": "POST",
    "/html": "POST",
    "/screenshot": "POST",
    "/pdf": "POST",
    "/llm/{url}": "GET",
}
# Each target role the report names, with the host prefix of the URL the command sends.
_ROLES = {
    "<metadata>": "169.254.169.254",
    "<loopback>": "localhost",
    "<kubernetes-api>": "kubernetes.default.svc",
    "<crawl4ai-service>": "crawl4ai.devops.svc",
    "<roadmap-service>": "roadmap-service.devops.svc",
}
_METADATA_ADDRESSES = ("169.254.169.254",)


class _RunningForward:
    """The `kubectl port-forward` child while it runs. Its pid is one that no process holds."""

    pid = -1

    def poll(self) -> int | None:
        return None


def _route(request: RecordedRequest) -> str:
    path = urlsplit(request.url).path
    return "/llm/{url}" if path.startswith("/llm/") else path


def _target(request: RecordedRequest) -> str:
    """The URL that the request asks the service to fetch."""
    if request.method == "GET":
        return unquote(urlsplit(request.url).path.removeprefix("/llm/"))
    return str(json.loads(request.body)["url"])


def _role(request: RecordedRequest) -> str:
    host = urlsplit(_target(request)).hostname or ""
    (role,) = (name for name, prefix in _ROLES.items() if host.startswith(prefix))
    return role


def _with_token(requests: Sequence[RecordedRequest]) -> list[RecordedRequest]:
    return [r for r in requests if r.headers.get("authorization") == f"Bearer {_TOKEN}"]


def _without_token(requests: Sequence[RecordedRequest]) -> list[RecordedRequest]:
    return [r for r in requests if "authorization" not in r.headers]


class _Service:
    """The Crawl4AI service behind the forward: `/health` is open, every other route needs the
    bearer token, and a request with the token for an internal target gets the documented
    refusal. A test sets `answer` to give another reply for a request with the token, and
    `without_token` to change the status of a request without it."""

    def __init__(self) -> None:
        self.answer: Callable[[RecordedRequest], tuple[int, bytes] | None] | None = None
        self.without_token = 401

    def __call__(self, request: httpx2.Request) -> httpx2.Response | None:
        if request.url.host != "127.0.0.1" or request.url.port != _PORT:
            return None
        if request.url.path == "/health":
            return httpx2.Response(200, content=b'{"status":"ok"}')
        recorded = RecordedRequest(
            request.method, str(request.url), dict(request.headers), request.read()
        )
        if request.headers.get("authorization") != f"Bearer {_TOKEN}":
            return httpx2.Response(self.without_token, content=b'{"detail":"Not authenticated"}')
        custom = self.answer(recorded) if self.answer else None
        status, body = custom or (400, _BLOCKED)
        return httpx2.Response(status, content=body)


@pytest.fixture
def service(web: WebFake) -> _Service:
    """The service, installed on the HTTP fake."""
    fake = _Service()
    web.serve(fake)
    return fake


@pytest.fixture
def cluster(
    service: _Service, process_fake: ProcessFake, keyring_store: FakeKeyring, clock: ClockFake
) -> ProcessFake:
    """A cluster that blocks the pod, a service that refuses each internal target, a running
    forward, the token in the keyring and a ClusterIP for the Service of the roadmap."""
    keyring_store.set_password("devops-cli", "crawl4ai_api_token", _TOKEN)
    process_fake.answer(lambda call: call.detached, ProcessAnswer(process=_RunningForward()))
    process_fake.answer(
        lambda call: call.argv[:1] == ("kubectl",) and "get" in call.argv,
        ProcessAnswer(stdout=_CLUSTER_IP),
    )
    process_fake.answer(_is_exec, ProcessAnswer(returncode=1))
    return process_fake


def _is_exec(call: ProcessCall) -> bool:
    return call.argv[:1] == ("kubectl",) and "exec" in call.argv


def _check(cli: Callable[..., Any], *args: str) -> Any:
    return cli("k8s", "crawl4ai-check", "--local-port", str(_PORT), *args)


def test_each_route_gets_one_request_with_the_token_for_each_internal_target(
    cli: Callable[..., Any], cluster: ProcessFake, web: WebFake
) -> None:
    result = _check(cli)

    sent = sorted((r.method, _route(r), _role(r)) for r in _with_token(web.recorded))
    expected = sorted(
        (method, route, role)
        for (route, method), role in itertools.product(_ROUTES.items(), _ROLES)
    )
    assert (result.exit_code, sent) == (0, expected)


def test_the_requests_go_through_the_local_forward_of_the_service(
    cli: Callable[..., Any], cluster: ProcessFake, web: WebFake
) -> None:
    _check(cli)

    forward = next(call for call in cluster.calls if call.detached)
    assert (
        forward.argv[:2],
        "svc/crawl4ai" in forward.argv or "crawl4ai" in forward.argv,
        f"{_PORT}:11235" in forward.argv,
        namespace_of(forward.argv),
        {urlsplit(r.url).netloc for r in web.recorded},
    ) == (("kubectl", "port-forward"), True, True, "devops", {f"127.0.0.1:{_PORT}"})
    assert cluster.terminated_pids == [(-1, signal.SIGTERM)]


def test_a_request_without_the_token_must_be_refused_on_every_route_but_health(
    cli: Callable[..., Any], cluster: ProcessFake, web: WebFake
) -> None:
    result = _check(cli)

    sent = sorted((r.method, _route(r)) for r in _without_token(web.recorded))
    expected = sorted([("GET", "/health"), *((method, route) for route, method in _ROUTES.items())])
    assert (result.exit_code, sent) == (0, expected)


def test_a_route_that_serves_a_page_without_the_token_fails_the_check(
    cli: Callable[..., Any], cluster: ProcessFake, service: _Service
) -> None:
    service.without_token = 200

    result = _check(cli)

    assert result.exit_code == 1


def test_a_route_that_serves_a_page_of_an_internal_target_fails_the_check_and_names_it(
    cli: Callable[..., Any], cluster: ProcessFake, service: _Service
) -> None:
    def serve_roadmap_page(request: RecordedRequest) -> tuple[int, bytes] | None:
        if _route(request) == "/md" and _role(request) == "<roadmap-service>":
            return 200, b'{"markdown":"# Roadmap service"}'
        return None

    service.answer = serve_roadmap_page

    result = _check(cli)

    served = [line for line in result.output.splitlines() if "/md" in line and "200" in line]
    assert (result.exit_code, ["<roadmap-service>" in line for line in served]) == (1, [True])


def test_a_fault_of_the_service_is_no_refusal(
    cli: Callable[..., Any], cluster: ProcessFake, service: _Service
) -> None:
    service.answer = lambda request: (500, b"{}") if _route(request) == "/pdf" else None

    result = _check(cli)

    assert result.exit_code == 1


def test_the_report_has_one_row_for_each_route_and_target_with_its_status_and_body_length(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    result = _check(cli)

    lines = result.output.splitlines()
    rows = {
        (route, role): [line for line in lines if route in line and role in line and "400" in line]
        for route, role in itertools.product(_ROUTES, _ROLES)
    }
    assert (
        {key: len(found) for key, found in rows.items()},
        all(str(len(_BLOCKED)) in found[0] for found in rows.values()),
    ) == ({key: 1 for key in rows}, True)


def test_the_output_names_each_target_by_a_role_and_holds_no_address_or_host(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    result = _check(cli)

    leaks = [
        text
        for text in (*_METADATA_ADDRESSES, ".svc", ".cluster.local", _CLUSTER_IP)
        if text in result.output
    ]
    assert (result.exit_code, leaks) == (0, [])


def test_the_token_comes_from_the_keyring_and_is_never_printed_or_passed_on_a_command_line(
    cli: Callable[..., Any], cluster: ProcessFake, web: WebFake
) -> None:
    result = _check(cli)

    assert (
        _TOKEN in result.output,
        any(_TOKEN in word for call in cluster.calls for word in call.argv),
        len(_with_token(web.recorded)),
    ) == (False, False, 25)


def test_a_missing_keyring_entry_stops_the_command_before_it_starts_anything(
    cli: Callable[..., Any],
    process_fake: ProcessFake,
    web: WebFake,
    keyring_store: FakeKeyring,
) -> None:
    result = _check(cli)

    assert (result.exit_code, "crawl4ai_api_token" in result.output, process_fake.calls) == (
        1,
        True,
        [],
    )
    assert web.recorded == []


def test_a_forward_that_ends_at_once_stops_the_command_before_it_sends_a_request(
    cli: Callable[..., Any],
    process_fake: ProcessFake,
    web: WebFake,
    service: _Service,
    keyring_store: FakeKeyring,
) -> None:
    keyring_store.set_password("devops-cli", "crawl4ai_api_token", _TOKEN)

    result = _check(cli)

    assert (result.exit_code, web.recorded) == (1, [])


def test_a_service_that_does_not_answer_health_stops_the_command_and_stops_the_forward(
    cli: Callable[..., Any], cluster: ProcessFake, web: WebFake
) -> None:
    web.refuse(f"{_BASE}/health")

    result = _check(cli)

    assert (result.exit_code, _with_token(web.recorded), cluster.terminated_pids) == (
        1,
        [],
        [(-1, signal.SIGTERM)],
    )


def test_the_network_policy_layer_runs_from_a_pod_with_the_label_of_the_service(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    result = _check(cli)

    calls = kubectl_calls(cluster)
    (run,) = (argv for argv in calls if verb(argv) == "run")
    probed = [argv for argv in calls if verb(argv) == "exec"]
    assert (
        flag(run, "--labels"),
        namespace_of(run),
        len(probed),
        any(_CLUSTER_IP in " ".join(argv) for argv in probed),
        verb(calls[-1]),
    ) == ("app.kubernetes.io/name=crawl4ai", "devops", 2, True, "delete")
    roles = ("<metadata>", "<private-cluster-ip>")
    rows = [line for line in result.output.splitlines() if "blocked" in line]
    assert (result.exit_code, len(rows), {r for r in roles for line in rows if r in line}) == (
        0,
        2,
        set(roles),
    )


def test_a_destination_that_the_pod_reaches_fails_the_check_and_the_pod_is_deleted(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    cluster.answer(
        lambda call: _is_exec(call) and "169.254.169.254" in " ".join(call.argv),
        ProcessAnswer(returncode=0),
    )

    result = _check(cli)

    reached = [line for line in result.output.splitlines() if "reached" in line]
    assert (
        result.exit_code,
        ["<metadata>" in line for line in reached],
        verb(kubectl_calls(cluster)[-1]),
    ) == (1, [True], "delete")


def test_the_context_option_reaches_every_kubectl_call(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    result = _check(cli, "--context", "test-ctx")

    assert (
        result.exit_code,
        {context_of(argv) for argv in kubectl_calls(cluster)},
    ) == (0, {"test-ctx"})


def test_a_dry_run_lists_every_request_and_makes_none(
    cli: Callable[..., Any], process_fake: ProcessFake, web: WebFake, keyring_store: FakeKeyring
) -> None:
    result = _check(cli, "--dry-run")

    lines = result.output.splitlines()
    missing = [
        (route, role)
        for route, role in itertools.product(_ROUTES, _ROLES)
        if not any(route in line and role in line for line in lines)
    ]
    leaks = [text for text in (*_METADATA_ADDRESSES, ".svc") if text in result.output]
    assert (
        result.exit_code,
        missing,
        leaks,
        "kubectl port-forward" in result.output,
        "kubectl run" in result.output,
        process_fake.calls,
        web.recorded,
    ) == (0, [], [], True, True, [], [])
