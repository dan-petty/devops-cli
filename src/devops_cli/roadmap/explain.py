"""`devops roadmap explain`: why the refine job, the stage job and the implement job take an item
or leave it out (#2911, #3483).

The command holds no rule of its own. The issue is judged by the selection of each job, through
the same functions the jobs call (`refine_left_out`, `read_stage_selection` and `plan_implement`).
The walks of the stage job and the implement job take the issue as `probe`, so that they judge it
also after the limit. Refine has no limit to probe: its reason is the wait of the item. The reason of the first rule that fails
is the text that the "Left out" list of the plan prints. The order is the order of the code: the
issue is an open item, then the filter, then the rules of the job, then the limit of a run.

The command calls no model and writes nothing to git or to GitHub. It reads what the plans read.
The report gives the totals of the last implement run, from the trace in the job record of the
issue that the command reads (#3217).
The stage job finds a task group over the budget only after the model plans the item, so the
command reports that rule from the record of an earlier run (`stage.needs_split`), as the job
does. The failures ledger of the Service counts failed rounds for each job, not for each item, and
the Service keeps it on its own volume: the command does not read it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NamedTuple

from devops_cli.config.defaults import DEFAULT_ROADMAP_IMPLEMENT_LIMIT
from devops_cli.config.settings import load_settings
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.git.worktree_add import read_remote_heads
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement.implement import (
    ImplementPlan,
    effort_filter,
    implement_efforts,
    plan_implement,
)
from devops_cli.roadmap.implement.implement_trace import (
    ImplementTrace,
    TraceDecodeError,
    TraceEvent,
    TraceEventKind,
    decode,
)
from devops_cli.roadmap.planned import PlannedChanges, read_planned_changes
from devops_cli.roadmap.refine.refine import refine_left_out
from devops_cli.roadmap.stage.stage import LeftOut, StageFilter, read_stage_selection
from devops_cli.roadmap.stores.store import GitHubState, ImplementRecordKey, Item, RoadmapStore

_GIT_OPERATION: Final[str] = "roadmap.explain"


class JobVerdict(NamedTuple):
    """Whether a job takes the item, and, when it does not, the reason of the first rule that
    fails."""

    takes: bool
    reason: str = ""


@dataclass(frozen=True)
class TraceTotals:
    """The totals of the last implement run, from its trace (#3217): the tokens in and out, the
    seconds of the model calls, the repair rounds, the count of each attempt outcome, and the
    events that the trace bound dropped. The totals leave the dropped events out."""

    tokens_total: int
    seconds_total: float
    repair_rounds: int
    outcomes: dict[str, int]
    dropped: int


def trace_totals(trace: ImplementTrace) -> TraceTotals:
    """The totals of `trace` (#3217): the tokens and the seconds of its model events, the repair
    rounds and the outcomes of its attempt events, and the events that the bound dropped."""
    models = [event.fields for event in trace.events if event.kind is TraceEventKind.MODEL]
    attempts = [event.fields for event in trace.events if event.kind is TraceEventKind.ATTEMPT]
    return TraceTotals(
        tokens_total=sum(
            int(fields.get("tokens_in", 0)) + int(fields.get("tokens_out", 0)) for fields in models
        ),
        seconds_total=round(sum(float(fields.get("seconds", 0)) for fields in models), 1),
        repair_rounds=sum(1 for fields in attempts if fields.get("next") == "repair"),
        outcomes=dict(Counter(str(fields.get("outcome", "")) for fields in attempts)),
        dropped=trace.dropped,
    )


@dataclass(frozen=True)
class Explanation:
    """The verdict of each job for one issue. `title` is empty for an issue that is no item.
    `totals` is None for an issue whose record holds no trace of an implement run."""

    repo: str
    number: int
    title: str
    refine: JobVerdict
    stage: JobVerdict
    implement: JobVerdict
    implement_effort: str = ""
    totals: TraceTotals | None = None

    def as_dict(self) -> dict[str, object]:
        """The explanation as the JSON object of `explain --json` (#3217): the number, the totals
        of the last implement run and the events that the bound dropped. Each total is None for an
        issue whose record holds no trace of a run."""
        totals = self.totals
        return {
            "number": self.number,
            "tokens_total": totals.tokens_total if totals else None,
            "seconds_total": totals.seconds_total if totals else None,
            "repair_rounds": totals.repair_rounds if totals else None,
            "outcomes": totals.outcomes if totals else None,
            "dropped": totals.dropped if totals else None,
        }


def _verdict(
    number: int, left_out: Iterable[LeftOut], beyond: Collection[int], limit: int
) -> JobVerdict:
    """The verdict that a walk gives for the probe: its reason when a rule left it out, the limit
    when it passes every rule behind a full run, else yes."""
    for left in left_out:
        if left.number == number:
            return JobVerdict(False, left.reason)
    if number in beyond:
        return JobVerdict(False, MESSAGES.roadmap.item_left_limit.format(limit=limit))
    return JobVerdict(True)


class _Reads(NamedTuple):
    """What both jobs read from git: the heads of `origin` and the plans on the default branch."""

    heads: str
    planned: PlannedChanges


def _refine_verdict(store: RoadmapStore, item: Item) -> JobVerdict:
    """Whether a round of the refine job takes the item, and, when it does not, why: the rule of
    `refine_left_out`, which the round uses (#3483)."""
    why = refine_left_out(store, item)
    return JobVerdict(True) if why is None else JobVerdict(False, why)


def _stage_verdict(
    store: RoadmapStore,
    *,
    repo: str,
    source: Path,
    item: Item,
    filters: StageFilter,
    limit: int,
    planned_limit: int,
    reads: _Reads,
) -> JobVerdict:
    if (why := filters.mismatch(item)) is not None:
        return JobVerdict(False, why)
    selection = read_stage_selection(
        store,
        repo=repo,
        source=source,
        filters=filters,
        limit=limit,
        planned_limit=planned_limit,
        probe=item.number,
        heads=reads.heads,
        planned=reads.planned,
    ).selection
    return _verdict(item.number, selection.left_out, selection.beyond, limit)


def _implement_effort_line(
    plan: ImplementPlan | None, item: Item, efforts: Sequence[str], filters: StageFilter
) -> str:
    """The line that names the effort set of the implement job and whether the fallback pass
    applies to the item (#3385). The fallback applies when the pass in use takes the effort of the
    item and that pass is a later value of the set. When no pass takes an item, no pass is in use,
    so the fallback does not apply."""
    texts = MESSAGES.roadmap
    if "effort" in filters.families:
        return texts.explain_effort_explicit
    own = next((value for value in efforts if f"effort/{value}" in item.labels), "")
    applies = plan is not None and bool(own) and own != efforts[0] and plan.effort == own
    return texts.explain_effort_line.format(
        efforts=",".join(efforts),
        state=texts.explain_effort_applies if applies else texts.explain_effort_not_applies,
    )


def _implement_verdict(
    store: RoadmapStore,
    *,
    repo: str,
    source: Path,
    item: Item,
    filters: StageFilter,
    limit: int,
    reads: _Reads,
) -> tuple[JobVerdict, str]:
    """The verdict of the implement job for `item`, and the line that names its effort set (#3385).
    The filter of the set names the efforts that the job takes, so an item of another effort gets
    the reason of the filter."""
    efforts = implement_efforts()
    if (why := effort_filter(filters, efforts).mismatch(item)) is not None:
        return JobVerdict(False, why), _implement_effort_line(None, item, efforts, filters)
    plan = plan_implement(
        store,
        repo=repo,
        source=source,
        filters=filters,
        limit=limit,
        probe=item.number,
        remote_heads=reads.heads,
        planned=reads.planned,
    )
    verdict = _verdict(item.number, plan.left_out, plan.beyond, limit)
    return verdict, _implement_effort_line(plan, item, efforts, filters)


def _trace_of(item: Item, number: int) -> ImplementTrace | None:
    """The trace in the job record of `item`, or None when the record holds none. Raises
    `RoadmapImplementError` for a value of `implement.trace` that is no trace."""
    text = item.job_record.get(ImplementRecordKey.TRACE)
    if not text:
        return None
    try:
        return decode(text)
    except TraceDecodeError as error:
        raise RoadmapImplementError(
            MESSAGES.roadmap.explain_trace_unreadable.format(number=number, error=error)
        ) from error


def _totals(item: Item | None, number: int) -> TraceTotals | None:
    """The totals of the last implement run in the job record of `item`, or None when the issue
    is no item or its record holds no trace. Raises `RoadmapImplementError` for a value of
    `implement.trace` that is no trace."""
    if item is None:
        return None
    trace = _trace_of(item, number)
    return None if trace is None else trace_totals(trace)


def explain_item(
    store: RoadmapStore,
    *,
    repo: str,
    source: Path | str,
    number: int,
    stage_filters: StageFilter,
    implement_filters: StageFilter,
    stage_limit: int | None = None,
    implement_limit: int | None = None,
    planned_limit: int | None = None,
) -> Explanation:
    """Why each job takes issue `number` or leaves it out, with no model call and no write.
    `source` is the clone of the repository. A limit left as None is the limit that the Service
    uses for the job: `roadmap.stage.limit` for stage, one item for implement. A `planned_limit`
    left as None is `roadmap.stage.planned_limit`. The totals come from the trace of the last
    implement run in the job record of the issue that the call reads."""
    item = store.item(number)
    totals = _totals(item, number)
    if item is None or item.state is not GitHubState.OPEN:
        texts = MESSAGES.roadmap
        refusal = JobVerdict(
            False, texts.item_left_not_item if item is None else texts.item_left_closed
        )
        return Explanation(
            repo, number, item.title if item else "", refusal, refusal, refusal, totals=totals
        )
    checkout = Path(source)
    stage_settings = load_settings().roadmap.stage
    reads = _Reads(
        read_remote_heads(checkout), read_planned_changes(checkout, operation=_GIT_OPERATION)
    )
    implement, implement_effort = _implement_verdict(
        store,
        repo=repo,
        source=checkout,
        item=item,
        filters=implement_filters,
        limit=implement_limit or DEFAULT_ROADMAP_IMPLEMENT_LIMIT,
        reads=reads,
    )
    return Explanation(
        repo,
        number,
        item.title,
        _refine_verdict(store, item),
        _stage_verdict(
            store,
            repo=repo,
            source=checkout,
            item=item,
            filters=stage_filters,
            limit=stage_limit or stage_settings.limit,
            planned_limit=planned_limit or stage_settings.planned_limit,
            reads=reads,
        ),
        implement,
        implement_effort=implement_effort,
        totals=totals,
    )


def _totals_lines(explained: Explanation) -> list[str]:
    """The lines of the totals of the last implement run (#3217): the totals and the events that
    the bound dropped, or the line that says that the item has no recorded run."""
    texts = MESSAGES.roadmap
    totals = explained.totals
    if totals is None:
        return [texts.explain_totals_none.format(number=explained.number)]
    lines = [
        texts.explain_totals_line.format(
            tokens_total=totals.tokens_total,
            seconds_total=totals.seconds_total,
            repair_rounds=totals.repair_rounds,
            failed=totals.outcomes.get("failed", 0),
            passed=totals.outcomes.get("passed", 0),
        )
    ]
    if totals.dropped:
        lines.append(texts.explain_totals_dropped.format(count=totals.dropped))
    return lines


def render_explanation(explained: Explanation) -> str:
    """The explanation as the report of the command: the issue, then one line for each job, the
    line of the effort set, and the totals of the last implement run."""
    texts = MESSAGES.roadmap
    title = (
        texts.explain_title.format(
            repo=explained.repo, number=explained.number, title=explained.title
        )
        if explained.title
        else texts.explain_title_untitled.format(repo=explained.repo, number=explained.number)
    )
    lines = [title, ""]
    for job, verdict in (
        (texts.explain_job_refine, explained.refine),
        (texts.explain_job_stage, explained.stage),
        (texts.explain_job_implement, explained.implement),
    ):
        line = texts.explain_line_yes if verdict.takes else texts.explain_line_no
        lines.append(line.format(job=job, reason=verdict.reason))
    if explained.implement_effort:
        lines.append(explained.implement_effort)
    lines.extend(_totals_lines(explained))
    return "\n".join(lines)


def read_trace(store: RoadmapStore, number: int) -> ImplementTrace | None:
    """The trace of the last run of the implement job for issue `number` (#3032), or None when the
    record holds none. It reads the one issue and nothing else. Raises `RoadmapImplementError`
    for an issue that is no item, and for a value of `implement.trace` that is no trace."""
    item = store.item(number)
    if item is None:
        raise RoadmapImplementError(MESSAGES.roadmap.item_left_not_item)
    return _trace_of(item, number)


def _event_line(event: TraceEvent) -> str:
    """One line for an event: its step, its kind and its fields."""
    texts = MESSAGES.roadmap
    fields = event.fields
    step = event.step or "-"
    match event.kind:
        case TraceEventKind.MODEL:
            return texts.explain_trace_model.format(
                step=step,
                model=fields.get("model", ""),
                tokens_in=fields.get("tokens_in", 0),
                tokens_out=fields.get("tokens_out", 0),
                seconds=fields.get("seconds", 0),
            )
        case TraceEventKind.TOOL:
            program = fields.get("program")
            reason = fields.get("reason")
            status = fields.get("status")
            return texts.explain_trace_tool.format(
                step=step,
                tool=fields.get("tool", ""),
                program=texts.explain_trace_tool_program.format(program=program) if program else "",
                outcome=fields.get("outcome", ""),
                status=(
                    texts.explain_trace_tool_status.format(status=status)
                    if status is not None
                    else ""
                ),
                reason=texts.explain_trace_tool_reason.format(reason=reason) if reason else "",
            )
        case TraceEventKind.CHECK:
            result = (
                texts.explain_trace_check_timeout
                if fields.get("timeout")
                else texts.explain_trace_check_status.format(status=fields.get("status", ""))
            )
            return texts.explain_trace_check.format(
                step=step, command=fields.get("command", ""), result=result
            )
        case TraceEventKind.RETRY:
            return texts.explain_trace_retry.format(step=step, reason=fields.get("reason", ""))
        case TraceEventKind.ATTEMPT:
            tier = fields.get("tier")
            failure_class = fields.get("class")
            return texts.explain_trace_attempt.format(
                step=step,
                number=fields.get("number", ""),
                tier=texts.explain_trace_attempt_tier.format(tier=tier) if tier else "",
                outcome=fields.get("outcome", ""),
                failure=texts.explain_trace_attempt_failure.format(
                    failure_class=failure_class, evidence=fields.get("evidence", "")
                )
                if failure_class
                else "",
                next=fields.get("next", ""),
            )


def render_trace(trace: ImplementTrace | None, *, number: int) -> str:
    """The trace as the report of `explain --trace`: one line for each event, oldest first, then
    the count that the bound dropped. A line says that the issue has no trace when `trace` is
    None."""
    texts = MESSAGES.roadmap
    if trace is None:
        return texts.explain_trace_none.format(number=number)
    lines = [_event_line(event) for event in trace.events]
    if trace.dropped:
        lines.append(texts.explain_trace_dropped.format(count=trace.dropped))
    return "\n".join(lines)


__all__ = [
    "Explanation",
    "JobVerdict",
    "TraceTotals",
    "explain_item",
    "read_trace",
    "render_explanation",
    "render_trace",
    "trace_totals",
]
