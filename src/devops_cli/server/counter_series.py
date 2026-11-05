"""The label sets of the Service counters that exist at zero from the start (#3495).

A labelled counter has no series until its first count, and `increase()` loses that first count.
So the Service creates each bounded label set at zero when it starts, before the first scrape of
its `/metrics`. A label set that a new pod counts later still starts at zero in that pod.
"""

from __future__ import annotations

from collections.abc import Iterable

from devops_cli.config.constants import CONST_SERVICE_METRIC_IMPLEMENT_FAILURES
from devops_cli.roadmap.failure import FailureClass
from devops_cli.telemetry.metrics import GLOBAL_METRICS


def prime_service_counters(repos: Iterable[str]) -> None:
    """Create the bounded label sets of the Service counters at zero for the repositories
    `repos`: each failure class for each repository on the failure counter."""
    repo_names = list(repos)
    GLOBAL_METRICS.prime_counter(
        CONST_SERVICE_METRIC_IMPLEMENT_FAILURES,
        ({"class": klass.value, "repo": repo} for klass in FailureClass for repo in repo_names),
    )
