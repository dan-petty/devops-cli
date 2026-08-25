"""Unit tests for GitHub SSH and signing key registration module."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock

import pytest

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


def test_register_key_on_github_via_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify register_key_on_github falls back to token API when gh CLI is unavailable."""
    monkeypatch.setattr("devops_cli.github.ssh._register_with_gh", lambda pub, t: False)
    called_token = False

    def mock_token_api(token: str, pub: str, t: str) -> None:
        nonlocal called_token
        called_token = True

    monkeypatch.setattr("devops_cli.github.ssh._register_with_token_api", mock_token_api)
    register_key_on_github(
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA test@example.com", "My Key", token="ghp_secret"
    )
    assert called_token is True


def test_register_key_on_github_no_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify SSHRegistrationError is raised when neither gh CLI nor token is provided."""
    monkeypatch.setattr("devops_cli.github.ssh._register_with_gh", lambda pub, t: False)
    with pytest.raises(SSHRegistrationError, match="No usable GitHub auth found"):
        register_key_on_github("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA test@example.com", "My Key")


def test_gh_auth_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _gh_auth_ok evaluates gh auth status return code."""
    mock_run = MagicMock(returncode=0)
    monkeypatch.setattr("devops_cli.github.ssh.run_subprocess", lambda *args, **kwargs: mock_run)
    assert _gh_auth_ok() is True

    mock_run_fail = MagicMock(returncode=1)
    monkeypatch.setattr(
        "devops_cli.github.ssh.run_subprocess", lambda *args, **kwargs: mock_run_fail
    )
    assert _gh_auth_ok() is False

    def mock_raise(*args, **kwargs):
        raise FileNotFoundError("gh not found")

    monkeypatch.setattr("devops_cli.github.ssh.run_subprocess", mock_raise)
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
    monkeypatch.setattr(
        "devops_cli.github.ssh.run_subprocess", lambda *args, **kwargs: mock_success
    )
    keys = _gh_list_keys("/user/keys")
    assert keys is not None
    assert "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA1111" in keys
    assert "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAA2222" in keys

    # Non-zero returncode
    mock_fail = MagicMock(returncode=1, stdout="")
    monkeypatch.setattr("devops_cli.github.ssh.run_subprocess", lambda *args, **kwargs: mock_fail)
    assert _gh_list_keys("/user/keys") is None

    # Invalid JSON
    mock_bad_json = MagicMock(returncode=0, stdout="not-json")
    monkeypatch.setattr(
        "devops_cli.github.ssh.run_subprocess", lambda *args, **kwargs: mock_bad_json
    )
    assert _gh_list_keys("/user/keys") is None

    # Non-list payload
    mock_dict_json = MagicMock(returncode=0, stdout=json.dumps({"message": "error"}))
    monkeypatch.setattr(
        "devops_cli.github.ssh.run_subprocess", lambda *args, **kwargs: mock_dict_json
    )
    assert _gh_list_keys("/user/keys") is None

    # Exception raised
    def mock_exc(*args, **kwargs):
        raise OSError("Subprocess failure")

    monkeypatch.setattr("devops_cli.github.ssh.run_subprocess", mock_exc)
    assert _gh_list_keys("/user/keys") is None


def test_gh_add_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _gh_add_key handles success, existing key, missing scope, and failure."""
    # 1. Success
    mock_ok = MagicMock(returncode=0, stdout="{}", stderr="")
    monkeypatch.setattr("devops_cli.github.ssh.run_subprocess", lambda *args, **kwargs: mock_ok)
    _gh_add_key("/user/keys", "ssh-ed25519 AAAAC3 test@example.com", "Title")

    # 2. Already exists
    mock_exists = MagicMock(returncode=1, stdout="", stderr="key already exists")
    monkeypatch.setattr("devops_cli.github.ssh.run_subprocess", lambda *args, **kwargs: mock_exists)
    _gh_add_key("/user/keys", "ssh-ed25519 AAAAC3 test@example.com", "Title")

    # 3. Missing scope
    mock_scope = MagicMock(returncode=1, stdout="", stderr="needs the admin:public_key scope")
    monkeypatch.setattr("devops_cli.github.ssh.run_subprocess", lambda *args, **kwargs: mock_scope)
    with pytest.raises(SSHRegistrationError, match="GitHub CLI auth is missing required scopes"):
        _gh_add_key("/user/keys", "ssh-ed25519 AAAAC3 test@example.com", "Title")

    # 4. Generic error
    mock_err = MagicMock(returncode=1, stdout="", stderr="API rate limit exceeded")
    monkeypatch.setattr("devops_cli.github.ssh.run_subprocess", lambda *args, **kwargs: mock_err)
    with pytest.raises(SSHRegistrationError, match="API rate limit exceeded"):
        _gh_add_key("/user/keys", "ssh-ed25519 AAAAC3 test@example.com", "Title")

    # 5. Process exception
    def mock_raise(*args, **kwargs):
        raise subprocess.SubprocessError("Subprocess died")

    monkeypatch.setattr("devops_cli.github.ssh.run_subprocess", mock_raise)
    with pytest.raises(SSHRegistrationError, match="GitHub CLI key registration failed"):
        _gh_add_key("/user/keys", "ssh-ed25519 AAAAC3 test@example.com", "Title")


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
    """Verify _register_with_token_api calls GitHubClient and _add_signing_key."""
    mock_client = MagicMock()
    mock_existing_key = MagicMock()
    mock_existing_key.key = "ssh-rsa OTHERKEY"
    mock_client.get_user_ssh_keys.return_value = [mock_existing_key]

    monkeypatch.setattr("devops_cli.github.ssh.GitHubClient", lambda token: mock_client)
    signing_called = False

    def mock_signing(token: str, pub: str, t: str) -> None:
        nonlocal signing_called
        signing_called = True

    monkeypatch.setattr("devops_cli.github.ssh._add_signing_key", mock_signing)
    _register_with_token_api(
        "ghp_token", "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA test@example.com", "Title"
    )

    mock_client.add_user_ssh_key.assert_called_once()
    assert signing_called is True


def test_add_signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _add_signing_key performs HTTP POST with httpx2."""
    mock_resp = MagicMock(status_code=201)
    mock_http_client = MagicMock()
    mock_http_client.post.return_value = mock_resp
    mock_http_client.__enter__.return_value = mock_http_client
    mock_http_client.__exit__.return_value = None

    monkeypatch.setattr("httpx2.Client", lambda: mock_http_client)
    _add_signing_key("ghp_token", "ssh-ed25519 AAAAC3", "Title")
    mock_http_client.post.assert_called_once()

    # 422 response should not raise error
    mock_resp_422 = MagicMock(status_code=422)
    mock_http_client.post.return_value = mock_resp_422
    _add_signing_key("ghp_token", "ssh-ed25519 AAAAC3", "Title")

    # 500 response raises HTTPStatusError
    mock_resp_500 = MagicMock(status_code=500)
    mock_resp_500.raise_for_status.side_effect = RuntimeError("Server Error")
    mock_http_client.post.return_value = mock_resp_500
    with pytest.raises(RuntimeError, match="Server Error"):
        _add_signing_key("ghp_token", "ssh-ed25519 AAAAC3", "Title")
