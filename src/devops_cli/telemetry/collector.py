"""Finding the cluster's OpenTelemetry collector from a workstation.

devops-cli exports traces and metrics over OTLP to `telemetry.endpoint`. The default,
`http://localhost:4318`, answers only where a collector runs locally; the cluster's collector
is reached through its NodePort. The endpoint is found from the cluster itself, so no host
name or port is written into the repository.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from devops_cli.config.commands import BIN_KUBECTL
from devops_cli.config.constants import CONST_OTEL_OTLP_HTTP_PORT
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import DevOpsCLIError


class CollectorNotFoundError(DevOpsCLIError):
    """The collector service cannot be reached from outside the cluster."""


def _kubectl(context: str | None, *args: str) -> str:
    cmd = [BIN_KUBECTL, *(["--context", context] if context else []), *args]
    proc = run_subprocess(cmd, timeout=30, quiet=True)
    if proc.returncode != 0:
        raise CollectorNotFoundError((proc.stderr or proc.stdout or "kubectl failed").strip())
    return proc.stdout


def _otlp_http_node_port(service: dict[str, object]) -> int:
    spec = service.get("spec")
    if not isinstance(spec, dict):
        raise CollectorNotFoundError("the collector service has no spec")
    if spec.get("type") not in ("NodePort", "LoadBalancer"):
        raise CollectorNotFoundError(
            f"the collector service is {spec.get('type')}, reachable only inside the cluster; "
            "expose it as a NodePort (k8s/otel/values.yaml)"
        )
    for port in spec.get("ports") or []:
        is_http = port.get("port") == CONST_OTEL_OTLP_HTTP_PORT or port.get("name") == "otlp-http"
        if is_http and port.get("nodePort"):
            return int(port["nodePort"])
    raise CollectorNotFoundError("the collector service exposes no OTLP HTTP node port")


def collector_endpoint(context: str | None, namespace: str, service: str) -> str:
    """The OTLP HTTP endpoint of the cluster's collector, as a workstation reaches it.

    The host is the current context's API server, since a NodePort answers on every node.
    """
    svc = json.loads(_kubectl(context, "-n", namespace, "get", "service", service, "-o", "json"))
    node_port = _otlp_http_node_port(svc)
    server = _kubectl(
        context, "config", "view", "--minify", "-o", "jsonpath={.clusters[0].cluster.server}"
    )
    host = urlparse(server.strip()).hostname
    if not host:
        raise CollectorNotFoundError(f"cannot tell the cluster's host from {server.strip()!r}")
    return f"http://{host}:{node_port}"


__all__ = ["CollectorNotFoundError", "collector_endpoint"]
