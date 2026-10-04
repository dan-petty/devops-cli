"""Tests for the process's one GitHub session (#767)."""

from __future__ import annotations

import ast
import subprocess
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review import runner
from devops_cli.commands import analyze
from devops_cli.commands.gh import _get_github_client
from devops_cli.commands.repos import _require_client
from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.core import process
from devops_cli.exceptions.git import GitHubOperationError, GitHubUnauthenticatedError
from devops_cli.github import ssh
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.github.session import get_github_session, reset_github_session

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
