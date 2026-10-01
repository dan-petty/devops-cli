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
    monkeypatch.chdir(tmp_path)
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

    endpoint_map = {
        "dashboards/uid": mock_dashboard_detail,
        "search": mock_dashboards,
        "datasources": mock_datasources,
        "alert-rules": mock_alerts,
    }

    def mock_get(*args: object, **kwargs: object) -> MagicMock:
        resp = MagicMock(status_code=200)
        url_str = next(
            (
                str(a)
                for a in (*args, kwargs.get("url", ""))
                if "http" in str(a) or "/api/" in str(a)
            ),
            "",
        )
        resp.json.return_value = next(
            (val for key, val in endpoint_map.items() if key in url_str), []
        )
        return resp

    def mock_post(*args: object, **kwargs: object) -> MagicMock:
        return MagicMock(
            status_code=200, json=lambda: {"slug": "imported-dash", "status": "success"}
        )

    monkeypatch.chdir(tmp_path)
    sample_dash_file = tmp_path / "dash.json"
    sample_dash_file.write_text(
        json.dumps({"title": "Sample Dashboard", "panels": []}), encoding="utf-8"
    )
    export_out = tmp_path / "test_exported.json"

    with (
        patch("devops_cli.commands.grafana.httpx2.Client.get", side_effect=mock_get),
        patch("devops_cli.commands.grafana.httpx2.Client.post", side_effect=mock_post),
        patch("devops_cli.commands.grafana.load_settings", return_value=mock_settings),
    ):
        res_list = runner.invoke(grafana_app, ["dashboards", "list"])
        res_export = runner.invoke(
            grafana_app,
            ["dashboards", "export", "cluster-overview", "--output", str(export_out)],
        )
        export_created = export_out.exists()
        res_import = runner.invoke(grafana_app, ["dashboards", "import", str(sample_dash_file)])
        res_search = runner.invoke(grafana_app, ["search", "--query", "cluster"])
        res_ds = runner.invoke(grafana_app, ["datasources"])
        res_alerts = runner.invoke(grafana_app, ["alerts"])

        assert (
            res_list.exit_code,
            res_export.exit_code,
            export_created,
            res_import.exit_code,
            res_search.exit_code,
            res_ds.exit_code,
            res_alerts.exit_code,
        ) == (0, 0, True, 0, 0, 0, 0)


def test_grafana_client_args_masked_token_fallback() -> None:
    from devops_cli.commands.grafana import _client_args

    settings_masked = Settings()
    settings_masked.grafana.url = "http://example.com:3000"
    with (
        patch("devops_cli.commands.grafana.get_grafana_token", return_value="******"),
        patch(
            "devops_cli.k8s.credentials.get_or_mint_grafana_auth",
            return_value=("minted-token", None),
        ) as mock_mint,
    ):
        base_url, headers = _client_args(settings_masked)
        assert (
            base_url,
            headers.get("Authorization"),
            mock_mint.called,
        ) == ("http://example.com:3000", "Bearer minted-token", True)
