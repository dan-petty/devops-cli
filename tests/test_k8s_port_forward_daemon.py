"""Unit tests for Kubernetes background port-forward daemon management."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.commands.k8s.networking import port_forward_status, port_forward_stop
from devops_cli.core.cli import new_typer
from devops_cli.k8s.port_forward_daemon import (
    PortForwardDaemonManager,
    PortForwardInfo,
)

runner = CliRunner()
dummy_app = new_typer()
dummy_app.command("status")(port_forward_status)
dummy_app.command("stop")(port_forward_stop)


def test_port_forward_info_model() -> None:
    """Test PortForwardInfo model serialization and liveness check."""
    info = PortForwardInfo(
        pid=os.getpid(),
        service="svc/argocd-server",
        namespace="argocd",
        local_port=8080,
        remote_port=80,
        address="127.0.0.1",
        stack="infra",
    )
    assert info.is_alive is True

    dead_info = PortForwardInfo(
        pid=99999999,
        service="svc/jaeger",
        namespace="otel",
        local_port=16686,
        remote_port=16686,
        address="127.0.0.1",
        stack="infra",
    )
    assert dead_info.is_alive is False


def test_daemon_manager_save_and_list(tmp_path: Path) -> None:
    """Test saving and listing port-forward state file."""
    mgr = PortForwardDaemonManager(state_file=tmp_path / "port_forwards.json")
    item = PortForwardInfo(
        pid=os.getpid(),
        service="svc/ollama",
        namespace="llm",
        local_port=11434,
        remote_port=11434,
        address="127.0.0.1",
        stack="llm",
    )
    mgr.save_forwards([item])

    loaded = mgr.list_forwards()
    assert len(loaded) == 1
    assert loaded[0].service == "svc/ollama"
    assert loaded[0].local_port == 11434


def test_daemon_manager_stop_forwards(tmp_path: Path) -> None:
    """Test stopping active port forwards and pruning state file."""
    mgr = PortForwardDaemonManager(state_file=tmp_path / "port_forwards.json")
    item = PortForwardInfo(
        pid=12345,
        service="svc/grafana",
        namespace="monitoring",
        local_port=8030,
        remote_port=80,
        address="127.0.0.1",
        stack="infra",
    )
    mgr.save_forwards([item])

    with patch("os.kill") as mock_kill:
        stopped = mgr.stop_forwards()
        assert stopped == 1
        assert mock_kill.called

    remaining = mgr.list_forwards()
    assert len(remaining) == 0


def test_cli_port_forward_status_empty(tmp_path: Path) -> None:
    """Test CLI port-forward status when no daemons are running."""
    with patch("devops_cli.k8s.port_forward_daemon.get_daemon_manager") as mock_get:
        mgr = PortForwardDaemonManager(state_file=tmp_path / "port_forwards.json")
        mock_get.return_value = mgr
        res = runner.invoke(dummy_app, ["status"])
        assert res.exit_code == 0
        assert "No active" in res.output or "Active Kubernetes Port-Forward" in res.output


def test_cli_port_forward_stop(tmp_path: Path) -> None:
    """Test CLI port-forward stop command."""
    with patch("devops_cli.k8s.port_forward_daemon.get_daemon_manager") as mock_get:
        mgr = PortForwardDaemonManager(state_file=tmp_path / "port_forwards.json")
        item = PortForwardInfo(
            pid=54321,
            service="svc/prometheus",
            namespace="monitoring",
            local_port=8090,
            remote_port=9090,
            address="127.0.0.1",
            stack="infra",
        )
        mgr.save_forwards([item])
        mock_get.return_value = mgr

        with patch("os.kill"):
            res = runner.invoke(dummy_app, ["stop"])
            assert res.exit_code == 0
            assert "Terminated" in res.output or "Stopped" in res.output
