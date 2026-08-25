"""Tests for ops tools, config, grafana, prometheus, argo, docker, branches, and release."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.main import app as main_app

runner = CliRunner()


def _mock_proc(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["cmd"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# ── Install Tools ─────────────────────────────────────────────────────────────
def test_install_tools_commands(tmp_path: Path) -> None:
    with (
        patch("shutil.which", return_value="/usr/local/bin/kubectl"),
        patch("devops_cli.commands.install_tools._current_version", return_value="v1.28.0"),
    ):
        res_stat = runner.invoke(main_app, ["install-tools", "status"])
        assert res_stat.exit_code == 0

        res_all = runner.invoke(main_app, ["--dry-run", "install-tools", "all"])
        assert res_all.exit_code == 0


# ── Config Commands ───────────────────────────────────────────────────────────
def test_config_commands_comprehensive(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.yaml"
    with (
        patch("devops_cli.config.settings.CONFIG_PATH", cfg_file),
        patch("devops_cli.commands.config._gh_auth_status", return_value=True),
        patch("devops_cli.commands.config._gh_auth_token", return_value="ghp_test"),
    ):
        res_show = runner.invoke(main_app, ["config", "show"])
        assert res_show.exit_code == 0

        res_get = runner.invoke(main_app, ["config", "get", "ai.provider"])
        assert res_get.exit_code == 0

        res_set = runner.invoke(main_app, ["config", "set", "ai.provider", "openai"])
        assert res_set.exit_code == 0

        res_out = runner.invoke(main_app, ["config", "output"])
        assert res_out.exit_code == 0

        res_env = runner.invoke(main_app, ["config", "env"])
        assert res_env.exit_code == 0


# ── Prometheus Commands ───────────────────────────────────────────────────────
def test_prometheus_commands(monkeypatch: pytest.MonkeyPatch) -> None:
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


# ── Grafana Commands ──────────────────────────────────────────────────────────
def test_grafana_commands(monkeypatch: pytest.MonkeyPatch) -> None:
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


# ── Argo Commands ─────────────────────────────────────────────────────────────
def test_argo_commands() -> None:
    mock_apps = {
        "items": [
            {
                "metadata": {"name": "guestbook", "namespace": "argocd"},
                "status": {"sync": {"status": "Synced"}, "health": {"status": "Healthy"}},
            }
        ]
    }
    with patch(
        "devops_cli.core.process.run_subprocess",
        return_value=_mock_proc(0, json.dumps(mock_apps)),
    ):
        res_list = runner.invoke(main_app, ["--dry-run", "argo", "list"])
        assert res_list.exit_code == 0

        res_status = runner.invoke(main_app, ["--dry-run", "argo", "status", "guestbook"])
        assert res_status.exit_code == 0


# ── Docker Commands ───────────────────────────────────────────────────────────
def test_docker_commands() -> None:
    mock_stats = [
        {
            "Container": "devops-app",
            "CPUPerc": "1.2%",
            "MemUsage": "50MiB / 1GiB",
            "MemPerc": "5.0%",
        }
    ]
    lines = "\n".join(json.dumps(s) for s in mock_stats)
    with patch("devops_cli.core.process.run_subprocess", return_value=_mock_proc(0, lines)):
        res_stats = runner.invoke(main_app, ["--dry-run", "docker", "stats"])
        assert res_stats.exit_code == 0

        res_ps = runner.invoke(main_app, ["--dry-run", "docker", "ps"])
        assert res_ps.exit_code == 0


# ── Branches Commands ─────────────────────────────────────────────────────────
def test_branches_commands(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    with (
        patch("devops_cli.core.repo.find_repo_root", return_value=tmp_path),
        patch(
            "devops_cli.git.operations.list_branches",
            return_value=MagicMock(branches=["main", "feat/test"], current="main"),
        ),
        patch("devops_cli.git.operations.delete_merged_branches", return_value=["feat/test"]),
    ):
        res_list = runner.invoke(main_app, ["--dry-run", "branches", "list"])
        assert res_list.exit_code == 0

        res_del = runner.invoke(main_app, ["--dry-run", "branches", "delete-merged"])
        assert res_del.exit_code == 0


# ── Analyze Commands ──────────────────────────────────────────────────────────
def test_analyze_commands(tmp_path: Path) -> None:
    from devops_cli.commands.analyze import app as analyze_app

    res_path = runner.invoke(analyze_app, ["path", "--explain"])
    assert res_path.exit_code == 0


# ── Release Commands ──────────────────────────────────────────────────────────
def test_release_commands(tmp_path: Path) -> None:
    with patch("devops_cli.core.process.run_subprocess", return_value=_mock_proc(0, "v0.1.0")):
        res_stat = runner.invoke(main_app, ["--dry-run", "release", "status"])
        assert res_stat.exit_code == 0
