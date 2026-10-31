"""Tests for the Mattermost /roadmap slash command integration (#1395)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest
from starlette.testclient import TestClient

from devops_cli.config.constants import (
    CONST_SERVICE_METRIC_CHAT_COMMANDS,
    WebhookExposure,
    WebhookProviderName,
)
from devops_cli.server.routes.webhooks import WEBHOOK_PROVIDERS
from devops_cli.server.service import (
    ServiceManager,
    TriggerBatch,
    create_service_app,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS

pytestmark = pytest.mark.usefixtures("keyring_store")

_TOKEN = "mattermost-secret-token-123"
_AUTH_HEADER = {"Authorization": f"Token {_TOKEN}"}


def _now() -> datetime:
    return datetime(2026, 10, 31, 14, 0, 0, tzinfo=UTC)


@pytest.fixture
def service_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN", _TOKEN)
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_REPOS", '["org/repo1", "org/repo2"]')
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_APP_ID", "123")
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_INSTALLATION_ID", "456")
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_SLUG", "devops-cli-service")
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_BOT_LOGIN", "devops-cli-service[bot]")
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY", "test-app-private-key")
    monkeypatch.setenv(
        "DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS", '{"org/repo1": "sec1", "org/repo2": "sec2"}'
    )


def test_mattermost_provider_declaration() -> None:
    """Verify mattermost provider is declared with cluster exposure and form urlencoded content type."""
    provider = WEBHOOK_PROVIDERS[WebhookProviderName.MATTERMOST]
    assert provider.name == WebhookProviderName.MATTERMOST
    assert provider.exposure == WebhookExposure.CLUSTER
    assert provider.path == "/webhooks/mattermost"
    assert provider.content_type == "application/x-www-form-urlencoded"
    assert provider.verifier.scheme == "Token"


def test_mattermost_slash_command_status_all_repos_and_lanes(
    service_env: None,
) -> None:
    """Invoking /roadmap or /roadmap status returns status for all configured repositories."""
    clock_time = _now()
    app = create_service_app(
        clock=lambda: clock_time,
    )
    client = TestClient(app)

    response = client.post(
        "/webhooks/mattermost",
        headers={**_AUTH_HEADER, "Content-Type": "application/x-www-form-urlencoded"},
        data={"command": "/roadmap", "text": "status"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["response_type"] == "ephemeral"
    assert "org/repo1" in data["text"]
    assert "org/repo2" in data["text"]
    assert "no round yet" in data["text"]

    metric_val = GLOBAL_METRICS.get_counter_value(
        CONST_SERVICE_METRIC_CHAT_COMMANDS, labels={"command": "/roadmap", "result": "status"}
    )
    assert metric_val >= 1.0


def test_mattermost_slash_command_empty_text(
    service_env: None,
) -> None:
    """Invoking /roadmap with no text gives status for all repos."""
    app = create_service_app()
    client = TestClient(app)

    response = client.post(
        "/webhooks/mattermost",
        headers={**_AUTH_HEADER, "Content-Type": "application/x-www-form-urlencoded"},
        data={"command": "/roadmap", "text": ""},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["response_type"] == "ephemeral"
    assert "org/repo1" in data["text"]


def test_mattermost_slash_command_specific_repo(
    service_env: None,
) -> None:
    """Invoking /roadmap status <repo> returns status only for that repository."""
    app = create_service_app()
    client = TestClient(app)

    response = client.post(
        "/webhooks/mattermost",
        headers={**_AUTH_HEADER, "Content-Type": "application/x-www-form-urlencoded"},
        data={"command": "/roadmap", "text": "status org/repo1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "org/repo1" in data["text"]
    assert "org/repo2" not in data["text"]


def test_mattermost_slash_command_unknown_repo(
    service_env: None,
) -> None:
    """Invoking /roadmap status <unknown> returns the list of known repos and increments unknown_repo."""
    app = create_service_app()
    client = TestClient(app)

    response = client.post(
        "/webhooks/mattermost",
        headers={**_AUTH_HEADER, "Content-Type": "application/x-www-form-urlencoded"},
        data={"command": "/roadmap", "text": "status unknown/repo"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "Unknown repository unknown/repo" in data["text"]
    assert "org/repo1" in data["text"]
    assert "org/repo2" in data["text"]

    metric_val = GLOBAL_METRICS.get_counter_value(
        CONST_SERVICE_METRIC_CHAT_COMMANDS,
        labels={"command": "/roadmap", "result": "unknown_repo"},
    )
    assert metric_val >= 1.0


def test_mattermost_slash_command_invalid_subcommand_gives_usage(
    service_env: None,
) -> None:
    """Invoking an invalid subcommand returns usage text and increments usage counter."""
    app = create_service_app()
    client = TestClient(app)

    response = client.post(
        "/webhooks/mattermost",
        headers={**_AUTH_HEADER, "Content-Type": "application/x-www-form-urlencoded"},
        data={"command": "/roadmap", "text": "invalid_command"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "Usage: /roadmap" in data["text"]

    metric_val = GLOBAL_METRICS.get_counter_value(
        CONST_SERVICE_METRIC_CHAT_COMMANDS, labels={"command": "/roadmap", "result": "usage"}
    )
    assert metric_val >= 1.0


def test_mattermost_slash_command_rejects_json_body_with_415(
    service_env: None,
) -> None:
    """Posting JSON payload to mattermost webhook route yields 415 unsupported media type."""
    app = create_service_app()
    client = TestClient(app)

    response = client.post(
        "/webhooks/mattermost",
        headers=_AUTH_HEADER,
        json={"command": "/roadmap", "text": "status"},
    )
    assert response.status_code == 415


def test_mattermost_slash_command_auth_failures(
    service_env: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify wrong token, missing header, and Bearer scheme all return 401 and log warnings."""
    app = create_service_app()
    client = TestClient(app)

    # 1. Missing Authorization header
    res_missing = client.post(
        "/webhooks/mattermost",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"command": "/roadmap", "text": "status"},
    )
    assert res_missing.status_code == 401

    # 2. Bearer scheme instead of Token
    res_bearer = client.post(
        "/webhooks/mattermost",
        headers={
            "Authorization": f"Bearer {_TOKEN}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"command": "/roadmap", "text": "status"},
    )
    assert res_bearer.status_code == 401

    # 3. Wrong token: warning logged naming no token value
    with caplog.at_level(logging.WARNING):
        res_wrong = client.post(
            "/webhooks/mattermost",
            headers={
                "Authorization": "Token wrong-token-value-xyz",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"command": "/roadmap", "text": "status"},
        )
    assert res_wrong.status_code == 401
    assert "wrong-token-value-xyz" not in caplog.text


def test_mattermost_slash_command_unset_option_returns_401_and_warns(
    service_env: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When mattermost.command_token is unset, router returns 401 and logs warning naming the setting."""
    monkeypatch.delenv("DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN", raising=False)
    app = create_service_app()
    client = TestClient(app)

    with caplog.at_level(logging.WARNING):
        response = client.post(
            "/webhooks/mattermost",
            headers={
                "Authorization": f"Token {_TOKEN}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"command": "/roadmap", "text": "status"},
        )
    assert response.status_code == 401
    assert "mattermost.command_token" in caplog.text


def test_mattermost_slash_command_displays_completed_round(
    service_env: None,
) -> None:
    """When a worker has run a round, status output shows start, end, and result."""
    clock_time = _now()
    app = create_service_app(
        clock=lambda: clock_time,
    )
    manager: ServiceManager = app.state.service_manager
    # Simulate a completed round on org/repo1 default lane
    worker = manager.workers[("org/repo1", "default")]
    batch = TriggerBatch(
        repo="org/repo1",
        counts={("test", "poll", ""): 1},
        first_at=clock_time,
        last_at=clock_time,
    )
    worker._execute_batch(batch)

    client = TestClient(app)
    response = client.post(
        "/webhooks/mattermost",
        headers={**_AUTH_HEADER, "Content-Type": "application/x-www-form-urlencoded"},
        data={"command": "/roadmap", "text": "status org/repo1"},
    )
    assert response.status_code == 200
    text = response.json()["text"]
    assert "last round" in text
    assert "success" in text
    assert "2026-10-31T14:00:00Z" in text
