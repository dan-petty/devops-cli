"""Unit tests for Prometheus CLI commands (devops_cli.commands.prometheus)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.prometheus import app as prometheus_app
from devops_cli.config.settings import Settings
from devops_cli.main import app as main_app

runner = CliRunner()


def test_prometheus_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify prometheus query, query-range, targets, and rules subcommands."""
    monkeypatch.setattr(
        "devops_cli.http.validation.validate_service_url", lambda *args, **kwargs: None
    )
    mock_vector = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {
                    "metric": {
                        "__name__": "node_cpu_seconds_total",
                        "instance": "localhost:9100",
                    },
                    "value": [1700000000, "100.5"],
                }
            ],
        },
    }
    mock_matrix = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"instance": "localhost:9100"},
                    "values": [[1700000000, "100.5"], [1700000060, "101.0"]],
                }
            ],
        },
    }
    mock_rules = {
        "status": "success",
        "data": {
            "groups": [
                {
                    "name": "node-alerts",
                    "rules": [{"name": "HighCPU", "type": "alerting", "health": "ok"}],
                }
            ]
        },
    }
    mock_targets = {
        "status": "success",
        "data": {
            "activeTargets": [
                {
                    "health": "up",
                    "labels": {"job": "node-exporter", "instance": "localhost:9100"},
                    "lastScrape": "2026-08-26T00:00:00Z",
                }
            ]
        },
    }

    def mock_get(*args: object, **kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "application/json"}
        url_str = ""
        for a in args:
            if isinstance(a, str) and ("http" in a or "/api/" in a):
                url_str = a
                break
        if not url_str and "url" in kwargs:
            url_str = str(kwargs["url"])

        if "query_range" in url_str:
            resp.json.return_value = mock_matrix
        elif "query" in url_str:
            resp.json.return_value = mock_vector
        elif "rules" in url_str:
            resp.json.return_value = mock_rules
        elif "targets" in url_str:
            resp.json.return_value = mock_targets
        else:
            resp.json.return_value = {}
        return resp

    settings = Settings()
    settings.prometheus.url = "http://localhost:9090"
    settings.ai.allow_private_network = True

    with (
        patch("devops_cli.commands.prometheus.httpx2.Client.get", side_effect=mock_get),
        patch("devops_cli.commands.prometheus.load_settings", return_value=settings),
    ):
        res_q = runner.invoke(
            main_app, ["--dry-run", "prometheus", "query", "node_cpu_seconds_total"]
        )
        assert res_q.exit_code == 0

        res_direct_q = runner.invoke(prometheus_app, ["query", "up"])
        assert res_direct_q.exit_code == 0

        res_qr = runner.invoke(
            prometheus_app, ["query-range", "up", "--start", "30m", "--step", "30s"]
        )
        assert res_qr.exit_code == 0

        res_targets = runner.invoke(prometheus_app, ["targets"])
        assert res_targets.exit_code == 0

        res_rules = runner.invoke(prometheus_app, ["rules"])
        assert res_rules.exit_code == 0


def test_prometheus_errors_and_edge_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify prometheus error branches: missing URL, validation, long expr, invalid content-type, duration parsing."""
    # 1. Missing URL
    settings_no_url = Settings()
    settings_no_url.prometheus.url = None
    with patch("devops_cli.commands.prometheus.load_settings", return_value=settings_no_url):
        res_no_url = runner.invoke(prometheus_app, ["query", "up"])
        assert res_no_url.exit_code == 1

    # 2. Invalid service URL (SSRF block)
    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    settings_bad_url = Settings()
    settings_bad_url.prometheus.url = "http://10.0.0.1:9090"
    settings_bad_url.ai.allow_private_network = False
    with patch("devops_cli.commands.prometheus.load_settings", return_value=settings_bad_url):
        res_bad_url = runner.invoke(prometheus_app, ["query", "up"])
        assert res_bad_url.exit_code == 1

    # 3. Expr too long
    settings_ok = Settings()
    settings_ok.prometheus.url = "http://localhost:9090"
    settings_ok.ai.allow_private_network = True
    with patch("devops_cli.commands.prometheus.load_settings", return_value=settings_ok):
        res_long = runner.invoke(prometheus_app, ["query", "a" * 5000])
        assert res_long.exit_code == 1

    # 4. Invalid content type
    mock_bad_resp = MagicMock()
    mock_bad_resp.status_code = 200
    mock_bad_resp.headers = {"content-type": "text/html"}
    mock_client_bad = MagicMock()
    mock_client_bad.__enter__.return_value.get.return_value = mock_bad_resp
    with (
        patch("devops_cli.commands.prometheus.load_settings", return_value=settings_ok),
        patch("devops_cli.commands.prometheus.validate_service_url", return_value=None),
        patch("devops_cli.commands.prometheus.httpx2.Client", return_value=mock_client_bad),
    ):
        res_bad_ct = runner.invoke(prometheus_app, ["query", "up"])
        assert res_bad_ct.exit_code == 1

    # 5. Query returning empty / failed
    mock_empty_resp = MagicMock()
    mock_empty_resp.status_code = 200
    mock_empty_resp.headers = {"content-type": "application/json"}
    mock_empty_resp.json.return_value = {
        "status": "success",
        "data": {"resultType": "vector", "result": []},
    }
    mock_client_empty = MagicMock()
    mock_client_empty.__enter__.return_value.get.return_value = mock_empty_resp
    with (
        patch("devops_cli.commands.prometheus.load_settings", return_value=settings_ok),
        patch("devops_cli.commands.prometheus.validate_service_url", return_value=None),
        patch("devops_cli.commands.prometheus.httpx2.Client", return_value=mock_client_empty),
    ):
        res_empty = runner.invoke(prometheus_app, ["query", "empty_metric"])
        assert res_empty.exit_code == 0

    # 6. Parse duration helpers
    from devops_cli.commands.prometheus import _parse_duration

    assert _parse_duration("10s") == 10.0
    assert _parse_duration("5m") == 300.0
    assert _parse_duration("2h") == 7200.0
    assert _parse_duration("1d") == 86400.0
    assert _parse_duration("") == 0.0
    assert _parse_duration("invalid") == 0.0
    with pytest.raises(Exception):
        _parse_duration("400d")
