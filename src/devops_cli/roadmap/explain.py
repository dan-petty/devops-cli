"""`devops roadmap explain`: why the stage job and the implement job take an item or leave it out
(#2911).

The command holds no rule of its own. The issue is judged by the selection of each job, through
the same functions the jobs call (`read_stage_selection` and `plan_implement`), with the issue as
`probe` so that the walk judges it also after the limit. The reason of the first rule that fails
is the text that the "Left out" list of the plan prints. The order is the order of the code: the
issue is an open item, then the filter, then the rules of the job, then the limit of a run.

The command calls no model and writes nothing to git or to GitHub. It reads what the plans read.
The stage job finds a task group over the budget only after the model plans the item, so the
command reports that rule from the record of an earlier run (`stage.needs_split`), as the job
does. The failures ledger of the Service counts failed rounds for each job, not for each item, and
the Service keeps it on its own volume: the command does not read it.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NamedTuple

from devops_cli.config.defaults import DEFAULT_ROADMAP_IMPLEMENT_LIMIT
from devops_cli.config.settings import load_settings
from devops_cli.git.worktree_add import read_remote_heads
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement import plan_implement
from devops_cli.roadmap.planned import PlannedChanges, read_planned_changes
from devops_cli.roadmap.stage import LeftOut, StageFilter, read_stage_selection
from devops_cli.roadmap.store import GitHubState, Item, RoadmapStore

_GIT_OPERATION: Final[str] = "roadmap.explain"


class JobVerdict(NamedTuple):
    """Whether a job takes the item, and, when it does not, the reason of the first rule that
    fails."""

    takes: bool
    reason: str = ""


@dataclass(frozen=True)
class Explanation:
    """The verdict of each job for one issue. `title` is empty for an issue that is no item."""

    repo: str
    number: int
    title: str
    stage: JobVerdict
    implement: JobVerdict


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


def _stage_verdict(
    store: RoadmapStore,
    *,
    repo: str,
    source: Path,
    item: Item,
    filters: StageFilter,
    limit: int,
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
        probe=item.number,
        heads=reads.heads,
        planned=reads.planned,
    ).selection
    return _verdict(item.number, selection.left_out, selection.beyond, limit)


def _implement_verdict(
    store: RoadmapStore,
    *,
    repo: str,
    source: Path,
    item: Item,
    filters: StageFilter,
    limit: int,
    reads: _Reads,
) -> JobVerdict:
    if (why := filters.mismatch(item)) is not None:
        return JobVerdict(False, why)
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
    return _verdict(item.number, plan.left_out, plan.beyond, limit)


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
) -> Explanation:
    """Why each job takes issue `number` or leaves it out, with no model call and no write.
    `source` is the clone of the repository. A limit left as None is the limit that the Service
    uses for the job: `roadmap.stage.limit` for stage, one item for implement."""
    item = store.item(number)
    if item is None or item.state is not GitHubState.OPEN:
        texts = MESSAGES.roadmap
        refusal = JobVerdict(
            False, texts.item_left_not_item if item is None else texts.item_left_closed
        )
        return Explanation(repo, number, item.title if item else "", refusal, refusal)
    checkout = Path(source)
    reads = _Reads(
        read_remote_heads(checkout), read_planned_changes(checkout, operation=_GIT_OPERATION)
    )
    return Explanation(
        repo,
        number,
        item.title,
        _stage_verdict(
            store,
            repo=repo,
            source=checkout,
            item=item,
            filters=stage_filters,
            limit=stage_limit or load_settings().roadmap.stage.limit,
            reads=reads,
        ),
        _implement_verdict(
            store,
            repo=repo,
            source=checkout,
            item=item,
            filters=implement_filters,
            limit=implement_limit or DEFAULT_ROADMAP_IMPLEMENT_LIMIT,
            reads=reads,
        ),
    )


def render_explanation(explained: Explanation) -> str:
    """The explanation as the report of the command: the issue, then one line for each job."""
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
        (texts.explain_job_stage, explained.stage),
        (texts.explain_job_implement, explained.implement),
    ):
        line = texts.explain_line_yes if verdict.takes else texts.explain_line_no
        lines.append(line.format(job=job, reason=verdict.reason))
    return "\n".join(lines)


__all__ = ["Explanation", "JobVerdict", "explain_item", "render_explanation"]
