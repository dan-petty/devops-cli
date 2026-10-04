"""Unit tests for FastAPI REST & OpenAPI service engine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from devops_cli import __version__
from devops_cli.commands.serve import app as serve_app
from devops_cli.server.app import create_app

runner = CliRunner()


@pytest.fixture
def client() -> TestClient:
    """Fixture providing TestClient for FastAPI app."""
    app = create_app()
    return TestClient(app)


def test_root_endpoint(client: TestClient) -> None:
    """Test root endpoint metadata response."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "DevOps CLI REST API"
    assert data["version"] == __version__
    assert "X-Process-Time" in response.headers
    assert response.headers["X-DevOps-Version"] == __version__


def test_health_endpoints(client: TestClient) -> None:
    """Test /health and /healthz liveness probe endpoints."""
    for path in ["/health", "/healthz"]:
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "devops-cli"
        assert data["version"] == __version__
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], int | float)


def test_status_endpoint(client: TestClient) -> None:
    """Test /api/v1/status workstation inspection endpoint."""
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == __version__
    assert "python_version" in data
    assert "platform" in data
    assert "tools" in data
    assert isinstance(data["tools"], dict)
    assert "uv" in data["tools"]
    assert "telemetry_enabled" in data


def test_workspaces_endpoint_with_nested_repos(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test /api/v1/workspaces discovery with direct and nested owner/repo hierarchies."""
    fake_root = tmp_path / "workspace"
    repos_dir = fake_root / "repos"
    owner_a = repos_dir / "owner_a"
    repo_1 = owner_a / "repo_1"
    repo_1.mkdir(parents=True)
    (repo_1 / ".git").mkdir()
    (repo_1 / ".devcontainer").mkdir()
    (repo_1 / "pyproject.toml").write_text("[project]\nname='repo1'", encoding="utf-8")

    direct_repo = repos_dir / "direct_repo"
    direct_repo.mkdir(parents=True)
    (direct_repo / ".git").mkdir()

    monkeypatch.setattr("devops_cli.server.routes.workspace.main_worktree_root", lambda: fake_root)
    response = client.get("/api/v1/workspaces")
    assert response.status_code == 200
    data = response.json()
    assert data["workspace_root"] == str(fake_root.resolve())
    repo_names = [r["name"] for r in data["repositories"]]
    assert "direct_repo" in repo_names
    assert "owner_a/repo_1" in repo_names


def test_config_endpoint_sanitization(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test /api/v1/config returns sanitized configuration for all secret keys."""
    monkeypatch.setenv("DEVOPS_CLI_GRAFANA_TOKEN", "FAKE-secret-token-12345")
    monkeypatch.setenv("DEVOPS_CLI_ARGOCD_PASSWORD", "secret_argo_pass")
    monkeypatch.setenv("DEVOPS_CLI_GRAFANA_PASSWORD", "secret_graf_pass")
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "config" in data
    cfg = data["config"]
    assert "ssh" in cfg
    assert "repos" in cfg
    assert "workspace" in cfg
    assert cfg.get("grafana", {}).get("token") in ("***REDACTED***", None)
    assert cfg.get("argocd", {}).get("password") in ("***REDACTED***", None)
    assert cfg.get("grafana", {}).get("password") in ("***REDACTED***", None)


def test_config_recursive_redaction_helper() -> None:
    """Test _redact_config_dict handles deeply nested dictionaries and secret keywords."""
    from devops_cli.server.routes.workspace import _redact_config_dict

    secret_options = frozenset({"deeply.nested.secret_field", "auth.custom_token"})
    payload = {
        "deeply": {
            "nested": {
                "secret_field": "confidential_value",
                "safe_field": "public_value",
            },
        },
        "auth": {
            "custom_token": "token_123",
            "plain_password": "super_secret_password",
            "nested_auth": {
                "api_key": "nested_api_key_val",
                "private_key": "synthetic_mock_private_key_data",
                "standard_info": "visible",
            },
        },
        "normal": {"name": "app", "version": "1.0"},
        "ai": {"allow_private_network": False},
    }
    redacted = _redact_config_dict(payload, secret_options)
    assert redacted["deeply"]["nested"]["secret_field"] == "***REDACTED***"
    assert redacted["deeply"]["nested"]["safe_field"] == "public_value"
    assert redacted["auth"]["custom_token"] == "***REDACTED***"
    assert redacted["auth"]["plain_password"] == "***REDACTED***"
    assert redacted["auth"]["nested_auth"]["api_key"] == "***REDACTED***"
    assert redacted["auth"]["nested_auth"]["private_key"] == "***REDACTED***"
    assert redacted["auth"]["nested_auth"]["standard_info"] == "visible"
    assert redacted["normal"]["name"] == "app"
    assert redacted["ai"]["allow_private_network"] is False


def test_server_cors_configuration() -> None:
    """Test server CORS middleware uses safe explicit origin list."""
    app = create_app(cors_origins=["https://example.com"])
    custom_client = TestClient(app)
    res = custom_client.options(
        "/",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.headers.get("access-control-allow-origin") == "https://example.com"


def test_workspaces_endpoint_empty_repos(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test /api/v1/workspaces when repos directory does not exist."""
    fake_empty = tmp_path / "empty_workspace"
    fake_empty.mkdir()
    monkeypatch.setattr("devops_cli.server.routes.workspace.main_worktree_root", lambda: fake_empty)
    response = client.get("/api/v1/workspaces")
    assert response.status_code == 200
    data = response.json()
    assert data["repositories"] == []


def test_telemetry_endpoint(client: TestClient) -> None:
    """Test /api/v1/telemetry status endpoint."""
    with patch(
        "devops_cli.telemetry.tracer.OTelTelemetryClient.test_connection",
        return_value=(True, "HTTP 200 OK", 5.0),
    ):
        response = client.get("/api/v1/telemetry")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "endpoint" in data
        assert data["ping_ok"] is True
        assert data["ping_message"] == "Connected successfully"
        assert data["ping_latency_ms"] == 5.0


def test_metrics_prometheus_endpoint(client: TestClient) -> None:
    """Test /metrics endpoint returns Prometheus formatted text."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    assert "devops_cli_info" in text
    assert "devops_cli_uptime_seconds" in text
    assert "devops_cli_telemetry_enabled" in text


def test_openapi_docs_endpoint(client: TestClient) -> None:
    """Test OpenAPI JSON and Swagger UI endpoints."""
    openapi_res = client.get("/openapi.json")
    assert openapi_res.status_code == 200
    schema = openapi_res.json()
    assert schema["info"]["title"] == "DevOps CLI REST & OpenAPI Service"
    assert schema["info"]["version"] == __version__
    assert "/health" in schema["paths"]
    assert "/api/v1/status" in schema["paths"]

    docs_res = client.get("/docs")
    assert docs_res.status_code == 200
    assert "swagger-ui" in docs_res.text.lower()


def test_serve_cli_help() -> None:
    """Test devops serve --help CLI output."""
    result = runner.invoke(serve_app, ["--help"])
    assert result.exit_code == 0
    assert "FastAPI REST & OpenAPI Service Engine" in result.output
    assert "--host" in result.output
    assert "--port" in result.output
    assert "--reload" in result.output


def test_serve_cli_invocation_mocked() -> None:
    """Test devops serve starts uvicorn server."""
    with patch("uvicorn.run") as mock_uvicorn:
        result = runner.invoke(serve_app, ["--host", "0.0.0.0", "--port", "9000"])
        assert result.exit_code == 0
        assert mock_uvicorn.called
        assert (mock_uvicorn.call_args.kwargs["host"], mock_uvicorn.call_args.kwargs["port"]) == (
            "0.0.0.0",
            9000,
        )


def test_serve_service_mode_flags_rejected() -> None:
    """Test --service rejects --workers > 1 and --reload with exit code 2."""
    res_workers = runner.invoke(serve_app, ["--service", "--workers", "2"])
    res_reload = runner.invoke(serve_app, ["--service", "--reload"])

    assert (
        res_workers.exit_code,
        "--workers > 1" in res_workers.output,
        res_reload.exit_code,
        "--reload" in res_reload.output,
    ) == (2, True, 2, True)


def test_serve_service_mode_config_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test --service enforces repos, machine_account, and valid JSON webhook secrets."""
    # 1. Missing repos
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_REPOS", "[]")
    res_repos = runner.invoke(serve_app, ["--service"])

    # 2. Missing machine_account
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_REPOS", '["example-org/repo1"]')
    monkeypatch.delenv("DEVOPS_CLI_SERVICE_MACHINE_ACCOUNT", raising=False)
    res_account = runner.invoke(serve_app, ["--service"])

    # 3. Missing webhook_secrets
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_MACHINE_ACCOUNT", "bot-account")
    monkeypatch.delenv("DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS", raising=False)
    res_no_secrets = runner.invoke(serve_app, ["--service"])

    # 4. Invalid JSON webhook_secrets
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS", "not-a-json-object")
    res_bad_secrets = runner.invoke(serve_app, ["--service"])

    assert (
        res_repos.exit_code,
        "service.repos" in res_repos.output,
        res_account.exit_code,
        "service.machine_account" in res_account.output,
        res_no_secrets.exit_code,
        "service.webhook_secrets" in res_no_secrets.output,
        res_bad_secrets.exit_code,
        "service.webhook_secrets" in res_bad_secrets.output,
    ) == (1, True, 1, True, 1, True, 1, True)


def test_serve_service_mode_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test valid --service invocation starts uvicorn without banner."""
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_REPOS", '["example-org/repo1"]')
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_MACHINE_ACCOUNT", "bot-account")
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS", '{"example-org/repo1":"secret-1"}')

    with patch("uvicorn.run") as mock_uvicorn:
        result = runner.invoke(serve_app, ["--service", "--host", "0.0.0.0", "--port", "8787"])
        assert (
            result.exit_code,
            mock_uvicorn.called,
            mock_uvicorn.call_args.kwargs["host"],
            mock_uvicorn.call_args.kwargs["port"],
            mock_uvicorn.call_args.kwargs["log_config"],
        ) == (0, True, "0.0.0.0", 8787, None)
