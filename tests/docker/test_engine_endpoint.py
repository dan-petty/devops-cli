"""Tests for how `DockerEngineService` finds and checks the daemon's endpoint.

The service reads `DOCKER_HOST`, `CONTAINER_HOST`, the Docker contexts and the Podman sockets, then
refuses a network host that egress validation refuses. A test sets the environment with the
`docker_endpoint_env` fixture and gives the service a `DockerEngineFake` factory, so the service's
own endpoint checks run for real. A host name needs a DNS answer, from the `dns` fixture.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from docker.errors import DockerException

from devops_cli.docker.engine import (
    DockerEngineService,
)
from devops_cli.exceptions.docker import DockerDaemonUnavailableError, DockerEngineError
from tests.support.fakes.dns import PUBLIC_ADDRESS, DnsFake, Lookup
from tests.support.fakes.docker_engine import UNREACHABLE_MESSAGE, DockerEngineFake


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


def test_resolve_host_validates_network_endpoints(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch, dns: DnsFake
) -> None:
    """A TCP DOCKER_HOST is routed through SSRF egress validation before connecting."""
    dns.add("example.com", PUBLIC_ADDRESS)
    monkeypatch.setenv("DOCKER_HOST", "tcp://example.com:2375")

    endpoint = DockerEngineService().resolve_host()

    assert (
        endpoint.source,
        endpoint.raw,
        endpoint.base_url,
        dns.lookups_of("example.com"),
    ) == (
        "DOCKER_HOST",
        "tcp://example.com:2375",
        "http://example.com:2375",
        [Lookup("example.com", 2375)],
    )


def test_resolve_host_refuses_a_name_that_resolves_to_a_private_address(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch, dns: DnsFake
) -> None:
    """A TCP DOCKER_HOST whose name resolves to a private address is refused before connecting."""
    dns.add("example.com", "10.0.0.5")
    monkeypatch.setenv("DOCKER_HOST", "tcp://example.com:2375")

    with pytest.raises(DockerDaemonUnavailableError) as raised:
        DockerEngineService().resolve_host()

    assert "DOCKER_HOST" in str(raised.value)


def test_resolve_host_leaves_unix_socket_unvalidated(
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch, dns: DnsFake
) -> None:
    """A Unix socket endpoint bypasses network egress validation entirely."""
    monkeypatch.setenv("DOCKER_HOST", "unix:///run/user/1000/docker.sock")

    endpoint = DockerEngineService().resolve_host()

    assert (
        endpoint.source,
        endpoint.raw,
        endpoint.base_url,
        dns.lookups,
    ) == (
        "DOCKER_HOST",
        "unix:///run/user/1000/docker.sock",
        "http+unix:///run/user/1000/docker.sock",
        [],
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
    cli: Callable[..., Any],
) -> None:
    """devops docker images exits 1 with a single clean error line and no traceback (#1108)."""
    monkeypatch.setenv("DOCKER_HOST", docker_host)
    res = cli("docker", "images")
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
    docker_endpoint_env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When XDG_RUNTIME_DIR is unset, fallback to /run/user/<uid>/podman/podman.sock."""
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    user_sock_dir = docker_endpoint_env.run_user_base / str(os.getuid()) / "podman"
    user_sock_dir.mkdir(parents=True, exist_ok=True)
    podman_sock = user_sock_dir / "podman.sock"
    podman_sock.touch()

    endpoint = DockerEngineService().resolve_host()

    assert (endpoint.source, endpoint.raw, endpoint.base_url) == (
        str(podman_sock),
        f"unix://{podman_sock}",
        f"http+unix://{podman_sock}",
    )


def test_endpoint_podman_rootful_used_when_accessible(docker_endpoint_env: Any) -> None:
    """Rootful Podman socket is used when rootless socket is absent and rootful is R/W."""
    rootful_sock = docker_endpoint_env.rootful_socket
    rootful_sock.parent.mkdir(parents=True, exist_ok=True)
    rootful_sock.touch()

    endpoint = DockerEngineService().resolve_host()

    assert (endpoint.source, endpoint.raw) == (str(rootful_sock), f"unix://{rootful_sock}")


@pytest.mark.skipif(os.geteuid() == 0, reason="root can open any socket path")
def test_endpoint_podman_rootful_skipped_when_inaccessible(docker_endpoint_env: Any) -> None:
    """Rootful Podman socket is ignored if not accessible with R/W permissions."""
    rootful_sock = docker_endpoint_env.rootful_socket
    rootful_sock.parent.mkdir(parents=True, exist_ok=True)
    rootful_sock.touch()
    rootful_sock.chmod(0o444)

    endpoint = DockerEngineService().resolve_host()

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

    rootful_sock = docker_endpoint_env.rootful_socket
    rootful_sock.parent.mkdir(parents=True, exist_ok=True)
    rootful_sock.touch()

    endpoint = DockerEngineService().resolve_host()

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
