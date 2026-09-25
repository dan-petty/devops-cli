"""Cluster services a workstation reaches through a NodePort, found from the cluster itself.

A NodePort answers on every node, so a workstation reaches it at the host of the current
context's API server. The port is read from the service, so no host name or port is written
into the repository.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from urllib.parse import urlparse

from devops_cli.config.commands import BIN_KUBECTL
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import DevOpsCLIError


class ServiceNotReachableError(DevOpsCLIError):
    """A service cannot be reached from outside the cluster."""


@dataclass(frozen=True)
class NodePortSpec:
    """One port of a service that workstations reach on a NodePort."""

    # What the service is, for messages, e.g. "collector".
    what: str
    port: int
    port_name: str
    # What the port carries, for messages, e.g. "OTLP HTTP".
    port_label: str
    # Where the service is exposed, named when it is not.
    manifest: str


def kubectl(context: str | None, *args: str) -> str:
    """Run kubectl against a context, the current one when None, and return its output."""
    cmd = [BIN_KUBECTL, *(["--context", context] if context else []), *args]
    proc = run_subprocess(cmd, timeout=30, quiet=True)
    if proc.returncode != 0:
        raise ServiceNotReachableError((proc.stderr or proc.stdout or "kubectl failed").strip())
    return proc.stdout


def _node_port(service: dict[str, object], spec: NodePortSpec) -> int:
    svc_spec = service.get("spec")
    if not isinstance(svc_spec, dict):
        raise ServiceNotReachableError(f"the {spec.what} service has no spec")
    if svc_spec.get("type") not in ("NodePort", "LoadBalancer"):
        raise ServiceNotReachableError(
            f"the {spec.what} service is {svc_spec.get('type')}, reachable only inside the "
            f"cluster; expose it as a NodePort ({spec.manifest})"
        )
    for port in svc_spec.get("ports") or []:
        matches = port.get("port") == spec.port or port.get("name") == spec.port_name
        if matches and port.get("nodePort"):
            return int(port["nodePort"])
    raise ServiceNotReachableError(
        f"the {spec.what} service exposes no {spec.port_label} node port"
    )


def cluster_host(context: str | None) -> str:
    """The host of the context's API server, where every NodePort answers."""
    server = kubectl(
        context, "config", "view", "--minify", "-o", "jsonpath={.clusters[0].cluster.server}"
    ).strip()
    host = urlparse(server).hostname
    if not host:
        raise ServiceNotReachableError(f"cannot tell the cluster's host from {server!r}")
    return host


def node_port_address(
    context: str | None, namespace: str, service: str, spec: NodePortSpec
) -> tuple[str, int]:
    """The host and port a workstation reaches the service's port at."""
    svc = json.loads(kubectl(context, "-n", namespace, "get", "service", service, "-o", "json"))
    node_port = _node_port(svc, spec)
    return cluster_host(context), node_port


def secret_value(context: str | None, namespace: str, secret: str, key: str) -> str:
    """One key of a secret, decoded. The value is never logged or echoed."""
    encoded = kubectl(
        context, "-n", namespace, "get", "secret", secret, "-o", f"jsonpath={{.data.{key}}}"
    ).strip()
    if not encoded:
        raise ServiceNotReachableError(f"secret {namespace}/{secret} has no {key!r} key")
    try:
        return base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise ServiceNotReachableError(
            f"secret {namespace}/{secret} key {key!r} is not text"
        ) from exc


__all__ = [
    "NodePortSpec",
    "ServiceNotReachableError",
    "cluster_host",
    "kubectl",
    "node_port_address",
    "secret_value",
]
