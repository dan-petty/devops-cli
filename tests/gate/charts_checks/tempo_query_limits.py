"""The Tempo query limits, which stay under the memory limit of the pod (#6616, #6730).

Ten reads of the Tempo search API held the memory of pod `tempo-0` at its limit, which OOM-killed
the pod twice in one minute (#6616). The outstanding queries per tenant, the result limit of a
search, the concurrent queries of the querier and the size limit of a trace bound the memory that
the reads hold, and the read timeout of the query frontend stops a read and cancels its queued
jobs. The check reads the Tempo configuration that chart `tempo` renders and the memory limit of
the rendered `tempo` container, as Argo CD applies them. A key that the chart does not render,
such as `tempo.global_overrides` (#6730), leaves Tempo at its default and fails the check. The
check asserts the bounds and no value, so a new value within the bounds needs no change here
(docs/TESTING.md).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Final

import yaml
from kubernetes.utils.quantity import parse_quantity

from tests.gate.charts_render import ARGOCD_APPLICATIONS, chart_objects

TEMPO_APPLICATION: Final = ARGOCD_APPLICATIONS / "tempo.yaml"

TEMPO_CONTAINER: Final[str] = "tempo"

# The ConfigMap of the chart and its key that the container reads with `-config.file`.
CONFIG_MAP: Final[str] = "tempo"
CONFIG_FILE: Final[str] = "tempo.yaml"

# The keys of the rendered Tempo configuration that bound the reads.
OUTSTANDING: Final[tuple[str, ...]] = ("query_frontend", "max_outstanding_per_tenant")
RESULT_LIMIT: Final[tuple[str, ...]] = ("query_frontend", "search", "max_result_limit")
CONCURRENT: Final[tuple[str, ...]] = ("querier", "max_concurrent_queries")
TRACE_BYTES: Final[tuple[str, ...]] = ("overrides", "defaults", "global", "max_bytes_per_trace")
READ_TIMEOUT: Final[tuple[str, ...]] = ("query_frontend", "api_timeout")


def _rendered() -> tuple[dict[str, Any], Decimal]:
    """The rendered Tempo configuration and the memory limit of the rendered `tempo` container."""
    objects = chart_objects(TEMPO_APPLICATION)
    (config_map,) = (
        document
        for document in objects
        if document["kind"] == "ConfigMap" and document["metadata"]["name"] == CONFIG_MAP
    )
    (statefulset,) = (document for document in objects if document["kind"] == "StatefulSet")
    (container,) = (
        entry
        for entry in statefulset["spec"]["template"]["spec"]["containers"]
        if entry["name"] == TEMPO_CONTAINER
    )
    config: dict[str, Any] = yaml.safe_load(config_map["data"][CONFIG_FILE])
    return config, parse_quantity(container["resources"]["limits"]["memory"])


def _setting(config: dict[str, Any], path: tuple[str, ...]) -> Any:
    """The value at `path` of the configuration, or None when a key of the path is absent."""
    value: Any = config
    for key in path:
        value = value.get(key) if isinstance(value, dict) else None
    return value


def check_the_tempo_query_limits_stay_under_the_memory_limit() -> None:
    """The rendered configuration sets the outstanding queries, the result limit, the concurrent
    queries, the trace size limit and the read timeout. The outstanding searches and the
    concurrent reads hold at most half of the memory limit of the pod (#6616)."""
    config, memory = _rendered()
    found = {
        ".".join(path): _setting(config, path)
        for path in (OUTSTANDING, RESULT_LIMIT, CONCURRENT, TRACE_BYTES, READ_TIMEOUT)
    }
    unset = sorted(name for name, value in found.items() if value is None)

    assert unset == [], (
        f"{TEMPO_APPLICATION}: the rendered Tempo configuration does not set {unset}, so Tempo "
        "uses its default there"
    )

    outstanding = found[".".join(OUTSTANDING)]
    results = found[".".join(RESULT_LIMIT)]
    concurrent = found[".".join(CONCURRENT)]
    trace_bytes = found[".".join(TRACE_BYTES)]
    searched = outstanding * results * trace_bytes

    assert searched <= memory / 2, (
        f"{TEMPO_APPLICATION}: query_frontend.max_outstanding_per_tenant {outstanding} times "
        f"query_frontend.search.max_result_limit {results} times "
        f"overrides.defaults.global.max_bytes_per_trace {trace_bytes} is {searched} bytes, more "
        f"than half of the memory limit {memory}"
    )

    assert concurrent <= outstanding, (
        f"{TEMPO_APPLICATION}: querier.max_concurrent_queries {concurrent} is more than "
        f"query_frontend.max_outstanding_per_tenant {outstanding}"
    )

    held = concurrent * trace_bytes

    assert held <= memory / 2, (
        f"{TEMPO_APPLICATION}: querier.max_concurrent_queries {concurrent} times "
        f"overrides.defaults.global.max_bytes_per_trace {trace_bytes} is {held} bytes, more than "
        f"half of the memory limit {memory}"
    )
