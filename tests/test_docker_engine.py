"""Unit tests for the unified Docker Engine API socket service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
from docker.errors import DockerException
from typer.testing import CliRunner

from devops_cli.commands.docker import app as docker_app
from devops_cli.config.constants import (
    CONST_SANDBOX_DOCKER_INTERNAL_NET,
)
from devops_cli.docker.engine import (
    DockerEngineService,
    build_cache_report,
    decode_stream,
    get_engine,
    project_container_state,
    project_container_stats,
)
from devops_cli.exceptions.docker import DockerDaemonUnavailableError, DockerEngineError

runner = CliRunner()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Connection lifecycle & host resolution
# ─────────────────────────────────────────────────────────────────────────────


def test_resolve_host_docstring_mentions_preflight_and_dns() -> None:
    """resolve_host docstring states it is a pre-flight check and documents the DNS window."""
    doc = DockerEngineService.resolve_host.__doc__ or ""
    assert ("pre-flight" in doc, "DNS" in doc) == (True, True)


def test_parse_host_contract() -> None:
    """Pin docker.utils.parse_host output mappings for docker 7.2.0 contract stability."""
    import docker.constants
    import docker.utils

    cases = [
        ("TCP://192.0.2.1:2376", "http://192.0.2.1:2376"),
        ("192.0.2.1:2375", "http://192.0.2.1:2375"),
        ("HTTPS://192.0.2.1:2376", "https://192.0.2.1:2376"),
        ("ssh://u@192.0.2.1", "ssh://u@192.0.2.1:22"),
        ("unix:///x", "http+unix:///x"),
        (
            "unix:///run/user/1000/podman/podman.sock",
            "http+unix:///run/user/1000/podman/podman.sock",
        ),
        (None, "http+unix:///var/run/docker.sock"),
    ]
    results = [
        docker.utils.parse_host(raw, docker.constants.IS_WINDOWS_PLATFORM) for raw, _ in cases
    ]
    expected = [exp for _, exp in cases]
    assert results == expected

    for bad in [
        "tcp://192.0.2.1",
        "localhost:2375",
        "ssh://u@192.0.2.1:22/run/user/1000/podman/podman.sock",
    ]:
        with pytest.raises(DockerException):
            docker.utils.parse_host(bad, docker.constants.IS_WINDOWS_PLATFORM)


def test_resolve_host_defaults_to_unix_socket(docker_endpoint_env: Any) -> None:
    """With no DOCKER_HOST set, the daemon Unix domain socket is addressed."""
    engine = DockerEngineService()
    endpoint = engine.resolve_host()
    assert (endpoint.source, endpoint.raw, endpoint.base_url) == (
        "/var/run/docker.sock",
        "unix:///var/run/docker.sock",
        "http+unix:///var/run/docker.sock",
    )


def test_resolve_host_validates_network_endpoints(docker_endpoint_env: Any) -> None:
    """A TCP DOCKER_HOST is routed through SSRF egress validation before connecting."""
    engine = DockerEngineService()
    with (
        patch.dict(os.environ, {"DOCKER_HOST": "tcp://example.com:2375"}),
        patch("devops_cli.core.validation.validate_service_url") as mock_validate,
    ):
        endpoint = engine.resolve_host()

    assert (
        endpoint.source,
        endpoint.raw,
        endpoint.base_url,
        mock_validate.call_args[0][0],
    ) == (
        "DOCKER_HOST",
        "tcp://example.com:2375",
        "http://example.com:2375",
        "http://example.com:2375",
    )


def test_resolve_host_leaves_unix_socket_unvalidated(docker_endpoint_env: Any) -> None:
    """A Unix socket endpoint bypasses network egress validation entirely."""
    engine = DockerEngineService()
    with (
        patch.dict(os.environ, {"DOCKER_HOST": "unix:///run/user/1000/docker.sock"}),
        patch("devops_cli.core.validation.validate_service_url") as mock_validate,
    ):
        endpoint = engine.resolve_host()

    assert (
        endpoint.source,
        endpoint.raw,
        endpoint.base_url,
        mock_validate.called,
    ) == (
        "DOCKER_HOST",
        "unix:///run/user/1000/docker.sock",
        "http+unix:///run/user/1000/docker.sock",
        False,
    )


def test_client_is_cached_across_calls(docker_endpoint_env: Any) -> None:
    """The negotiated Engine API client is reused instead of re-handshaking per call."""
    engine = DockerEngineService()
    with patch("docker.DockerClient", return_value=MagicMock()) as mock_client:
        first = engine.client()
        second = engine.client()

    assert (first is second, mock_client.call_count) == (True, 1)


def test_client_failure_raises_daemon_unavailable(docker_endpoint_env: Any) -> None:
    """An unreachable daemon raises a typed, host-annotated failure."""
    engine = DockerEngineService()
    with patch("docker.DockerClient", side_effect=RuntimeError("no such file")):
        with pytest.raises(DockerDaemonUnavailableError) as exc_info:
            engine.client()

    assert "/var/run/docker.sock: no such file" in str(exc_info.value)


@pytest.mark.parametrize(
    "docker_host",
    [
        "TCP://192.0.2.1:2376",
        "Tcp://192.0.2.1:2376",
        "HTTP://192.0.2.1:2375",
        "HTTPS://192.0.2.1:2376",
        "192.0.2.1:2375",
        "[::1]:2375",
        "tcp://192.0.2.1:2375",
    ],
)
def test_endpoint_table_refused_network_endpoints(
    docker_host: str, docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prohibited private/TEST-NET endpoints are refused before building any client."""
    monkeypatch.setenv("DOCKER_HOST", docker_host)
    engine = DockerEngineService()
    with patch("docker.DockerClient") as mock_client:
        with pytest.raises(DockerDaemonUnavailableError) as exc_info:
            engine.client()

    assert (mock_client.called, "DOCKER_HOST" in str(exc_info.value)) == (False, True)


def test_endpoint_table_allowed_network_endpoint(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When private networks are permitted, tcp:// normalises to http:// for client dialling."""
    monkeypatch.setenv("DOCKER_HOST", "tcp://192.0.2.1:2375")
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")

    engine = DockerEngineService()
    with patch("docker.DockerClient") as mock_client:
        engine.client()

    assert (mock_client.called, mock_client.call_args.kwargs.get("base_url")) == (
        True,
        "http://192.0.2.1:2375",
    )


def test_endpoint_table_unix_socket_reaches_client(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unix socket addresses reach the SDK client directly without egress validation."""
    monkeypatch.setenv("DOCKER_HOST", "unix:///run/user/1000/docker.sock")
    engine = DockerEngineService()
    with patch("docker.DockerClient") as mock_client:
        engine.client()

    assert (mock_client.called, mock_client.call_args.kwargs.get("base_url")) == (
        True,
        "http+unix:///run/user/1000/docker.sock",
    )


def test_endpoint_table_ssh_raises_daemon_unavailable(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SSH endpoints without paramiko fail fast before network I/O."""
    monkeypatch.setenv("DOCKER_HOST", "ssh://u@192.0.2.1")
    engine = DockerEngineService()
    with pytest.raises(DockerDaemonUnavailableError) as exc_info:
        engine.client()

    assert "DOCKER_HOST" in str(exc_info.value)


@pytest.mark.parametrize(
    "docker_host",
    [
        "fd://3",
        "localhost:2375",
        "tcp://192.0.2.1",
        "tcp://192.0.2.1:99999",
        "tcp://192.0.2.1:abc",
    ],
)
def test_endpoint_table_invalid_formats_raise_daemon_unavailable(
    docker_host: str, docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Malformed or unsupported endpoint schemes raise DockerDaemonUnavailableError."""
    monkeypatch.setenv("DOCKER_HOST", docker_host)
    engine = DockerEngineService()
    with pytest.raises(DockerDaemonUnavailableError) as exc_info:
        engine.resolve_host()

    assert "DOCKER_HOST" in str(exc_info.value)


def test_context_current_context_refused_on_private_network(
    docker_endpoint_env: Any, tmp_path: Path
) -> None:
    """A context configured as currentContext in config.json is validated against SSRF."""
    import json

    docker_endpoint_env("myctx", "tcp://192.0.2.10:2376")
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"currentContext": "myctx"}), encoding="utf-8")

    engine = DockerEngineService()
    with patch("docker.DockerClient") as mock_client:
        with pytest.raises(DockerDaemonUnavailableError) as exc_info:
            engine.client()

    assert (mock_client.called, "myctx" in str(exc_info.value)) == (False, True)


def test_context_docker_context_env_refused_on_private_network(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A context selected via DOCKER_CONTEXT is validated against SSRF."""
    docker_endpoint_env("myctx", "tcp://192.0.2.10:2376")
    monkeypatch.setenv("DOCKER_CONTEXT", "myctx")

    engine = DockerEngineService()
    with patch("docker.DockerClient") as mock_client:
        with pytest.raises(DockerDaemonUnavailableError) as exc_info:
            engine.client()

    assert (mock_client.called, "myctx" in str(exc_info.value)) == (False, True)


def test_context_private_network_allowed_reaches_client(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With allow_private_network enabled, the context endpoint reaches DockerClient."""
    docker_endpoint_env("myctx", "tcp://192.0.2.10:2376")
    monkeypatch.setenv("DOCKER_CONTEXT", "myctx")
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")

    engine = DockerEngineService()
    with patch("docker.DockerClient") as mock_client:
        engine.client()

    assert (mock_client.called, mock_client.call_args.kwargs.get("base_url")) == (
        True,
        "http://192.0.2.10:2376",
    )


def test_context_tls_verify_and_cert_path_applies_https(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Environment TLS settings apply to context endpoints, upgrading scheme to https."""
    docker_endpoint_env("myctx", "tcp://192.0.2.10:2376")
    monkeypatch.setenv("DOCKER_CONTEXT", "myctx")
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")

    cert_dir = tmp_path / "certs"
    cert_dir.mkdir(parents=True, exist_ok=True)
    (cert_dir / "ca.pem").write_text("", encoding="utf-8")
    (cert_dir / "cert.pem").write_text("", encoding="utf-8")
    (cert_dir / "key.pem").write_text("", encoding="utf-8")
    monkeypatch.setenv("DOCKER_TLS_VERIFY", "1")
    monkeypatch.setenv("DOCKER_CERT_PATH", str(cert_dir))

    engine = DockerEngineService()
    with patch("docker.DockerClient") as mock_client:
        engine.client()

    assert (
        mock_client.called,
        mock_client.call_args.kwargs.get("base_url"),
        "tls" in mock_client.call_args.kwargs,
    ) == (True, "https://192.0.2.10:2376", True)


def test_context_precedence_and_overrides(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify DOCKER_CONTEXT beats currentContext, and currentContext: default gives socket."""
    import json

    docker_endpoint_env("ctx1", "unix:///run/user/1000/ctx1.sock")
    docker_endpoint_env("ctx2", "unix:///run/user/1000/ctx2.sock")

    # DOCKER_CONTEXT beats currentContext
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"currentContext": "ctx1"}), encoding="utf-8")
    monkeypatch.setenv("DOCKER_CONTEXT", "ctx2")
    engine = DockerEngineService()
    endpoint = engine.resolve_host()
    assert (endpoint.source, endpoint.raw) == ("ctx2", "unix:///run/user/1000/ctx2.sock")

    # currentContext: default gives the default socket
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    config_file.write_text(json.dumps({"currentContext": "default"}), encoding="utf-8")
    DockerEngineService.reset_instance()
    engine = DockerEngineService()
    endpoint = engine.resolve_host()
    assert (endpoint.source, endpoint.raw, endpoint.base_url) == (
        "/var/run/docker.sock",
        "unix:///var/run/docker.sock",
        "http+unix:///var/run/docker.sock",
    )


def test_context_missing_context_errors(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Missing context in DOCKER_CONTEXT or currentContext raises typed error naming context."""
    import json

    monkeypatch.setenv("DOCKER_CONTEXT", "nope")
    engine = DockerEngineService()
    with patch("docker.DockerClient") as mock_client:
        with pytest.raises(DockerDaemonUnavailableError) as exc_info:
            engine.resolve_host()
    assert (mock_client.called, 'context "nope": context not found' in str(exc_info.value)) == (
        False,
        True,
    )

    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"currentContext": "gone"}), encoding="utf-8")
    DockerEngineService.reset_instance()
    engine = DockerEngineService()
    with patch("docker.DockerClient") as mock_client:
        with pytest.raises(DockerDaemonUnavailableError) as exc_info:
            engine.resolve_host()
    assert (mock_client.called, 'context "gone": context not found' in str(exc_info.value)) == (
        False,
        True,
    )


def test_docker_host_env_overrides_context(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DOCKER_HOST has highest precedence over any configured Docker context."""
    docker_endpoint_env("myctx", "unix:///run/user/1000/myctx.sock")
    monkeypatch.setenv("DOCKER_CONTEXT", "myctx")
    monkeypatch.setenv("DOCKER_HOST", "unix:///run/user/1000/host.sock")

    engine = DockerEngineService()
    endpoint = engine.resolve_host()
    assert (endpoint.source, endpoint.raw) == ("DOCKER_HOST", "unix:///run/user/1000/host.sock")


@pytest.mark.parametrize(
    ("docker_host", "expected_fragment"),
    [
        ("tcp://192.0.2.1:2375", "DOCKER_HOST"),
        ("tcp://192.0.2.1:abc", "DOCKER_HOST"),
        ("abc://x/[/x]", "abc://x/[/x]"),
    ],
)
def test_docker_images_cli_no_traceback_on_bad_endpoints(
    docker_host: str,
    expected_fragment: str,
    docker_endpoint_env: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """devops docker images exits 1 with a single clean error line and no traceback (#1108)."""
    monkeypatch.setenv("DOCKER_HOST", docker_host)
    res = runner.invoke(docker_app, ["images"])
    assert (res.exit_code, "Traceback" in res.output, expected_fragment in res.output) == (
        1,
        False,
        True,
    )


def test_unix_socket_path_resolution(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """unix_socket_path returns socket Path for unix endpoints and None for network hosts."""
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")

    monkeypatch.setenv("DOCKER_HOST", "unix:///run/user/1000/docker.sock")
    engine = DockerEngineService()
    assert engine.unix_socket_path() == Path("/run/user/1000/docker.sock")

    DockerEngineService.reset_instance()
    monkeypatch.setenv("DOCKER_HOST", "tcp://192.0.2.1:2375")
    engine = DockerEngineService()
    assert engine.unix_socket_path() is None


def test_close_releases_socket_and_clears_cache() -> None:
    """Closing the service releases the socket and drops memoised responses."""
    engine = DockerEngineService()
    mock_client = MagicMock()
    engine._client = mock_client
    engine._set_cached("disk_usage", {"BuildCache": []})

    engine.close()

    assert (mock_client.close.called, engine._client, engine._cache) == (True, None, {})


def test_singleton_instance_reuse_and_reset() -> None:
    """The engine singleton is shared process-wide and resettable for test isolation."""
    DockerEngineService.reset_instance()
    first = get_engine()
    assert first is DockerEngineService.get_instance()

    DockerEngineService.reset_instance()
    assert get_engine() is not first


def test_ping_caches_reachability(docker_engine: Any) -> None:
    """Daemon liveness probes are TTL-cached so repeated commands avoid extra round-trips."""
    mock_client = MagicMock()
    mock_client.ping.return_value = True

    with docker_engine(mock_client) as engine:
        assert (engine.ping(), engine.ping()) == (True, True)

    assert mock_client.ping.call_count == 1


def test_ping_returns_false_when_daemon_down(docker_engine: Any) -> None:
    """A failing socket ping reports the daemon as unreachable rather than raising."""
    mock_client = MagicMock()
    mock_client.ping.side_effect = RuntimeError("connection refused")

    with docker_engine(mock_client) as engine:
        assert engine.ping() is False


def test_cache_entry_expires(docker_engine: Any) -> None:
    """A memoised response is discarded once its TTL elapses."""
    mock_client = MagicMock()
    with docker_engine(mock_client) as engine:
        engine._set_cached("probe", "value", ttl=0.0)
        assert engine._get_cached("probe") is None


# ─────────────────────────────────────────────────────────────────────────────
# 2. Engine API payload projection
# ─────────────────────────────────────────────────────────────────────────────


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


# ─────────────────────────────────────────────────────────────────────────────
# 3. Container introspection & lifecycle
# ─────────────────────────────────────────────────────────────────────────────


def test_list_and_inspect_containers(docker_engine: Any) -> None:
    """Containers are listed and inspected as typed state models."""
    mock_container = MagicMock()
    mock_container.attrs = {
        "Id": "cid-1",
        "Name": "/svc",
        "State": {"Status": "running", "Running": True},
    }
    mock_client = MagicMock()
    mock_client.containers.list.return_value = [mock_container]
    mock_client.containers.get.return_value = mock_container

    with docker_engine(mock_client) as engine:
        listed = engine.list_containers(name="svc")
        inspected = engine.inspect_container("cid-1")

    assert (len(listed), listed[0].name, inspected.running) == (1, "svc", True)
    assert mock_client.containers.list.call_args.kwargs["filters"] == {"name": "svc"}


def test_list_containers_failure_is_typed(docker_engine: Any) -> None:
    """A daemon listing failure surfaces as a typed engine error."""
    mock_client = MagicMock()
    mock_client.containers.list.side_effect = RuntimeError("daemon busy")

    with docker_engine(mock_client) as engine:
        with pytest.raises(DockerEngineError, match="Container listing failed"):
            engine.list_containers()


def test_container_stats_and_stream(docker_engine: Any) -> None:
    """Single-shot and streamed stats both yield typed resource samples."""
    frame = {"pids_stats": {"current": 3}, "memory_stats": {"usage": 100, "limit": 1000}}
    mock_container = MagicMock()
    mock_container.name = "svc"
    mock_container.stats.side_effect = [frame, iter([frame, frame, frame])]
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container

    with docker_engine(mock_client) as engine:
        single = engine.container_stats("cid-1")
        streamed = list(engine.stream_container_stats("cid-1", samples=2))

    assert (single.pids_count, len(streamed), streamed[0].name) == (3, 2, "svc")


def test_stream_container_stats_unbounded_drains_source(docker_engine: Any) -> None:
    """Without a sample cap, the stats stream is drained to exhaustion."""
    frame = {"pids_stats": {"current": 1}}
    mock_container = MagicMock()
    mock_container.name = "svc"
    mock_container.stats.return_value = iter([frame, frame])
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container

    with docker_engine(mock_client) as engine:
        assert len(list(engine.stream_container_stats("cid-1"))) == 2


def test_lifecycle_operations_use_direct_api_calls(docker_engine: Any) -> None:
    """Stop, remove, exec, wait, and logs issue direct Engine API calls."""
    mock_container = MagicMock()
    mock_container.exec_run.return_value = (0, b"output\n")
    mock_container.wait.return_value = {"StatusCode": 7}
    mock_container.logs.return_value = b"log line\n"
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container

    with docker_engine(mock_client) as engine:
        engine.stop_container("cid-1", timeout=3)
        engine.remove_container("cid-2")
        exec_result = engine.exec_in_container("cid-1", ["ls"], workdir="/app")
        exit_code = engine.wait_container("cid-1", timeout=30)
        logs = engine.container_logs("cid-1", tail=10)

    assert (exec_result, exit_code, logs) == ((0, "output\n"), 7, "log line\n")
    mock_client.api.stop.assert_called_once_with("cid-1", timeout=3)
    assert mock_client.api.remove_container.call_count == 2


def test_exec_in_container_hands_its_environment_to_the_exec(docker_engine: Any) -> None:
    """An exec's environment reaches the Engine API, and none is sent when the caller has none."""
    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    mock_container = MagicMock()
    mock_container.exec_run.return_value = (0, b"")
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container

    with docker_engine(mock_client) as engine:
        engine.exec_in_container("cid-1", ["env"], environment={"TRACEPARENT": traceparent})
        engine.exec_in_container("cid-1", ["env"], workdir="/app")

    assert mock_container.exec_run.call_args_list == [
        call(["env"], workdir=None, environment={"TRACEPARENT": traceparent}),
        call(["env"], workdir="/app", environment=None),
    ]


def test_remove_container_tolerates_already_reaped(docker_engine: Any) -> None:
    """Removing a container the daemon already reclaimed is not an error."""
    mock_client = MagicMock()
    mock_client.api.remove_container.side_effect = RuntimeError("no such container")

    with docker_engine(mock_client) as engine:
        engine.remove_container("gone")  # Must not raise.


def test_stop_container_failure_is_typed(docker_engine: Any) -> None:
    """A rejected stop surfaces as a typed, container-annotated engine error."""
    mock_client = MagicMock()
    mock_client.api.stop.side_effect = RuntimeError("container unresponsive")

    with docker_engine(mock_client) as engine:
        with pytest.raises(DockerEngineError, match="Container termination failed"):
            engine.stop_container("cid-1")


def test_create_container_failure_records_image(docker_engine: Any) -> None:
    """A failed creation annotates the offending image in the typed error."""
    mock_client = MagicMock()
    mock_client.containers.create.side_effect = RuntimeError("no such image")

    with docker_engine(mock_client) as engine:
        with pytest.raises(DockerEngineError) as exc_info:
            engine.create_container(image="missing:latest")

    assert exc_info.value.details.get("image") == "missing:latest"


def test_container_logs_failure_is_typed(docker_engine: Any) -> None:
    """A log retrieval failure surfaces as a typed engine error."""
    mock_container = MagicMock()
    mock_container.logs.side_effect = RuntimeError("stream closed")
    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container

    with docker_engine(mock_client) as engine:
        with pytest.raises(DockerEngineError, match="Container log retrieval failed"):
            engine.container_logs("cid-1")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Internal network provisioning
# ─────────────────────────────────────────────────────────────────────────────


def test_ensure_internal_network_accepts_conforming_network(docker_engine: Any) -> None:
    """An existing internal bridge network is accepted without being recreated."""
    mock_network = MagicMock()
    mock_network.attrs = {"Internal": True}
    mock_client = MagicMock()
    mock_client.networks.get.return_value = mock_network

    with docker_engine(mock_client) as engine:
        assert engine.ensure_internal_network(CONST_SANDBOX_DOCKER_INTERNAL_NET) is True

    assert mock_client.networks.create.called is False


def test_ensure_internal_network_recreates_drifted_network(docker_engine: Any) -> None:
    """A network that lost its internal (egress-denied) flag is removed and recreated."""
    mock_network = MagicMock()
    mock_network.attrs = {"Internal": False}
    mock_client = MagicMock()
    mock_client.networks.get.return_value = mock_network

    with docker_engine(mock_client) as engine:
        assert engine.ensure_internal_network(CONST_SANDBOX_DOCKER_INTERNAL_NET) is True

    assert mock_network.remove.called
    assert mock_client.networks.create.call_args.kwargs == {"driver": "bridge", "internal": True}


def test_ensure_internal_network_reports_creation_failure(docker_engine: Any) -> None:
    """A refused network creation reports failure rather than raising."""
    mock_client = MagicMock()
    mock_client.networks.get.side_effect = RuntimeError("not found")
    mock_client.networks.create.side_effect = RuntimeError("permission denied")

    with docker_engine(mock_client) as engine:
        assert engine.ensure_internal_network("net") is False


def test_ensure_internal_network_handles_unavailable_daemon() -> None:
    """An unreachable daemon reports network provisioning failure without raising."""
    engine = DockerEngineService()
    with patch("docker.DockerClient", side_effect=RuntimeError("socket missing")):
        assert engine.ensure_internal_network("net") is False


# ─────────────────────────────────────────────────────────────────────────────
# 5. BuildKit layer cache introspection
# ─────────────────────────────────────────────────────────────────────────────


_CACHE_ENTRIES = [
    {
        "ID": "cache-a",
        "Type": "regular",
        "Description": "RUN uv sync",
        "InUse": True,
        "Shared": True,
        "Size": 300,
        "UsageCount": 4,
        "CreatedAt": "2026-09-20T10:00:00Z",
        "LastUsedAt": "2026-09-21T09:00:00Z",
    },
    {
        "ID": "cache-b",
        "Type": "source.local",
        "Description": "local source",
        "InUse": False,
        "Shared": False,
        "Size": 100,
        "UsageCount": 0,
        "CreatedAt": "2026-09-19T10:00:00Z",
    },
]


def test_build_cache_report_aggregates_reuse() -> None:
    """Cache records aggregate into totals, reclaimable bytes, and a reuse ratio."""
    report = build_cache_report(_CACHE_ENTRIES)

    assert (
        report.total_bytes,
        report.reclaimable_bytes,
        report.in_use_count,
        report.shared_count,
        report.reuse_ratio,
        report.records[1].last_used_at,
    ) == (400, 100, 1, 1, 0.75, None)


def test_build_cache_report_handles_empty_cache() -> None:
    """An empty build cache reports zeroed totals without dividing by zero."""
    report = build_cache_report([])
    assert (report.total_bytes, report.reuse_ratio, report.records) == (0, 0.0, [])


def test_build_cache_report_tolerates_unknown_record_type() -> None:
    """A cache record class outside the known BuildKit vertex set is still projected."""
    report = build_cache_report([{"ID": "x", "Type": "future.kind", "Size": 10}])
    assert report.records[0].cache_type == "future.kind"


def test_engine_build_cache_reads_disk_usage(docker_engine: Any) -> None:
    """The build cache report is sourced from the Engine API disk-usage endpoint."""
    mock_client = MagicMock()
    mock_client.df.return_value = {"BuildCache": _CACHE_ENTRIES, "Images": []}

    with docker_engine(mock_client) as engine:
        report = engine.build_cache()
        engine.build_cache()

    # The second call is served from the response cache.
    assert (report.total_bytes, mock_client.df.call_count) == (400, 1)


def test_engine_disk_usage_failure_is_typed(docker_engine: Any) -> None:
    """A failing disk-usage query surfaces as a typed engine error."""
    mock_client = MagicMock()
    mock_client.df.side_effect = RuntimeError("endpoint unavailable")

    with docker_engine(mock_client) as engine:
        with pytest.raises(DockerEngineError, match="Engine disk usage query failed"):
            engine.disk_usage()


def test_prune_build_cache_invalidates_cached_usage(docker_engine: Any) -> None:
    """Pruning reports reclaimed bytes and invalidates the memoised disk-usage response."""
    mock_client = MagicMock()
    mock_client.df.return_value = {"BuildCache": _CACHE_ENTRIES}
    mock_client.api.prune_builds.return_value = {"SpaceReclaimed": 4096}

    with docker_engine(mock_client) as engine:
        engine.build_cache()
        reclaimed = engine.prune_build_cache()
        engine.build_cache()

    assert (reclaimed, mock_client.df.call_count) == (4096, 2)


def test_prune_build_cache_failure_is_typed(docker_engine: Any) -> None:
    """A refused prune surfaces as a typed engine error."""
    mock_client = MagicMock()
    mock_client.api.prune_builds.side_effect = RuntimeError("prune unsupported")

    with docker_engine(mock_client) as engine:
        with pytest.raises(DockerEngineError, match="Build cache prune failed"):
            engine.prune_build_cache()


# ─────────────────────────────────────────────────────────────────────────────
# 6. devops docker cache CLI command
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_docker_cache_table(docker_engine: Any) -> None:
    """The cache command renders BuildKit records with a reuse summary."""
    mock_client = MagicMock()
    mock_client.df.return_value = {"BuildCache": _CACHE_ENTRIES}

    with docker_engine(mock_client):
        result = runner.invoke(docker_app, ["cache"])

    assert result.exit_code == 0
    assert "cache-a" in result.output
    assert "reclaimable" in result.output


def test_cli_docker_cache_json(docker_engine: Any) -> None:
    """The cache command emits the typed report as JSON on demand."""
    mock_client = MagicMock()
    mock_client.df.return_value = {"BuildCache": _CACHE_ENTRIES}

    with docker_engine(mock_client):
        result = runner.invoke(docker_app, ["cache", "--json"])

    assert result.exit_code == 0
    assert '"reclaimable_bytes"' in result.output


def test_cli_docker_cache_prune(docker_engine: Any) -> None:
    """The --prune flag reclaims unused records after reporting them."""
    mock_client = MagicMock()
    mock_client.df.return_value = {"BuildCache": _CACHE_ENTRIES}
    mock_client.api.prune_builds.return_value = {"SpaceReclaimed": 1048576}

    with docker_engine(mock_client):
        result = runner.invoke(docker_app, ["cache", "--prune"])

    assert result.exit_code == 0
    assert mock_client.api.prune_builds.called


def test_cli_docker_cache_dry_run() -> None:
    """The cache command supports dry-run inspection without contacting the daemon."""
    result = runner.invoke(docker_app, ["cache", "--dry-run"])
    assert result.exit_code == 0
    assert "docker_build_cache_introspect" in result.output
