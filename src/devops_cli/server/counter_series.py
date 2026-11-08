"""The label sets of the Service counters that exist at zero from the start (#3495).

A labelled counter has no series until its first count, and `increase()` loses that first count.
So the Service creates each bounded label set at zero when it starts, before the first scrape of
its `/metrics`. A label set that a new pod counts later still starts at zero in that pod.
"""

from __future__ import annotations

from collections.abc import Iterable

from devops_cli.config.constants import (
    CONST_BRANCH_TYPES,
    CONST_SERVICE_CHAT_COMMAND_ROADMAP,
    CONST_SERVICE_CHAT_RESULT_ERROR,
    CONST_SERVICE_CHAT_RESULT_STATUS,
    CONST_SERVICE_CHAT_RESULT_UNKNOWN_REPO,
    CONST_SERVICE_CHAT_RESULT_USAGE,
    CONST_SERVICE_JOB_RESULT_ERROR,
    CONST_SERVICE_JOB_RESULT_STOPPED,
    CONST_SERVICE_JOB_RESULT_SUCCESS,
    CONST_SERVICE_LANE_MODEL,
    CONST_SERVICE_LANE_STATUS,
    CONST_SERVICE_LANE_TRIAGE,
    CONST_SERVICE_METRIC_BUDGET_HOLDS,
    CONST_SERVICE_METRIC_CHAT_COMMANDS,
    CONST_SERVICE_METRIC_IMPLEMENT_FAILURES,
    CONST_SERVICE_METRIC_IMPLEMENT_JOBS,
    CONST_SERVICE_METRIC_IMPLEMENT_REPAIR_ROUNDS,
    CONST_SERVICE_METRIC_IMPLEMENT_TOKENS,
    CONST_SERVICE_METRIC_JOB_SECONDS,
    CONST_SERVICE_METRIC_JOBS,
    CONST_SERVICE_METRIC_TRIGGERS,
    CONST_SERVICE_SOURCE_POLL,
    CONST_SERVICE_SOURCE_WEBHOOK,
)
from devops_cli.roadmap.failure import FailureClass
from devops_cli.telemetry.metrics import GLOBAL_METRICS

_SERVICE_JOB_RESULTS = (
    CONST_SERVICE_JOB_RESULT_SUCCESS,
    CONST_SERVICE_JOB_RESULT_ERROR,
    CONST_SERVICE_JOB_RESULT_STOPPED,
)
"""The value of the label `result` of a job that ended, as the roadmap run counts it."""

_SERVICE_TRIGGER_SOURCES = (CONST_SERVICE_SOURCE_WEBHOOK, CONST_SERVICE_SOURCE_POLL)
"""The values of the label `source` of a trigger, as the Service enqueues it."""

_SERVICE_CHAT_RESULTS = (
    CONST_SERVICE_CHAT_RESULT_USAGE,
    CONST_SERVICE_CHAT_RESULT_STATUS,
    CONST_SERVICE_CHAT_RESULT_UNKNOWN_REPO,
    CONST_SERVICE_CHAT_RESULT_ERROR,
)
"""The values of the label `result` of a `/roadmap` chat command, as the webhook router counts
them."""


def prime_service_counters(repos: Iterable[str]) -> None:
    """Create the bounded label sets of the Service counters at zero for the repositories
    `repos`: each failure class for each repository on the failure counter, each repository,
    lane, row and result on the job counter, each repository and lane on the job seconds, each
    repository and source on the trigger counter, each result of the chat command, and the one
    series of the budget holds, which has no label."""
    # The roadmap run imports the Service, so the lane tables are read when the counters are
    # primed, not when this module is imported.
    from devops_cli.roadmap.run import MODEL_LANE_ROWS, STATUS_LANE_ROWS, TRIAGE_LANE_ROWS

    lane_rows = (
        (CONST_SERVICE_LANE_STATUS, STATUS_LANE_ROWS),
        (CONST_SERVICE_LANE_TRIAGE, TRIAGE_LANE_ROWS),
        (CONST_SERVICE_LANE_MODEL, MODEL_LANE_ROWS),
    )
    repo_names = list(repos)
    GLOBAL_METRICS.prime_counter(
        CONST_SERVICE_METRIC_IMPLEMENT_FAILURES,
        ({"class": klass.value, "repo": repo} for klass in FailureClass for repo in repo_names),
    )
    GLOBAL_METRICS.prime_counter(
        CONST_SERVICE_METRIC_IMPLEMENT_JOBS,
        (
            {"repo": repo, "item_class": item_class, "result": result}
            for repo in repo_names
            for item_class in CONST_BRANCH_TYPES
            for result in ("succeeded", "failed", "gone")
        ),
    )
    GLOBAL_METRICS.prime_counter(
        CONST_SERVICE_METRIC_IMPLEMENT_REPAIR_ROUNDS,
        (
            {"repo": repo, "item_class": item_class}
            for repo in repo_names
            for item_class in CONST_BRANCH_TYPES
        ),
    )
    GLOBAL_METRICS.prime_counter(
        CONST_SERVICE_METRIC_IMPLEMENT_TOKENS,
        (
            {"repo": repo, "item_class": item_class}
            for repo in repo_names
            for item_class in CONST_BRANCH_TYPES
        ),
    )
    GLOBAL_METRICS.prime_counter(
        CONST_SERVICE_METRIC_JOBS,
        (
            {"repo": repo, "lane": lane, "row": row.name, "result": result}
            for lane, rows in lane_rows
            for row in rows
            for repo in repo_names
            for result in _SERVICE_JOB_RESULTS
        ),
    )
    GLOBAL_METRICS.prime_counter(
        CONST_SERVICE_METRIC_JOB_SECONDS,
        ({"repo": repo, "lane": lane} for lane, _rows in lane_rows for repo in repo_names),
    )
    GLOBAL_METRICS.prime_counter(
        CONST_SERVICE_METRIC_TRIGGERS,
        (
            {"repo": repo, "source": source}
            for repo in repo_names
            for source in _SERVICE_TRIGGER_SOURCES
        ),
    )
    GLOBAL_METRICS.prime_counter(
        CONST_SERVICE_METRIC_CHAT_COMMANDS,
        (
            {"command": CONST_SERVICE_CHAT_COMMAND_ROADMAP, "result": result}
            for result in _SERVICE_CHAT_RESULTS
        ),
    )
    GLOBAL_METRICS.prime_counter(CONST_SERVICE_METRIC_BUDGET_HOLDS, [{}])
