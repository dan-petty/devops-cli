"""The Tempo query limits, which stay under the memory limit of the pod (#6616).

Two reads of the Tempo search API held the memory of pod `tempo-0` at the limit of
`k8s/otel/tempo-values.yaml:39:memory: 2048Mi`, which OOM-killed the pod twice in one minute. The
chart values cap the bytes of a trace that a search reads, the result count, the search duration,
the byte rate, the outstanding queries per tenant and the concurrent queries of the querier, so a
search cannot hold the memory of the pod. The chart renders the `queryFrontend` and `querier`
blocks of the values into the Tempo configuration (#1813).
"""

from __future__ import annotations

from typing import Any, Final

import yaml
from kubernetes.utils.quantity import parse_quantity

from tests.support.paths import REPO_ROOT

TEMPO_VALUES: Final = REPO_ROOT / "k8s" / "otel" / "tempo-values.yaml"


# The memory limit of the pod, and the query limits that the chart values set under it.
MEMORY_LIMIT: Final[str] = "2048Mi"

MAX_BYTES_PER_TRACE: Final[int] = 1000000

MAX_RESULT_LIMIT: Final[int] = 50

MAX_DURATION: Final[str] = "30s"

TARGET_BYTES_PER_SECOND: Final[int] = 25000000

MAX_OUTSTANDING_PER_TENANT: Final[int] = 10

MAX_CONCURRENT_QUERIES: Final[int] = 4


def _tempo() -> dict[str, Any]:
    """The `tempo:` block of the Tempo chart values."""
    values: dict[str, Any] = yaml.safe_load(TEMPO_VALUES.read_text(encoding="utf-8"))
    return values["tempo"]


def check_the_tempo_query_limits_stay_under_the_memory_limit() -> None:
    """The values set the search byte, result, duration and byte-rate limits, the outstanding
    queries per tenant and the concurrent queries of the querier under the `2048Mi` memory limit of
    the pod, so an oversized search or trace read is refused or cut and the pod stays up (#6616)."""
    tempo = _tempo()
    frontend = tempo.get("queryFrontend", {})
    querier = tempo.get("querier", {})
    found = (
        tempo.get("resources", {}).get("limits", {}).get("memory"),
        frontend,
        querier,
    )

    assert found == (
        MEMORY_LIMIT,
        {
            "search": {
                "max_bytes_per_trace": MAX_BYTES_PER_TRACE,
                "max_result_limit": MAX_RESULT_LIMIT,
                "max_duration": MAX_DURATION,
                "target_bytes_per_second": TARGET_BYTES_PER_SECOND,
            },
            "max_outstanding_per_tenant": MAX_OUTSTANDING_PER_TENANT,
        },
        {"max_concurrent_queries": MAX_CONCURRENT_QUERIES},
    ), (
        f"{TEMPO_VALUES}: resources.limits.memory is {found[0]}, queryFrontend is {found[1]} "
        f"and querier is {found[2]}"
    )

    search = frontend["search"]
    memory = parse_quantity(tempo["resources"]["limits"]["memory"])
    searched = (
        frontend["max_outstanding_per_tenant"]
        * search["max_result_limit"]
        * search["max_bytes_per_trace"]
    )

    assert searched <= memory / 2, (
        f"{TEMPO_VALUES}: queryFrontend.max_outstanding_per_tenant "
        f"{frontend['max_outstanding_per_tenant']} times queryFrontend.search.max_result_limit "
        f"{search['max_result_limit']} times queryFrontend.search.max_bytes_per_trace "
        f"{search['max_bytes_per_trace']} is {searched} bytes, more than half of "
        f"resources.limits.memory {memory}"
    )

    assert querier["max_concurrent_queries"] <= frontend["max_outstanding_per_tenant"], (
        f"{TEMPO_VALUES}: querier.max_concurrent_queries "
        f"{querier['max_concurrent_queries']} is more than queryFrontend."
        f"max_outstanding_per_tenant {frontend['max_outstanding_per_tenant']}"
    )
