"""Probes of a service on a running cluster: a local forward and a throwaway pod (#3894).

Two methods test what a NetworkPolicy and a service allow, and both are independent of the workload:

- `forward_service` forwards a local port to a Service with `kubectl port-forward`, waits until the
  health route answers, and stops the forward when the block ends. A caller sends its requests to
  the local address with `devops_cli.http.entry`.
- `probe_from_pod` starts a throwaway pod with the labels of a workload, so that the NetworkPolicy
  of the workload applies to it, tries a TCP connect to each target from inside the pod, and
  deletes the pod. A connect that fails means that the policy blocks the destination.

The module knows no service name. `devops k8s crawl4ai-check` and `devops k8s searxng-check` (#3929) use it.

The pod must pass two checks of the cluster:

- Namespace `devops` enforces Pod Security `restricted`, so the pod runs as a non-root user, drops
  all capabilities, forbids privilege escalation and sets the seccomp profile `RuntimeDefault`.
- The Service of the workload selects its pods by label, and the pod carries that label. So the
  pod never becomes ready: its readiness probe runs `false`, and a pod that is not ready is not an
  endpoint of the Service. (A ReplicaSet does not adopt the pod either: its selector holds the
  `pod-template-hash` label, which the pod lacks.)

The pod runs the image `PROBE_IMAGE`. Its `nc` applet connects with `nc -w 3 <host> <port>
</dev/null` and exits with 0 when the connect succeeds and 1 when it fails or times out. The applet
has no `-z` option: BusyBox 1.37.0 `nc --help` lists `-e`, `-l`, `-p`, `-s`, `-w` and `-i`, and
`nc -z` exits 1 against an open port. The exit codes were checked against the pinned image with a
listener, a closed port and an address that drops packets.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import secrets
import signal
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

import httpx2

from devops_cli.config.commands import BIN_KUBECTL
from devops_cli.config.defaults import (
    DEFAULT_PROBE_CONNECT_SECONDS,
    DEFAULT_PROBE_POD_LIFETIME_SECONDS,
    DEFAULT_PROBE_POD_START_SECONDS,
    DEFAULT_SERVICE_FORWARD_POLL_SECONDS,
    DEFAULT_SERVICE_FORWARD_WAIT_SECONDS,
)
from devops_cli.core import clock
from devops_cli.core.process import run_subprocess, spawn_detached, terminate_process_group
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.k8s import ServiceProbeError
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client, request_headers
from devops_cli.lang import ERRORS

logger = logging.getLogger(__name__)

# BusyBox 1.37.0 on Docker Hub: the index digest of the tag, which covers each platform.
PROBE_IMAGE = (
    "busybox:1.37.0@sha256:a7dbc319b1438115a207e11930dc4bb3e643dcb3ec0bdd694bb36cd8fad289ec"
)
_KUBECTL_TIMEOUT_SECONDS = 30
_NON_ROOT_ID = 65534
_EXEC_TERMINATED = "command terminated with exit code"


@dataclass(frozen=True)
class PodTarget:
    """A destination to try from the pod: `role` names it in a report, so a report holds no
    address or host name."""

    role: str
    host: str
    port: int


@dataclass(frozen=True)
class PodProbeRow:
    """The result for one target: `reached` is true when the pod opened a TCP connection."""

    role: str
    reached: bool


def kubectl_argv(
    verb: str,
    *args: str,
    context: str | None = None,
    command: Sequence[str] = (),
) -> list[str]:
    """A `kubectl` call: `verb`, its `args`, the context flag, and after `--` the `command` that
    runs in a pod."""
    return [
        BIN_KUBECTL,
        verb,
        *args,
        *(["--context", context] if context else []),
        *(["--", *command] if command else []),
    ]


def _kubectl(argv: list[str]) -> tuple[int, str, str]:
    result = run_subprocess(argv, timeout=_KUBECTL_TIMEOUT_SECONDS, quiet=True)
    return result.returncode, result.stdout or "", result.stderr or ""


def read_capped(response: httpx2.Response, limit: int) -> bytes:
    """The body of a streamed reply, cut once it passes `limit` bytes."""
    body = bytearray()
    for chunk in response.iter_bytes():
        body += chunk
        if len(body) > limit:
            break
    return bytes(body)


def _label_selector(labels: Mapping[str, str]) -> str:
    return ",".join(f"{key}={value}" for key, value in labels.items())


def _pod_overrides(name: str) -> dict[str, object]:
    """The pod spec that `kubectl run --overrides` merges: the `restricted` level of Pod Security,
    a readiness probe that never succeeds, and a lifetime."""
    security = {
        "runAsNonRoot": True,
        "runAsUser": _NON_ROOT_ID,
        "runAsGroup": _NON_ROOT_ID,
        "seccompProfile": {"type": "RuntimeDefault"},
    }
    return {
        "apiVersion": "v1",
        "spec": {
            "automountServiceAccountToken": False,
            "activeDeadlineSeconds": DEFAULT_PROBE_POD_LIFETIME_SECONDS,
            "terminationGracePeriodSeconds": 0,
            "securityContext": security,
            "containers": [
                {
                    "name": name,
                    "image": PROBE_IMAGE,
                    "command": ["sleep", str(DEFAULT_PROBE_POD_LIFETIME_SECONDS)],
                    "securityContext": {
                        **security,
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                        "readOnlyRootFilesystem": True,
                    },
                    "readinessProbe": {"exec": {"command": ["false"]}, "periodSeconds": 5},
                    "resources": {
                        "requests": {"cpu": "10m", "memory": "16Mi"},
                        "limits": {"cpu": "100m", "memory": "32Mi"},
                    },
                }
            ],
        },
    }


def _run_argv(
    name: str, namespace: str, labels: Mapping[str, str], overrides: str, context: str | None
) -> list[str]:
    return kubectl_argv(
        "run",
        name,
        "--image",
        PROBE_IMAGE,
        "--labels",
        _label_selector(labels),
        "--restart",
        "Never",
        "-n",
        namespace,
        "--overrides",
        overrides,
        context=context,
    )


def _connect_command(target: PodTarget) -> list[str]:
    """The command that runs in the pod. The host and the port are positional arguments of the
    shell, so no value is part of the script."""
    return [
        "sh",
        "-c",
        f'nc -w {DEFAULT_PROBE_CONNECT_SECONDS} "$0" "$1" </dev/null',
        target.host,
        str(target.port),
    ]


def _connects(name: str, namespace: str, target: PodTarget, context: str | None) -> bool:
    """Whether the pod opens a connection to `target`.

    Exit code 0 of the shell is a connection. Exit code 1 with the line `command terminated with
    exit code 1` of kubectl, or with no stderr, is a failed connect. Any other code, or an error
    line of kubectl itself, is a probe that did not run, which is no evidence that the policy
    blocks the target, so it raises.
    """
    argv = kubectl_argv(
        "exec", name, "-n", namespace, context=context, command=_connect_command(target)
    )
    code, _, stderr = _kubectl(argv)
    if code == 0:
        return True
    detail = stderr.strip()
    if code == 1 and (not detail or detail.endswith(f"{_EXEC_TERMINATED} 1")):
        return False
    raise ServiceProbeError(
        ERRORS.k8s.probe_exec_failed.format(
            pod=name, role=target.role, code=code, detail=detail or "no output"
        )
    )


def _start_pod(name: str, namespace: str, labels: Mapping[str, str], context: str | None) -> None:
    code, _, stderr = _kubectl(
        _run_argv(name, namespace, labels, json.dumps(_pod_overrides(name)), context)
    )
    if code != 0:
        raise ServiceProbeError(
            ERRORS.k8s.probe_pod_failed.format(
                pod=name, step="run", detail=stderr.strip() or f"exit code {code}"
            )
        )
    code, _, stderr = _kubectl(
        kubectl_argv(
            "wait",
            f"pod/{name}",
            "--for",
            "jsonpath={.status.phase}=Running",
            "--timeout",
            f"{DEFAULT_PROBE_POD_START_SECONDS}s",
            "-n",
            namespace,
            context=context,
        )
    )
    if code != 0:
        raise ServiceProbeError(
            ERRORS.k8s.probe_pod_failed.format(
                pod=name, step="wait", detail=stderr.strip() or f"exit code {code}"
            )
        )


def _delete_pod(name: str, namespace: str, context: str | None) -> str | None:
    """Delete the pod. Returns the reason when it fails, else None."""
    code, _, stderr = _kubectl(
        kubectl_argv(
            "delete",
            "pod",
            name,
            "-n",
            namespace,
            "--now",
            "--wait=false",
            "--ignore-not-found",
            context=context,
        )
    )
    return None if code == 0 else (stderr.strip() or f"exit code {code}")


def probe_from_pod(
    *,
    namespace: str,
    labels: Mapping[str, str],
    targets: Sequence[PodTarget],
    name_prefix: str,
    context: str | None = None,
) -> list[PodProbeRow]:
    """Start a pod with `labels` in `namespace`, try a TCP connect to each target from it, and
    delete the pod, also after a failure.

    The pod name is `name_prefix` and a random suffix, so two runs never meet. Raises
    `ServiceProbeError` when the pod does not start, a probe does not run, or the pod cannot be
    deleted (the error names the command that deletes it).
    """
    name = f"{name_prefix}-{secrets.token_hex(4)}"
    try:
        _start_pod(name, namespace, labels, context)
        rows = [
            PodProbeRow(role=target.role, reached=_connects(name, namespace, target, context))
            for target in targets
        ]
    except BaseException:
        failure = _delete_pod(name, namespace, context)
        if failure:
            logger.error(
                ERRORS.k8s.probe_pod_not_deleted.format(
                    pod=name, namespace=namespace, detail=failure
                )
            )
        raise
    failure = _delete_pod(name, namespace, context)
    if failure:
        raise ServiceProbeError(
            ERRORS.k8s.probe_pod_not_deleted.format(pod=name, namespace=namespace, detail=failure)
        )
    return rows


def plan_probe_from_pod(
    *,
    namespace: str,
    labels: Mapping[str, str],
    targets: Sequence[PodTarget],
    name_prefix: str,
    context: str | None = None,
) -> list[PlannedRequest]:
    """The calls of `probe_from_pod`, in order, with a placeholder for the pod name and the pod
    spec. The plan holds the role of each target, never its address."""
    name = f"{name_prefix}-<suffix>"
    plan = [
        PlannedRequest(
            method="kubectl run",
            target=name,
            argv=tuple(_run_argv(name, namespace, labels, "<restricted pod spec>", context)),
        )
    ]
    plan.extend(
        PlannedRequest(method="kubectl exec", target=f"{name} -> {target.role}")
        for target in targets
    )
    plan.append(PlannedRequest(method="kubectl delete", target=name))
    return plan


def service_cluster_ip(namespace: str, service: str, context: str | None = None) -> str:
    """The ClusterIP of a Service, as a probe target. Raises `ServiceProbeError` for a Service
    that has none that can be read."""
    code, stdout, stderr = _kubectl(
        kubectl_argv(
            "get",
            "service",
            service,
            "-n",
            namespace,
            "-o",
            "jsonpath={.spec.clusterIP}",
            context=context,
        )
    )
    try:
        if code != 0:
            raise ValueError(stderr.strip() or f"exit code {code}")
        return str(ipaddress.ip_address(stdout.strip()))
    except ValueError as exc:
        raise ServiceProbeError(
            ERRORS.k8s.probe_cluster_ip.format(service=service, detail=exc)
        ) from exc


def forward_argv(
    service: str, namespace: str, remote_port: int, local_port: int, context: str | None
) -> list[str]:
    """The `kubectl port-forward` call of `forward_service`."""
    return kubectl_argv(
        "port-forward",
        f"svc/{service}",
        f"{local_port}:{remote_port}",
        "-n",
        namespace,
        context=context,
    )


def _answers(base_url: str, health_path: str) -> bool:
    """Whether the health route answers 200 through the forward."""
    try:
        with http_client(
            EgressLevel.LOOPBACK, timeout=DEFAULT_SERVICE_FORWARD_POLL_SECONDS * 4
        ) as client:
            response = client.get(f"{base_url}{health_path}", headers=request_headers())
    except httpx2.HTTPError:
        return False
    return response.status_code == 200


@contextmanager
def forward_service(
    *,
    service: str,
    namespace: str,
    remote_port: int,
    local_port: int,
    health_path: str,
    context: str | None = None,
) -> Iterator[str]:
    """Forward `local_port` to `service` and yield the local base URL, once `health_path` answers.

    The health request carries no credential. A forward that ends before the route answers, or a
    route that stays silent for `DEFAULT_SERVICE_FORWARD_WAIT_SECONDS`, raises `ServiceProbeError`.
    The forward stops when the block ends, also after an error.
    """
    base_url = f"http://127.0.0.1:{local_port}"
    process = spawn_detached(forward_argv(service, namespace, remote_port, local_port, context))
    try:
        deadline = clock.monotonic() + DEFAULT_SERVICE_FORWARD_WAIT_SECONDS
        while True:
            code = process.poll()
            if code is not None:
                raise ServiceProbeError(
                    ERRORS.k8s.probe_forward_exited.format(service=service, code=code)
                )
            if _answers(base_url, health_path):
                break
            if clock.monotonic() >= deadline:
                raise ServiceProbeError(
                    ERRORS.k8s.probe_forward_silent.format(
                        service=service,
                        path=health_path,
                        seconds=DEFAULT_SERVICE_FORWARD_WAIT_SECONDS,
                    )
                )
            clock.sleep(DEFAULT_SERVICE_FORWARD_POLL_SECONDS)
        yield base_url
    finally:
        if process.poll() is None:
            terminate_process_group(process.pid, signal.SIGTERM)
