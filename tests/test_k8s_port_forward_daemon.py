"""Unit tests for Kubernetes background port-forward daemon management."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import PropertyMock, patch

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

    # Termination now signals the forward's process group, so the group has to be
    # resolvable; `os.kill` still stands in for the liveness probe in `is_alive`.
    with (
        patch("os.kill") as mock_kill,
        patch("os.getpgid", side_effect=lambda pid: 4242 if pid else 7),
        patch("os.killpg") as mock_killpg,
    ):
        stopped = mgr.stop_forwards()
        assert stopped == 1
        assert mock_kill.called and mock_killpg.called

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


def test_daemon_manager_corrupt_state_file(tmp_path: Path) -> None:
    """Test handling of unparseable or corrupt JSON in state file."""
    state_file = tmp_path / "port_forwards.json"
    state_file.write_text("invalid json content {{{", encoding="utf-8")
    mgr = PortForwardDaemonManager(state_file=state_file)
    assert mgr.list_forwards() == []


def test_daemon_manager_stop_filter_and_dead_process(tmp_path: Path) -> None:
    """Test stopping with service filter and handling dead process exceptions."""
    mgr = PortForwardDaemonManager(state_file=tmp_path / "port_forwards.json")
    item1 = PortForwardInfo(
        pid=11111,
        service="svc/grafana",
        namespace="monitoring",
        local_port=8030,
        remote_port=80,
        address="127.0.0.1",
        stack="infra",
    )
    item2 = PortForwardInfo(
        pid=22222,
        service="svc/prometheus",
        namespace="monitoring",
        local_port=8090,
        remote_port=9090,
        address="127.0.0.1",
        stack="infra",
    )
    mgr.save_forwards([item1, item2])

    with (
        patch.object(PortForwardInfo, "is_alive", new_callable=PropertyMock, return_value=True),
        patch("os.kill", side_effect=ProcessLookupError("No such process")),
    ):
        # Stopping only grafana should filter item1 and preserve item2
        stopped = mgr.stop_forwards(service_filter="grafana")
        assert stopped == 0

    # Item2 was preserved because of service_filter
    remaining_raw = json.loads((tmp_path / "port_forwards.json").read_text(encoding="utf-8"))
    assert len(remaining_raw) == 1
    assert remaining_raw[0]["service"] == "svc/prometheus"


# =============================================================================
# Process group containment
# =============================================================================


def test_stopping_a_forward_signals_its_whole_group() -> None:
    """A forward runs in its own session, so `kubectl` leads a group of its own.

    Signalling only the pid left anything it spawned running and the local port still
    bound, which reads as "stopped" in the daemon listing while the port is held.
    """
    from unittest.mock import patch

    from devops_cli.k8s import port_forward_daemon as module

    with (
        patch.object(module.os, "getpgid", side_effect=lambda pid: 4242 if pid else 7),
        patch.object(module.os, "killpg") as killpg,
        patch.object(module.os, "kill") as kill,
    ):
        stopped = module._terminate_process_group(9001)
    assert (stopped, killpg.call_count, kill.call_count) == (True, 1, 0)


def test_a_forward_sharing_this_processes_group_is_signalled_alone() -> None:
    """A forward recorded before sessions were used still shares the CLI's group.

    Signalling that group would kill the CLI running the stop command.
    """
    from unittest.mock import patch

    from devops_cli.k8s import port_forward_daemon as module

    with (
        patch.object(module.os, "getpgid", return_value=4242),
        patch.object(module.os, "killpg") as killpg,
        patch.object(module.os, "kill") as kill,
    ):
        stopped = module._terminate_process_group(9001)
    assert (stopped, killpg.call_count, kill.call_count) == (True, 0, 1)


def test_an_already_dead_forward_is_not_counted_as_stopped() -> None:
    """A stale record must not report a termination that did not happen."""
    from unittest.mock import patch

    from devops_cli.k8s import port_forward_daemon as module

    with patch.object(module.os, "getpgid", side_effect=ProcessLookupError):
        assert module._terminate_process_group(9001) is False


def test_a_forward_is_started_in_its_own_session() -> None:
    """`port-forward status` calls these background daemons; that holds only if detached."""
    import inspect

    from devops_cli.commands.k8s import networking

    source = inspect.getsource(networking)
    forward_call = source[source.index("kubectl") : source.index("active_forwards.append")]
    assert "start_new_session=True" in forward_call
