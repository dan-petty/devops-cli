"""Tests for how the Engine API payloads project into typed container models."""

from __future__ import annotations

from devops_cli.docker.engine import (
    decode_stream,
    project_container_state,
    project_container_stats,
)


def test_project_container_state_full_payload() -> None:
    """A full inspect payload projects into a typed container state model."""
    state = project_container_state(
        {
            "Id": "abc123",
            "Name": "/web",
            "Created": "2026-09-20T10:00:00Z",
            "Image": "sha256:deadbeef",
            "Config": {"Image": "nginx:1.27", "Labels": {"app": "web"}},
            "State": {
                "Status": "running",
                "Running": True,
                "ExitCode": 0,
                "StartedAt": "2026-09-20T10:00:05Z",
                "Health": {"Status": "healthy"},
            },
            "HostConfig": {"NetworkMode": "bridge"},
            "NetworkSettings": {"Ports": {"80/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8080"}]}},
        }
    )

    assert (
        state.container_id,
        state.name,
        state.image,
        state.status,
        state.running,
        state.health,
        state.network_mode,
        state.labels,
        state.ports["80/tcp"][0]["HostPort"],
    ) == (
        "abc123",
        "web",
        "nginx:1.27",
        "running",
        True,
        "healthy",
        "bridge",
        {"app": "web"},
        "8080",
    )


def test_project_container_state_tolerates_sparse_payload() -> None:
    """A minimal inspect payload projects without raising on absent sections."""
    state = project_container_state({"Id": "bare"})
    assert (state.container_id, state.running, state.health, state.labels, state.ports) == (
        "bare",
        False,
        None,
        {},
        {},
    )


def test_project_container_stats_computes_utilisation() -> None:
    """CPU, memory, network, and block counters are derived from a raw stats frame."""
    sample = project_container_stats(
        "cid",
        "svc",
        {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 400_000_000},
                "system_cpu_usage": 2_000_000_000,
                "online_cpus": 2,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 200_000_000},
                "system_cpu_usage": 1_000_000_000,
            },
            "memory_stats": {
                "usage": 104_857_600,
                "limit": 1_073_741_824,
                "stats": {"cache": 4_857_600},
            },
            "networks": {
                "eth0": {"rx_bytes": 1_000, "tx_bytes": 2_000},
                "eth1": {"rx_bytes": 500, "tx_bytes": 250},
            },
            "blkio_stats": {
                "io_service_bytes_recursive": [
                    {"op": "Read", "value": 4_096},
                    {"op": "Write", "value": 8_192},
                    {"op": "Sync", "value": 999},
                ]
            },
            "pids_stats": {"current": 12},
        },
    )

    assert (
        sample.cpu_percentage,
        sample.memory_usage_bytes,
        sample.memory_limit_bytes,
        sample.net_io_in_bytes,
        sample.net_io_out_bytes,
        sample.block_io_read_bytes,
        sample.block_io_write_bytes,
        sample.pids_count,
    ) == (40.0, 100_000_000, 1_073_741_824, 1_500, 2_250, 4_096, 8_192, 12)


def test_project_container_stats_handles_first_frame() -> None:
    """The first stats frame, which has no prior sample to diff, reports zero CPU."""
    sample = project_container_stats("cid", "svc", {"cpu_stats": {}, "precpu_stats": {}})
    assert (sample.cpu_percentage, sample.memory_percentage) == (0.0, 0.0)


def test_decode_stream_variants() -> None:
    """Engine API stream payloads decode from bytes, text, and absent values alike."""
    assert (decode_stream(b"hello"), decode_stream("hi"), decode_stream(None)) == (
        "hello",
        "hi",
        "",
    )


def test_decode_stream_replaces_invalid_utf8() -> None:
    """Invalid UTF-8 in container output is replaced rather than raising."""
    assert "�" in decode_stream(b"ok\xff")
