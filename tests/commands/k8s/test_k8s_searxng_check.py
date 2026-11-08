"""`devops k8s searxng-check`: the points that a digest bump of SearXNG can change (#3929).

The command forwards a local port to Service `searxng`, sends six search requests with
`format=json`, and tries three connects from throwaway pods, so the NetworkPolicy applies to them.
The tests fake the process edge and the HTTP edge, and none skips on the state of the host.
"""

from __future__ import annotations

import json
import signal
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx2
import pytest

from devops_cli.commands.k8s import searxng_check as command
from devops_cli.config.defaults import DEFAULT_SEARXNG_CATEGORIES
from devops_cli.k8s import service_probe
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import RecordedRequest, WebFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.kubectl_calls import (
    RunningForward,
    context_of,
    flag,
    kubectl_calls,
    namespace_of,
    verb,
    without_context,
)

_PORT = 18236
_BASE = f"http://127.0.0.1:{_PORT}"
_SEARXNG_IP = "192.0.2.10"
_ROADMAP_IP = "192.0.2.20"
_METADATA = "169.254.169.254"
_EXTERNAL = "https://example.com/redirected"
_ROWS = (
    "json-general",
    "json-it",
    "json-science",
    "bang-off-engine",
    "bang-external",
    "unused-category",
)
_CATEGORIES = DEFAULT_SEARXNG_CATEGORIES.split(",")
# The engine that answers in each category, as the pinned image does.
_ENGINE = {"general": "duckduckgo", "it": "github", "science": "arxiv"}
_KEYS = ("answers", "corrections", "infoboxes", "query", "results", "suggestions")


@dataclass(frozen=True)
class _Search:
    q: str
    categories: str
    format: str

    @property
    def kind(self) -> str:
        if self.q.startswith("!!"):
            return "bang-external"
        if self.q.startswith("!"):
            return "bang-off-engine"
        return "plain"


def _search(request: httpx2.Request | RecordedRequest) -> _Search:
    params = dict(httpx2.URL(str(request.url)).params)
    return _Search(params.get("q", ""), params.get("categories", ""), params.get("format", ""))


def _reply(search: _Search, **changes: Any) -> bytes:
    engine = _ENGINE.get(search.categories, _ENGINE["general"])
    reply: dict[str, Any] = {
        "query": search.q,
        "number_of_results": 0,
        "results": [
            {"url": "https://example.com/a", "title": "A", "content": "B", "engine": engine}
        ],
        "answers": [],
        "corrections": [],
        "infoboxes": [],
        "suggestions": [],
        "unresponsive_engines": [],
    }
    reply.update(changes)
    return json.dumps(reply).encode()


class _Service:
    """SearXNG behind the forward, as the pinned image answers. `/healthz` is open, a query that
    starts with `!!` gets a redirect, and every other query gets a reply with one hit of the
    engine of its category. A test sets `answer` to give another reply for one search."""

    def __init__(self) -> None:
        self.answer: Callable[[_Search], tuple[int, dict[str, str], bytes] | None] | None = None

    def __call__(self, request: httpx2.Request) -> httpx2.Response | None:
        if request.url.host != "127.0.0.1" or request.url.port != _PORT:
            return None
        if request.url.path == "/healthz":
            return httpx2.Response(200, content=b"OK")
        search = _search(request)
        custom = self.answer(search) if self.answer else None
        if custom:
            status, headers, body = custom
            return httpx2.Response(status, headers=headers, content=body)
        if search.kind == "bang-external":
            return httpx2.Response(302, headers={"location": _EXTERNAL})
        return httpx2.Response(
            200, headers={"content-type": "application/json"}, content=_reply(search)
        )


@pytest.fixture
def service(web: WebFake) -> _Service:
    """The service, installed on the HTTP fake."""
    fake = _Service()
    web.serve(fake)
    return fake


def _is_exec(call: ProcessCall) -> bool:
    return call.argv[:1] == ("kubectl",) and "exec" in call.argv


def _is_get_of(name: str) -> Callable[[ProcessCall], bool]:
    return lambda call: call.argv[:1] == ("kubectl",) and "get" in call.argv and name in call.argv


@pytest.fixture
def cluster(service: _Service, process_fake: ProcessFake, clock: ClockFake) -> ProcessFake:
    """A cluster that blocks every pod, a running forward, and the ClusterIP of each Service."""
    process_fake.answer(lambda call: call.detached, ProcessAnswer(process=RunningForward()))
    process_fake.answer(_is_get_of("searxng"), ProcessAnswer(stdout=_SEARXNG_IP))
    process_fake.answer(_is_get_of("roadmap-service"), ProcessAnswer(stdout=_ROADMAP_IP))
    process_fake.answer(_is_exec, ProcessAnswer(returncode=1))
    return process_fake


def _check(cli: Callable[..., Any], *args: str) -> Any:
    return cli("k8s", "searxng-check", "--local-port", str(_PORT), *args)


def _searches(web: WebFake) -> list[_Search]:
    return [_search(r) for r in web.recorded if urlsplit(r.url).path == "/search"]


def _pod_of(argv: tuple[str, ...]) -> str:
    return without_context(argv)[2]


def _exec_targets(cluster: ProcessFake, pod: str) -> list[tuple[str, str]]:
    """The host and the port of each connect probe that ran in `pod`."""
    return [
        (argv[-2], argv[-1])
        for argv in kubectl_calls(cluster)
        if verb(argv) == "exec" and _pod_of(argv) == pod
    ]


def _lines(result: Any, *words: str) -> list[str]:
    return [line for line in result.output.splitlines() if all(w in line for w in words)]


def test_six_requests_go_through_the_forward_with_format_json_and_no_credential(
    cli: Callable[..., Any], cluster: ProcessFake, web: WebFake
) -> None:
    result = _check(cli)

    searches = _searches(web)
    plain = [s for s in searches if s.kind == "plain"]
    unused = {s.categories for s in plain} - set(_CATEGORIES)
    assert (
        result.exit_code,
        len(searches),
        sorted(s.kind for s in searches),
        {s.categories for s in plain} - unused,
        len(unused),
        {s.format for s in searches},
        {urlsplit(r.url).netloc for r in web.recorded},
        [r for r in web.recorded if "authorization" in r.headers],
    ) == (
        0,
        6,
        ["bang-external", "bang-off-engine", "plain", "plain", "plain", "plain"],
        set(_CATEGORIES),
        1,
        {"json"},
        {f"127.0.0.1:{_PORT}"},
        [],
    )


def test_the_report_has_one_row_for_each_search(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    result = _check(cli)

    assert {row: len(_lines(result, row)) >= 1 for row in _ROWS} == {row: True for row in _ROWS}


def test_the_forward_goes_to_service_searxng_and_stops_when_the_command_ends(
    cli: Callable[..., Any], cluster: ProcessFake, web: WebFake
) -> None:
    _check(cli)

    forward = next(call for call in cluster.calls if call.detached)
    assert (
        forward.argv[:2],
        "svc/searxng" in forward.argv,
        f"{_PORT}:8080" in forward.argv,
        namespace_of(forward.argv),
        cluster.terminated_pids,
    ) == (("kubectl", "port-forward"), True, True, "devops", [(-1, signal.SIGTERM)])
    assert next(r.url for r in web.recorded) == f"{_BASE}/healthz"


@pytest.mark.parametrize("key", _KEYS)
def test_a_reply_without_a_key_fails_the_check_and_names_the_key(
    cli: Callable[..., Any], cluster: ProcessFake, service: _Service, key: str
) -> None:
    def leave_out(search: _Search) -> tuple[int, dict[str, str], bytes] | None:
        if search.categories != "general" or search.kind != "plain":
            return None
        reply = json.loads(_reply(search))
        del reply[key]
        return 200, {}, json.dumps(reply).encode()

    service.answer = leave_out

    result = _check(cli)

    assert (result.exit_code, key in result.output) == (1, True)


def test_unresponsive_engines_that_is_a_string_fails_the_check(
    cli: Callable[..., Any], cluster: ProcessFake, service: _Service
) -> None:
    service.answer = lambda search: (
        (200, {}, _reply(search, unresponsive_engines="duckduckgo: timeout"))
        if search.kind == "plain" and search.categories == "it"
        else None
    )

    result = _check(cli)

    assert (result.exit_code, "unresponsive_engines" in result.output) == (1, True)


def test_a_category_of_the_provider_with_no_hit_fails_the_check_and_names_it(
    cli: Callable[..., Any], cluster: ProcessFake, service: _Service
) -> None:
    service.answer = lambda search: (
        (200, {}, _reply(search, results=[]))
        if search.kind == "plain" and search.categories == "science"
        else None
    )

    result = _check(cli)

    assert (result.exit_code, _lines(result, "json-science", "FAILED") != []) == (1, True)
    assert "science" in result.output


def test_a_service_that_refuses_json_fails_the_check_and_names_the_formats_setting(
    cli: Callable[..., Any], cluster: ProcessFake, service: _Service
) -> None:
    service.answer = lambda search: (403, {}, b"<html>Forbidden</html>")

    result = _check(cli)

    assert (result.exit_code, "search.formats" in result.output) == (1, True)


def test_a_hit_of_an_engine_that_must_stay_off_fails_the_check_and_names_the_engine(
    cli: Callable[..., Any], cluster: ProcessFake, service: _Service
) -> None:
    def keyed(search: _Search) -> tuple[int, dict[str, str], bytes] | None:
        if search.kind != "plain" or search.categories != "general":
            return None
        hit = {"url": "https://example.com/g", "title": "G", "content": "G", "engine": "google"}
        return 200, {}, _reply(search, results=[hit])

    service.answer = keyed

    result = _check(cli)

    assert (result.exit_code, "google" in result.output) == (1, True)


def test_an_engine_that_must_stay_off_and_is_unresponsive_fails_the_check(
    cli: Callable[..., Any], cluster: ProcessFake, service: _Service
) -> None:
    service.answer = lambda search: (
        (200, {}, _reply(search, unresponsive_engines=[["bing", "CAPTCHA"]]))
        if search.kind == "plain" and search.categories == "general"
        else None
    )

    result = _check(cli)

    assert (result.exit_code, "bing" in result.output) == (1, True)


def test_the_external_bang_redirect_is_recorded_and_never_followed(
    cli: Callable[..., Any], cluster: ProcessFake, web: WebFake
) -> None:
    result = _check(cli)

    assert (
        result.exit_code,
        len(_lines(result, "bang-external", "302")),
        [r.url for r in web.recorded if "example.com" in urlsplit(r.url).netloc],
    ) == (0, 1, [])


def test_an_external_bang_that_gets_a_fault_fails_the_check(
    cli: Callable[..., Any], cluster: ProcessFake, service: _Service
) -> None:
    service.answer = lambda search: (500, {}, b"error") if search.kind == "bang-external" else None

    result = _check(cli)

    assert (result.exit_code, _lines(result, "bang-external", "500") != []) == (1, True)


def test_a_bang_for_an_engine_that_is_off_stays_text(
    cli: Callable[..., Any], cluster: ProcessFake, web: WebFake
) -> None:
    result = _check(cli)

    (bang,) = (s for s in _searches(web) if s.kind == "bang-off-engine")
    assert (result.exit_code, bang.q.startswith("!google ")) == (0, True)


def test_a_bang_that_selects_the_engine_that_is_off_fails_the_check_and_names_it(
    cli: Callable[..., Any], cluster: ProcessFake, service: _Service
) -> None:
    def selects(search: _Search) -> tuple[int, dict[str, str], bytes] | None:
        if search.kind != "bang-off-engine":
            return None
        hit = {"url": "https://example.com/g", "title": "G", "content": "G", "engine": "google"}
        return 200, {}, _reply(search, results=[hit])

    service.answer = selects

    result = _check(cli)

    assert (result.exit_code, _lines(result, "bang-off-engine", "FAILED") != []) == (1, True)
    assert "google" in result.output


def test_a_bang_that_redirects_fails_the_check(
    cli: Callable[..., Any], cluster: ProcessFake, service: _Service
) -> None:
    service.answer = lambda search: (
        (302, {"location": _EXTERNAL}, b"") if search.kind == "bang-off-engine" else None
    )

    result = _check(cli)

    assert (result.exit_code, _lines(result, "bang-off-engine", "FAILED") != []) == (1, True)


def test_the_unused_category_row_records_its_status_and_its_number_of_hits(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    result = _check(cli)

    rows = _lines(result, "unused-category")
    assert (result.exit_code, len(rows), "200" in rows[0], "1" in rows[0]) == (0, 1, True, True)


def test_an_unused_category_that_gets_a_fault_fails_the_check(
    cli: Callable[..., Any], cluster: ProcessFake, service: _Service
) -> None:
    service.answer = lambda search: (
        (500, {}, b"error")
        if search.kind == "plain" and search.categories not in _CATEGORIES
        else None
    )

    result = _check(cli)

    assert result.exit_code == 1
    assert _lines(result, "unused-category", "500") != []


def test_two_pods_run_the_three_connects_of_the_network_policy(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    result = _check(cli)

    runs = [argv for argv in kubectl_calls(cluster) if verb(argv) == "run"]
    labels = {_pod_of(argv): flag(argv, "--labels") for argv in runs}
    labeled = next(
        pod for pod, label in labels.items() if label == "app.kubernetes.io/name=searxng"
    )
    unlabeled = next(pod for pod in labels if pod != labeled)
    client_labels = ("app.kubernetes.io/name=searxng", "app.kubernetes.io/name=roadmap-service")
    assert (
        result.exit_code,
        len(runs),
        {namespace_of(argv) for argv in runs},
        labels[unlabeled] in client_labels,
        _exec_targets(cluster, unlabeled),
        _exec_targets(cluster, labeled),
        verb(kubectl_calls(cluster)[-1]),
        sorted(verb(a) for a in kubectl_calls(cluster) if verb(a) == "delete"),
    ) == (
        0,
        2,
        {"devops"},
        False,
        [(_SEARXNG_IP, "8080")],
        [(_METADATA, "80"), (_ROADMAP_IP, "8000")],
        "delete",
        ["delete", "delete"],
    )


def test_the_report_names_each_pod_and_target_by_a_role_and_shows_three_blocked_rows(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    result = _check(cli)

    rows = _lines(result, "blocked")
    assert (result.exit_code, len(rows)) == (0, 3)
    assert [
        ("<unlabeled-pod>" in rows[0]) and ("<searxng-service>" in rows[0]),
        all("<searxng-pod>" in row for row in rows[1:]),
        "<metadata>" in " ".join(rows),
        "<private-cluster-ip>" in " ".join(rows),
    ] == [True, True, True, True]


def test_the_output_holds_no_address_and_no_host_name(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    result = _check(cli)

    leaks = [
        text
        for text in (_METADATA, _SEARXNG_IP, _ROADMAP_IP, ".svc", ".cluster.local")
        if text in result.output
    ]
    assert (result.exit_code, leaks) == (0, [])


def test_an_unlabeled_pod_that_connects_to_the_service_fails_the_check_and_the_pods_are_deleted(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    cluster.answer(
        lambda call: _is_exec(call) and _SEARXNG_IP in call.argv, ProcessAnswer(returncode=0)
    )

    result = _check(cli)

    reached = _lines(result, "reached")
    assert (
        result.exit_code,
        [("<unlabeled-pod>" in r and "<searxng-service>" in r) for r in reached],
        verb(kubectl_calls(cluster)[-1]),
    ) == (1, [True], "delete")


def test_a_searxng_pod_that_reaches_the_metadata_address_fails_the_check(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    cluster.answer(
        lambda call: _is_exec(call) and _METADATA in call.argv, ProcessAnswer(returncode=0)
    )

    result = _check(cli)

    reached = _lines(result, "reached")
    assert (
        result.exit_code,
        [("<searxng-pod>" in r and "<metadata>" in r) for r in reached],
    ) == (1, [True])


def test_a_searxng_pod_that_reaches_a_private_cluster_ip_fails_the_check(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    cluster.answer(
        lambda call: _is_exec(call) and _ROADMAP_IP in call.argv, ProcessAnswer(returncode=0)
    )

    result = _check(cli)

    reached = _lines(result, "reached")
    assert (
        result.exit_code,
        [("<searxng-pod>" in r and "<private-cluster-ip>" in r) for r in reached],
    ) == (1, [True])


def test_a_forward_that_ends_at_once_stops_the_command_before_it_sends_a_request(
    cli: Callable[..., Any], process_fake: ProcessFake, web: WebFake, service: _Service
) -> None:
    result = _check(cli)

    assert (result.exit_code, web.recorded) == (1, [])
    assert "run" not in [verb(argv) for argv in kubectl_calls(process_fake)]


def test_a_service_that_does_not_answer_health_stops_the_command_and_stops_the_forward(
    cli: Callable[..., Any], cluster: ProcessFake, web: WebFake
) -> None:
    web.refuse(f"{_BASE}/healthz")

    result = _check(cli)

    assert (result.exit_code, _searches(web), cluster.terminated_pids) == (
        1,
        [],
        [(-1, signal.SIGTERM)],
    )


def test_the_context_option_reaches_every_kubectl_call(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    result = _check(cli, "--context", "test-ctx")

    assert (result.exit_code, {context_of(argv) for argv in kubectl_calls(cluster)}) == (
        0,
        {"test-ctx"},
    )


def test_a_dry_run_lists_every_call_and_makes_none(
    cli: Callable[..., Any], process_fake: ProcessFake, web: WebFake
) -> None:
    result = _check(cli, "--dry-run")

    lines = result.output.splitlines()
    missing = [row for row in _ROWS if not any(row in line for line in lines)]
    leaks = [text for text in (_METADATA, ".svc") if text in result.output]
    assert (
        result.exit_code,
        missing,
        leaks,
        "kubectl port-forward" in result.output,
        "kubectl run" in result.output,
        process_fake.calls,
        web.recorded,
    ) == (0, [], [], True, True, [], [])


def test_the_command_uses_the_forward_of_the_shared_probe_module() -> None:
    assert command.forward_service is service_probe.forward_service
