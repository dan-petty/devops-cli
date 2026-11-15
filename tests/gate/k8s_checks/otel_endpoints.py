"""Every OTLP endpoint in `k8s/` names the Collector Service that the cluster holds (#4528)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import yaml

from tests.support.paths import REPO_ROOT

COLLECTOR_SERVICE = "otel-collector-opentelemetry-collector.otel.svc.cluster.local"
COLLECTOR_NAMESPACE = ".otel.svc.cluster.local"
ENDPOINT_VARIABLE = "OTEL_EXPORTER_OTLP_ENDPOINT"


def _endpoints(node: Any) -> list[str]:
    """The value of each `OTEL_EXPORTER_OTLP_ENDPOINT` entry of an environment, at any depth."""
    found: list[str] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if current.get("name") == ENDPOINT_VARIABLE and isinstance(current.get("value"), str):
                found.append(current["value"])
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return found


def check_every_otlp_endpoint_names_the_collector_service() -> None:
    """No `OTEL_EXPORTER_OTLP_ENDPOINT` in `k8s/` names a Service in namespace `otel` other than
    `otel-collector-opentelemetry-collector`, which the Collector chart applies."""
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "k8s").rglob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        for document in yaml.safe_load_all(text):
            for endpoint in _endpoints(document):
                host = urlsplit(endpoint).hostname or ""
                if host.endswith(COLLECTOR_NAMESPACE) and host != COLLECTOR_SERVICE:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {host}")
    assert offenders == [], f"an OTLP endpoint names no Collector Service: {offenders}"
