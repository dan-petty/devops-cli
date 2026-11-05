"""The metrics of the tool calls of a plan run (#3240).

A plan run of the stage planner calls read-only tools. `start_run` adds 0 to
`devops_cli_roadmap_tool_calls_total` for each tool of the toolset before the run calls any, so a
tool that no run calls keeps a series, and an alert can find it. `end_run` sends what the
`RunTrace` of the run holds: one count and one answer size for each call, the calls of the run, and
the limit that ended its tools.

Each label has a closed set of values: the tools of the registry, the job row, the toolset, the
three outcomes and the three limits. The label for the job row is `row`: the collector sets the
label `job` from the resource and loses a data point attribute of that name.
"""

from __future__ import annotations

from collections.abc import Iterable

from devops_cli.roadmap.agent_run import RunTrace, ToolOutcome
from devops_cli.telemetry.instruments import (
    ROADMAP_TOOL_ANSWER_CHARS,
    ROADMAP_TOOL_CALLS_PER_RUN,
    ROADMAP_TOOL_CALLS_TOTAL,
    ROADMAP_TOOL_LIMIT_HITS_TOTAL,
    emit,
)


def start_run(tools: Iterable[str], *, row: str, toolset: str) -> None:
    """Add 0 to the counter of the calls for each of `tools`, with the outcome `ok`."""
    for tool in tools:
        labels = {"tool": tool, "row": row, "toolset": toolset, "outcome": ToolOutcome.OK.value}
        emit(ROADMAP_TOOL_CALLS_TOTAL, 0, labels)


def end_run(trace: RunTrace, *, row: str, toolset: str, finished: bool) -> None:
    """Send the calls of one plan run. A call that got no answer adds no answer size. A run that
    did not finish, because a model call failed, made no plan run: it adds its calls, and no count
    of calls for the run, so a model that is down does not make each tool look unused."""
    for record in trace.tool_calls:
        labels = {"tool": record.name, "row": row, "toolset": toolset}
        emit(ROADMAP_TOOL_CALLS_TOTAL, 1, {**labels, "outcome": record.outcome.value})
        if record.outcome is not ToolOutcome.ERROR:
            emit(ROADMAP_TOOL_ANSWER_CHARS, record.chars, labels)
    if not finished:
        return
    run = {"row": row, "toolset": toolset}
    emit(ROADMAP_TOOL_CALLS_PER_RUN, len(trace.tool_calls), run)
    if trace.limit is not None:
        emit(ROADMAP_TOOL_LIMIT_HITS_TOTAL, 1, {**run, "limit": trace.limit.value})


__all__ = ["end_run", "start_run"]
