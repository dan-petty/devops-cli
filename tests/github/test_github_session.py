"""Tests for the process's one GitHub session (#767)."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import threading
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch

import anyio
import httpx2
import pytest

from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_GITHUB_API_VERSION,
    CONST_GITHUB_DIFF_MEDIA_TYPE,
    CONST_GITHUB_USER_AGENT,
)
from devops_cli.core import process
from devops_cli.core.process import GitHubIdentity
from devops_cli.exceptions.git import (
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.github import rate_limiter, session_transport
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.github.session import GitHubSession, get_github_session, reset_github_session
from devops_cli.http.egress import EgressLevel
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.github import (
    API,
    JSON_TYPE,
    GitHubApiFake,
    github_json,
    github_redirect,
    github_text,
    next_page,
    quota_headers,
)
from tests.support.paths import REPO_ROOT
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until, wait_while_running
from tests.web_fakes import rebinding, scripted_resolver

_SRC = REPO_ROOT / "src" / "devops_cli"


def _gh_answers(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    """A finished child, as `subprocess.run` returns it."""
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


def test_the_session_carries_the_pinned_token(pin_github_session: str) -> None:
    """The session's token is the one the identity lookup gave the process."""
    assert get_github_session().token == pin_github_session


def test_the_session_is_one_per_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """One identity keeps one session; another token gets another one."""
    first = get_github_session()
    again = get_github_session()
    monkeypatch.setattr(process, "_github_token", "B")
    assert (again is first, get_github_session().token) == (True, "B")


def test_the_session_never_shows_its_token(pin_github_session: str) -> None:
    """Neither the session's repr nor its cache directory holds the token."""
    session = get_github_session()
    assert pin_github_session not in f"{session!r} {session.cache_dir}"


def test_login_is_read_once_from_get_user(github_api: GitHubApiFake) -> None:
    """`session.login` asks `GET /user` the first time it is read, then keeps the answer."""
    github_api.route("GET", "/user", github_json({"login": "octocat"}))
    session = get_github_session()
    logins = (session.login, session.login)
    assert (logins, len(github_api.sent)) == (
        ("octocat", "octocat"),
        1,
    )


def test_login_raises_when_get_user_fails(github_api: GitHubApiFake) -> None:
    """`session.login` raises when `GET /user` fails, with no fallback."""
    github_api.route("GET", "/user", github_json({"message": "Bad credentials"}, status=401))
    session = get_github_session()
    with pytest.raises(GitHubUnauthenticatedError) as raised:
        _ = session.login
    assert raised.value.error_code == "GITHUB_UNAUTHENTICATED"


def test_without_a_token_the_session_raises_the_unauthenticated_error(
    no_github_identity: None,
) -> None:
    """No token from `gh auth token` means no session, and no fallback to any other token."""
    with pytest.raises(GitHubUnauthenticatedError) as raised:
        get_github_session()
    assert raised.value.error_code == "GITHUB_UNAUTHENTICATED"


def test_a_session_keeps_its_own_identity_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    """A session held across a token change still names its own identity's directory."""
    held = get_github_session()
    before = held.cache_dir
    monkeypatch.setattr(process, "_github_token", "B")
    assert (held.cache_dir, get_github_session().cache_dir != before) == (before, True)


def test_reset_forgets_the_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """After a reset, the next GitHub call looks the identity up again."""
    reset_github_session()
    with patch("subprocess.run", return_value=_gh_answers("C\n")) as run:
        token = get_github_session().token
    assert (token, run.call_args.args[0]) == ("C", [CONST_GH_CLI, "auth", "token"])


def _github_client_calls(path: Path) -> list[str]:
    """`GitHubClient(...)` calls in one module, read with Python's parser."""
    source = path.read_text(encoding="utf-8")
    if "GitHubClient" not in source:
        return []
    return [
        str(path.relative_to(_SRC))
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "GitHubClient"
    ]


def test_the_client_is_built_only_by_the_session() -> None:
    """`GitHubClient(...)` is called in one place in src: the session module."""
    constructions = [
        call for path in sorted(_SRC.rglob("*.py")) for call in _github_client_calls(path)
    ]
    assert constructions == ["github/session.py"]


# ── REST transport (#983) ────────────────────────────────────────────────────────────────────────

_PULL = "/repos/octo/repo/pulls/42"
_MOVED = "https://api.github.com/repositories/1/pulls/42"
_DIFF = "diff --git a/f b/f\n+line\n"


def test_a_get_carries_the_token_the_api_version_and_the_user_agent(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """A REST request is sent as the session's identity, at the pinned API version."""
    github_api.route("GET", "/user", github_json({"login": "octocat"}))
    answer = get_github_session().rest("GET", "/user")
    sent = github_api.sent[0].headers
    assert (
        answer,
        sent["authorization"],
        sent["x-github-api-version"],
        sent["user-agent"],
    ) == (
        {"login": "octocat"},
        f"token {pin_github_session}",
        CONST_GITHUB_API_VERSION,
        CONST_GITHUB_USER_AGENT,
    )


@pytest.mark.parametrize(
    ("remaining", "named", "charged"),
    [
        pytest.param(42, "core", {"core": 42}, id="names-core"),
        pytest.param(41, None, {"core": 41}, id="names-none-so-the-paced-one"),
        pytest.param(7, "search", {"core": 4999, "search": 7}, id="names-another"),
    ],
)
def test_a_response_charges_its_quota_to_the_resource_github_names(
    github_api: GitHubApiFake, remaining: int, named: str | None, charged: dict[str, int]
) -> None:
    """The ledger takes each answer's `x-ratelimit-*` figures for the resource it names."""
    headers = quota_headers(remaining, resource=named or "core")
    if named is None:
        del headers["x-ratelimit-resource"]
    github_api.route("GET", "/user", github_json({"login": "octocat"}, headers=headers))
    get_github_session().rest("GET", "/user")
    limiter = get_github_rate_limiter()
    assert {resource: limiter.get_quota(resource).remaining for resource in charged} == charged


def test_a_post_is_paced_as_a_mutation_a_get_as_a_read_and_the_quota_read_not_at_all(
    github_api: GitHubApiFake,
) -> None:
    """Every request but `GET /rate_limit` waits its turn on the ledger, a write as a write."""
    github_api.route("POST", "/user/ssh_signing_keys", github_json({"id": 1}, status=201))
    github_api.route("GET", "/user", github_json({"login": "octocat"}))
    github_api.route("GET", "/rate_limit", github_json({"resources": {}}))
    limiter = get_github_rate_limiter()
    session = get_github_session()
    with patch.object(limiter, "acquire", wraps=limiter.acquire) as acquire:
        session.rest("POST", "/user/ssh_signing_keys", body={"title": "t", "key": "k"})
        session.rest("GET", "/user")
        session.rest("GET", "/rate_limit")
    paced = [(call.kwargs["subcommand"], call.kwargs["is_mutation"]) for call in acquire.mock_calls]
    assert (paced, json.loads(github_api.sent[0].content), len(github_api.sent)) == (
        [("core", True), ("core", False)],
        {"title": "t", "key": "k"},
        3,
    )


def test_a_429_with_retry_after_is_retried_once_after_that_wait(github_api: GitHubApiFake) -> None:
    """A rate-limited answer is retried after the wait GitHub asked for."""
    github_api.route(
        "GET",
        "/user",
        github_json({"message": "slow down"}, status=429, headers={"retry-after": "1"}),
        github_json({"login": "octocat"}),
    )
    answer = get_github_session().rest("GET", "/user")
    assert (answer, len(github_api.sent), github_api.waits) == ({"login": "octocat"}, 2, [1.0])


def test_three_502s_raise_the_unread_error_after_the_retries(github_api: GitHubApiFake) -> None:
    """A read that GitHub keeps failing is sent three times, then raises the unread error."""
    github_api.route("GET", "/user", github_json({"message": "Bad Gateway"}, status=502))
    with pytest.raises(GitHubUnreadError) as raised:
        get_github_session().rest("GET", "/user")
    assert (len(github_api.sent), len(github_api.waits), raised.value.details["status"]) == (
        3,
        2,
        502,
    )


def test_a_write_that_gets_a_502_is_not_sent_again(github_api: GitHubApiFake) -> None:
    """GitHub may have applied a write it answered with a 5xx, so the write is not repeated."""
    github_api.route("POST", "/user/keys", github_json({"message": "Bad Gateway"}, status=502))
    with pytest.raises(GitHubUnreadError) as raised:
        get_github_session().rest("POST", "/user/keys", body={"title": "t", "key": "k"})
    assert raised.value.error_code == "GITHUB_UNREAD"
    assert (len(github_api.sent), github_api.waits) == (1, [])


@pytest.mark.parametrize(
    "hops",
    [
        pytest.param([(_PULL, _MOVED, 301)], id="moved-repository"),
        pytest.param([(_PULL, "/repositories/1/pulls/42", 301)], id="relative-location"),
        pytest.param(
            [(_PULL, "https://API.GITHUB.COM:443/repositories/1/pulls/42", 301)],
            id="upper-case-host-and-default-port",
        ),
        pytest.param(
            [
                (_PULL, "/repositories/2/pulls/42", 301),
                ("/repositories/2/pulls/42", _MOVED, 307),
            ],
            id="a-301-then-a-307",
        ),
    ],
)
def test_redirects_on_the_api_origin_are_followed_with_the_token_on_each_hop(
    github_api: GitHubApiFake, pin_github_session: str, hops: list[tuple[str, str, int]]
) -> None:
    """httpx2 follows a redirect that stays on GitHub's API origin, keeping the token."""
    for source, location, status in hops:
        github_api.route("GET", source, github_redirect(location, status=status))
    github_api.route("GET", _MOVED, github_text(_DIFF, media_type=CONST_GITHUB_DIFF_MEDIA_TYPE))
    diff = get_github_session().rest("GET", _PULL, accept=CONST_GITHUB_DIFF_MEDIA_TYPE)
    carried = {(r.headers["authorization"], r.headers["accept"]) for r in github_api.sent}
    assert (diff, carried, len(github_api.sent)) == (
        _DIFF,
        {(f"token {pin_github_session}", CONST_GITHUB_DIFF_MEDIA_TYPE)},
        len(hops) + 1,
    )


@pytest.mark.parametrize(
    "location",
    [
        pytest.param("https://example.com/x", id="another-host"),
        pytest.param("https://api.github.com@example.com/x", id="userinfo-naming-github"),
        pytest.param("https://api.github.com:8443/x", id="another-port"),
        pytest.param("http://api.github.com/repositories/1/pulls/42", id="scheme-downgrade"),
        pytest.param("https://github.com/octo/repo/pull/42.diff", id="github-web-host"),
    ],
)
def test_a_redirect_off_the_api_origin_is_refused_before_it_is_sent(
    github_api: GitHubApiFake, location: str
) -> None:
    """The origin hook stops a hop to any other origin, so the token never leaves the API."""
    github_api.route("GET", _PULL, github_redirect(location, status=302))
    with pytest.raises(GitHubUnreadError) as raised:
        get_github_session().rest("GET", _PULL, accept=CONST_GITHUB_DIFF_MEDIA_TYPE)
    refused = httpx2.URL(location).origin
    named = f"{refused.scheme}://{refused.host}:{refused.port}"
    assert (github_api.requested, named in str(raised.value), github_api.waits) == (
        [f"GET {API}{_PULL}"],
        True,
        [],
    )


def _portal_threads() -> set[threading.Thread]:
    """The threads running an anyio blocking portal's event loop."""
    return {thread for thread in threading.enumerate() if "-portal-" in thread.name}


def _record_clients(monkeypatch: pytest.MonkeyPatch) -> list[httpx2.AsyncClient]:
    """Keep every client a session's transport builds from now on."""
    built: list[httpx2.AsyncClient] = []
    real_session_client = session_transport.session_client

    def recording() -> httpx2.AsyncClient:
        built.append(real_session_client())
        return built[-1]

    monkeypatch.setattr(session_transport, "session_client", recording)
    return built


def test_reset_closes_the_sessions_client_and_portal(
    github_api: GitHubApiFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`reset_github_session()` closes the session's client and stops the event loop thread its
    requests ran on."""
    clients = _record_clients(monkeypatch)
    github_api.route("GET", "/user", github_json({"login": "octocat"}))
    before = _portal_threads()
    get_github_session().rest("GET", "/user")
    opened = _portal_threads() - before
    reset_github_session()
    assert (
        len(opened),
        [thread for thread in opened if thread.is_alive()],
        [client.is_closed for client in clients],
    ) == (1, [], [True])


def test_a_token_change_closes_the_replaced_session(
    github_api: GitHubApiFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the identity changes, the session it replaces is closed, not left running."""
    clients = _record_clients(monkeypatch)
    github_api.route("GET", "/user", github_json({"login": "octocat"}))
    replaced = get_github_session()
    replaced.rest("GET", "/user")
    monkeypatch.setattr(process, "_github_token", "B")
    current = get_github_session()
    assert (current is replaced, [client.is_closed for client in clients]) == (False, [True])


# The child sends one request through the process's session over the fake GitHub API, and again
# through the same session after `reset_github_session()` reopened it, and never closes it: the
# interpreter must still exit. It fakes GitHub as the `github_api` fixture does, through the
# httpx2 client seam, and resolves GitHub's API host to a public address with the web fakes'
# resolver, so its requests are vetted with no DNS, no network and no gh.
_EXITING_CHILD = """
import socket
import time

import httpx2

from devops_cli.core import process
from devops_cli.github import session
from devops_cli.github.rate_limiter import get_github_rate_limiter
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.web_fakes import PUBLIC_ADDRESS, ScriptedResolver

socket.getaddrinfo = ScriptedResolver({"api.github.com": [[PUBLIC_ADDRESS]]}, socket.getaddrinfo)
process._github_token = "child-token"
api = GitHubApiFake()
api.route("GET", "/user", github_json({"login": "octocat"}))
httpx2.AsyncClient = api.client_class()
get_github_rate_limiter().update_quota(
    "core", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
)
held = session.get_github_session()
first = held.rest("GET", "/user")["login"]
session.reset_github_session()
print(first, held.rest("GET", "/user")["login"], flush=True)
"""


@pytest.mark.live("python")
def test_a_process_that_sent_a_request_exits_without_closing_its_session(tmp_path: Path) -> None:
    """A session left open at exit is closed while its event loop thread can still run, so the
    interpreter exits instead of waiting forever on the loop it stopped."""
    stdout_file = tmp_path / "stdout.log"
    with open(stdout_file, "w") as out:
        proc = subprocess.Popen(
            [sys.executable, "-c", _EXITING_CHILD],
            cwd=REPO_ROOT,
            env={**os.environ, "DEVOPS_CLI_DATA_DIR": str(tmp_path)},
            stdout=out,
            stderr=subprocess.PIPE,
            text=True,
        )
    wait_while_running(
        lambda: stdout_file.exists() and "octocat octocat" in stdout_file.read_text(),
        proc,
    )
    proc.wait()
    assert (proc.returncode, stdout_file.read_text()) == (0, "octocat octocat\n")


async def _sleep_on_the_loop(_api: object, seconds: float) -> None:
    """gidgethub's own wait, on the portal's loop."""
    await anyio.sleep(seconds)


def test_closing_a_session_cancels_a_request_waiting_out_a_retry(
    github_api: GitHubApiFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Closing does not wait out a retry's wait: the request is cancelled and fails as unread.

    The retry waits an hour, far past the handoff bound. A close that waited it out would leave
    the caller running when the join gives up, so the test reads no clock (#1902).
    """
    monkeypatch.setattr(session_transport.SessionGitHubAPI, "sleep", _sleep_on_the_loop)
    github_api.route(
        "GET",
        "/user",
        github_json({"message": "slow down"}, status=429, headers={"retry-after": "3600"}),
    )
    session = get_github_session()
    failures: list[BaseException] = []

    def call() -> None:
        try:
            session.rest("GET", "/user")
        except BaseException as error:
            failures.append(error)

    caller = threading.Thread(target=call)
    caller.start()
    sent = wait_until(lambda: bool(github_api.sent))
    session.close()
    caller.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    assert (sent, caller.is_alive(), [type(failure) for failure in failures]) == (
        True,
        False,
        [GitHubUnreadError],
    )


def test_closing_a_session_mid_flight_fails_each_request_with_a_typed_error(
    github_api: GitHubApiFake, clock: ClockFake
) -> None:
    """Requests in flight when the session closes fail with `GitHubUnreadError`, never with the
    closed client's or the stopped loop's own exceptions."""
    github_api.route("GET", "/user", github_json({"login": "octocat"}))
    github_api.delay = 0.005
    session = get_github_session()
    outcomes: list[str] = []

    def call(times: int) -> None:
        for _ in range(times):
            try:
                outcomes.append(session.rest("GET", "/user")["login"])
            except Exception as error:
                outcomes.append(type(error).__name__)

    callers = [threading.Thread(target=call, args=(15,)) for _ in range(4)]
    for caller in callers:
        caller.start()
    clock.sleep(0.03)
    session.close()
    for caller in callers:
        caller.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    session.close()
    assert set(outcomes) <= {"octocat", "GitHubUnreadError"}


def test_the_ledger_is_only_read_and_charged_off_the_event_loop(github_api: GitHubApiFake) -> None:
    """Pacing, charging and the retry wait take the ledger's lock in a worker thread, so a lock
    held through another thread's quota refresh never stalls the session's other requests."""
    github_api.route(
        "GET",
        "/user",
        github_json({"message": "slow down"}, status=429, headers={"retry-after": "1"}),
        github_json({"login": "octocat"}),
    )
    limiter = get_github_rate_limiter()
    threads: set[str] = set()

    def on_the_calling_thread(method: Any) -> Any:
        def record(*args: Any, **kwargs: Any) -> Any:
            threads.add(threading.current_thread().name)
            return method(*args, **kwargs)

        return record

    with ExitStack() as patches:
        for name in ("acquire", "update_quota", "retry_delay", "record_throttle"):
            patches.enter_context(
                patch.object(limiter, name, on_the_calling_thread(getattr(limiter, name)))
            )
        get_github_session().rest("GET", "/user")
    assert threads == {"AnyIO worker thread"}


def test_two_sessions_charge_their_own_identities_ledgers(github_api: GitHubApiFake) -> None:
    """A session paces and charges the ledger of its own identity, not the process identity's."""
    github_api.route("GET", "/user", github_json({"login": "a"}, headers=quota_headers(11)))
    github_api.route("GET", "/user/keys", github_json([], headers=quota_headers(22)))
    for token in ("token-a", "token-b"):
        rate_limiter.identity_rate_limiter(token).update_quota(
            "core", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
        )
    first, second = (
        GitHubSession(GitHubIdentity("token-a")),
        GitHubSession(GitHubIdentity("token-b")),
    )
    try:
        first.rest("GET", "/user")
        second.rest("GET", "/user/keys")
    finally:
        first.close()
        second.close()
    assert (
        rate_limiter.identity_rate_limiter("token-a").get_quota("core").remaining,
        rate_limiter.identity_rate_limiter("token-b").get_quota("core").remaining,
        get_github_rate_limiter().get_quota("core").remaining,
    ) == (11, 22, 5000)


def test_braces_in_a_path_are_sent_as_literal_characters(github_api: GitHubApiFake) -> None:
    """gidgethub expands a path as a URI template; a brace in a file name is still sent."""
    github_api.route(
        "GET", "/repos/octo/repo/contents/a%7Bb%7Dc.txt", github_json({"name": "a{b}c.txt"})
    )
    answer = get_github_session().rest("GET", "/repos/octo/repo/contents/a{b}c.txt")
    assert (answer, github_api.requested) == (
        {"name": "a{b}c.txt"},
        [f"GET {API}/repos/octo/repo/contents/a%7Bb%7Dc.txt"],
    )


def test_the_sessions_requests_are_vetted_at_the_public_egress_level(
    github_api: GitHubApiFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The factory builds the session's client at the public egress level, and a request whose
    host comes to resolve to loopback is refused before anything reaches GitHub's fake."""
    github_api.route("GET", "/user", github_json({"login": "octocat"}))
    scripted_resolver(monkeypatch, {"api.github.com": rebinding(1, "127.0.0.1")})
    session = get_github_session()
    first = session.rest("GET", "/user")
    with pytest.raises(SSRFBlockedError) as raised:
        session.rest("GET", "/user")
    assert raised.value.error_code == "SSRF_BLOCKED"
    assert (first, github_api.levels, len(github_api.sent)) == (
        {"login": "octocat"},
        [EgressLevel.PUBLIC],
        1,
    )


def test_the_sessions_client_waits_a_public_connect_timeout_and_the_factorys_read_timeout(
    github_api: GitHubApiFake,
) -> None:
    """GitHub is reached over the public internet, where a lost SYN is resent after 1 s and a
    TLS handshake on a lossy link takes longer: the factory's 1 s connect timeout, sized for
    local services, made reads fail with `ConnectTimeout` (2026-10-19). The session's client
    connects within `DEFAULT_GH_SESSION_CONNECT_TIMEOUT_SECONDS` and keeps the factory's read
    timeout."""
    from devops_cli.config import defaults

    github_api.route("GET", "/user", github_json({"login": "octocat"}))
    get_github_session().rest("GET", "/user")
    (client,) = github_api.clients
    assert (client.timeout.connect, client.timeout.read) == (
        getattr(defaults, "DEFAULT_GH_SESSION_CONNECT_TIMEOUT_SECONDS", None),
        defaults.DEFAULT_HTTP_TIMEOUT_SECONDS,
    )


def test_a_connect_timeout_raises_the_unread_error_naming_the_endpoint_without_a_retry(
    github_api: GitHubApiFake,
) -> None:
    """A connect that still times out is not retried: it raises the unread error naming the
    endpoint and the cause, after one request."""
    check_runs = "/repos/octo/repo/commits/abc/check-runs?per_page=100"
    github_api.route("GET", check_runs, httpx2.ConnectTimeout)
    with pytest.raises(GitHubUnreadError) as raised:
        list(get_github_session().paginate(check_runs, iterable_key="check_runs"))
    assert (
        raised.value.details["path"],
        f"{check_runs} (page 1): ConnectTimeout" in raised.value.message,
        len(github_api.sent),
    ) == (check_runs, True, 1)


# ── Pagination (#983) ────────────────────────────────────────────────────────────────────────────

_ISSUES = "/repos/octo/repo/issues?state=all&per_page=2"

# How GitHub links one page to the next: by page number, or by an opaque cursor.
_LINK_STYLES = {
    "page-links": (
        "/repositories/1/issues?state=all&per_page=2&page=2",
        "/repositories/1/issues?state=all&per_page=2&page=3",
    ),
    "cursor-links": (
        "/repositories/1/issues?per_page=2&after=Y3Vyc29yOjI",
        "/repositories/1/issues?per_page=2&after=Y3Vyc29yOjQ",
    ),
}


def _page(
    items: list[Any], iterable_key: str | None, *, next_url: str | None = None
) -> httpx2.Response:
    """One page of a listing: a plain array, or an object holding it under `iterable_key`."""
    payload: Any = items if iterable_key is None else {"total_count": 5, iterable_key: items}
    return github_json(payload, headers=next_page(next_url) if next_url else None)


@pytest.mark.parametrize("links", sorted(_LINK_STYLES))
@pytest.mark.parametrize("iterable_key", [None, "check_runs", "workflow_runs", "items"])
def test_linked_pages_yield_one_flat_sequence(
    github_api: GitHubApiFake, links: str, iterable_key: str | None
) -> None:
    """Three pages linked by `rel="next"`, by page or by cursor, read as one listing of items."""
    second, third = _LINK_STYLES[links]
    github_api.route("GET", _ISSUES, _page([{"id": 1}, {"id": 2}], iterable_key, next_url=second))
    github_api.route("GET", second, _page([{"id": 3}, {"id": 4}], iterable_key, next_url=third))
    github_api.route("GET", third, _page([{"id": 5}], iterable_key))
    items = list(get_github_session().paginate(_ISSUES, iterable_key=iterable_key))
    assert (items, github_api.requested) == (
        [{"id": n} for n in range(1, 6)],
        [f"GET {API}{_ISSUES}", f"GET {API}{second}", f"GET {API}{third}"],
    )


def test_a_short_listing_is_one_request(github_api: GitHubApiFake) -> None:
    """A page without `rel="next"` is the last one."""
    github_api.route("GET", _ISSUES, _page([{"id": 1}], None))
    assert (list(get_github_session().paginate(_ISSUES)), len(github_api.sent)) == ([{"id": 1}], 1)


def test_an_empty_page_ends_the_listing(github_api: GitHubApiFake) -> None:
    """`[]` ends a listing, even when GitHub still links a next page."""
    github_api.route("GET", _ISSUES, _page([], None, next_url=_LINK_STYLES["page-links"][0]))
    assert (list(get_github_session().paginate(_ISSUES)), len(github_api.sent)) == ([], 1)


def test_a_consumer_that_stops_after_the_first_item_sends_one_request(
    github_api: GitHubApiFake,
) -> None:
    """Pages are read as the consumer asks for items, so one that stops early asks for no more."""
    second = _LINK_STYLES["page-links"][0]
    github_api.route("GET", _ISSUES, _page([{"id": 1}, {"id": 2}], None, next_url=second))
    github_api.route("GET", second, _page([{"id": 3}], None))
    first = next(iter(get_github_session().paginate(_ISSUES)))
    assert (first, len(github_api.sent)) == ({"id": 1}, 1)


def test_a_listing_that_runs_past_the_page_cap_fails_closed(
    github_api: GitHubApiFake,
) -> None:
    """A `rel="next"` chain that never ends stops at the page cap, read when the listing runs,
    and raises naming the endpoint and the cap instead of reading forever."""
    second, third = _LINK_STYLES["page-links"]
    github_api.route("GET", _ISSUES, _page([{"id": 1}], None, next_url=second))
    github_api.route("GET", second, _page([{"id": 2}], None, next_url=third))
    github_api.route("GET", third, _page([{"id": 3}], None, next_url=second))
    read: list[Any] = []
    with pytest.raises(GitHubUnreadError) as raised:
        read.extend(get_github_session().paginate(_ISSUES, max_pages=2))
    details = raised.value.details
    assert (
        read,
        len(github_api.sent),
        details["path"],
        details["max_pages"],
        "runs past 2 pages" in str(raised.value),
    ) == ([{"id": 1}, {"id": 2}], 2, _ISSUES, 2, True)


def test_a_listing_of_exactly_the_page_cap_reads_every_page(
    github_api: GitHubApiFake,
) -> None:
    """A listing whose last page falls on the cap is read whole."""
    second = _LINK_STYLES["page-links"][0]
    github_api.route("GET", _ISSUES, _page([{"id": 1}], None, next_url=second))
    github_api.route("GET", second, _page([{"id": 2}], None))
    items = list(get_github_session().paginate(_ISSUES, max_pages=2))
    assert (items, len(github_api.sent)) == ([{"id": 1}, {"id": 2}], 2)


def test_a_link_to_another_origin_is_refused_before_it_is_sent(github_api: GitHubApiFake) -> None:
    """A `Link` naming another origin is refused by the origin hook, so the token never goes
    there: the transport sees no request to it."""
    github_api.route(
        "GET",
        _ISSUES,
        _page([{"id": 1}], None, next_url="https://example.com/repos/octo/repo/issues?page=2"),
    )
    read: list[Any] = []
    with pytest.raises(GitHubUnreadError) as raised:
        read.extend(get_github_session().paginate(_ISSUES))
    assert (read, github_api.requested, "https://example.com:443" in str(raised.value)) == (
        [{"id": 1}],
        [f"GET {API}{_ISSUES}"],
        True,
    )


@pytest.mark.parametrize(
    ("second_page", "iterable_key"),
    [
        pytest.param(
            httpx2.Response(
                200, headers={"content-type": "text/html; charset=utf-8"}, content=b"<html></html>"
            ),
            None,
            id="html",
        ),
        pytest.param(github_json({"message": "Server Error"}), None, id="error-object"),
        pytest.param(
            github_json({"message": "Server Error"}), "check_runs", id="error-object-wrapped"
        ),
        pytest.param(
            httpx2.Response(200, headers={"content-type": JSON_TYPE}, content=b'[{"id": 3'),
            None,
            id="truncated",
        ),
        pytest.param(httpx2.Response(200, headers={"content-type": JSON_TYPE}), None, id="empty"),
    ],
)
def test_a_page_that_is_no_list_of_items_fails_closed(
    github_api: GitHubApiFake, second_page: httpx2.Response, iterable_key: str | None
) -> None:
    """A page that is not the listing's array raises `GitHubUnreadError` naming the endpoint and
    the page, rather than a string's characters or a dict's keys being read as items."""
    second = _LINK_STYLES["page-links"][0]
    github_api.route("GET", _ISSUES, _page([{"id": 1}], iterable_key, next_url=second))
    github_api.route("GET", second, second_page)
    read: list[Any] = []
    with pytest.raises(GitHubUnreadError) as raised:
        read.extend(get_github_session().paginate(_ISSUES, iterable_key=iterable_key))
    details = raised.value.details
    assert (read, details["path"], details["page"], "page 2" in str(raised.value)) == (
        [{"id": 1}],
        _ISSUES,
        2,
        True,
    )


# ── Conditional requests (#983) ──────────────────────────────────────────────────────────────────

_ETAG = 'W/"0a953aa2"'
_LATER_ETAG = 'W/"5c6521e1"'
_KEYS = "/user/ssh_signing_keys"


def _conditions(github_api: GitHubApiFake) -> list[str | None]:
    """The `If-None-Match` of each request the fake received, None where it sent none."""
    return [request.headers.get("if-none-match") for request in github_api.sent]


def _tagged_page(items: list[Any], etag: str, *, next_url: str | None = None) -> httpx2.Response:
    """One page of a plain listing, carrying `etag`."""
    links = next_page(next_url) if next_url else {}
    return github_json(items, headers={"etag": etag, **links})


def test_a_second_get_of_a_url_sends_the_etag_it_was_answered_with(
    github_api: GitHubApiFake,
) -> None:
    """The session keeps a GET's ETag and makes the next GET of that URL conditional on it."""
    github_api.route("GET", "/user", github_json({"login": "octocat"}, headers={"etag": _ETAG}))
    session = get_github_session()
    answers = [session.rest("GET", "/user") for _ in range(2)]
    assert (answers, _conditions(github_api)) == ([{"login": "octocat"}] * 2, [None, _ETAG])


def test_a_304_answers_with_the_stored_body_paced_and_charged_with_the_quota_it_reports(
    github_api: GitHubApiFake,
) -> None:
    """A 304 gives back the body stored with its ETag; it still waits its turn on the ledger,
    which keeps the `x-ratelimit-remaining` the 304 reported."""
    github_api.route(
        "GET",
        "/user",
        github_json({"login": "octocat"}, headers={"etag": _ETAG, **quota_headers(4934)}),
        httpx2.Response(304, headers={"etag": _ETAG, **quota_headers(4930)}),
    )
    limiter = get_github_rate_limiter()
    session = get_github_session()
    with patch.object(limiter, "acquire", wraps=limiter.acquire) as acquire:
        answers = [session.rest("GET", "/user") for _ in range(2)]
    assert (answers, acquire.call_count, limiter.get_quota("core").remaining) == (
        [{"login": "octocat"}] * 2,
        2,
        4930,
    )


def test_a_session_over_another_token_sends_no_etag_for_the_same_url(
    github_api: GitHubApiFake,
) -> None:
    """Each session keeps its own ETags, so one identity's are never sent as another's."""
    github_api.route("GET", "/user", github_json({"login": "a"}, headers={"etag": _ETAG}))
    for token in ("token-a", "token-b"):
        rate_limiter.identity_rate_limiter(token).update_quota(
            "core", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
        )
    first, second = (
        GitHubSession(GitHubIdentity("token-a")),
        GitHubSession(GitHubIdentity("token-b")),
    )
    try:
        first.rest("GET", "/user")
        second.rest("GET", "/user")
        first.rest("GET", "/user")
    finally:
        first.close()
        second.close()
    assert _conditions(github_api) == [None, None, _ETAG]


def test_a_post_stores_nothing(github_api: GitHubApiFake) -> None:
    """A write's answer is never kept, so neither another write nor a read of its URL is made
    conditional on it."""
    github_api.route("POST", _KEYS, github_json({"id": 1}, status=201, headers={"etag": _ETAG}))
    github_api.route("GET", _KEYS, github_json([], headers={"etag": _LATER_ETAG}))
    session = get_github_session()
    session.rest("POST", _KEYS, body={"title": "t", "key": "k"})
    session.rest("POST", _KEYS, body={"title": "t", "key": "k"})
    session.rest("GET", _KEYS)
    assert _conditions(github_api) == [None, None, None]


def test_a_conditional_get_retried_after_a_502_still_answers_from_its_etag(
    github_api: GitHubApiFake,
) -> None:
    """A retry sends the same `If-None-Match`, and its 304 gives back the stored body."""
    github_api.route(
        "GET",
        "/user",
        github_json({"login": "octocat"}, headers={"etag": _ETAG}),
        github_json({"message": "Server Error"}, status=502),
        github_json({"login": "octocat"}, headers={"etag": _ETAG}),
    )
    session = get_github_session()
    answers = [session.rest("GET", "/user") for _ in range(2)]
    assert (answers, _conditions(github_api), len(github_api.waits)) == (
        [{"login": "octocat"}] * 2,
        [None, _ETAG, _ETAG],
        1,
    )


def test_a_caller_that_changes_an_answer_leaves_the_stored_one_as_github_sent_it(
    github_api: GitHubApiFake,
) -> None:
    """Every read gets its own copy, so what one caller changes is never what a 304 gives back."""
    github_api.route(
        "GET",
        "/user",
        github_json({"login": "octocat"}, headers={"etag": _ETAG}),
        httpx2.Response(304, headers={"etag": _ETAG}),
    )
    session = get_github_session()
    session.rest("GET", "/user")["login"] = "changed"
    assert session.rest("GET", "/user") == {"login": "octocat"}


def test_the_session_keeps_the_etags_of_its_latest_reads_only(
    github_api: GitHubApiFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ETag store is bounded: past `DEFAULT_GH_SESSION_ETAG_CACHE_SIZE` URLs, the one read
    longest ago is dropped and read in full again."""
    monkeypatch.setattr(session_transport, "DEFAULT_GH_SESSION_ETAG_CACHE_SIZE", 1)
    github_api.route("GET", "/user", github_json({"login": "octocat"}, headers={"etag": _ETAG}))
    github_api.route("GET", _KEYS, github_json([], headers={"etag": _LATER_ETAG}))
    session = get_github_session()
    for path in ("/user", _KEYS, "/user", "/user"):
        session.rest("GET", path)
    assert _conditions(github_api) == [None, None, None, _ETAG]


def test_a_page_answered_from_its_etag_keeps_its_next_link_and_the_last_page_is_read_in_full(
    github_api: GitHubApiFake,
) -> None:
    """A 304 for a page gives back its items and the next link stored with them; a page that
    linked no next one is read in full, since its 304 could not show a next page added since."""
    second = _LINK_STYLES["page-links"][0]
    github_api.route("GET", _ISSUES, _tagged_page([{"id": 1}, {"id": 2}], _ETAG, next_url=second))
    github_api.route("GET", second, _tagged_page([{"id": 3}], _LATER_ETAG))
    session = get_github_session()
    listings = [list(session.paginate(_ISSUES)) for _ in range(2)]
    assert (listings, _conditions(github_api)) == (
        [[{"id": 1}, {"id": 2}, {"id": 3}]] * 2,
        [None, None, _ETAG, None],
    )


def test_a_one_page_listing_leaves_nothing_stored(github_api: GitHubApiFake) -> None:
    """A page that links no next one is not kept once it is read, so a later GET of its URL is
    sent in full."""
    github_api.route("GET", _ISSUES, _tagged_page([{"id": 1}], _ETAG))
    session = get_github_session()
    list(session.paginate(_ISSUES))
    session.rest("GET", _ISSUES)
    assert _conditions(github_api) == [None, None]


def test_a_listing_reads_in_full_a_last_page_a_rest_get_stored(github_api: GitHubApiFake) -> None:
    """A `rest` GET keeps its answer, which links no next page; a listing of that URL still
    reads it in full, so a next page added since is read on to."""
    second = _LINK_STYLES["page-links"][0]
    github_api.route(
        "GET",
        _ISSUES,
        _tagged_page([{"id": 1}, {"id": 2}], _ETAG),
        _tagged_page([{"id": 1}, {"id": 2}], _ETAG, next_url=second),
    )
    github_api.route("GET", second, _page([{"id": 3}], None))
    session = get_github_session()
    session.rest("GET", _ISSUES)
    listing = list(session.paginate(_ISSUES))
    assert (listing, _conditions(github_api)) == (
        [{"id": 1}, {"id": 2}, {"id": 3}],
        [None, None, None],
    )


def test_one_page_listings_leave_the_store_to_pages_that_can_answer_304(
    github_api: GitHubApiFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With room for three answers, three one-page listings read between two reads of a
    two-page listing leave its first page stored, so the second read sends it conditionally."""
    monkeypatch.setattr(session_transport, "DEFAULT_GH_SESSION_ETAG_CACHE_SIZE", 3)
    second = _LINK_STYLES["page-links"][0]
    github_api.route("GET", _ISSUES, _tagged_page([{"id": 1}, {"id": 2}], _ETAG, next_url=second))
    github_api.route("GET", second, _tagged_page([{"id": 3}], _LATER_ETAG))
    comments = [f"/repos/octo/repo/issues/{number}/comments" for number in range(3)]
    for number, path in enumerate(comments):
        github_api.route("GET", path, _tagged_page([], f'W/"c{number}"'))
    session = get_github_session()
    for path in (_ISSUES, *comments, _ISSUES):
        list(session.paginate(path))
    first_pages = [request for request in github_api.sent if request.url == f"{API}{_ISSUES}"]
    assert [request.headers.get("if-none-match") for request in first_pages] == [None, _ETAG]


def test_a_last_page_that_gains_a_next_page_is_read_on_to_it(github_api: GitHubApiFake) -> None:
    """GitHub's ETag covers a page's body only, so a full last page keeps its ETag when a next
    page is added after it; the listing still reads the new page."""
    second = _LINK_STYLES["page-links"][0]
    github_api.route(
        "GET",
        _ISSUES,
        _tagged_page([{"id": 1}, {"id": 2}], _ETAG),
        _tagged_page([{"id": 1}, {"id": 2}], _ETAG, next_url=second),
    )
    github_api.route("GET", second, _page([{"id": 3}], None))
    session = get_github_session()
    listings = [list(session.paginate(_ISSUES)) for _ in range(2)]
    assert listings == [[{"id": 1}, {"id": 2}], [{"id": 1}, {"id": 2}, {"id": 3}]]


def test_a_page_answered_from_its_etag_that_is_no_list_of_items_still_fails_closed(
    github_api: GitHubApiFake,
) -> None:
    """The stored body of a 304 goes through the same check as a fresh page: an error object
    is never read as a listing."""
    second = _LINK_STYLES["page-links"][0]
    error_page = github_json(
        {"message": "Server Error"}, headers={"etag": _ETAG, **next_page(second)}
    )
    github_api.route("GET", _ISSUES, error_page)
    session = get_github_session()
    pages = []
    for _ in range(2):
        with pytest.raises(GitHubUnreadError) as unread:
            list(session.paginate(_ISSUES))
        pages.append(unread.value.details["page"])
    assert (pages, _conditions(github_api)) == ([1, 1], [None, _ETAG])
