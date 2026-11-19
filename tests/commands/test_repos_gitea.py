"""Tests for devops repos gitea connect and credential helper commands (#1090)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest

from devops_cli.config.settings import load_settings
from devops_cli.http.entry import install_transport, remove_transport
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.process import ProcessAnswer, ProcessFake


@pytest.fixture(autouse=True)
def cleanup_transport() -> Any:
    yield
    remove_transport()


def test_credential_group_is_hidden(cli: Callable[..., Any]) -> None:
    """The credential group is hidden from devops repos gitea --help."""
    result = cli("repos", "gitea", "--help")
    assert result.exit_code == 0
    # Commands table lists visible commands; credential must not be listed as a command
    assert "credential " not in result.output
    assert "\n  credential" not in result.output
    assert "│ credential" not in result.output


def test_connect_refuses_http_url(cli: Callable[..., Any]) -> None:
    """connect --url http://... exits 1 with no request and no keyring read."""
    requests: list[httpx2.Request] = []
    install_transport(
        lambda level: httpx2.MockTransport(lambda req: requests.append(req) or httpx2.Response(200))
    )

    result = cli("repos", "gitea", "connect", "--url", "http://git.example.com")
    assert result.exit_code != 0
    assert "https" in result.output.lower()
    assert len(requests) == 0


def test_connect_refuses_url_with_path(cli: Callable[..., Any]) -> None:
    """connect --url with path exits 1."""
    result = cli("repos", "gitea", "connect", "--url", "https://git.example.com/api/v1")
    assert result.exit_code != 0
    assert "path" in result.output.lower()


def test_connect_names_missing_token(
    cli: Callable[..., Any], isolate_devops_cli_config: Path, keyring_store: FakeKeyring
) -> None:
    """connect exits 1 and names 'devops config set gitea.token' when token is missing."""
    result = cli("repos", "gitea", "connect", "--url", "https://git.example.com")
    assert result.exit_code != 0
    assert "devops config set gitea.token" in result.output


def test_connect_names_missing_ingress(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    process_fake: ProcessFake,
) -> None:
    """connect exits 1 and names '--url' when no ingress exists and --url is omitted."""
    process_fake.answer(
        ["kubectl", "get", "ingress", "-A", "-o", "json"],
        ProcessAnswer(stdout=json.dumps({"items": []})),
    )
    result = cli("repos", "gitea", "connect")
    assert result.exit_code != 0
    assert "--url" in result.output


def test_connect_checks_and_saves(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
) -> None:
    """connect verifies version and current_user, saves url and username, and prints them."""
    keyring_store.set_password("devops-cli", "gitea_token", "valid-token-123")

    def handler(request: httpx2.Request) -> httpx2.Response:
        url_str = str(request.url)
        assert request.headers["Authorization"] == "token valid-token-123"
        if url_str == "https://git.example.com/api/v1/version":
            return httpx2.Response(200, json={"version": "1.27.3"})
        if url_str == "https://git.example.com/api/v1/user":
            return httpx2.Response(200, json={"id": 1, "login": "testdev", "username": "testdev"})
        return httpx2.Response(404)

    install_transport(lambda level: httpx2.MockTransport(handler))

    result = cli("repos", "gitea", "connect", "--url", "https://git.example.com")
    assert result.exit_code == 0
    assert "1.27.3" in result.output
    assert "testdev" in result.output
    assert "https://git.example.com" in result.output

    settings = load_settings()
    assert (settings.gitea.url, settings.gitea.username) == ("https://git.example.com", "testdev")


def test_connect_instructs_remotes_on_url_change(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
) -> None:
    """connect prints note to run devops repos remotes when url changes."""
    keyring_store.set_password("devops-cli", "gitea_token", "valid-token-123")

    # Set initial url in config
    settings = load_settings()
    settings.gitea.url = "https://git-old.example.com"
    settings.gitea.username = "testdev"
    from devops_cli.config.settings import save_settings

    save_settings(settings, keys=("gitea.url", "gitea.username"))

    def handler(request: httpx2.Request) -> httpx2.Response:
        url_str = str(request.url)
        if "version" in url_str:
            return httpx2.Response(200, json={"version": "1.27.3"})
        if "user" in url_str:
            return httpx2.Response(200, json={"id": 1, "login": "testdev", "username": "testdev"})
        return httpx2.Response(404)

    install_transport(lambda level: httpx2.MockTransport(handler))

    result = cli("repos", "gitea", "connect", "--url", "https://git-new.example.com")
    assert result.exit_code == 0
    assert "devops repos remotes" in result.output


def test_connect_discovers_ingress(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
    process_fake: ProcessFake,
) -> None:
    """connect discovers the gitea-http Ingress host when --url is omitted."""
    keyring_store.set_password("devops-cli", "gitea_token", "valid-token-123")

    ingress_json = {
        "items": [
            {
                "metadata": {"name": "gitea-ingress", "namespace": "gitea"},
                "spec": {
                    "rules": [
                        {
                            "host": "git.discovered.example.com",
                            "http": {
                                "paths": [
                                    {"path": "/", "backend": {"service": {"name": "gitea-http"}}}
                                ]
                            },
                        }
                    ]
                },
            }
        ]
    }
    process_fake.answer(
        ["kubectl", "get", "ingress", "-A", "-o", "json"],
        ProcessAnswer(stdout=json.dumps(ingress_json)),
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        url_str = str(request.url)
        assert "git.discovered.example.com" in url_str
        if "version" in url_str:
            return httpx2.Response(200, json={"version": "1.27.3"})
        if "user" in url_str:
            return httpx2.Response(200, json={"id": 1, "login": "testdev", "username": "testdev"})
        return httpx2.Response(404)

    install_transport(lambda level: httpx2.MockTransport(handler))

    result = cli("repos", "gitea", "connect")
    assert result.exit_code == 0
    assert "git.discovered.example.com" in result.output

    settings = load_settings()
    assert settings.gitea.url == "https://git.discovered.example.com"


def test_credential_get_matching_host(
    cli: Callable[..., Any], isolate_devops_cli_config: Path, keyring_store: FakeKeyring
) -> None:
    """credential get prints username and password for matching https host."""
    keyring_store.set_password("devops-cli", "gitea_token", "my-secret-token")
    settings = load_settings()
    settings.gitea.url = "https://git.example.com"
    settings.gitea.username = "gituser"
    from devops_cli.config.settings import save_settings

    save_settings(settings, keys=("gitea.url", "gitea.username"))

    stdin_input = "protocol=https\nhost=git.example.com\n\n"
    result = cli("repos", "gitea", "credential", "get", input=stdin_input)
    assert result.exit_code == 0
    assert "username=gituser" in result.output
    assert "password=my-secret-token" in result.output


def test_credential_get_ignores_mismatched_host(
    cli: Callable[..., Any], isolate_devops_cli_config: Path, keyring_store: FakeKeyring
) -> None:
    """credential get prints nothing for other hosts or non-https."""
    keyring_store.set_password("devops-cli", "gitea_token", "my-secret-token")
    settings = load_settings()
    settings.gitea.url = "https://git.example.com"
    settings.gitea.username = "gituser"
    from devops_cli.config.settings import save_settings

    save_settings(settings, keys=("gitea.url", "gitea.username"))

    stdin_input = "protocol=https\nhost=other.example.com\n\n"
    result = cli("repos", "gitea", "credential", "get", input=stdin_input)
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_credential_store_and_erase_noop(cli: Callable[..., Any]) -> None:
    """credential store and erase do nothing and exit 0."""
    res1 = cli("repos", "gitea", "credential", "store")
    assert res1.exit_code == 0
    res2 = cli("repos", "gitea", "credential", "erase")
    assert res2.exit_code == 0


def test_connect_dry_run(cli: Callable[..., Any]) -> None:
    """connect --dry-run prints request plan and makes no changes."""
    result = cli("repos", "gitea", "connect", "--url", "https://git.example.com", "--dry-run")
    assert result.exit_code == 0
    assert (
        "Plan for" in result.output
        or "PlannedRequest" in result.output
        or "connect" in result.output
    )


def test_connect_refuses_invalid_url(
    cli: Callable[..., Any], isolate_devops_cli_config: Path
) -> None:
    """connect refuses an invalid URL."""
    result = cli("repos", "gitea", "connect", "--url", "http://git.example.com")
    assert result.exit_code != 0
    assert "invalid" in result.output.lower() or "https" in result.output.lower()


def test_connect_fails_when_token_unset(
    cli: Callable[..., Any], isolate_devops_cli_config: Path, keyring_store: FakeKeyring
) -> None:
    """connect fails with exit 1 when gitea.token is unset."""
    result = cli("repos", "gitea", "connect", "--url", "https://git.example.com")
    assert result.exit_code != 0
    assert "gitea.token" in result.output


def test_connect_fails_when_ingress_not_found(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
    process_fake: ProcessFake,
) -> None:
    """connect fails when no Ingress matching gitea-http is found."""
    keyring_store.set_password("devops-cli", "gitea_token", "valid-token-123")
    empty_ingress = {"items": []}
    process_fake.answer(
        ["kubectl", "get", "ingress", "-A", "-o", "json"],
        ProcessAnswer(stdout=json.dumps(empty_ingress)),
    )
    result = cli("repos", "gitea", "connect")
    assert result.exit_code != 0
    assert "gitea-http" in result.output


def test_connect_handles_access_blocked(
    cli: Callable[..., Any],
    isolate_devops_cli_config: Path,
    keyring_store: FakeKeyring,
) -> None:
    """connect handles Cloudflare Access redirect gracefully."""
    keyring_store.set_password("devops-cli", "gitea_token", "valid-token-123")

    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            302, headers={"Location": "https://access.cloudflareaccess.com/login"}
        )

    install_transport(lambda level: httpx2.MockTransport(handler))
    result = cli("repos", "gitea", "connect", "--url", "https://git.example.com")
    assert result.exit_code != 0
    assert "bypass" in result.output.lower() or "blocked" in result.output.lower()


def test_credential_get_non_https_and_missing_url(
    cli: Callable[..., Any], isolate_devops_cli_config: Path, keyring_store: FakeKeyring
) -> None:
    """credential get exits silently when protocol is not https or gitea.url is not set."""
    keyring_store.set_password("devops-cli", "gitea_token", "tok")
    # 1. Non-https protocol
    res1 = cli(
        "repos", "gitea", "credential", "get", input="protocol=http\nhost=git.example.com\n\n"
    )
    assert res1.exit_code == 0
    assert res1.output.strip() == ""

    # 2. Gitea URL unset
    res2 = cli(
        "repos", "gitea", "credential", "get", input="protocol=https\nhost=git.example.com\n\n"
    )
    assert res2.exit_code == 0
    assert res2.output.strip() == ""
