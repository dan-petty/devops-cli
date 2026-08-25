"""Unit tests for Prometheus CLI commands (devops_cli.commands.prometheus)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.prometheus import app as prometheus_app
from devops_cli.main import app as main_app

runner = CliRunner()


def test_prometheus_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify prometheus query, targets, and rules subcommands."""
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )
    mock_data = {
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
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_data

    with patch("devops_cli.commands.prometheus.httpx2.get", return_value=mock_resp):
        res_q = runner.invoke(
            main_app, ["--dry-run", "prometheus", "query", "node_cpu_seconds_total"]
        )
        assert res_q.exit_code == 0

        res_targets = runner.invoke(main_app, ["--dry-run", "prometheus", "targets"])
        assert res_targets.exit_code == 0

        res_rules = runner.invoke(main_app, ["--dry-run", "prometheus", "rules"])
        assert res_rules.exit_code == 0

        res_direct_q = runner.invoke(prometheus_app, ["query", "up"])
        assert res_direct_q.exit_code == 0
