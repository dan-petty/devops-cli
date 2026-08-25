"""Unit tests for Grafana CLI commands and dashboard sync."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.grafana import app
from devops_cli.main import app as main_app

runner = CliRunner()


def test_dashboard_json_templates_valid() -> None:
    """Verify built-in Grafana dashboard templates are valid JSON."""
    dashboard_dir = Path("k8s/monitoring/dashboards")
    assert dashboard_dir.exists()

    json_files = list(dashboard_dir.glob("*.json"))
    assert len(json_files) >= 3

    for f in json_files:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert "title" in data
        assert "panels" in data
        assert "uid" in data
        assert isinstance(data["panels"], list)


def test_grafana_dashboards_sync_dry_run() -> None:
    """Verify grafana dashboards sync in dry-run mode."""
    result = runner.invoke(main_app, ["--dry-run", "grafana", "dashboards", "sync"])
    assert result.exit_code == 0
    assert "Would run delegated command: devops grafana dashboards sync" in result.output


def test_grafana_dashboards_sync_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify successful sync of dashboards with mock Grafana API."""
    import httpx2

    from devops_cli.config.settings import Settings

    mock_settings = Settings()
    mock_settings.grafana.url = "http://localhost:3000"
    mock_settings.ai.allow_private_network = True
    monkeypatch.setattr("devops_cli.commands.grafana.load_settings", lambda: mock_settings)

    class DummyResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"slug": "test-dashboard", "status": "success"}

    class DummyClient:
        def __enter__(self) -> DummyClient:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def post(self, url: str, **kwargs: object) -> DummyResponse:
            return DummyResponse()

    monkeypatch.setattr(httpx2, "Client", lambda *args, **kwargs: DummyClient())

    result = runner.invoke(app, ["dashboards", "sync"])
    assert result.exit_code == 0
    assert "Dashboard sync completed" in result.output


def test_grafana_commands_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify grafana dashboards list and sync execution via main CLI."""
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )
    mock_dashboards = [
        {
            "uid": "cluster-overview",
            "title": "Cluster Overview",
            "url": "/d/cluster",
            "type": "dash-db",
        }
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_dashboards

    with patch("devops_cli.commands.grafana.httpx2.get", return_value=mock_resp):
        res_dash = runner.invoke(main_app, ["--dry-run", "grafana", "dashboards"])
        assert res_dash.exit_code == 0

        res_sync = runner.invoke(main_app, ["--dry-run", "grafana", "sync"])
        assert res_sync.exit_code == 0
