"""Unit tests for Kubernetes background port-forward daemon management."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
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


def _own_start_ticks() -> int:
    """This process's start time in clock ticks after boot, field 22 of /proc/self/stat."""
    stat = Path("/proc/self/stat").read_bytes()
    return int(stat[stat.rindex(b")") + 2 :].split()[19])


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
        start_ticks=_own_start_ticks(),
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
        start_ticks=None,
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
        start_ticks=_own_start_ticks(),
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
        start_ticks=None,
    )
    mgr.save_forwards([item])

    # Termination signals the forward's process group, so the group has to be resolvable.
    with (
        patch.object(PortForwardInfo, "is_alive", new_callable=PropertyMock, return_value=True),
        patch("os.getpgid", side_effect=lambda pid: 4242 if pid else 7),
        patch("os.killpg") as mock_killpg,
    ):
        stopped = mgr.stop_forwards()
        assert stopped == 1
        assert mock_killpg.called

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
            start_ticks=None,
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
        start_ticks=None,
    )
    item2 = PortForwardInfo(
        pid=22222,
        service="svc/prometheus",
        namespace="monitoring",
        local_port=8090,
        remote_port=9090,
        address="127.0.0.1",
        stack="infra",
        start_ticks=None,
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


# =============================================================================
# State file locking, atomic saves and reused pids (#961)
# =============================================================================


def test_concurrent_launches_keep_both_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two `devops k8s port-forward` runs at once both keep their forwards on record (#961).

    Each run read the state file, started its forwards and saved, with no lock. A run that
    read before the other saved wrote its own list over the other's, so those detached
    forwards held their local ports but were never listed or stopped again.
    """
    import subprocess
    import threading
    from types import SimpleNamespace

    from devops_cli.commands.k8s import networking
    from devops_cli.k8s import port_forward_daemon as module

    state_file = tmp_path / "port_forwards.json"
    # Each run is its own process with its own manager; they share only the state file.
    monkeypatch.setattr(
        module, "get_daemon_manager", lambda: PortForwardDaemonManager(state_file=state_file)
    )
    first_spawning, second_spawned = threading.Event(), threading.Event()

    def popen(cmd: list[str], **kwargs: object) -> MagicMock:
        if "svc/ollama" in cmd:
            second_spawned.set()
        else:
            first_spawning.set()
            # Without a lock, the second run reads the state file while the first waits here.
            second_spawned.wait(timeout=0.2)
        return MagicMock(pid=os.getpid())

    monkeypatch.setattr(
        networking, "subprocess", SimpleNamespace(Popen=popen, DEVNULL=subprocess.DEVNULL)
    )
    first = threading.Thread(
        target=networking._launch_port_forwards,
        args=([("otel", "svc/jaeger", 16686, 16686)], None, "127.0.0.1", "infra"),
    )
    first.start()
    first_spawning.wait(timeout=5)
    networking._launch_port_forwards(
        [("llm", "svc/ollama", 11434, 11434)], None, "127.0.0.1", "llm"
    )
    first.join(timeout=5)

    listed = PortForwardDaemonManager(state_file=state_file).list_forwards()
    assert sorted(f.service for f in listed) == ["svc/jaeger", "svc/ollama"]


def test_a_failed_save_leaves_the_previous_state_intact(tmp_path: Path) -> None:
    """The state file only changes by a whole-file replace (#961).

    It was rewritten in place, so a read during a save, or a save cut short, saw truncated
    JSON, which reads as no forwards at all, and the next save dropped every record.
    """
    state_file = tmp_path / "port_forwards.json"
    mgr = PortForwardDaemonManager(state_file=state_file)
    jaeger = PortForwardInfo(
        pid=os.getpid(),
        service="svc/jaeger",
        namespace="otel",
        local_port=16686,
        remote_port=16686,
        start_ticks=_own_start_ticks(),
    )
    mgr.save_forwards([jaeger])
    before = state_file.read_bytes()

    with (
        patch("os.replace", side_effect=OSError("No space left on device")),
        pytest.raises(OSError, match="No space left"),
    ):
        mgr.save_forwards([jaeger, jaeger.model_copy(update={"service": "svc/ollama"})])

    assert (state_file.read_bytes(), [f.service for f in mgr.list_forwards()]) == (
        before,
        ["svc/jaeger"],
    )


def test_reused_pid_is_neither_listed_nor_signalled(tmp_path: Path) -> None:
    """A recorded pid that now names another process is not a forward (#961).

    The state file outlives container and WSL restarts, and pids are handed out again. A
    record whose pid was live read as a running forward, and `port-forward stop` signalled
    whatever process held that pid. The start time recorded at launch tells them apart.
    """
    state_file = tmp_path / "port_forwards.json"
    mgr = PortForwardDaemonManager(state_file=state_file)
    stale = PortForwardInfo(
        pid=os.getpid(),
        service="svc/grafana",
        namespace="monitoring",
        local_port=8030,
        remote_port=80,
        start_ticks=_own_start_ticks() + 1,
    )
    mgr.save_forwards([stale])
    listed = mgr.list_forwards()
    mgr.save_forwards([stale])

    with patch("os.killpg") as killpg, patch("os.kill") as kill:
        stopped = mgr.stop_forwards()

    signals = [call.args for call in kill.call_args_list if call.args[1] != 0]
    assert (listed, stopped, killpg.call_args_list, signals) == ([], 0, [], [])


def test_without_proc_a_live_pid_is_a_running_forward(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Where /proc cannot be read, as on macOS, liveness falls back to signal 0 on the pid."""
    from devops_cli.k8s import port_forward_daemon as module

    monkeypatch.setattr(module, "_PROC_ROOT", tmp_path / "no-proc")
    recorded = {
        "service": "svc/qdrant",
        "namespace": "llm",
        "local_port": 6333,
        "remote_port": 6333,
        "start_ticks": None,
    }
    live = PortForwardInfo(pid=os.getpid(), **recorded)
    gone = PortForwardInfo(pid=99999999, **recorded)

    assert (module.process_start_ticks(os.getpid()), live.is_alive, gone.is_alive) == (
        None,
        True,
        False,
    )


@pytest.mark.parametrize("operation", ["list", "stop"])
def test_listing_and_stopping_wait_for_a_run_holding_the_lock(
    tmp_path: Path, operation: str
) -> None:
    """A list or stop that prunes the state file waits while another run holds its lock (#961).

    Without the lock, a stop during a start saved its list over the starting run's records.
    """
    import threading

    state_file = tmp_path / "port_forwards.json"
    holder = PortForwardDaemonManager(state_file=state_file)
    holder.save_forwards([])
    other = PortForwardDaemonManager(state_file=state_file)
    finished = threading.Event()
    run = other.list_forwards if operation == "list" else other.stop_forwards

    with holder.locked():
        worker = threading.Thread(target=lambda: (run(), finished.set()))
        worker.start()
        waited = not finished.wait(timeout=0.1)
    worker.join(timeout=5)

    assert (waited, finished.is_set()) == (True, True)


def test_a_status_check_with_no_state_file_creates_nothing(tmp_path: Path) -> None:
    """Listing with no state file returns nothing and leaves no directory or lock behind."""
    state_file = tmp_path / "k8s" / "port_forwards.json"

    listed = PortForwardDaemonManager(state_file=state_file).list_forwards()

    assert (listed, state_file.parent.exists()) == ([], False)
