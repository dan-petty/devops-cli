"""Unit tests for Grafana CLI commands and dashboard sync."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.grafana import app as grafana_app
from devops_cli.config.settings import Settings
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

    mock_settings = Settings()
    mock_settings.grafana.url = "http://localhost:3000"
    mock_settings.ai.allow_private_network = True
    monkeypatch.setattr("devops_cli.commands.grafana.load_settings", lambda: mock_settings)

    class DummyResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, str]:
            return {"slug": "test-dashboard", "status": "success"}

    class DummyClient:
        def __enter__(self) -> DummyClient:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def post(self, url: str, **kwargs: object) -> DummyResponse:
            return DummyResponse()

    monkeypatch.setattr(httpx2, "Client", lambda *args, **kwargs: DummyClient())

    result = runner.invoke(grafana_app, ["dashboards", "sync"])
    assert result.exit_code == 0
    assert "Dashboard sync completed" in result.output


def test_grafana_commands_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify grafana dashboards list, export, import, search, datasources, and alerts execution."""
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )
    mock_dashboards = [
        {
            "uid": "cluster-overview",
            "title": "Cluster Overview",
            "folderTitle": "General",
            "url": "/d/cluster",
            "type": "dash-db",
        }
    ]
    mock_datasources = [
        {
            "name": "Prometheus",
            "type": "prometheus",
            "url": "http://prometheus:9090",
            "isDefault": True,
        }
    ]
    mock_alerts = [
        {
            "uid": "alert-1",
            "title": "High CPU",
            "folderUID": "general",
            "condition": "A",
        }
    ]
    mock_dashboard_detail = {
        "dashboard": {
            "title": "Exported Dash",
            "panels": [],
        },
        "meta": {},
    }

    mock_settings = Settings()
    mock_settings.grafana.url = "http://localhost:3000"
    mock_settings.ai.allow_private_network = True

    def mock_get(*args: object, **kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        url_str = ""
        for a in args:
            if isinstance(a, str) and ("http" in a or "/api/" in a):
                url_str = a
                break
        if not url_str and "url" in kwargs:
            url_str = str(kwargs["url"])

        if "dashboards/uid" in url_str:
            resp.json.return_value = mock_dashboard_detail
        elif "search" in url_str:
            resp.json.return_value = mock_dashboards
        elif "datasources" in url_str:
            resp.json.return_value = mock_datasources
        elif "alert-rules" in url_str:
            resp.json.return_value = mock_alerts
        else:
            resp.json.return_value = []
        return resp

    def mock_post(*args: object, **kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"slug": "imported-dash", "status": "success"}
        return resp

    sample_dash_file = tmp_path / "dash.json"
    sample_dash_file.write_text(
        json.dumps({"title": "Sample Dashboard", "panels": []}), encoding="utf-8"
    )

    with (
        patch("devops_cli.commands.grafana.httpx2.Client.get", side_effect=mock_get),
        patch("devops_cli.commands.grafana.httpx2.Client.post", side_effect=mock_post),
        patch("devops_cli.commands.grafana.load_settings", return_value=mock_settings),
    ):
        res_list = runner.invoke(grafana_app, ["dashboards", "list"])
        assert res_list.exit_code == 0
        export_out = Path("test_exported.json")
        try:
            res_export = runner.invoke(
                grafana_app,
                ["dashboards", "export", "cluster-overview", "--output", str(export_out)],
            )
            assert res_export.exit_code == 0
            assert export_out.exists()
        finally:
            if export_out.exists():
                export_out.unlink()

        res_import = runner.invoke(grafana_app, ["dashboards", "import", str(sample_dash_file)])
        assert res_import.exit_code == 0

        res_search = runner.invoke(grafana_app, ["search", "--query", "cluster"])
        assert res_search.exit_code == 0

        res_ds = runner.invoke(grafana_app, ["datasources"])
        assert res_ds.exit_code == 0

        res_alerts = runner.invoke(grafana_app, ["alerts"])
        assert res_alerts.exit_code == 0
