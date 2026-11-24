"""Probes of a service on a running cluster: a local forward and a throwaway pod (#3894).

Two methods test what a NetworkPolicy and a service allow, and both are independent of the workload:

- `forward_service` forwards a local port to a Service with `kubectl port-forward`, waits until the
  health route answers, and stops the forward when the block ends. A caller sends its requests to
  the local address with `devops_cli.http.entry`.
- `probe_from_pod` starts a throwaway pod with the labels of a workload, so that the NetworkPolicy
  of the workload applies to it, tries a TCP connect to each target from inside the pod, and
  deletes the pod. A connect that fails means that the policy blocks the destination.
- `probe_http_from_pod` starts the same throwaway pod with an image that holds `curl`, sends one
  HTTP request from it, and deletes the pod. It sends the request again while the connection is
  refused, because kube-router programs the policy of a new pod a few seconds after the pod starts.

The module knows no service name. `devops k8s crawl4ai-check` and `devops k8s searxng-check` (#3929) use it.

The pod must pass two checks of the cluster:

- Namespace `devops` enforces Pod Security `restricted`, so the pod runs as a non-root user, drops
  all capabilities, forbids privilege escalation and sets the seccomp profile `RuntimeDefault`.
- The Service of the workload selects its pods by label, and the pod carries that label. So the
  pod never becomes ready: its readiness probe runs `false`, and a pod that is not ready is not an
  endpoint of the Service. (A ReplicaSet does not adopt the pod either: its selector holds the
  `pod-template-hash` label, which the pod lacks.)

The pod runs the image that its caller names. The TCP probe pod runs the image of suspended
CronJob `devops/service-probe`, and its `nc` applet connects with `nc -w 3 <host> <port> </dev/null`
and exits with 0 when the connect succeeds and 1 when it fails or times out. The applet has no `-z` option: BusyBox 1.37.0 `nc --help` lists
`-e`, `-l`, `-p`, `-s`, `-w` and `-i`, and `nc -z` exits 1 against an open port. The exit codes were
checked against the pinned image with a listener, a closed port and an address that drops packets.
The HTTP probe pod runs `CURL_IMAGE`, and its `curl` prints the HTTP status and exits 7 when it
cannot connect. A header value reaches curl as a configuration line on the standard input of the
exec call, so no command line and no output holds it.
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
from typing import Any

import httpx2

from devops_cli.config.commands import BIN_KUBECTL
from devops_cli.config.defaults import (
    DEFAULT_PROBE_CONNECT_SECONDS,
    DEFAULT_PROBE_POD_LIFETIME_SECONDS,
    DEFAULT_PROBE_POD_START_SECONDS,
    DEFAULT_PROBE_RETRY_SECONDS,
    DEFAULT_PROBE_TIMEOUT_SECONDS,
    DEFAULT_PROBE_WAIT_SECONDS,
    DEFAULT_SERVICE_FORWARD_POLL_SECONDS,
    DEFAULT_SERVICE_FORWARD_WAIT_SECONDS,
)
from devops_cli.core import clock
from devops_cli.core.process import run_subprocess, spawn_detached, terminate_process_group
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.k8s import ServiceProbeError
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client, request_headers
from devops_cli.lang import ERRORS, MESSAGES

logger = logging.getLogger(__name__)

# curlimages/curl 8.23.0 on Docker Hub, read from the registry with `tag_digest`: the index digest
# of the tag, which covers each platform. The image holds `curl`, `sh` and `sleep`.
CURL_IMAGE = (
    "curlimages/curl:8.23.0@sha256:3fb7e13e5d179a845c97d78204f3f1064d1907037f26a3ebf91710571151fd93"
)
_KUBECTL_TIMEOUT_SECONDS = 30
_NON_ROOT_ID = 65534
_EXEC_TERMINATED = "command terminated with exit code"
# The exit code of curl when it cannot connect: the policy refuses the path, or kube-router has not
# programmed the policy of the new pod yet.
_CURL_CANNOT_CONNECT = 7


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


@dataclass(frozen=True)
class PodHttpResult:
    """The result of one HTTP request from the pod: the HTTP `status` that the service answered, or
    the `curl` exit code when no response arrived, such as 7 for a refused connection."""

    status: int | None
    curl_exit: int | None


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


def _read_probe_template(
    context: str | None = None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Read the probe image and security contexts from suspended CronJob devops/service-probe."""
    argv = kubectl_argv(
        "get",
        "cronjob",
        "service-probe",
        "-n",
        "devops",
        "--ignore-not-found",
        "-o",
        "json",
        context=context,
    )
    code, stdout, stderr = _kubectl(argv)
    if code != 0 or not stdout.strip():
        detail = stderr.strip() if code != 0 else ""
        raise ServiceProbeError(
            MESSAGES.k8s.job_cronjob_missing.format(cronjob="service-probe")
            + (f": {detail}" if detail else "")
        )
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as err:
        raise ServiceProbeError(
            f"CronJob devops/service-probe returned invalid JSON: {err}"
        ) from err
    if not data:
        raise ServiceProbeError(MESSAGES.k8s.job_cronjob_missing.format(cronjob="service-probe"))
    pod_spec = (
        data.get("spec", {})
        .get("jobTemplate", {})
        .get("spec", {})
        .get("template", {})
        .get("spec", {})
    )
    pod_security = dict(pod_spec.get("securityContext") or {})
    containers = pod_spec.get("containers") or []
    container = next((c for c in containers if c.get("name") == "probe"), None)
    if not container or not container.get("image"):
        raise ServiceProbeError("CronJob devops/service-probe has no probe container with an image")
    image = str(container["image"])
    container_security = dict(container.get("securityContext") or {})
    return image, pod_security, container_security


def _pod_overrides(
    name: str,
    *,
    image: str,
    pod_security: Mapping[str, Any] | None = None,
    container_security: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """The pod spec that `kubectl run --overrides` merges: the security contexts from the
    template, a readiness probe that never succeeds, and a lifetime."""
    default_security = {
        "runAsNonRoot": True,
        "runAsUser": _NON_ROOT_ID,
        "runAsGroup": _NON_ROOT_ID,
        "seccompProfile": {"type": "RuntimeDefault"},
    }
    pod_sec = dict(pod_security) if pod_security is not None else default_security
    cont_sec = (
        dict(container_security)
        if container_security is not None
        else {
            **pod_sec,
            "allowPrivilegeEscalation": False,
            "capabilities": {"drop": ["ALL"]},
            "readOnlyRootFilesystem": True,
        }
    )
    return {
        "apiVersion": "v1",
        "spec": {
            "automountServiceAccountToken": False,
            "activeDeadlineSeconds": DEFAULT_PROBE_POD_LIFETIME_SECONDS,
            "terminationGracePeriodSeconds": 0,
            "securityContext": pod_sec,
            "containers": [
                {
                    "name": name,
                    "image": image,
                    "command": ["sleep", str(DEFAULT_PROBE_POD_LIFETIME_SECONDS)],
                    "securityContext": cont_sec,
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
    name: str,
    namespace: str,
    labels: Mapping[str, str],
    overrides: str,
    context: str | None,
    *,
    image: str,
) -> list[str]:
    return kubectl_argv(
        "run",
        name,
        "--image",
        image,
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


def _curl_command(url: str, method: str) -> list[str]:
    """The command that runs in the pod: curl prints the HTTP status on its standard output and
    reads the headers as configuration lines on its standard input, so no command line holds a
    header value. curl stops at the connect bound, which keeps one attempt inside its exec call."""
    return [
        "curl",
        "-sS",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        "--connect-timeout",
        str(DEFAULT_PROBE_CONNECT_SECONDS),
        "--max-time",
        str(DEFAULT_PROBE_CONNECT_SECONDS),
        "-K",
        "-",
        *(["-X", method] if method != "GET" else []),
        url,
    ]


def _curl_config(headers: Sequence[str]) -> str:
    """The curl configuration lines of the headers, which travel on the standard input of the exec
    call. It is empty for no headers, so curl reads no line and waits for nothing."""
    return "".join(f'header = "{header}"\n' for header in headers)


def _curl_exit(code: int, stderr: str) -> int:
    """The exit code of the pod's curl: the code on the `command terminated with exit code` line
    that `kubectl exec` prints, else the exit status of the call, which kubectl takes from the
    remote command."""
    marker = f"{_EXEC_TERMINATED} "
    for line in reversed(stderr.strip().splitlines()):
        if marker in line:
            code_text = line.rsplit(marker, 1)[1].strip()
            if code_text.isdigit():
                return int(code_text)
    return code


def _http_status(stdout: str, name: str) -> int:
    """The HTTP status that curl printed for the request, or an error when it printed none."""
    text = stdout.strip()
    if not text.isdigit():
        raise ServiceProbeError(
            ERRORS.k8s.probe_pod_failed.format(
                pod=name, step="curl", detail=f"no HTTP status in the output: {text or 'no output'}"
            )
        )
    return int(text)


def _request_from_pod(
    name: str,
    namespace: str,
    url: str,
    method: str,
    headers: Sequence[str],
    context: str | None,
) -> PodHttpResult:
    """One HTTP request from the pod, with each header value on the standard input of the exec
    call, so that no command line holds it.

    Exit code 7 of curl is a connection that the policy refuses, or one that kube-router has not
    programmed yet, so the caller sends the request again. Any other non-zero code is a curl that
    did not run, which is no measurement, so it raises.
    """
    argv = kubectl_argv(
        "exec",
        "-i",
        name,
        "-n",
        namespace,
        context=context,
        command=_curl_command(url, method),
    )
    result = run_subprocess(
        argv,
        input=_curl_config(headers),
        timeout=DEFAULT_PROBE_CONNECT_SECONDS,
        quiet=True,
    )
    code = _curl_exit(result.returncode, result.stderr or "")
    if code == _CURL_CANNOT_CONNECT:
        return PodHttpResult(status=None, curl_exit=code)
    if code != 0:
        raise ServiceProbeError(
            ERRORS.k8s.probe_pod_failed.format(
                pod=name,
                step="curl",
                detail=f"curl exit code {code}: {result.stderr.strip() or 'no output'}",
            )
        )
    return PodHttpResult(status=_http_status(result.stdout or "", name), curl_exit=None)


def _measure_http(
    name: str,
    namespace: str,
    url: str,
    method: str,
    headers: Sequence[str],
    wait: float,
    timeout: float,
    context: str | None,
) -> PodHttpResult:
    """Send the request again while curl cannot connect, and return the first measurement.

    The timeout deadline ends the probe with an error. The wait deadline ends the retry with the
    exit code of the last attempt, because a path that stays refused is a measurement.
    """
    deadline = clock.monotonic() + timeout
    wait_deadline = clock.monotonic() + wait
    while True:
        if clock.monotonic() >= deadline:
            raise ServiceProbeError(
                ERRORS.k8s.probe_timeout.format(pod=name, url=url, seconds=timeout)
            )
        measured = _request_from_pod(name, namespace, url, method, headers, context)
        if measured.curl_exit != _CURL_CANNOT_CONNECT or clock.monotonic() >= wait_deadline:
            return measured
        clock.sleep(DEFAULT_PROBE_RETRY_SECONDS)


def _start_pod(
    name: str,
    namespace: str,
    labels: Mapping[str, str],
    context: str | None,
    *,
    image: str,
    pod_security: Mapping[str, Any] | None = None,
    container_security: Mapping[str, Any] | None = None,
) -> None:
    overrides = json.dumps(
        _pod_overrides(
            name,
            image=image,
            pod_security=pod_security,
            container_security=container_security,
        )
    )
    code, _, stderr = _kubectl(_run_argv(name, namespace, labels, overrides, context, image=image))
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
    image, pod_security, container_security = _read_probe_template(context)
    try:
        _start_pod(
            name,
            namespace,
            labels,
            context,
            image=image,
            pod_security=pod_security,
            container_security=container_security,
        )
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
    image: str | None = None,
) -> list[PlannedRequest]:
    """The calls of `probe_from_pod`, in order, with a placeholder for the pod name and the pod
    spec. The plan holds the role of each target, never its address."""
    name = f"{name_prefix}-<suffix>"
    image = image or "<template image>"
    plan = [
        PlannedRequest(
            method="kubectl run",
            target=name,
            argv=tuple(
                _run_argv(
                    name,
                    namespace,
                    labels,
                    "<restricted pod spec>",
                    context,
                    image=image,
                )
            ),
        )
    ]
    plan.extend(
        PlannedRequest(method="kubectl exec", target=f"{name} -> {target.role}")
        for target in targets
    )
    plan.append(PlannedRequest(method="kubectl delete", target=name))
    return plan


def probe_http_from_pod(
    *,
    namespace: str,
    labels: Mapping[str, str],
    url: str,
    name_prefix: str,
    method: str = "GET",
    headers: Sequence[str] | None = None,
    image: str = CURL_IMAGE,
    wait: float = DEFAULT_PROBE_WAIT_SECONDS,
    timeout: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    context: str | None = None,
) -> PodHttpResult:
    """Start one pod with `labels` in `namespace`, send one HTTP request from it, and delete the
    pod, also after a failure.

    The request goes to `url` with `method` and each header of `headers`, whose values travel on
    the standard input of the exec call. The probe sends the request again while curl exits 7,
    until `wait` seconds pass, and stops with an error at `timeout` seconds. The result holds the
    HTTP status, or the exit code of curl for a path that stays refused. The pod name is
    `name_prefix` and a random suffix, so two runs never meet.
    """
    name = f"{name_prefix}-{secrets.token_hex(4)}"
    try:
        _start_pod(name, namespace, labels, context, image=image)
        measured = _measure_http(
            name, namespace, url, method, headers or (), wait, timeout, context
        )
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
    return measured


def plan_probe_http_from_pod(
    *,
    namespace: str,
    labels: Mapping[str, str],
    url: str,
    name_prefix: str,
    method: str = "GET",
    headers: Sequence[str] | None = None,
    image: str = CURL_IMAGE,
    wait: float = DEFAULT_PROBE_WAIT_SECONDS,
    context: str | None = None,
) -> list[PlannedRequest]:
    """The calls of `probe_http_from_pod`, in order, with a placeholder for the pod name, the pod
    spec and each header value. The plan holds the URL and the curl command line, and never a
    header value."""
    name = f"{name_prefix}-<suffix>"
    return [
        PlannedRequest(
            method="kubectl run",
            target=name,
            argv=tuple(
                _run_argv(
                    name,
                    namespace,
                    labels,
                    "<restricted pod spec>",
                    context,
                    image=image,
                )
            ),
        ),
        PlannedRequest(
            method="kubectl exec",
            target=f"{name} -> {url}",
            argv=tuple(
                kubectl_argv(
                    "exec",
                    "-i",
                    name,
                    "-n",
                    namespace,
                    context=context,
                    command=_curl_command(url, method),
                )
            ),
            stdin=_curl_config(["<value>"] * len(headers or [])),
            repeat=f"while curl exits {_CURL_CANNOT_CONNECT}, until {wait:g} s",
        ),
        PlannedRequest(method="kubectl delete", target=name),
    ]


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
