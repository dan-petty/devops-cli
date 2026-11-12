"""`devops roadmap retitle` (#3486, #4508): shorten the long title of an open item, and correct a
title type that `CONST_BRANCH_TYPES` does not list.

The stage job and the implement job leave out an item whose title summary is over
`SUMMARY_MAX_CHARS` characters (`long_title_reason`), and the check `Semantic PR title` refuses
the delivery title at the push. No other job shortened such a title, so a person had to edit it.
This job does it, and `devops roadmap intake` refuses a new candidate with a long summary.

The stage job also leaves out an item whose title type is not listed, such as `security(ssh): x`,
because its branch has no type. Such an item waited with no comment (#4508). This job writes
the correction of `corrected_title` (`fix(security)`) with no model call, and shortens a long
summary of the corrected title in the same round. It comments once on an unlisted type that has
no correction, and a person corrects it. Refine does not set such an item Ready, and intake
keeps a new candidate with it, because this job corrects it.

**Selection.** An open Item whose title has an unlisted type, or a Conventional Commit type and a
summary over the limit, the lowest number first, at most `--limit` a run. `--item` names the one
item to examine.

**The skip mark (#4038).** When the job leaves an item (a person's edit, no plan title, no usable
reply of the model, a type with no correction), `apply_retitle` writes `retitle.skipped` in the
job record of the item, and one log line with the reason, once.
The value is `skip_hash`: a hash of the title, the body and the `stage.pr` mark. The selection
leaves out an item while the mark equals the current hash, so a later round reads no comment of
it, makes no model request for it, and does not let it hold a place of `--limit`. A change to the
title, the body or the `stage.pr` mark selects the item again. A comment does not.

**The source of the new summary.** The job keeps the type and the scope of a listed type (or of
the corrected title), and writes only the summary (`build_title`), so `title_problems` holds for
the new title. When the summary of a corrected title stays too long, the job writes the corrected
title with its old summary, and the next round shortens it as for any listed type.

- A Planned item takes the summary of the title of its plan pull request, which the job record
  names (`stage.pr`). The stage job bounds that summary (`STAGE_SUMMARY_MAX_CHARS`). The job makes
  no model call for a Planned item. When the pull request has no usable title, the job leaves the
  item and comments the reason.
- Another item gets one request to the background model, and one more with the faults of the
  first reply. A reply that fails `title_problems` twice leaves the item.

**A person's edit stays.** The job reads the title changes on the timeline of the item and its
comments. When someone changed the title after the last comment of a job, or when a title change
exists and no job commented, the job leaves the title.

A plan writes nothing. `apply_retitle` writes the title, then one comment with the marker of the
job, and it skips an item whose title changed after the plan read it.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_BRANCH_TYPES,
    CONST_ROADMAP_JOB_COMMENT_MARKERS,
    CONST_ROADMAP_RETITLE_COMMENT_MARKER,
)
from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_INTAKE_TEXT_CHARS,
    DEFAULT_ROADMAP_RETITLE_LIMIT,
)
from devops_cli.config.settings import AIConfig
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.ai import ModelGatewayUnreachableError
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.validation import ValidationError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.body_hash import hash_text
from devops_cli.roadmap.commit_title import (
    commit_summary,
    commit_type,
    corrected_title,
    unlisted_type,
)
from devops_cli.roadmap.intake.intake_model import gateway_address
from devops_cli.roadmap.pull_form import SUMMARY_MAX_CHARS, build_title, summary_length
from devops_cli.roadmap.stores.store import (
    IssueComment,
    Item,
    RetitleRecordKey,
    RoadmapStore,
    StageRecordKey,
)

logger = logging.getLogger(__name__)

_PROMPT = "roadmap_retitle.md"
# The requests to the model for one item: the first, and one with the faults of its reply.
_ATTEMPTS = 2
# The reason keys of the log line of a skip (#4508): a title type that the stage job cannot take,
# and a title summary over the limit.
_KEY_TYPE = "invalid-title-type"
_KEY_LONG = "long-title"


class RetitleReply(BaseModel):
    """The model's reply: the new summary, and nothing else."""

    model_config = ConfigDict(extra="forbid")

    summary: str


class RetitleClient(Protocol):
    """What the job needs of `LLMClient`."""

    def chat_structured(
        self, system: str, prompt: str, schema: type[RetitleReply]
    ) -> RetitleReply: ...


class RetitleModel(Protocol):
    """The one model call of the job."""

    def summarize(self, request: str) -> RetitleReply:
        """The reply to `request`, the JSON that `_request` builds."""


class GatewayRetitleModel:
    """The call through the `triage` task's client, and so through the gateway when one is
    configured. The client is built on first use, so a run with no item that needs the model
    opens no connection. A test passes its own `client`."""

    def __init__(
        self, ai: AIConfig, *, api_key: str | None = None, client: RetitleClient | None = None
    ) -> None:
        self._ai = ai
        self._api_key = api_key
        self._client = client

    def summarize(self, request: str) -> RetitleReply:
        """Ask the model for a summary. A call that cannot reach its model raises
        `ModelGatewayUnreachableError`, and the run writes nothing."""
        from devops_cli.ai.client.models import StructuredOutputValidationError

        try:
            return self._built().chat_structured(load_task_prompt(_PROMPT), request, RetitleReply)
        except StructuredOutputValidationError:
            return RetitleReply(summary="")
        except (DevOpsCLIError, OSError) as exc:
            raise ModelGatewayUnreachableError(
                gateway_address(self._ai), exc, consequence="retitle wrote nothing"
            ) from exc

    def _built(self) -> RetitleClient:
        if self._client is None:
            from devops_cli.ai.client import get_llm_client

            self._client = get_llm_client(
                task="triage", config=self._ai.for_task("triage"), api_key=self._api_key
            )
        return self._client


def build_retitle_model() -> GatewayRetitleModel:
    """The model call with this checkout's AI settings and API key."""
    from devops_cli.config.settings import get_ai_api_key, load_settings

    settings = load_settings()
    return GatewayRetitleModel(settings.ai, api_key=get_ai_api_key(settings))


@dataclass(frozen=True)
class TitleChange:
    """A new title for an item: the title it replaces, the title, and where the summary came from."""

    item: Item
    title: str
    source: str

    @property
    def old_length(self) -> int:
        return summary_length(commit_summary(self.item.title))


@dataclass(frozen=True)
class TitleSkip:
    """An item the job leaves as it is, and why. `comment` says the job comments the reason."""

    item: Item
    reason: str
    comment: bool = False


@dataclass(frozen=True)
class RetitlePlan:
    """What a run decided: the new titles, the items it left, and how many items with a long
    title or an unlisted type the limit left for a later run. A dry run holds the requests of a run
    instead."""

    repo: str
    changes: tuple[TitleChange, ...] = ()
    skips: tuple[TitleSkip, ...] = ()
    left: int = 0
    dry_run: bool = False
    requests: tuple[PlannedRequest, ...] = ()
    write_requests: tuple[PlannedRequest, ...] = ()

    @property
    def has_writes(self) -> bool:
        """Whether `--confirm` writes something."""
        return bool(self.changes) or any(skip.comment for skip in self.skips)


def skip_hash(item: Item) -> str:
    """The hash of what the decision for `item` reads: its title, its body and its `stage.pr`
    mark. The body of an Item holds no record block, so the write of the mark leaves it as it is."""
    recorded = str(item.job_record.get(StageRecordKey.PR) or "")
    return hash_text("\0".join((item.title, item.body, recorded)))


def _is_skipped(item: Item) -> bool:
    return item.job_record.get(RetitleRecordKey.SKIPPED) == skip_hash(item)


def _needs_retitle(title: str) -> bool:
    """Whether `title` has an unlisted type, or a Conventional Commit type and a summary over the
    limit."""
    if unlisted_type(title) is not None:
        return True
    return (
        commit_type(title) is not None and summary_length(commit_summary(title)) > SUMMARY_MAX_CHARS
    )


def retitle_items(store: RoadmapStore, item_number: int | None = None) -> list[Item]:
    """The open Items whose title has an unlisted type, or a Conventional Commit type and a
    summary over the limit, the lowest number first, without an item whose skip mark holds. With
    `item_number`, only that item, when it is one of them."""
    found = [
        item
        for item in store.open_items()
        if _needs_retitle(item.title)
        and item_number in (None, item.number)
        and not _is_skipped(item)
    ]
    return sorted(found, key=lambda item: item.number)


def _is_job_comment(comment: IssueComment) -> bool:
    return any(marker in comment.body for marker in CONST_ROADMAP_JOB_COMMENT_MARKERS)


def person_changed_title(comments: Sequence[IssueComment], renamed_at: datetime | None) -> bool:
    """Whether someone changed the title after the last comment of a job, or changed it when no
    job commented. The job's own change always comes before its comment."""
    if renamed_at is None:
        return False
    last = max((c.created_at for c in comments if _is_job_comment(c)), default=None)
    return last is None or renamed_at > last


def _request(item: Item, title: str, problems: Sequence[str]) -> str:
    """The JSON the model sees: the title to shorten, its summary, the limit, the start of the
    body and the faults of the last reply."""
    return json.dumps(
        {
            "title": title,
            "summary": commit_summary(title),
            "limit": SUMMARY_MAX_CHARS,
            "body": item.body[:DEFAULT_ROADMAP_INTAKE_TEXT_CHARS],
            "problems": list(problems),
        },
        ensure_ascii=False,
        indent=1,
    )


def _title_with(title: str, summary: str) -> tuple[str | None, str]:
    """`title` with `summary` as its summary, or None and the problems that the title form
    finds."""
    try:
        return build_title(title, summary, None), ""
    except ValidationError as exc:
        return None, str(exc)


def _plan_title(store: RoadmapStore, item: Item, title: str) -> TitleChange | TitleSkip:
    """`title`, the title of a Planned item, with the summary of the title of its plan pull
    request. The stage job writes that title as `plan #<issue> <summary>`, and bounds the
    summary."""
    texts = MESSAGES.roadmap
    recorded = item.job_record.get(StageRecordKey.PR)
    if not (recorded and recorded.isdecimal()):
        return TitleSkip(item, texts.retitle_reason_no_pull, comment=True)
    pull = int(recorded)
    pull_title = store.pull_title(pull)
    lead = texts.stage_title_lead.format(number=item.number)
    summary = commit_summary(pull_title or "")
    if not summary.startswith(lead):
        reason = texts.retitle_reason_pull_title.format(
            pull=pull, problems=f"it does not start with `{lead.strip()}`."
        )
        return TitleSkip(item, reason, comment=True)
    new, problems = _title_with(title, summary.removeprefix(lead))
    if new is None:
        reason = texts.retitle_reason_pull_title.format(pull=pull, problems=problems)
        return TitleSkip(item, reason, comment=True)
    return TitleChange(item, new, texts.retitle_source_plan.format(pull=pull))


def _model_title(model: RetitleModel, item: Item, title: str) -> TitleChange | TitleSkip:
    """`title`, the title of an item that has no plan, with the reply of the model that passes the
    title form. The second request carries the faults of the first reply."""
    problems = ""
    for _ in range(_ATTEMPTS):
        reply = model.summarize(_request(item, title, [problems] if problems else []))
        new, problems = _title_with(title, reply.summary)
        if new is not None:
            return TitleChange(item, new, MESSAGES.roadmap.retitle_source_model)
    reason = MESSAGES.roadmap.retitle_reason_model_failed.format(problems=problems)
    return TitleSkip(item, reason)


def _shortened(
    store: RoadmapStore, model: RetitleModel, item: Item, title: str
) -> TitleChange | TitleSkip:
    """`title` with a short summary: the plan's for a Planned item, else the model's."""
    if item.status == "Planned":
        return _plan_title(store, item, title)
    return _model_title(model, item, title)


def _typed(store: RoadmapStore, model: RetitleModel, item: Item) -> TitleChange | TitleSkip:
    """An item whose title type is not listed (#4508): the corrected title, with no model call
    when its summary is short. A long summary is shortened; when that fails, the corrected title
    keeps its old summary, so the stage job reads a listed type and a later round shortens it.
    A type with no correction leaves the item with a comment."""
    texts = MESSAGES.roadmap
    typed = corrected_title(item.title)
    if typed is None:
        reason = texts.retitle_reason_type_unknown.format(type=unlisted_type(item.title))
        return TitleSkip(item, reason, comment=True)
    kept = TitleChange(item, typed, texts.retitle_source_title)
    if summary_length(commit_summary(typed)) <= SUMMARY_MAX_CHARS:
        return kept
    shortened = _shortened(store, model, item, typed)
    return shortened if isinstance(shortened, TitleChange) else kept


def _decide(store: RoadmapStore, model: RetitleModel, item: Item) -> TitleChange | TitleSkip:
    """One item: the person's edit first, which costs no token, then the correction of an
    unlisted type, then the plan's title or the model's. A person's title with an unlisted type
    stays, and the comment names the type, because the stage job cannot take it."""
    texts = MESSAGES.roadmap
    comments = store.comments_on(item.number)
    unlisted = unlisted_type(item.title) is not None
    if person_changed_title(comments, store.last_renamed_at(item.number)):
        return TitleSkip(item, texts.retitle_reason_person_edit, comment=unlisted)
    if unlisted:
        return _typed(store, model, item)
    return _shortened(store, model, item, item.title)


def plan_retitle(
    store: RoadmapStore,
    *,
    repo: str,
    model: RetitleModel,
    item_number: int | None = None,
    limit: int | None = None,
) -> RetitlePlan:
    """Decide the items with a long title or an unlisted type, at most `limit` of them
    (`DEFAULT_ROADMAP_RETITLE_LIMIT` by default), writing nothing."""
    cap = DEFAULT_ROADMAP_RETITLE_LIMIT if limit is None else limit
    found = retitle_items(store, item_number)
    changes: list[TitleChange] = []
    skips: list[TitleSkip] = []
    for item in found[:cap]:
        decided = _decide(store, model, item)
        if isinstance(decided, TitleChange):
            changes.append(decided)
        else:
            skips.append(decided)
    return RetitlePlan(
        repo=repo, changes=tuple(changes), skips=tuple(skips), left=max(len(found) - cap, 0)
    )


def _comment_of(change: TitleChange) -> str:
    kind = unlisted_type(change.item.title)
    if kind is not None:
        return MESSAGES.roadmap.retitle_comment_type_changed.format(
            marker=CONST_ROADMAP_RETITLE_COMMENT_MARKER,
            type=kind,
            types=", ".join(CONST_BRANCH_TYPES),
            old=change.item.title,
            new=change.title,
            source=change.source,
        )
    return MESSAGES.roadmap.retitle_comment_changed.format(
        marker=CONST_ROADMAP_RETITLE_COMMENT_MARKER,
        length=change.old_length,
        limit=SUMMARY_MAX_CHARS,
        old=change.item.title,
        new=change.title,
        source=change.source,
    )


def _skip_comment_of(skip: TitleSkip) -> str:
    texts = MESSAGES.roadmap
    kind = unlisted_type(skip.item.title)
    if kind is not None:
        typed = corrected_title(skip.item.title)
        return texts.retitle_comment_type_skipped.format(
            marker=CONST_ROADMAP_RETITLE_COMMENT_MARKER,
            type=kind,
            types=", ".join(CONST_BRANCH_TYPES),
            reason=skip.reason,
            correction=texts.title_type_correction.format(title=typed) if typed else "",
        )
    return texts.retitle_comment_skipped.format(
        marker=CONST_ROADMAP_RETITLE_COMMENT_MARKER,
        length=summary_length(commit_summary(skip.item.title)),
        limit=SUMMARY_MAX_CHARS,
        reason=skip.reason,
    )


def _changed_since_read(store: RoadmapStore, change: TitleChange) -> bool:
    now = store.item(change.item.number)
    return now is None or now.title != change.item.title


def apply_retitle(store: RoadmapStore, plan: RetitlePlan) -> int:
    """Write each new title and one comment on its item, and one comment for each skip that says
    so, unless the item already holds that comment. Each skip also gets the skip mark, in one write,
    and one log line with its reason key: the selection leaves out a marked item, so the line comes
    once.
    An item whose title changed since the plan read it is left. Returns the number of titles
    written."""
    written = 0
    for change in plan.changes:
        if _changed_since_read(store, change):
            logger.warning(
                "The title of #%d changed after the run read it, so retitle left it.",
                change.item.number,
            )
            continue
        store.set_title(change.item.number, change.title)
        store.comment(change.item.number, _comment_of(change))
        written += 1
    for skip in plan.skips:
        key = _KEY_TYPE if unlisted_type(skip.item.title) is not None else _KEY_LONG
        logger.warning(
            MESSAGES.roadmap.retitle_log_left.format(
                number=skip.item.number, key=key, reason=skip.reason
            ),
            extra={"reason": key},
        )
        body = _skip_comment_of(skip)
        if skip.comment and all(c.body != body for c in store.comments_on(skip.item.number)):
            store.comment(skip.item.number, body)
        store.set_marks(skip.item, {RetitleRecordKey.SKIPPED: skip_hash(skip.item)})
    return written


def dry_run_retitle(repo: str, *, item: int | None = None, limit: int | None = None) -> RetitlePlan:
    """The plan a dry run returns, having made no external request."""
    from devops_cli.roadmap.request_plan import retitle_requests

    reads, writes = retitle_requests(repo, item=item, limit=limit)
    return RetitlePlan(repo=repo, dry_run=True, requests=reads, write_requests=writes)


def render_retitle_plan(plan: RetitlePlan) -> str:
    """The report: each new title, each item left as it is, and how many items wait."""
    texts = MESSAGES.roadmap
    lines = [texts.retitle_title.format(repo=plan.repo)]
    if not (plan.changes or plan.skips):
        lines.append(texts.retitle_none.format(limit=SUMMARY_MAX_CHARS))
        return "\n".join(lines)
    if plan.changes:
        lines.append(texts.retitle_changes_heading)
        lines += [
            texts.retitle_change_line.format(
                number=change.item.number, old=change.item.title, new=change.title
            )
            for change in plan.changes
        ]
    if plan.skips:
        lines.append(texts.retitle_skips_heading)
        lines += [
            texts.retitle_skip_line.format(
                number=skip.item.number, title=skip.item.title, reason=skip.reason
            )
            for skip in plan.skips
        ]
    if plan.left:
        lines.append(texts.retitle_left.format(count=plan.left))
    return "\n".join(lines)


__all__ = [
    "GatewayRetitleModel",
    "RetitleModel",
    "RetitlePlan",
    "RetitleReply",
    "TitleChange",
    "TitleSkip",
    "apply_retitle",
    "build_retitle_model",
    "dry_run_retitle",
    "person_changed_title",
    "plan_retitle",
    "render_retitle_plan",
    "retitle_items",
    "skip_hash",
]
