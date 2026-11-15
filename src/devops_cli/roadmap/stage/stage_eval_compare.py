"""The comparison of the stage toolsets on the golden set (#3239).

`run_toolset` plans each case with the tools of one toolset and measures the run: the defects that
the gates caught in the first reply, the defects that the verification pass caught, the tool calls,
the model requests, the input and output tokens, the elapsed time and the cost at the hosted price
of the model. A run without the verification pass holds no count of its defects, so the column says
`not run` rather than a clean zero. `render_compare` prints one row for each toolset with the eight
measured columns and one delta line for each toolset after the first, against the first.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from devops_cli.config.defaults import StageToolset
from devops_cli.core import clock
from devops_cli.openspec.tool import OpenSpecTool
from devops_cli.roadmap.agent_run import RunTrace
from devops_cli.roadmap.stage.stage import StageClient, openspec_tool
from devops_cli.roadmap.stage.stage_eval_cases import StageCase
from devops_cli.roadmap.stage.stage_eval_run import CaseRun, run_case
from devops_cli.roadmap.stage.stage_eval_usage import RunUsage

_NOT_RUN: Final[str] = "not run"
_UNPRICED: Final[str] = "unpriced"
_COMPARE_HEADER: Final[str] = (
    "Toolset          Gate defects  Verification defects  Tool calls  Requests  Input tokens  "
    "Output tokens  Elapsed time      Cost"
)
_COMPARE_ROW: Final[str] = (
    "{toolset:<16} {gate:>12}  {verify:>20}  {tools:>10}  {requests:>8}  {input:>12}  "
    "{output:>13}  {seconds:>12}  {cost:>9}"
)


@dataclass(frozen=True)
class Measure:
    """One run of one case: the defects that the gates caught in its first reply, the defects that
    the verification pass caught (None when the pass did not run), the tool calls, the requests,
    the input and output tokens, the elapsed seconds and the cost in USD (None when the model has
    no price)."""

    case: str
    gate_defects: int
    verification_defects: int | None
    tool_calls: int
    requests: int
    input_tokens: int
    output_tokens: int
    seconds: float
    cost: float | None


@dataclass(frozen=True)
class Spread:
    """The minimum and the maximum of each measured value of the runs of one case. A value that no
    run measured, such as the verification pass, is `(None, None)`."""

    gate_defects: tuple[int, int]
    verification_defects: tuple[int | None, int | None]
    tool_calls: tuple[int, int]
    requests: tuple[int, int]
    input_tokens: tuple[int, int]
    output_tokens: tuple[int, int]
    seconds: tuple[float, float]
    cost: tuple[float | None, float | None]


@dataclass(frozen=True)
class ComparisonRow:
    """The measured values of one toolset, the measures that it sums, and the toolset that the row
    names. A delta row names both toolsets, such as `extended - base`, and sums no measure."""

    toolset: str
    gate_defects: int
    verification_defects: int | None
    tool_calls: int
    requests: int
    input_tokens: int
    output_tokens: int
    seconds: float
    cost: float | None
    measures: tuple[Measure, ...] = ()


def _sum_optional(values: Iterable[int | None]) -> int | None:
    """The sum of the values that a run measured, or None when no run measured one."""
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _sum_cost(values: Iterable[float | None]) -> float | None:
    """The sum of the prices that a run measured, or None when no run measured one."""
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _difference[ValueT: (int, float)](value: ValueT | None, base: ValueT | None) -> ValueT | None:
    """`value` less `base`, or None when either is unknown."""
    if value is None or base is None:
        return None
    return value - base


def _range[ValueT: (int, float)](values: Iterable[ValueT]) -> tuple[ValueT, ValueT]:
    """The minimum and the maximum of `values`, which holds at least one value."""
    known = list(values)
    return min(known), max(known)


def _range_optional[ValueT: (int, float)](
    values: Iterable[ValueT | None],
) -> tuple[ValueT | None, ValueT | None]:
    """The minimum and the maximum of the values that a run measured, or `(None, None)`."""
    known = [value for value in values if value is not None]
    return _range(known) if known else (None, None)


def row_of(toolset: str, measures: Sequence[Measure]) -> ComparisonRow:
    """The row of `toolset`: the sum of the measures of its cases."""
    return ComparisonRow(
        toolset,
        sum(measure.gate_defects for measure in measures),
        _sum_optional(measure.verification_defects for measure in measures),
        sum(measure.tool_calls for measure in measures),
        sum(measure.requests for measure in measures),
        sum(measure.input_tokens for measure in measures),
        sum(measure.output_tokens for measure in measures),
        sum(measure.seconds for measure in measures),
        _sum_cost(measure.cost for measure in measures),
        tuple(measures),
    )


def delta(row: ComparisonRow, base: ComparisonRow) -> ComparisonRow:
    """The measured values of `row` less those of `base`, as the line `<row> - <base>`. A value
    that either row did not measure stays None."""
    return ComparisonRow(
        toolset=f"{row.toolset} - {base.toolset}",
        gate_defects=row.gate_defects - base.gate_defects,
        verification_defects=_difference(row.verification_defects, base.verification_defects),
        tool_calls=row.tool_calls - base.tool_calls,
        requests=row.requests - base.requests,
        input_tokens=row.input_tokens - base.input_tokens,
        output_tokens=row.output_tokens - base.output_tokens,
        seconds=row.seconds - base.seconds,
        cost=_difference(row.cost, base.cost),
    )


def spread(measures: Sequence[Measure]) -> Spread:
    """The minimum and the maximum of each measured value of `measures`."""
    return Spread(
        _range(measure.gate_defects for measure in measures),
        _range_optional(measure.verification_defects for measure in measures),
        _range(measure.tool_calls for measure in measures),
        _range(measure.requests for measure in measures),
        _range(measure.input_tokens for measure in measures),
        _range(measure.output_tokens for measure in measures),
        _range(measure.seconds for measure in measures),
        _range_optional(measure.cost for measure in measures),
    )


def _gate_defects(run: CaseRun) -> int:
    """The problems that the gates found in the first reply of the run."""
    if run.first is None:
        return 0
    return sum(len(problems) for problems in run.first.values())


def _measure(
    case: StageCase,
    toolset: StageToolset,
    client: StageClient,
    repository: Path,
    *,
    toolbox: Any,
    model: str,
    openspec: OpenSpecTool | None,
) -> Measure:
    """Plan `case` with the tools of `toolset`, and measure the run from its traces. `openspec`
    reads the specs for the tool `read_spec` and for the gates of the first reply."""
    traces: list[RunTrace] = []
    started = clock.monotonic()
    run = run_case(
        case,
        client,
        repository,
        toolbox=toolbox,
        toolset=toolset,
        openspec=openspec,
        traces=traces,
    )
    seconds = clock.monotonic() - started
    trace = RunTrace.combined(traces)
    usage = RunUsage(trace.input_tokens, trace.output_tokens)
    return Measure(
        case=case.name,
        gate_defects=_gate_defects(run),
        verification_defects=None,
        tool_calls=len(trace.tool_calls),
        requests=trace.requests,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
        seconds=seconds,
        cost=usage.spend_usd(model),
    )


def run_toolset(
    toolset: StageToolset,
    cases: Sequence[StageCase],
    client: StageClient,
    repository: Path,
    *,
    toolbox: Any,
    model: str,
) -> ComparisonRow:
    """Plan each case with the tools of `toolset` and measure its run. `toolbox` is the model of
    the plan run, `client` answers every other call, and `model` is the name that prices the
    tokens of the run."""
    with openspec_tool() as tool:
        measures = [
            _measure(
                case,
                toolset,
                client,
                repository,
                toolbox=toolbox,
                model=model,
                openspec=tool,
            )
            for case in cases
        ]
    return row_of(toolset, measures)


def _count(value: int | None, empty: str) -> str:
    return str(value) if value is not None else empty


def _money(value: float | None) -> str:
    return f"{value:.4f}" if value is not None else _UNPRICED


def _row_line(row: ComparisonRow) -> str:
    return _COMPARE_ROW.format(
        toolset=row.toolset,
        gate=row.gate_defects,
        verify=_count(row.verification_defects, _NOT_RUN),
        tools=row.tool_calls,
        requests=row.requests,
        input=row.input_tokens,
        output=row.output_tokens,
        seconds=f"{row.seconds:.2f}",
        cost=_money(row.cost),
    )


def render_compare(rows: Sequence[ComparisonRow]) -> str:
    """The comparison as text: one row for each toolset with the eight measured columns, and one
    delta line for each toolset after the first, against the first."""
    lines = [_COMPARE_HEADER, *(_row_line(row) for row in rows)]
    if rows:
        lines += [_row_line(delta(row, rows[0])) for row in rows[1:]]
    return "\n".join(lines) + "\n"
