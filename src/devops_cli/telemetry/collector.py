"""Finding the cluster's OpenTelemetry collector from a workstation.

devops-cli exports traces and metrics over OTLP to `telemetry.endpoint`. The default,
`http://localhost:4318`, answers only where a collector runs locally; the cluster's collector
is reached through its NodePort, found from the cluster itself.
"""

from __future__ import annotations

from devops_cli.config.constants import CONST_OTEL_OTLP_HTTP_PORT
from devops_cli.k8s.node_port import NodePortSpec, node_port_address

OTLP_HTTP = NodePortSpec(
    what="collector",
    port=CONST_OTEL_OTLP_HTTP_PORT,
    port_name="otlp-http",
    port_label="OTLP HTTP",
    manifest="k8s/otel/values.yaml",
)


def collector_endpoint(context: str | None, namespace: str, service: str) -> str:
    """The OTLP HTTP endpoint of the cluster's collector, as a workstation reaches it."""
    host, port = node_port_address(context, namespace, service, OTLP_HTTP)
    return f"http://{host}:{port}"


__all__ = ["OTLP_HTTP", "collector_endpoint"]
