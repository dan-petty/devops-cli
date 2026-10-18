"""Tests for the process's one GitHub session (#767)."""

from __future__ import annotations

import ast
import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx2
import pytest

from devops_cli.ai.review import runner
from devops_cli.commands import analyze
from devops_cli.commands.gh import _get_github_client
from devops_cli.commands.repos import _require_client
from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_GITHUB_API_VERSION,
    CONST_GITHUB_DIFF_MEDIA_TYPE,
    CONST_GITHUB_USER_AGENT,
)
from devops_cli.core import process
from devops_cli.exceptions.git import (
    GitHubOperationError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.github import ssh
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.github.session import get_github_session, reset_github_session
from tests.github_session_fakes import (
    API,
    GitHubApiFake,
    github_json,
    github_redirect,
    github_text,
    quota_headers,
)

_SRC = Path(__file__).resolve().parents[1] / "src" / "devops_cli"


def _gh_answers(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    """A finished child, as `subprocess.run` returns it."""
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


class _RecordedGithub:
    """Stands in for PyGithub's `Github`, keeping the token it was built with."""

    def __init__(self, *, auth: Any) -> None:
        self.token = auth.token


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


def test_login_is_read_once_from_get_user() -> None:
    """`session.login` asks `GET /user` the first time it is read, then keeps the answer."""
    get_github_rate_limiter().update_quota(
        "core", remaining=5000, limit=5000, reset_epoch=time.time() + 60.0
    )
    session = get_github_session()
    with patch("subprocess.run", return_value=_gh_answers("octocat\n")) as run:
        logins = (session.login, session.login)
    gh_calls = [call.args[0] for call in run.call_args_list if call.args[0][0] == CONST_GH_CLI]
    assert (logins, gh_calls) == (
        ("octocat", "octocat"),
        [[CONST_GH_CLI, "api", "user", "--jq", ".login"]],
    )


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


def test_pygithub_is_built_only_by_the_session() -> None:
    """`GitHubClient(...)` is called in one place in src: the session module."""
    constructions = [
        call for path in sorted(_SRC.rglob("*.py")) for call in _github_client_calls(path)
    ]
    assert constructions == ["github/session.py"]


def _repos_client() -> Any:
    return _require_client()


def _gh_command_client() -> Any:
    return _get_github_client()


def _review_client() -> Any:
    """The client `_prepare_pr_content`, which `devops review pr` runs, fetches the PR with."""
    used: list[Any] = []

    def record(client: Any, *_: Any) -> None:
        used.append(client)
        raise RuntimeError("stop")

    with (
        patch("devops_cli.github.client.GitHubClient.get_pull", autospec=True, side_effect=record),
        pytest.raises(RuntimeError, match="stop"),
    ):
        runner._prepare_pr_content(7, "octo/repo")
    return used[0]


def _ssh_client() -> Any:
    """The client SSH key registration falls back to when gh cannot register the key."""
    used: list[Any] = []
    with (
        patch.object(ssh, "_register_with_gh", return_value=False),
        patch.object(ssh, "_add_signing_key"),
        patch(
            "devops_cli.github.client.GitHubClient.get_user_ssh_keys",
            autospec=True,
            side_effect=lambda client: used.append(client) or [],
        ),
        patch("devops_cli.github.client.GitHubClient.add_user_ssh_key"),
    ):
        ssh.register_key_on_github("ssh-ed25519 AAAA key", "title")
    return used[0]


def _analyze_client() -> Any:
    """The client `devops analyze pr` reads the pull request with."""
    used: list[Any] = []

    def record(client: Any, *_: Any) -> None:
        used.append(client)
        raise RuntimeError("stop")

    with (
        patch.object(analyze, "find_repo_root", return_value=Path.cwd()),
        patch.object(analyze, "get_repo_origin_name", return_value="octo/repo"),
        patch("devops_cli.github.client.GitHubClient.get_pull", autospec=True, side_effect=record),
        pytest.raises(RuntimeError, match="stop"),
    ):
        analyze.analyze_pr(pr_number=7, enhanced=False, update_all=False, explain=False)
    return used[0]


@pytest.mark.parametrize(
    "client_of",
    [_repos_client, _gh_command_client, _review_client, _ssh_client, _analyze_client],
    ids=["repos", "gh", "review", "ssh", "analyze"],
)
def test_every_pygithub_caller_uses_the_session_client(
    client_of: Any, pin_github_session: str
) -> None:
    """repos, review, analyze, ssh and `devops gh` use the session's client and its token."""
    with patch("github.Github", _RecordedGithub):
        client = client_of()
        session_client = get_github_session().client
    assert (client is session_client, client._gh.token) == (True, pin_github_session)


def test_a_failed_lookup_stops_a_pygithub_caller_with_the_unauthenticated_error(
    no_github_identity: None,
) -> None:
    """No client is built without the session's token, and nothing falls back to another one."""
    built = MagicMock()
    with patch("github.Github", built), pytest.raises(GitHubOperationError):
        _ = get_github_session().client
    assert built.call_count == 0


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
    with pytest.raises(GitHubUnreadError):
        get_github_session().rest("POST", "/user/keys", body={"title": "t", "key": "k"})
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
        # A deliberate exception to the bare example.com rule for mock hosts: only a subdomain
        # can begin with GitHub's API host name, which is the look-alike this case refuses.
        pytest.param("https://api.github.com.example.com/x", id="look-alike-host"),
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


def test_reset_closes_the_sessions_client_and_portal(github_api: GitHubApiFake) -> None:
    """`reset_github_session()` stops the event loop thread the session's requests ran on."""
    github_api.route("GET", "/user", github_json({"login": "octocat"}))
    before = _portal_threads()
    get_github_session().rest("GET", "/user")
    opened = _portal_threads() - before
    reset_github_session()
    assert (len(opened), [thread for thread in opened if thread.is_alive()]) == (1, [])
