"""Unit tests for the unified Docker Engine API socket service.

The service runs over `docker_daemon`, the in-memory engine of `tests/support/fakes/docker_engine.py`
(#1316), or over a `DockerEngineFake` whose factory a test gives the service, so the service's own
endpoint checks, projections, cache and error mapping run for real.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from docker.errors import DockerException
from typer.testing import CliRunner

from devops_cli.commands.docker import app as docker_app
from devops_cli.config.constants import (
    CONST_SANDBOX_DOCKER_INTERNAL_NET,
)
from devops_cli.config.defaults import DEFAULT_DOCKER_CACHE_TTL_SECONDS
from devops_cli.docker.engine import (
    DockerEngineService,
    build_cache_report,
    decode_stream,
    get_engine,
    project_container_state,
    project_container_stats,
)
from devops_cli.exceptions.docker import DockerDaemonUnavailableError, DockerEngineError
from devops_cli.http.egress import EgressLevel
from devops_cli.models.docker import EngineSecurityInfo
from tests.support.fakes.docker_engine import UNREACHABLE_MESSAGE, DockerEngineFake, EngineCall

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
        with pytest.raises(DockerException) as raised:
            docker.utils.parse_host(bad, docker.constants.IS_WINDOWS_PLATFORM)
        assert raised.value is not None


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
        patch("devops_cli.http.egress.vet_addresses") as mock_validate,
    ):
        endpoint = engine.resolve_host()

    assert (
        endpoint.source,
        endpoint.raw,
        endpoint.base_url,
        mock_validate.call_args[0],
    ) == (
        "DOCKER_HOST",
        "tcp://example.com:2375",
        "http://example.com:2375",
        ("example.com", 2375, EgressLevel.PUBLIC),
    )


def test_resolve_host_leaves_unix_socket_unvalidated(docker_endpoint_env: Any) -> None:
    """A Unix socket endpoint bypasses network egress validation entirely."""
    engine = DockerEngineService()
    with (
        patch.dict(os.environ, {"DOCKER_HOST": "unix:///run/user/1000/docker.sock"}),
        patch("devops_cli.http.egress.vet_addresses") as mock_validate,
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


def test_one_negotiated_sdk_connection_serves_every_call(docker_endpoint_env: Any) -> None:
    """The negotiated Engine API client is reused instead of re-handshaking per call."""
    fake = DockerEngineFake()
    engine = DockerEngineService(fake.client_factory)
    first = engine.client()
    second = engine.client()

    assert (first is second, len(fake.factory_params)) == (True, 1)


def test_a_failed_dial_raises_daemon_unavailable(docker_endpoint_env: Any) -> None:
    """An unreachable daemon raises a typed, host-annotated failure."""
    fake = DockerEngineFake()
    fake.unreachable = True
    engine = DockerEngineService(fake.client_factory)
    with pytest.raises(DockerDaemonUnavailableError) as exc_info:
        engine.client()

    assert str(exc_info.value).startswith(f"/var/run/docker.sock: {UNREACHABLE_MESSAGE}")


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
    fake = DockerEngineFake()
    engine = DockerEngineService(fake.client_factory)
    with pytest.raises(DockerDaemonUnavailableError) as exc_info:
        engine.client()

    assert (fake.factory_params, "DOCKER_HOST" in str(exc_info.value)) == ([], True)


def test_endpoint_table_allowed_network_endpoint(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When private networks are permitted, tcp:// normalises to http:// for client dialling."""
    monkeypatch.setenv("DOCKER_HOST", "tcp://192.0.2.1:2375")
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    fake = DockerEngineFake()

    DockerEngineService(fake.client_factory).client()

    assert [params.get("base_url") for params in fake.factory_params] == ["http://192.0.2.1:2375"]


def test_endpoint_table_unix_socket_reaches_the_sdk(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unix socket addresses reach the SDK client directly without egress validation."""
    monkeypatch.setenv("DOCKER_HOST", "unix:///run/user/1000/docker.sock")
    fake = DockerEngineFake()

    DockerEngineService(fake.client_factory).client()

    assert [params.get("base_url") for params in fake.factory_params] == [
        "http+unix:///run/user/1000/docker.sock"
    ]


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
    fake = DockerEngineFake()

    with pytest.raises(DockerDaemonUnavailableError) as exc_info:
        DockerEngineService(fake.client_factory).client()

    assert (fake.factory_params, "myctx" in str(exc_info.value)) == ([], True)


def test_context_docker_context_env_refused_on_private_network(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A context selected via DOCKER_CONTEXT is validated against SSRF."""
    docker_endpoint_env("myctx", "tcp://192.0.2.10:2376")
    monkeypatch.setenv("DOCKER_CONTEXT", "myctx")
    fake = DockerEngineFake()

    with pytest.raises(DockerDaemonUnavailableError) as exc_info:
        DockerEngineService(fake.client_factory).client()

    assert (fake.factory_params, "myctx" in str(exc_info.value)) == ([], True)


def test_context_private_network_allowed_reaches_the_sdk(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With allow_private_network enabled, the context endpoint reaches the SDK client."""
    docker_endpoint_env("myctx", "tcp://192.0.2.10:2376")
    monkeypatch.setenv("DOCKER_CONTEXT", "myctx")
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    fake = DockerEngineFake()

    DockerEngineService(fake.client_factory).client()

    assert [params.get("base_url") for params in fake.factory_params] == ["http://192.0.2.10:2376"]


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
    fake = DockerEngineFake()

    DockerEngineService(fake.client_factory).client()

    assert [(params.get("base_url"), "tls" in params) for params in fake.factory_params] == [
        ("https://192.0.2.10:2376", True)
    ]


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

    fake = DockerEngineFake()
    monkeypatch.setenv("DOCKER_CONTEXT", "nope")
    with pytest.raises(DockerDaemonUnavailableError) as env_context:
        DockerEngineService(fake.client_factory).client()

    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"currentContext": "gone"}), encoding="utf-8")
    with pytest.raises(DockerDaemonUnavailableError) as current_context:
        DockerEngineService(fake.client_factory).client()

    assert (
        'context "nope": context not found' in str(env_context.value),
        'context "gone": context not found' in str(current_context.value),
        fake.factory_params,
    ) == (True, True, [])


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


def test_endpoint_container_connection_set_raises_configuration_error(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTAINER_CONNECTION set raises configuration error naming CONTAINER_HOST."""
    monkeypatch.setenv("CONTAINER_CONNECTION", "dev")
    fake = DockerEngineFake()
    with pytest.raises(DockerEngineError, match="CONTAINER_HOST"):
        DockerEngineService(fake.client_factory).client()
    assert fake.factory_params == []


def test_endpoint_container_host_ssh_raises_daemon_unavailable(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTAINER_HOST with ssh scheme raises daemon unavailable without dialling."""
    monkeypatch.setenv("CONTAINER_HOST", "ssh://user@192.0.2.1")
    engine = DockerEngineService()
    with pytest.raises(DockerDaemonUnavailableError) as exc_info:
        engine.client()
    assert "CONTAINER_HOST" in str(exc_info.value)


def test_endpoint_container_host_beats_docker_host_and_podman(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CONTAINER_HOST has highest precedence over DOCKER_HOST and Podman sockets."""
    podman_sock = tmp_path / "podman.sock"
    podman_sock.parent.mkdir(parents=True, exist_ok=True)
    podman_sock.touch()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("DOCKER_HOST", "unix:///var/run/docker.sock")
    monkeypatch.setenv("CONTAINER_HOST", "unix:///run/custom/podman.sock")

    engine = DockerEngineService()
    endpoint = engine.resolve_host()
    assert (endpoint.source, endpoint.raw) == (
        "CONTAINER_HOST",
        "unix:///run/custom/podman.sock",
    )


def test_endpoint_podman_rootless_xdg_runtime_dir(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Rootless Podman socket under XDG_RUNTIME_DIR is discovered automatically."""
    sock_dir = tmp_path / "runtime" / "podman"
    sock_dir.mkdir(parents=True, exist_ok=True)
    podman_sock = sock_dir / "podman.sock"
    podman_sock.touch()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "runtime"))

    engine = DockerEngineService()
    endpoint = engine.resolve_host()
    assert (endpoint.source, endpoint.raw, endpoint.base_url) == (
        str(podman_sock),
        f"unix://{podman_sock}",
        f"http+unix://{podman_sock}",
    )


def test_endpoint_podman_rootless_fallback_run_user(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When XDG_RUNTIME_DIR is unset, fallback to /run/user/<uid>/podman/podman.sock."""
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    fake_run_user = tmp_path / "run" / "user"
    user_sock_dir = fake_run_user / str(os.getuid()) / "podman"
    user_sock_dir.mkdir(parents=True, exist_ok=True)
    podman_sock = user_sock_dir / "podman.sock"
    podman_sock.touch()

    monkeypatch.setattr("devops_cli.docker.engine.CONST_RUN_USER_BASE", fake_run_user)

    engine = DockerEngineService()
    endpoint = engine.resolve_host()
    assert (endpoint.source, endpoint.raw, endpoint.base_url) == (
        str(podman_sock),
        f"unix://{podman_sock}",
        f"http+unix://{podman_sock}",
    )


def test_endpoint_podman_rootful_used_when_accessible(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Rootful Podman socket is used when rootless socket is absent and rootful is R/W."""
    rootful_sock = tmp_path / "podman" / "podman.sock"
    rootful_sock.parent.mkdir(parents=True, exist_ok=True)
    rootful_sock.touch()

    monkeypatch.setattr("devops_cli.docker.engine.CONST_PODMAN_ROOTFUL_SOCKET_PATH", rootful_sock)
    orig_access = os.access

    def mock_access(path: Any, mode: int, **kwargs: Any) -> bool:
        if Path(path) == rootful_sock:
            return True
        return orig_access(path, mode, **kwargs)

    monkeypatch.setattr("os.access", mock_access)

    engine = DockerEngineService()
    endpoint = engine.resolve_host()
    assert (endpoint.source, endpoint.raw) == (
        str(rootful_sock),
        f"unix://{rootful_sock}",
    )


def test_endpoint_podman_rootful_skipped_when_inaccessible(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Rootful Podman socket is ignored if not accessible with R/W permissions."""
    rootful_sock = tmp_path / "podman" / "podman.sock"
    rootful_sock.parent.mkdir(parents=True, exist_ok=True)
    rootful_sock.touch()

    monkeypatch.setattr("devops_cli.docker.engine.CONST_PODMAN_ROOTFUL_SOCKET_PATH", rootful_sock)

    def mock_access(path: Any, mode: int, **kwargs: Any) -> bool:
        if Path(path) == rootful_sock:
            return False
        return True

    monkeypatch.setattr("os.access", mock_access)

    engine = DockerEngineService()
    endpoint = engine.resolve_host()
    assert endpoint.source == "/var/run/docker.sock"


def test_endpoint_podman_rootless_beats_rootful(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Rootless Podman socket takes precedence over rootful socket."""
    sock_dir = tmp_path / "runtime" / "podman"
    sock_dir.mkdir(parents=True, exist_ok=True)
    rootless_sock = sock_dir / "podman.sock"
    rootless_sock.touch()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "runtime"))

    rootful_sock = tmp_path / "run_podman" / "podman.sock"
    rootful_sock.parent.mkdir(parents=True, exist_ok=True)
    rootful_sock.touch()
    monkeypatch.setattr("devops_cli.docker.engine.CONST_PODMAN_ROOTFUL_SOCKET_PATH", rootful_sock)

    engine = DockerEngineService()
    endpoint = engine.resolve_host()
    assert endpoint.source == str(rootless_sock)


def test_endpoint_default_dial_failure_message_mentions_systemctl_podman(
    docker_endpoint_env: Any,
) -> None:
    """Docker default socket failure appends guidance to set CONTAINER_HOST or enable podman.socket."""
    fake = DockerEngineFake()
    fake.unreachable = True
    with pytest.raises(DockerDaemonUnavailableError) as exc_info:
        DockerEngineService(fake.client_factory).client()

    assert str(exc_info.value).endswith(
        "; set CONTAINER_HOST or DOCKER_HOST, or run systemctl --user enable --now podman.socket"
    )


def test_close_releases_socket_and_clears_cache(docker_daemon: DockerEngineFake) -> None:
    """Closing the service closes the client and drops memoised responses, so the next call
    builds a new client and reads the engine again."""
    engine = get_engine()
    engine.build_cache()
    engine.close()
    closed = docker_daemon.closed
    engine.build_cache()

    assert (closed, docker_daemon.call_names().count("df"), len(docker_daemon.factory_params)) == (
        True,
        2,
        2,
    )


def test_singleton_instance_reuse_and_reset() -> None:
    """The engine singleton is shared process-wide and resettable for test isolation."""
    DockerEngineService.reset_instance()
    first = get_engine()
    shared = first is get_engine()
    DockerEngineService.reset_instance()

    assert (shared, get_engine() is first) == (True, False)


def test_ping_caches_reachability(docker_daemon: DockerEngineFake) -> None:
    """Daemon liveness probes are TTL-cached so repeated commands avoid extra round-trips."""
    engine = get_engine()
    assert ((engine.ping(), engine.ping()), docker_daemon.call_names().count("ping")) == (
        (True, True),
        1,
    )


def test_ping_returns_false_when_daemon_down(docker_daemon: DockerEngineFake) -> None:
    """A failing socket ping reports the daemon as unreachable rather than raising."""
    docker_daemon.fail("ping", RuntimeError("connection refused"))
    assert get_engine().ping() is False


def test_cache_entry_expires(
    docker_daemon: DockerEngineFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A memoised ping is asked again once its TTL elapses."""
    now = [1000.0]
    monkeypatch.setattr("time.monotonic", lambda: now[0])
    engine = get_engine()
    engine.ping()
    now[0] += DEFAULT_DOCKER_CACHE_TTL_SECONDS - 0.1
    engine.ping()
    within = docker_daemon.call_names().count("ping")
    now[0] += 0.2
    engine.ping()

    assert (within, docker_daemon.call_names().count("ping")) == (1, 2)


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


def test_list_and_inspect_containers(docker_daemon: DockerEngineFake) -> None:
    """Containers are listed and inspected as typed state models."""
    container_id = docker_daemon.add_container("svc")
    docker_daemon.add_container("other")
    engine = get_engine()

    listed = engine.list_containers(name="svc")
    inspected = engine.inspect_container(container_id)

    assert (
        [state.name for state in listed],
        inspected.running,
        [call.kwargs for call in docker_daemon.calls if call.name == "containers.list"],
    ) == (["svc"], True, [{"all": False, "filters": {"name": "svc"}}])


def test_list_containers_failure_is_typed(docker_daemon: DockerEngineFake) -> None:
    """A daemon listing failure surfaces as a typed engine error."""
    docker_daemon.fail("containers.list", RuntimeError("daemon busy"))

    with pytest.raises(DockerEngineError, match="Container listing failed"):
        get_engine().list_containers()


def test_container_stats_and_stream(docker_daemon: DockerEngineFake) -> None:
    """Single-shot and streamed stats both yield typed resource samples."""
    frame = {"pids_stats": {"current": 3}, "memory_stats": {"usage": 100, "limit": 1000}}
    container_id = docker_daemon.add_container("svc")
    docker_daemon.script_stats("svc", [frame, frame, frame])
    engine = get_engine()

    single = engine.container_stats(container_id)
    streamed = list(engine.stream_container_stats(container_id, samples=2))

    assert (single.pids_count, len(streamed), streamed[0].name) == (3, 2, "svc")


def test_stream_container_stats_unbounded_drains_source(docker_daemon: DockerEngineFake) -> None:
    """Without a sample cap, the stats stream is drained to exhaustion after its first frame."""
    frame = {"pids_stats": {"current": 1}}
    container_id = docker_daemon.add_container("svc")
    docker_daemon.script_stats("svc", [frame, frame, frame])

    assert len(list(get_engine().stream_container_stats(container_id))) == 2


def test_engine_kind_podman_and_docker(docker_daemon: DockerEngineFake) -> None:
    """kind() identifies Podman Engine via Components or falls back to Docker."""
    docker_engine_kind = (get_engine().kind(), get_engine().is_podman())
    podman = DockerEngineFake()
    podman.set_podman()
    DockerEngineService.install(podman.client_factory)

    assert (docker_engine_kind, (get_engine().kind(), get_engine().is_podman())) == (
        ("Docker", False),
        ("Podman", True),
    )


@pytest.mark.parametrize(
    ("security_options", "rootless"),
    [(["name=rootless", "name=seccomp"], True), (["name=apparmor"], False)],
    ids=["rootless", "rootful"],
)
def test_engine_is_rootless(
    docker_daemon: DockerEngineFake, security_options: list[str], rootless: bool
) -> None:
    """is_rootless() checks info()['SecurityOptions'] for name=rootless."""
    docker_daemon.info_data["SecurityOptions"] = security_options
    engine = get_engine()

    assert (engine.is_rootless(), engine.security_options()) == (rootless, security_options)


def test_engine_facts_memoized(docker_daemon: DockerEngineFake) -> None:
    """Engine facts (kind, is_rootless) are fetched once and memoized."""
    docker_daemon.set_podman()
    docker_daemon.info_data["SecurityOptions"] = ["name=rootless"]
    engine = get_engine()
    for _ in range(2):
        engine.kind()
        engine.is_rootless()

    assert (
        docker_daemon.call_names().count("version"),
        docker_daemon.call_names().count("info"),
    ) == (1, 1)


_BUILTIN_SECCOMP = "name=seccomp,profile=builtin"


@pytest.mark.parametrize(
    ("daemon_info", "reported"),
    [
        pytest.param(
            {"SecurityOptions": [_BUILTIN_SECCOMP, "name=cgroupns"], "PidsLimit": True},
            EngineSecurityInfo(
                options=(_BUILTIN_SECCOMP, "name=cgroupns"), pids_limit_supported=True
            ),
            id="builtin-seccomp",
        ),
        pytest.param(
            {"SecurityOptions": ["name=seccomp,profile=unconfined"], "PidsLimit": True},
            EngineSecurityInfo(
                options=("name=seccomp,profile=unconfined",), pids_limit_supported=True
            ),
            id="unconfined-seccomp",
        ),
        pytest.param(
            {"SecurityOptions": ["name=rootless", _BUILTIN_SECCOMP], "PidsLimit": True},
            EngineSecurityInfo(
                options=("name=rootless", _BUILTIN_SECCOMP), pids_limit_supported=True
            ),
            id="rootless",
        ),
        pytest.param(
            {"SecurityOptions": [_BUILTIN_SECCOMP], "PidsLimit": False},
            EngineSecurityInfo(options=(_BUILTIN_SECCOMP,), pids_limit_supported=False),
            id="no-pids-limit",
        ),
        pytest.param(
            {"SecurityOptions": [], "PidsLimit": True},
            EngineSecurityInfo(options=(), pids_limit_supported=True),
            id="no-options",
        ),
        pytest.param({}, EngineSecurityInfo(), id="keys-omitted"),
        pytest.param(
            {"SecurityOptions": None, "PidsLimit": None},
            EngineSecurityInfo(),
            id="keys-null",
        ),
    ],
)
def test_security_info_reports_what_the_daemon_declares(
    docker_daemon: DockerEngineFake, daemon_info: dict[str, Any], reported: EngineSecurityInfo
) -> None:
    """The daemon's security options and pids-limit support are reported, and a key the daemon
    omits stays unreported rather than reading as a negative."""
    docker_daemon.info_data = daemon_info

    assert get_engine().security_info() == reported


@pytest.mark.parametrize(
    "failure",
    [
        ConnectionError("connection refused: " + "x" * 1000),
        DockerException("api error"),
        DockerDaemonUnavailableError("socket gone", host="unix:///x"),
    ],
    ids=["socket-error", "docker-sdk-error", "daemon-unavailable"],
)
def test_security_info_never_raises_and_bounds_the_reason(
    docker_daemon: DockerEngineFake, failure: Exception
) -> None:
    """A daemon that cannot answer yields the reason, capped at 256 characters, and no facts."""
    docker_daemon.fail("info", failure)

    report = get_engine().security_info()

    assert (report, len(str(report.error)) <= 256) == (
        EngineSecurityInfo(error=str(failure)[:256]),
        True,
    )


def test_one_info_call_serves_the_security_facts(docker_daemon: DockerEngineFake) -> None:
    """security_info(), security_options() and is_rootless() read one cached info() answer."""
    docker_daemon.info_data = {"SecurityOptions": ["name=rootless"], "PidsLimit": True}
    engine = get_engine()

    assert (
        engine.security_info(),
        engine.security_options(),
        engine.is_rootless(),
        docker_daemon.call_names().count("info"),
    ) == (
        EngineSecurityInfo(options=("name=rootless",), pids_limit_supported=True),
        ["name=rootless"],
        True,
        1,
    )


def test_an_unreachable_daemon_reports_no_security_options_and_not_rootless(
    docker_daemon: DockerEngineFake,
) -> None:
    """Callers that only want the options or rootless flag keep the empty answer on failure."""
    docker_daemon.fail("info", OSError("down"))
    engine = get_engine()

    assert (engine.security_options(), engine.is_rootless()) == ([], False)


def test_security_info_failure_is_retried_after_two_seconds_and_success_after_the_ttl(
    docker_daemon: DockerEngineFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed answer is remembered for 2 s, like a failed ping, and a good one for the normal
    cache lifetime."""
    now = [1000.0]
    monkeypatch.setattr("time.monotonic", lambda: now[0])
    docker_daemon.fail("info", OSError("down"), times=1)
    docker_daemon.info_data = {"SecurityOptions": [_BUILTIN_SECCOMP], "PidsLimit": True}
    engine = get_engine()

    reads: list[tuple[float, bool, int]] = []
    for elapsed in (0.0, 1.9, 2.1, 4.0, 5.2, 7.5):
        now[0] = 1000.0 + elapsed
        error = engine.security_info().error
        reads.append((elapsed, error is None, docker_daemon.call_names().count("info")))

    assert reads == [
        (0.0, False, 1),
        (1.9, False, 1),
        (2.1, True, 2),
        (4.0, True, 2),
        (5.2, True, 2),
        (7.5, True, 3),
    ]


def test_container_stats_two_frames_first_empty_precpu(docker_daemon: DockerEngineFake) -> None:
    """container_stats discards the 1st frame, uses the 2nd, and closes the stream."""
    frame1 = {
        "pids_stats": {"current": 1},
        "cpu_stats": {"cpu_usage": {"total_usage": 1000}},
        "precpu_stats": {},
    }
    frame2 = {
        "pids_stats": {"current": 2},
        "cpu_stats": {
            "cpu_usage": {"total_usage": 2000, "percpu_usage": [2000]},
            "system_cpu_usage": 20000,
            "online_cpus": 1,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 1000},
            "system_cpu_usage": 10000,
        },
        "memory_stats": {"usage": 512, "limit": 1024},
    }
    container_id = docker_daemon.add_container("svc")
    docker_daemon.script_stats("svc", [frame1, frame2])

    stats = get_engine().container_stats(container_id)

    assert (
        stats.pids_count,
        stats.cpu_percentage > 0.0,
        "container.stats.close" in docker_daemon.call_names(),
    ) == (2, True, True)


def test_lifecycle_operations_use_direct_api_calls(docker_daemon: DockerEngineFake) -> None:
    """Stop, remove, exec, wait, and logs reach the engine, and stop and remove use the
    low-level calls that take the container ID."""
    running = docker_daemon.add_container("svc")
    docker_daemon.script_exec("svc", ["ls"], output=b"output\n")
    docker_daemon.script_run("job", stdout=b"log line\n", exit_code=7)
    engine = get_engine()
    job = engine.create_container(image="alpine:3", command=["sh"], name="job")
    job.start()

    exec_result = engine.exec_in_container(running, ["ls"], workdir="/app")
    exit_code = engine.wait_container(job.id, timeout=30)
    logs = engine.container_logs(job.id, tail=10)
    engine.stop_container(running, timeout=3)
    engine.remove_container(job.id)

    removal = {"v": False, "link": False, "force": True}
    assert (
        exec_result,
        exit_code,
        logs,
        [call for call in docker_daemon.calls if call.name.startswith("api.")],
        docker_daemon.container_state,
    ) == (
        (0, "output\n"),
        7,
        "log line\n",
        [
            EngineCall("api.stop", (running,), {"timeout": 3}),
            EngineCall("api.remove_container", (running,), removal),
            EngineCall("api.remove_container", (job.id,), removal),
        ],
        {},
    )


def test_exec_in_container_hands_its_environment_to_the_exec(
    docker_daemon: DockerEngineFake,
) -> None:
    """An exec's environment reaches the Engine API, and none is sent when the caller has none."""
    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    running = docker_daemon.add_container("svc")
    engine = get_engine()

    engine.exec_in_container(running, ["env"], environment={"TRACEPARENT": traceparent})
    engine.exec_in_container(running, ["env"], workdir="/app")

    assert [call.kwargs for call in docker_daemon.calls if call.name == "container.exec_run"] == [
        {"workdir": None, "environment": {"TRACEPARENT": traceparent}},
        {"workdir": "/app", "environment": None},
    ]


def test_remove_container_tolerates_already_reaped(docker_daemon: DockerEngineFake) -> None:
    """Removing a container the daemon already reclaimed is not an error."""
    get_engine().remove_container("gone")

    assert docker_daemon.call_names()[-1] == "api.remove_container"


def test_stop_container_failure_is_typed(docker_daemon: DockerEngineFake) -> None:
    """A rejected stop surfaces as a typed, container-annotated engine error."""
    with pytest.raises(DockerEngineError, match="Container termination failed") as exc_info:
        get_engine().stop_container("missing")

    assert exc_info.value.details.get("container_id") == "missing"


def test_create_container_failure_records_image(docker_daemon: DockerEngineFake) -> None:
    """A failed creation annotates the offending image in the typed error."""
    with pytest.raises(DockerEngineError) as exc_info:
        get_engine().create_container(image="missing:latest")

    assert (
        exc_info.value.details.get("image"),
        "No such image: missing:latest" in str(exc_info.value),
    ) == ("missing:latest", True)


def test_container_logs_failure_is_typed(docker_daemon: DockerEngineFake) -> None:
    """A log retrieval failure surfaces as a typed engine error."""
    container_id = docker_daemon.add_container("svc")
    docker_daemon.fail("container.logs", RuntimeError("stream closed"))

    with pytest.raises(DockerEngineError, match="Container log retrieval failed"):
        get_engine().container_logs(container_id)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Internal network provisioning
# ─────────────────────────────────────────────────────────────────────────────


def test_ensure_internal_network_accepts_conforming_network(
    docker_daemon: DockerEngineFake,
) -> None:
    """An existing internal bridge network is accepted without being recreated."""
    docker_daemon.add_network(CONST_SANDBOX_DOCKER_INTERNAL_NET, internal=True)

    assert (
        get_engine().ensure_internal_network(CONST_SANDBOX_DOCKER_INTERNAL_NET),
        "networks.create" in docker_daemon.call_names(),
    ) == (True, False)


def test_ensure_internal_network_recreates_drifted_network(docker_daemon: DockerEngineFake) -> None:
    """A network that lost its internal (egress-denied) flag is removed and recreated."""
    docker_daemon.add_network(CONST_SANDBOX_DOCKER_INTERNAL_NET, internal=False)

    ensured = get_engine().ensure_internal_network(CONST_SANDBOX_DOCKER_INTERNAL_NET)

    assert (
        ensured,
        [call.name for call in docker_daemon.calls if call.name.startswith("network")],
        docker_daemon.calls[-1].kwargs,
        docker_daemon.find_network(CONST_SANDBOX_DOCKER_INTERNAL_NET)["Internal"],
    ) == (
        True,
        ["networks.get", "network.remove", "networks.create"],
        {"driver": "bridge", "internal": True},
        True,
    )


def test_ensure_internal_network_reports_creation_failure(docker_daemon: DockerEngineFake) -> None:
    """A refused network creation reports failure rather than raising."""
    docker_daemon.fail("networks.create", RuntimeError("permission denied"))

    assert get_engine().ensure_internal_network("net") is False


def test_ensure_internal_network_handles_unavailable_daemon(
    docker_daemon: DockerEngineFake,
) -> None:
    """An unreachable daemon reports network provisioning failure without raising."""
    docker_daemon.unreachable = True

    assert get_engine().ensure_internal_network("net") is False


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


def test_engine_build_cache_reads_disk_usage(docker_daemon: DockerEngineFake) -> None:
    """The build cache report is sourced from the Engine API disk-usage endpoint."""
    docker_daemon.build_cache = [dict(entry) for entry in _CACHE_ENTRIES]
    engine = get_engine()

    report = engine.build_cache()
    engine.build_cache()

    # The second call is served from the response cache.
    assert (report.total_bytes, docker_daemon.call_names().count("df")) == (400, 1)


def test_engine_disk_usage_failure_is_typed(docker_daemon: DockerEngineFake) -> None:
    """A failing disk-usage query surfaces as a typed engine error."""
    docker_daemon.fail("df", RuntimeError("endpoint unavailable"))

    with pytest.raises(DockerEngineError, match="Engine disk usage query failed"):
        get_engine().disk_usage()


def test_prune_build_cache_invalidates_cached_usage(docker_daemon: DockerEngineFake) -> None:
    """Pruning removes the unused records, reports their bytes, and invalidates the memoised
    disk-usage response."""
    docker_daemon.build_cache = [dict(entry) for entry in _CACHE_ENTRIES]
    engine = get_engine()

    engine.build_cache()
    reclaimed = engine.prune_build_cache()
    after = engine.build_cache()

    assert (
        reclaimed,
        [record.cache_id for record in after.records],
        docker_daemon.call_names().count("df"),
    ) == (100, ["cache-a"], 2)


def test_prune_build_cache_failure_is_typed(docker_daemon: DockerEngineFake) -> None:
    """A refused prune surfaces as a typed engine error."""
    docker_daemon.fail("api.prune_builds", RuntimeError("prune unsupported"))

    with pytest.raises(DockerEngineError, match="Build cache prune failed"):
        get_engine().prune_build_cache()


def test_engine_prune_calls_collections_in_order(docker_daemon: DockerEngineFake) -> None:
    """DockerEngineService.prune calls containers, networks, and images in order."""
    get_engine().prune()

    assert [name for name in docker_daemon.call_names() if name.endswith(".prune")] == [
        "containers.prune",
        "networks.prune",
        "images.prune",
    ]


def test_engine_prune_with_volumes(docker_daemon: DockerEngineFake) -> None:
    """DockerEngineService.prune with volumes=True calls volumes.prune."""
    get_engine().prune(volumes=True)

    assert [name for name in docker_daemon.call_names() if name.endswith(".prune")] == [
        "containers.prune",
        "networks.prune",
        "images.prune",
        "volumes.prune",
    ]


def test_engine_prune_reclaimed_bytes_sum(docker_daemon: DockerEngineFake) -> None:
    """DockerEngineService.prune sums SpaceReclaimed across the prunes, and a volume prune adds
    the anonymous volumes."""
    docker_daemon.add_container("old", running=False, size=500)
    docker_daemon.add_image(size=300)
    docker_daemon.add_volume("anonymous", anonymous=True, size=200)
    engine = get_engine()

    assert (engine.prune(), engine.prune(volumes=True)) == (800, 200)


def test_engine_prune_invalidates_disk_usage_cache(docker_daemon: DockerEngineFake) -> None:
    """Pruning invalidates the memoised disk-usage response."""
    engine = get_engine()
    engine.build_cache()
    engine.prune()
    engine.build_cache()

    assert docker_daemon.call_names().count("df") == 2


def test_engine_prune_failure_is_typed(docker_daemon: DockerEngineFake) -> None:
    """A collection prune failure surfaces as a typed DockerEngineError."""
    from docker.errors import APIError

    docker_daemon.fail("containers.prune", APIError("daemon error"))

    with pytest.raises(DockerEngineError, match="daemon error"):
        get_engine().prune()


# ─────────────────────────────────────────────────────────────────────────────
# 6. devops docker cache CLI command
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_docker_cache_table(docker_daemon: DockerEngineFake) -> None:
    """The cache command renders BuildKit records with a reuse summary."""
    docker_daemon.build_cache = [dict(entry) for entry in _CACHE_ENTRIES]

    result = runner.invoke(docker_app, ["cache"])

    assert (result.exit_code, "cache-a" in result.output, "reclaimable" in result.output) == (
        0,
        True,
        True,
    )


def test_cli_docker_cache_json(docker_daemon: DockerEngineFake) -> None:
    """The cache command emits the typed report as JSON on demand."""
    docker_daemon.build_cache = [dict(entry) for entry in _CACHE_ENTRIES]

    result = runner.invoke(docker_app, ["cache", "--json"])

    assert (result.exit_code, '"reclaimable_bytes"' in result.output) == (0, True)


def test_cli_docker_cache_prune(docker_daemon: DockerEngineFake) -> None:
    """The --prune flag reclaims unused records after reporting them."""
    docker_daemon.build_cache = [dict(entry) for entry in _CACHE_ENTRIES]

    result = runner.invoke(docker_app, ["cache", "--prune"])

    assert (
        result.exit_code,
        "api.prune_builds" in docker_daemon.call_names(),
        [entry["ID"] for entry in docker_daemon.build_cache],
    ) == (0, True, ["cache-a"])


def test_cli_docker_cache_dry_run() -> None:
    """The cache command supports dry-run inspection without contacting the daemon."""
    result = runner.invoke(docker_app, ["cache", "--dry-run"])
    assert result.exit_code == 0
    assert "DOCKER GET /system/df" in result.output


def test_cli_docker_cache_podman_engine(docker_daemon: DockerEngineFake) -> None:
    """The cache command on Podman informs user and exits 1 without prune_builds or df."""
    docker_daemon.set_podman()

    result = runner.invoke(docker_app, ["cache"])

    assert (
        result.exit_code,
        "Podman keeps no BuildKit cache; its build layers are images" in result.output,
        "df" in docker_daemon.call_names(),
        "api.prune_builds" in docker_daemon.call_names(),
    ) == (1, True, False, False)
