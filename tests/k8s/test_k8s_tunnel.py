"""`devops k8s tunnel`: the local end of the Kubernetes API route at `k8s.<domain>` (#1641).

cloudflared is never started. `ProcessFake` answers the login and records the detached forward,
and answers the forward with a stand-in the test starts itself: `git hash-object --stdin`, in a
session of its own, which waits on its standard input as a listener waits for connections. A
socket the test binds stands in for cloudflared's listener.
"""

from __future__ import annotations

import socket
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.defaults import DEFAULT_REST_HOST
from devops_cli.k8s.service import KubernetesService
from devops_cli.k8s.tunnel import TunnelRecord, load_tunnel, tunnel_state_file
from tests.support.fakes.kubernetes import FAKE_CONTEXT, FakeCluster, FakeVersion, api_exception
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

_HOST = "k8s.example.com"


class _RefusingVersion(FakeVersion):
    """An API server that answers `/version` with 401, as it does for a refused credential."""

    def get_code(self, **kwargs: Any) -> Any:
        self._record("get_code", kwargs)
        raise api_exception(401, "Unauthorized")


class _Listener:
    """A loopback port that refuses connections until `open`, as cloudflared's listener does."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.port: int = sock.getsockname()[1]

    def open(self) -> None:
        self.sock.listen()

    def opened_by(
        self, process: subprocess.Popen[bytes]
    ) -> Callable[[ProcessCall], subprocess.Popen[bytes]]:
        """A `spawn_detached` answer: the forward starts, so the port accepts connections."""

        def start(call: ProcessCall) -> subprocess.Popen[bytes]:
            self.open()
            return process

        return start


@pytest.fixture
def listener() -> Iterator[_Listener]:
    """A bound loopback port, not yet accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((DEFAULT_REST_HOST, 0))
        yield _Listener(sock)


@pytest.fixture
def stand_in() -> Iterator[subprocess.Popen[bytes]]:
    """A process in a session of its own that runs until it is signalled."""
    proc = subprocess.Popen(
        ["git", "hash-object", "--stdin"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        yield proc
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)


def _forward_calls(fake: ProcessFake) -> list[tuple[str, ...]]:
    return [call.argv for call in fake.calls if call.detached]


def _is_tcp_forward(argv: tuple[str, ...]) -> bool:
    return argv[1:3] == ("access", "tcp")


def test_start_refuses_an_unset_tunnel_host(
    cli: Callable[..., Any], config: Callable[..., Path], process_fake: ProcessFake
) -> None:
    """With no `k8s.tunnel_host`, start names the setting and starts nothing."""
    config(k8s={"tunnel_host": None})

    result = cli("k8s", "tunnel", "start")

    assert (result.exit_code != 0, "k8s.tunnel_host" in result.output, process_fake.calls) == (
        True,
        True,
        [],
    )


def test_start_logs_in_then_starts_one_detached_forward(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    process_fake: ProcessFake,
    listener: _Listener,
    stand_in: subprocess.Popen[bytes],
) -> None:
    """The login runs first with the terminal attached, then one forward starts in its own session."""
    config(k8s={"tunnel_host": _HOST})
    process_fake.answer(
        lambda call: _is_tcp_forward(call.argv), ProcessAnswer(process=listener.opened_by(stand_in))
    )

    first = cli("k8s", "tunnel", "start", "--port", str(listener.port))
    second = cli("k8s", "tunnel", "start", "--port", str(listener.port))

    login, forward = process_fake.calls[0], process_fake.calls[1]
    record = load_tunnel(tunnel_state_file())
    assert (
        first.exit_code,
        second.exit_code,
        login.argv[1:],
        login.capture_output,
        login.detached,
        forward.argv[1:],
        len(_forward_calls(process_fake)),
        (record.pid, record.hostname, record.port) if record else None,
    ) == (
        0,
        0,
        ("access", "login", "--quiet", f"https://{_HOST}"),
        False,
        False,
        (
            "access",
            "tcp",
            "--hostname",
            _HOST,
            "--url",
            f"{DEFAULT_REST_HOST}:{listener.port}",
            "--logfile",
            str(tunnel_state_file().with_suffix(".log")),
        ),
        1,
        (stand_in.pid, _HOST, listener.port),
    )


def test_start_with_context_adds_the_tunnel_context(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    process_fake: ProcessFake,
    listener: _Listener,
    stand_in: subprocess.Popen[bytes],
) -> None:
    """`--context` writes the `<cluster>-tunnel` cluster and context from the home context."""
    config(k8s={"tunnel_host": _HOST, "context": "home"})
    process_fake.answer(
        lambda call: _is_tcp_forward(call.argv), ProcessAnswer(process=listener.opened_by(stand_in))
    )
    process_fake.answer(
        ("kubectl", "config", "view"), ProcessAnswer(stdout="home-cluster\nadmin\nQ0EtREFUQQ==")
    )

    result = cli("k8s", "tunnel", "start", "--port", str(listener.port), "--context")

    kubectl = [call.argv for call in process_fake.calls if call.argv[0] == "kubectl"]
    record = load_tunnel(tunnel_state_file())
    assert (result.exit_code, kubectl[1:], record.context if record else None) == (
        0,
        [
            (
                "kubectl",
                "config",
                "set-cluster",
                "home-cluster-tunnel",
                f"--server=https://{DEFAULT_REST_HOST}:{listener.port}",
                "--tls-server-name=kubernetes.default.svc",
            ),
            (
                "kubectl",
                "config",
                "set",
                "clusters.home-cluster-tunnel.certificate-authority-data",
                "Q0EtREFUQQ==",
            ),
            (
                "kubectl",
                "config",
                "set-context",
                "home-cluster-tunnel",
                "--cluster=home-cluster-tunnel",
                "--user=admin",
            ),
        ],
        "home-cluster-tunnel",
    )


def test_start_dry_run_starts_nothing(
    cli: Callable[..., Any], config: Callable[..., Path], process_fake: ProcessFake
) -> None:
    """A dry run prints the login and the forward and starts no process."""
    config(k8s={"tunnel_host": _HOST})

    result = cli("k8s", "tunnel", "start", "--dry-run")

    assert (
        result.exit_code,
        process_fake.calls,
        "access login" in result.output,
        "access tcp" in result.output,
        tunnel_state_file().exists(),
    ) == (0, [], True, True, False)


def test_stop_ends_the_forward_process_group(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    process_fake: ProcessFake,
    listener: _Listener,
    stand_in: subprocess.Popen[bytes],
) -> None:
    """Stop signals the recorded forward's group and removes the record."""
    config(k8s={"tunnel_host": _HOST})
    process_fake.answer(
        lambda call: _is_tcp_forward(call.argv), ProcessAnswer(process=listener.opened_by(stand_in))
    )
    cli("k8s", "tunnel", "start", "--port", str(listener.port))

    result = cli("k8s", "tunnel", "stop")

    assert (
        result.exit_code,
        stand_in.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS) != 0,
        load_tunnel(tunnel_state_file()),
    ) == (0, True, None)


def test_status_counts_a_refused_credential_as_an_answer(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    listener: _Listener,
) -> None:
    """A 401 from `/version` tells that the tunnel reached the API server."""
    config(k8s={"tunnel_host": _HOST, "context": FAKE_CONTEXT})
    fake = FakeCluster(contexts=(FAKE_CONTEXT, "home-tunnel"), version=_RefusingVersion())
    KubernetesService.install(fake)
    listener.open()

    result = cli(
        "k8s", "tunnel", "status", "--port", str(listener.port), "--context", "home-tunnel"
    )

    assert (
        result.exit_code,
        "listening" in result.output,
        "answers" in result.output,
        fake.connects[-1],
    ) == (0, True, True, "home-tunnel")


def test_status_with_nothing_recorded_or_listening(
    cli: Callable[..., Any], config: Callable[..., Path], refusing_port: int
) -> None:
    """With no forward and a closed port, status says so and checks no API server."""
    config(k8s={"tunnel_host": _HOST})

    result = cli("k8s", "tunnel", "status", "--port", str(refusing_port))

    assert (
        result.exit_code,
        "No tunnel forward" in result.output,
        "not listening" in result.output,
    ) == (
        0,
        True,
        True,
    )


@pytest.mark.parametrize(
    ("version", "unreachable", "answers"),
    [
        (FakeVersion(), False, True),
        (_RefusingVersion(), False, True),
        (FakeVersion(), True, False),
    ],
    ids=["200", "401", "refused"],
)
def test_api_server_answers_counts_any_http_status(
    cluster: FakeCluster, version: FakeVersion, unreachable: bool, answers: bool
) -> None:
    """Any HTTP status from `/version` is an answer; a refused connection is not."""
    cluster.version = version
    if unreachable:
        cluster.unreachable()

    assert KubernetesService.get_instance().api_server_answers(FAKE_CONTEXT) is answers


def test_a_record_counts_only_while_its_process_runs(stand_in: subprocess.Popen[bytes]) -> None:
    """A recorded pid counts as the forward only while it keeps its start time."""
    from devops_cli.k8s.port_forward_daemon import process_start_ticks

    record = TunnelRecord(
        pid=stand_in.pid,
        start_ticks=process_start_ticks(stand_in.pid),
        hostname=_HOST,
        address=DEFAULT_REST_HOST,
        port=16443,
        log_file="tunnel.log",
    )
    running = record.is_alive
    stand_in.kill()
    stand_in.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    assert (running, record.is_alive) == (True, False)
