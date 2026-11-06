"""Resource use of a sandbox container: its cgroup v2 tree, or the Engine API stats.

The cgroup trees live under `tmp_path`. The cgroup path guard refuses a root such as `/var` or `/usr`,
so these tests need a temporary directory outside those roots (the default `/tmp` is fine).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.metrics import (
    parse_cgroup_v2_directory,
    read_cgroup_v2_metrics,
)
from devops_cli.sandbox.models import (
    CgroupV2Metrics,
    SandboxInstance,
)
from tests.support.fakes.docker_engine import DockerEngineFake
from tests.support.sandbox import (
    engine_stats_frame,
    port_of,
)


def test_cgroup_v2_metrics_model() -> None:
    """Test CgroupV2Metrics model instantiation and calculations."""
    metrics = CgroupV2Metrics(
        cpu_percent=45.2,
        memory_current_bytes=104857600,  # 100 MB
        memory_limit_bytes=209715200,  # 200 MB
        memory_peak_bytes=157286400,  # 150 MB
        memory_usage_percent=50.0,
        page_faults_total=1250,
        pids_current=12,
        io_read_bytes=1024000,
        io_write_bytes=2048000,
    )
    assert metrics.cpu_percent == 45.2
    assert metrics.memory_usage_percent == 50.0
    assert metrics.memory_current_mb == 100.0
    assert metrics.memory_limit_mb == 200.0

    dump = metrics.model_dump()
    assert dump["cpu_percent"] == 45.2
    assert dump["pids_current"] == 12


def test_parse_cgroup_v2_directory(tmp_path: Path) -> None:
    """Test parsing cgroup v2 filesystem controller files."""
    # Setup mock cgroup v2 controller files
    cgroup_dir = tmp_path / "cgroup" / "sandbox-1"
    cgroup_dir.mkdir(parents=True)

    (cgroup_dir / "memory.current").write_text("104857600\n")
    (cgroup_dir / "memory.peak").write_text("157286400\n")
    (cgroup_dir / "memory.max").write_text("209715200\n")
    (cgroup_dir / "pids.current").write_text("18\n")
    (cgroup_dir / "cpu.stat").write_text(
        "usage_usec 5000000\nuser_usec 4000000\nsystem_usec 1000000\nnr_periods 100\nnr_throttled 5\nthrottled_usec 20000\n"
    )
    (cgroup_dir / "memory.stat").write_text("pgfault 4321\npgmajfault 12\n")
    (cgroup_dir / "io.stat").write_text("8:0 rbytes=5242880 wbytes=10485760\n")

    metrics = parse_cgroup_v2_directory(cgroup_dir)
    assert metrics is not None
    assert metrics.memory_current_bytes == 104857600
    assert metrics.memory_peak_bytes == 157286400
    assert metrics.memory_limit_bytes == 209715200
    assert metrics.memory_usage_percent == pytest.approx(50.0, 0.1)
    assert metrics.pids_current == 18
    assert metrics.page_faults_total == 4321
    assert metrics.io_read_bytes == 5242880
    assert metrics.io_write_bytes == 10485760


def test_parse_cgroup_v2_directory_traversal_and_forbidden_paths() -> None:
    """Verify parse_cgroup_v2_directory rejects traversal sequences and forbidden host system paths."""
    assert parse_cgroup_v2_directory("../../etc") is None
    assert parse_cgroup_v2_directory("/etc") is None
    assert parse_cgroup_v2_directory("/root") is None
    assert parse_cgroup_v2_directory("") is None


def test_parse_cgroup_v2_directory_unlimited_memory(tmp_path: Path) -> None:
    """Test parsing cgroup v2 controller when memory.max is 'max' (unlimited)."""
    cgroup_dir = tmp_path / "cgroup" / "sandbox-2"
    cgroup_dir.mkdir(parents=True)

    (cgroup_dir / "memory.current").write_text("52428800\n")
    (cgroup_dir / "memory.max").write_text("max\n")

    metrics = parse_cgroup_v2_directory(cgroup_dir)
    assert metrics is not None
    assert metrics.memory_current_bytes == 52428800
    assert metrics.memory_limit_bytes is None
    assert metrics.memory_usage_percent is None


def test_parse_cgroup_v2_directory_missing_dir(tmp_path: Path) -> None:
    """Test graceful handling when cgroup directory does not exist."""
    non_existent = tmp_path / "does_not_exist"
    assert parse_cgroup_v2_directory(non_existent) is None


def test_read_cgroup_v2_metrics_fallback_to_docker_stats(
    docker_daemon: DockerEngineFake, tmp_path: Path
) -> None:
    """With no cgroup tree for the container, its resource use comes from the engine's stats."""
    container_id = docker_daemon.add_container("stats-fallback")
    docker_daemon.script_stats("stats-fallback", [engine_stats_frame(), engine_stats_frame()])

    metrics = read_cgroup_v2_metrics(container_id=container_id, cgroup_root=tmp_path)

    assert metrics is not None
    assert (
        metrics.cpu_percent,
        metrics.memory_current_bytes,
        metrics.memory_limit_bytes,
        metrics.memory_usage_percent,
        metrics.pids_current,
    ) == (25.0, 52_428_800, 209_715_200, 25.0, 4)


def test_a_controller_file_that_holds_no_number_reads_as_no_value(tmp_path: Path) -> None:
    """A controller file with text where a number belongs reads as no usage; a missing limit is none."""
    cgroup_dir = tmp_path / "cgroup" / "bad-files"
    cgroup_dir.mkdir(parents=True)
    (cgroup_dir / "memory.current").write_text("not-an-int\n")

    metrics = parse_cgroup_v2_directory(cgroup_dir)

    assert metrics is not None
    assert (metrics.memory_current_bytes, metrics.memory_limit_bytes) == (0, None)


def test_engine_stats_become_cgroup_metrics(
    docker_daemon: DockerEngineFake, tmp_path: Path
) -> None:
    """Engine API resource samples project into cgroup metrics."""
    container_id = docker_daemon.add_container("cont-valid")
    docker_daemon.script_stats("cont-valid", [engine_stats_frame(), engine_stats_frame()])

    res = read_cgroup_v2_metrics(container_id=container_id, cgroup_root=tmp_path)

    assert res is not None
    assert (
        res.cpu_percent,
        res.memory_current_bytes,
        res.memory_limit_bytes,
        res.pids_current,
        res.network_rx_bytes,
        res.network_tx_bytes,
    ) == (25.0, 52_428_800, 209_715_200, 4, 1_500_000, 3_200_000)


def test_an_unreachable_engine_gives_no_cgroup_metrics(
    docker_daemon: DockerEngineFake, tmp_path: Path
) -> None:
    """An unreachable daemon degrades to None rather than propagating."""
    docker_daemon.fail("containers.get", RuntimeError("daemon offline"))

    assert read_cgroup_v2_metrics(container_id="cont-failed", cgroup_root=tmp_path) is None


def test_read_cgroup_v2_metrics_finds_the_docker_scope_of_a_container(tmp_path: Path) -> None:
    """The cgroup of a container is read from its docker scope under the cgroup root."""
    scope = tmp_path / "system.slice" / "docker-c1.scope"
    scope.mkdir(parents=True)
    (scope / "pids.current").write_text("7\n")

    res = read_cgroup_v2_metrics(container_id="c1", cgroup_root=tmp_path)

    assert res is not None
    assert res.pids_current == 7


def test_parse_cgroup_v2_cpu_delta_calculation(tmp_path: Path) -> None:
    """Test parse_cgroup_v2_directory calculates delta CPU percent and records cpu_usage_usec."""
    cgroup_dir = tmp_path / "cgroup" / "delta-test"
    cgroup_dir.mkdir(parents=True)
    (cgroup_dir / "cpu.stat").write_text("usage_usec 2500000\n")

    # Initial sample without prior interval -> None (unknown) but records usage_usec
    first_sample = parse_cgroup_v2_directory(cgroup_dir)
    assert first_sample is not None
    assert first_sample.cpu_usage_usec == 2500000
    assert first_sample.cpu_percent is None

    # Second sample: previous was 2,000,000 usec, elapsed 1.0 sec -> delta = 500,000 usec -> 50.0%
    second_sample = parse_cgroup_v2_directory(
        cgroup_dir,
        previous_cpu_usec=2000000,
        elapsed_sec=1.0,
    )
    assert second_sample is not None
    assert second_sample.cpu_usage_usec == 2500000
    assert second_sample.cpu_percent == 50.0

    # Read helper test with delta arguments
    read_sample = read_cgroup_v2_metrics(
        cgroup_path=cgroup_dir,
        previous_cpu_usec=2000000,
        elapsed_sec=1.0,
    )
    assert read_sample is not None
    assert read_sample.cpu_percent == 50.0


def test_parse_cgroup_v2_network_stat(tmp_path: Path) -> None:
    """The network counters come from the network.stat file of a cgroup directory."""
    cgroup_dir = tmp_path / "cgroup" / "net-test"
    cgroup_dir.mkdir(parents=True)
    (cgroup_dir / "network.stat").write_text("rx_bytes 10485760\ntx_bytes 20971520\n")

    cgroup_metrics = parse_cgroup_v2_directory(cgroup_dir)

    assert cgroup_metrics is not None
    assert cgroup_metrics.network_rx_bytes == 10485760
    assert cgroup_metrics.network_tx_bytes == 20971520


def test_engine_stats_report_the_network_io_of_a_container(
    tmp_path: Path, docker_daemon: DockerEngineFake
) -> None:
    """The network counters come from the Engine API stats of a container with no cgroup tree."""
    container_id = docker_daemon.add_container("net-test")
    docker_daemon.script_stats("net-test", [engine_stats_frame(), engine_stats_frame()])

    engine_metrics = read_cgroup_v2_metrics(container_id=container_id, cgroup_root=tmp_path)

    assert engine_metrics is not None
    assert (engine_metrics.network_rx_bytes, engine_metrics.network_tx_bytes) == (
        1_500_000,
        3_200_000,
    )


def test_memory_percent_of_a_cgroup_is_zero_when_nothing_is_used(tmp_path: Path) -> None:
    """Memory use is 0.0 percent when no byte is used, and unknown when the limit is."""
    results = []
    for name, current, limit in (
        ("zero", "0", "1000"),
        ("tenth", "100", "1000"),
        ("unlimited", "100", "max"),
        ("zero-limit", "100", "0"),
    ):
        cgroup_dir = tmp_path / name
        cgroup_dir.mkdir()
        (cgroup_dir / "memory.current").write_text(f"{current}\n")
        (cgroup_dir / "memory.max").write_text(f"{limit}\n")
        metrics = parse_cgroup_v2_directory(cgroup_dir)
        results.append(metrics.memory_usage_percent if metrics else "no metrics")

    assert results == [0.0, 10.0, None, None]


def test_parse_open_fds_cgroup(tmp_path: Path) -> None:
    """Test parsing open file descriptor counts from cgroup stat files."""
    cgroup_dir = tmp_path / "cgroup" / "fds-test"
    cgroup_dir.mkdir(parents=True)
    (cgroup_dir / "fds.current").write_text("38\n")

    parsed = parse_cgroup_v2_directory(cgroup_dir)

    assert parsed is not None
    assert parsed.open_fds_count == 38


def test_read_cgroup_v2_metrics_fallback_when_path_invalid(
    tmp_path: Path, docker_daemon: DockerEngineFake
) -> None:
    """Test read_cgroup_v2_metrics falls back to container_id when cgroup_path is invalid."""
    container_id = docker_daemon.add_container("cont-fallback-1")
    docker_daemon.script_stats("cont-fallback-1", [engine_stats_frame(), engine_stats_frame()])

    res = read_cgroup_v2_metrics(
        container_id=container_id,
        cgroup_path=tmp_path / "nonexistent",
        cgroup_root=tmp_path,
    )

    assert res is not None
    assert res.cpu_percent == 25.0


def test_the_engine_threads_the_previous_sample_into_the_next_cpu_reading(
    register_sandbox: Callable[..., SandboxInstance], prom_server: str, tmp_path: Path
) -> None:
    """Consecutive engine readings give a CPU percent from the change in CPU time between them."""
    instance = register_sandbox("sandbox-delta-inst", host_ports=[port_of(prom_server)])
    scope = tmp_path / "cgroup" / "system.slice" / f"docker-{instance.container_id}.scope"
    scope.mkdir(parents=True)
    (scope / "cpu.stat").write_text("usage_usec 1000000\n")
    engine = WorkloadSandboxEngine(cgroup_root=tmp_path / "cgroup")

    first = engine.metrics("sandbox-delta-inst")
    (scope / "cpu.stat").write_text("usage_usec 1500000\n")
    second = engine.metrics("sandbox-delta-inst")

    assert first.cgroup is not None
    assert second.cgroup is not None
    assert (first.cgroup.cpu_percent, second.cgroup.cpu_percent is not None) == (None, True)
    assert second.cgroup.cpu_usage_usec == 1_500_000


@pytest.mark.parametrize("forbidden", ["/sys/kernel", "/etc", "/var/log", "/usr/bin"])
def test_a_system_directory_outside_the_cgroup_tree_is_never_read_as_a_cgroup(
    forbidden: str,
) -> None:
    """Only the cgroup mount and its descendants are read; /sys siblings and system dirs are not."""
    assert parse_cgroup_v2_directory(forbidden) is None
