"""Unit tests for Grafana dashboard sync and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.grafana import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_dashboard_json_templates_valid() -> None:
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


def test_grafana_dashboards_sync_dry_run(runner: CliRunner) -> None:
    from devops_cli.main import app as main_app

    result = runner.invoke(main_app, ["--dry-run", "grafana", "dashboards", "sync"])
    assert result.exit_code == 0
    assert "Would run delegated command: devops grafana dashboards sync" in result.output


def test_grafana_dashboards_sync_success(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
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
