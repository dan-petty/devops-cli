"""Unit tests for GitHub SSH and signing key registration module."""

from __future__ import annotations

import json
import re
import subprocess
from contextlib import nullcontext
from unittest.mock import MagicMock

import httpx2
import pytest

from devops_cli.exceptions.git import (
    GitHubRateLimitError,
    GitHubScopeError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.github.session import GitHubSession, get_github_session
from devops_cli.github.ssh import (
    SSHRegistrationError,
    _add_signing_key,
    _gh_add_key,
    _gh_auth_ok,
    _gh_list_keys,
    _register_with_gh,
    _register_with_token_api,
    register_key_on_github,
)
from tests.github_session_fakes import GitHubApiFake, github_json


def test_register_key_on_github_via_gh_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify register_key_on_github succeeds when GitHub CLI auth is available."""
    called_gh = False

    def mock_register_with_gh(pub_key: str, title: str) -> bool:
        nonlocal called_gh
        called_gh = True
        return True

    monkeypatch.setattr("devops_cli.github.ssh._register_with_gh", mock_register_with_gh)
    register_key_on_github("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA test@example.com", "My Key")
    assert called_gh is True


def test_register_key_on_github_via_token(
    monkeypatch: pytest.MonkeyPatch, pin_github_session: str
) -> None:
    """Verify register_key_on_github falls back to the token API with the session's token."""
    monkeypatch.setattr("devops_cli.github.ssh._register_with_gh", lambda pub, t: False)
    called_token = False

    def mock_token_api(session: GitHubSession, pub: str, t: str) -> None:
        nonlocal called_token
        called_token = session.token == pin_github_session

    monkeypatch.setattr("devops_cli.github.ssh._register_with_token_api", mock_token_api)
    register_key_on_github("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA test@example.com", "My Key")
    assert called_token is True


def test_register_key_on_github_no_auth(
    monkeypatch: pytest.MonkeyPatch, no_github_identity: None
) -> None:
    """Verify SSHRegistrationError is raised when neither gh nor the session can register."""
    monkeypatch.setattr("devops_cli.github.ssh._register_with_gh", lambda pub, t: False)
    with pytest.raises(SSHRegistrationError, match="gh auth login"):
        register_key_on_github("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA test@example.com", "My Key")


def test_gh_auth_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _gh_auth_ok evaluates gh auth status return code."""
    mock_run = MagicMock(returncode=0)
    monkeypatch.setattr("devops_cli.github.ssh.run_gh", lambda *args, **kwargs: mock_run)
    assert _gh_auth_ok() is True

    mock_run_fail = MagicMock(returncode=1)
    monkeypatch.setattr("devops_cli.github.ssh.run_gh", lambda *args, **kwargs: mock_run_fail)
    assert _gh_auth_ok() is False

    def mock_raise(*args, **kwargs):
        raise FileNotFoundError("gh not found")

    monkeypatch.setattr("devops_cli.github.ssh.run_gh", mock_raise)
    assert _gh_auth_ok() is False


def test_gh_list_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _gh_list_keys parses key lists from JSON output."""
    mock_success = MagicMock(
        returncode=0,
        stdout=json.dumps(
            [
                {"key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA1111 comment1"},
                {"key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAA2222 comment2"},
                {"invalid": 123},
            ]
        ),
    )
    monkeypatch.setattr("devops_cli.github.ssh.run_gh", lambda *args, **kwargs: mock_success)
    keys = _gh_list_keys("/user/keys")
    assert keys is not None
    assert "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA1111" in keys
    assert "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAA2222" in keys

    # Non-zero returncode
    mock_fail = MagicMock(returncode=1, stdout="")
    monkeypatch.setattr("devops_cli.github.ssh.run_gh", lambda *args, **kwargs: mock_fail)
    assert _gh_list_keys("/user/keys") is None

    # Invalid JSON
    mock_bad_json = MagicMock(returncode=0, stdout="not-json")
    monkeypatch.setattr("devops_cli.github.ssh.run_gh", lambda *args, **kwargs: mock_bad_json)
    assert _gh_list_keys("/user/keys") is None

    # Non-list payload
    mock_dict_json = MagicMock(returncode=0, stdout=json.dumps({"message": "error"}))
    monkeypatch.setattr("devops_cli.github.ssh.run_gh", lambda *args, **kwargs: mock_dict_json)
    assert _gh_list_keys("/user/keys") is None

    # Exception raised
    def mock_exc(*args, **kwargs):
        raise OSError("Subprocess failure")

    monkeypatch.setattr("devops_cli.github.ssh.run_gh", mock_exc)
    assert _gh_list_keys("/user/keys") is None


_KEY = "ssh-ed25519 AAAAC3 test@example.com"
_KEY_IN_USE = json.dumps(
    {
        "message": "Validation Failed",
        "errors": [
            {
                "resource": "PublicKey",
                "code": "custom",
                "field": "key",
                "message": "key is already in use",
            }
        ],
    }
)
_SCOPE_SUGGESTION = (
    "gh: Not Found (HTTP 404)\n"
    'gh: This API operation needs the "admin:public_key" scope. To request it, run:  '
    "gh auth refresh -h github.com -s admin:public_key"
)


@pytest.mark.parametrize(
    ("answer", "message", "cause"),
    [
        pytest.param((0, "{}", ""), None, None, id="added"),
        pytest.param(
            (1, _KEY_IN_USE, "gh: Validation Failed (HTTP 422)"), None, None, id="registered"
        ),
        pytest.param(
            (1, "", _SCOPE_SUGGESTION),
            "GitHub CLI auth is missing required scopes",
            GitHubScopeError,
            id="missing-scope",
        ),
        pytest.param(
            (1, "", "gh: API rate limit exceeded for user ID 1. (HTTP 403)"),
            "API rate limit exceeded for user ID 1.",
            GitHubRateLimitError,
            id="rate-limited",
        ),
        pytest.param(
            (1, "", "gh: Bad credentials (HTTP 401)"),
            "gh: Bad credentials (HTTP 401)",
            GitHubUnauthenticatedError,
            id="token-refused",
        ),
        pytest.param(
            (1, "", "gh: Server Error (HTTP 500)"), "gh: Server Error (HTTP 500)", None, id="other"
        ),
    ],
)
def test_gh_add_key_reads_gh_s_failure_through_the_classifier(
    monkeypatch: pytest.MonkeyPatch,
    answer: tuple[int, str, str],
    message: str | None,
    cause: type[Exception] | None,
) -> None:
    """A key gh adds, or one GitHub answers 422 for (already registered), is done. A missing
    scope asks for the scopes, and any other failure raises gh's text; a failure the gh
    classifier names is the raised error's cause (#983)."""
    added = subprocess.CompletedProcess(["gh", "api"], *answer)
    monkeypatch.setattr("devops_cli.github.ssh.run_gh", lambda *args, **kwargs: added)
    if message is None:
        _gh_add_key("/user/keys", _KEY, "Title")
        return
    with pytest.raises(SSHRegistrationError, match=re.escape(message)) as raised:
        _gh_add_key("/user/keys", _KEY, "Title")
    assert type(raised.value.__cause__) is (type(None) if cause is None else cause)


def test_gh_add_key_reports_a_gh_that_could_not_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """gh failing to start is a registration failure naming the reason."""

    def mock_raise(*args: object, **kwargs: object) -> None:
        raise subprocess.SubprocessError("Subprocess died")

    monkeypatch.setattr("devops_cli.github.ssh.run_gh", mock_raise)
    with pytest.raises(SSHRegistrationError, match="GitHub CLI key registration failed"):
        _gh_add_key("/user/keys", _KEY, "Title")


def test_register_with_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _register_with_gh registers keys when gh auth is OK."""
    monkeypatch.setattr("devops_cli.github.ssh._gh_auth_ok", lambda: False)
    assert _register_with_gh("ssh-ed25519 AAAAC3", "Title") is False

    monkeypatch.setattr("devops_cli.github.ssh._gh_auth_ok", lambda: True)
    monkeypatch.setattr("devops_cli.github.ssh._gh_list_keys", lambda ep: set())
    added: list[str] = []
    monkeypatch.setattr("devops_cli.github.ssh._gh_add_key", lambda ep, pub, t: added.append(ep))

    assert _register_with_gh("ssh-ed25519 AAAAC3 test@example.com", "Title") is True
    assert "/user/keys" in added
    assert "/user/ssh_signing_keys" in added


def test_register_with_token_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _register_with_token_api uses the session's client and token."""
    mock_client = MagicMock()
    mock_existing_key = MagicMock()
    mock_existing_key.key = "ssh-rsa OTHERKEY"
    mock_client.get_user_ssh_keys.return_value = [mock_existing_key]

    session = GitHubSession("FAKE-session-token")
    monkeypatch.setitem(session.__dict__, "client", mock_client)
    signing_called = False

    def mock_signing(signing_session: GitHubSession, pub: str, t: str) -> None:
        nonlocal signing_called
        signing_called = signing_session is session

    monkeypatch.setattr("devops_cli.github.ssh._add_signing_key", mock_signing)
    _register_with_token_api(
        session, "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA test@example.com", "Title"
    )

    mock_client.add_user_ssh_key.assert_called_once()
    assert signing_called is True


@pytest.mark.parametrize(
    ("answer", "raised"),
    [
        pytest.param(github_json({"id": 1}, status=201), None, id="registered"),
        pytest.param(
            github_json(
                {
                    "message": "Validation Failed",
                    "errors": [{"code": "custom", "field": "key", "message": "key is in use"}],
                },
                status=422,
            ),
            None,
            id="already-registered",
        ),
        pytest.param(
            github_json(
                {"message": "Forbidden"},
                status=403,
                headers={
                    "x-oauth-scopes": "repo",
                    "x-accepted-oauth-scopes": "write:ssh_signing_key",
                },
            ),
            GitHubScopeError,
            id="missing-scope",
        ),
        pytest.param(
            github_json({"message": "Server Error"}, status=500), GitHubUnreadError, id="5xx"
        ),
    ],
)
def test_add_signing_key(
    github_api: GitHubApiFake,
    pin_github_session: str,
    answer: httpx2.Response,
    raised: type[Exception] | None,
) -> None:
    """The signing key is one session POST; a 422 means it is already registered."""
    github_api.route("POST", "/user/ssh_signing_keys", answer)
    with pytest.raises(raised) if raised else nullcontext():
        _add_signing_key(get_github_session(), "ssh-ed25519 AAAAC3", "Title")
    sent = github_api.sent[0]
    assert (json.loads(sent.content), sent.headers["authorization"], len(github_api.sent)) == (
        {"title": "Title", "key": "ssh-ed25519 AAAAC3"},
        f"token {pin_github_session}",
        1,
    )
