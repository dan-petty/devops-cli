"""The local end of the Kubernetes API route at `k8s.<domain>` (#1641).

`cloudflared access tcp` carries kubectl's connection to the Cloudflare edge after an Access
login, and TLS stays end to end between kubectl and the API server (k8s/README.md, "The
Kubernetes API at k8s.<domain>"). cloudflared does not run itself in the background, so this
module starts it in a session of its own, keeps one record of it under the data directory and
stops it, with the lock, the liveness check and the group signal of `port_forward_daemon`.
"""

from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx2
from pydantic import BaseModel, Field

from devops_cli.config.defaults import DEFAULT_K8S_TUNNEL_PORT
from devops_cli.core.process import (
    DetachedProcess,
    run_subprocess,
    spawn_detached,
    terminate_process_group,
)
from devops_cli.exceptions.k8s import KubernetesTunnelError
from devops_cli.k8s.port_forward_daemon import (
    process_is_running,
    process_start_ticks,
    state_file_lock,
)
from devops_cli.lang import ERRORS
from devops_cli.output.file_writer import write_json_file

logger = logging.getLogger(__name__)

TUNNEL_CONTEXT_SUFFIX = "-tunnel"
# The name the API server's certificate carries; the forward's address is not in it.
TUNNEL_TLS_SERVER_NAME = "kubernetes.default.svc"

_STATE_NAME = "k8s/tunnel.json"
_LOGIN_TIMEOUT_SECONDS = 300.0
_START_TIMEOUT_SECONDS = 15.0
_POLL_SECONDS = 0.2
_PROBE_TIMEOUT_SECONDS = 1.0
# cloudflared opens a browser for the Access login when it can; else it prints the URL.
_BROWSER_ENV = frozenset({"DISPLAY", "WAYLAND_DISPLAY", "BROWSER"})
# The home context's cluster, user and CA data, one to a line; `--flatten` inlines a CA file.
_CONTEXT_TEMPLATE = (
    'jsonpath={.contexts[0].context.cluster}{"\\n"}{.contexts[0].context.user}{"\\n"}'
    "{.clusters[0].cluster.certificate-authority-data}"
)


class TunnelRecord(BaseModel):
    """The forward that `devops k8s tunnel start` started."""

    pid: int
    # When the process started, from `process_start_ticks`; None where /proc cannot be read.
    start_ticks: int | None
    hostname: str
    address: str
    port: int
    log_file: str
    # The kubeconfig context that `start --context` wrote, if it wrote one.
    context: str | None = None
    started_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def is_alive(self) -> bool:
        """Whether the recorded process still runs: never pid 0 or 1, and with its start time."""
        return self.pid > 1 and process_is_running(self.pid, self.start_ticks)

    @property
    def listener(self) -> str:
        """The `<address>:<port>` the forward listens on."""
        return listener_authority(self.address, self.port)


@dataclass(frozen=True)
class TunnelStart:
    """What `start_tunnel` did: started `record`, or found it already running."""

    record: TunnelRecord
    started: bool


@dataclass(frozen=True)
class TunnelStatus:
    """The recorded forward, its port and, for a context, whether the API server answers."""

    record: TunnelRecord | None
    listener: str
    listening: bool
    context: str | None
    api_answers: bool | None


def tunnel_state_file() -> Path:
    """Where the record of the forward lives, under the data directory."""
    from devops_cli.core.repo import resolve_store_path

    return resolve_store_path(_STATE_NAME)


def listener_authority(address: str, port: int) -> str:
    """`<address>:<port>` for cloudflared's `--url`, with an IPv6 address in brackets."""
    return httpx2.URL(scheme="tcp", host=address, port=port).netloc.decode("ascii")


def login_command(cloudflared: str, hostname: str) -> list[str]:
    """The Access login, which stores the token and, with `--quiet`, does not print it."""
    url = str(httpx2.URL(scheme="https", host=hostname))
    return [cloudflared, "access", "login", "--quiet", url]


def forward_command(
    cloudflared: str, hostname: str, address: str, port: int, log: Path
) -> list[str]:
    """The forward from `<address>:<port>` to the route `hostname`, logging to `log`."""
    listener = listener_authority(address, port)
    return [
        cloudflared,
        "access",
        "tcp",
        "--hostname",
        hostname,
        "--url",
        listener,
        "--logfile",
        str(log),
    ]


def context_commands(
    cluster: str, user: str, ca_data: str, address: str, port: int
) -> tuple[str, list[list[str]]]:
    """The tunnel context's name and the `kubectl config` commands that write it."""
    name = f"{cluster}{TUNNEL_CONTEXT_SUFFIX}"
    server = str(httpx2.URL(scheme="https", host=address, port=port))
    return name, [
        [
            "kubectl",
            "config",
            "set-cluster",
            name,
            f"--server={server}",
            f"--tls-server-name={TUNNEL_TLS_SERVER_NAME}",
        ],
        ["kubectl", "config", "set", f"clusters.{name}.certificate-authority-data", ca_data],
        ["kubectl", "config", "set-context", name, f"--cluster={name}", f"--user={user}"],
    ]


def port_listening(address: str, port: int, timeout: float = _PROBE_TIMEOUT_SECONDS) -> bool:
    """Whether `<address>:<port>` accepts a connection."""
    try:
        with socket.create_connection((address, port), timeout=timeout):
            return True
    except OSError:
        return False


def load_tunnel(state_file: Path) -> TunnelRecord | None:
    """The record of the forward, or None when there is none or it cannot be read."""
    if not state_file.is_file() or state_file.is_symlink():
        return None
    try:
        return TunnelRecord.model_validate_json(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.debug("Cannot read the tunnel record %s: %s", state_file, exc)
        return None


def _forget(state_file: Path) -> None:
    state_file.unlink(missing_ok=True)


def _log_in(cloudflared: str, hostname: str) -> None:
    """Run the Access login with the terminal attached, so cloudflared shows its login URL."""
    result = run_subprocess(
        login_command(cloudflared, hostname),
        capture_output=False,
        timeout=_LOGIN_TIMEOUT_SECONDS,
        extra_allowed_env=_BROWSER_ENV,
    )
    if result.returncode != 0:
        raise KubernetesTunnelError(
            ERRORS.k8s.tunnel_login_failed.format(host=hostname, code=result.returncode)
        )


def _wait_until_listening(
    process: DetachedProcess, record: TunnelRecord, state_file: Path, timeout: float
) -> None:
    """Return once the port accepts connections; stop and forget the forward when it does not."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_listening(record.address, record.port):
            return
        code = process.poll()
        if code is not None:
            _forget(state_file)
            raise KubernetesTunnelError(
                ERRORS.k8s.tunnel_exited.format(
                    code=code, listener=record.listener, log=record.log_file
                )
            )
        time.sleep(_POLL_SECONDS)
    terminate_process_group(record.pid)
    _forget(state_file)
    raise KubernetesTunnelError(
        ERRORS.k8s.tunnel_not_listening.format(
            listener=record.listener, seconds=timeout, log=record.log_file
        )
    )


def start_tunnel(
    hostname: str,
    *,
    cloudflared: str,
    address: str,
    port: int,
    state_file: Path,
    timeout: float = _START_TIMEOUT_SECONDS,
) -> TunnelStart:
    """Log in, start one forward in a session of its own and record it.

    The lock is held from the read of the record to its save, so two runs at once start one
    forward. A forward that already runs is reported, with no login and no second process.
    """
    with state_file_lock(state_file):
        running = load_tunnel(state_file)
        if running is not None and running.is_alive:
            return TunnelStart(running, started=False)
        listener = listener_authority(address, port)
        if port_listening(address, port):
            raise KubernetesTunnelError(ERRORS.k8s.tunnel_port_in_use.format(listener=listener))
        _log_in(cloudflared, hostname)
        log = state_file.with_suffix(".log")
        process = spawn_detached(forward_command(cloudflared, hostname, address, port, log))
        record = TunnelRecord(
            pid=process.pid,
            start_ticks=process_start_ticks(process.pid),
            hostname=hostname,
            address=address,
            port=port,
            log_file=str(log),
        )
        write_json_file(state_file, record, atomic=True)
        _wait_until_listening(process, record, state_file, timeout)
        return TunnelStart(record, started=True)


def remember_context(state_file: Path, context: str) -> None:
    """Record the tunnel context that `start --context` wrote, for `status`."""
    with state_file_lock(state_file):
        record = load_tunnel(state_file)
        if record is not None:
            write_json_file(state_file, record.model_copy(update={"context": context}), atomic=True)


def write_tunnel_context(home_context: str, *, address: str, port: int) -> str:
    """Add or update `<cluster>-tunnel` from the cluster, user and CA data of `home_context`."""
    view = run_subprocess(
        [
            "kubectl",
            "config",
            "view",
            "--raw",
            "--minify",
            "--flatten",
            "--context",
            home_context,
            "-o",
            _CONTEXT_TEMPLATE,
        ],
        local_read=True,
    )
    lines = view.stdout.splitlines() if view.returncode == 0 else []
    cluster, user, ca_data = (lines + ["", "", ""])[:3]
    if not (cluster.strip() and user.strip() and ca_data.strip()):
        raise KubernetesTunnelError(ERRORS.k8s.tunnel_context_unread.format(context=home_context))
    name, commands = context_commands(cluster.strip(), user.strip(), ca_data.strip(), address, port)
    for command in commands:
        run_subprocess(command, check=True)
    return name


def stop_tunnel(state_file: Path) -> TunnelRecord | None:
    """Signal the recorded forward's process group and forget it; None when none ran."""
    if not state_file.is_file():
        return None
    with state_file_lock(state_file):
        record = load_tunnel(state_file)
        stopped = record is not None and record.is_alive and terminate_process_group(record.pid)
        _forget(state_file)
    return record if stopped else None


def tunnel_status(
    state_file: Path, *, address: str, port: int | None, context: str | None
) -> TunnelStatus:
    """The recorded forward, its port and, for `context` or the recorded one, the API server."""
    from devops_cli.k8s.service import KubernetesService

    record = load_tunnel(state_file)
    if record is not None and not record.is_alive:
        record = None
    checked_address = record.address if record else address
    checked_port = (
        port if port is not None else (record.port if record else DEFAULT_K8S_TUNNEL_PORT)
    )
    checked_context = context or (record.context if record else None)
    answers = (
        KubernetesService.get_instance().api_server_answers(checked_context)
        if checked_context
        else None
    )
    return TunnelStatus(
        record=record,
        listener=listener_authority(checked_address, checked_port),
        listening=port_listening(checked_address, checked_port),
        context=checked_context,
        api_answers=answers,
    )
