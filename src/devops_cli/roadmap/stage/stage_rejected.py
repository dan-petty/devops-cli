"""A plan that a person rejected leaves its reason on the issue (#3503).

A person rejects a staged plan when they close its pull request with no merge. The reason stays on
the closed pull request, and refine can set the item Ready again, so the stage job could plan the
same false premise again. The stage job reads the plan pull request of each staged item
(`closed_plans`). For a pull request that closed with no merge it copies the reason to the issue in
a comment that holds the marker of the stage job and the marker of a rejected plan
(`comment_text`), returns the item to New, and records the rejection in `stage.rejected`
(`RejectedPlan`). Refine reads the comment as `stage_return`, and the stage request reads it as
`rejected_plan` (`rejected_reason`). The stage selection leaves the item out until the text of the
item or a file that the reason names changes (`hold_reason`).

The reason is the last comment on the pull request that a person with write access wrote, that the
Service bot did not write, and that has more than `EVIDENCE_MIN_CHARS` characters: a comment of one
word, such as `rejected`, is no reason (`reason_comment`). The module holds the rules that need no
git. `stage.py` finds the rejections of a round and writes them.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, NamedTuple

from pydantic import BaseModel, ConfigDict

from devops_cli.ai.context_budget import truncate_to_token_limit
from devops_cli.config.constants import (
    CONST_ROADMAP_JOB_COMMENT_MARKERS,
    CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
    CONST_ROADMAP_STAGE_REJECTED_MARKER,
    CONST_ROADMAP_STATUS_NEW,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.body_hash import body_hashes
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.refine.refine import changed_since, stage_comment_text, text_paths
from devops_cli.roadmap.stores.store import (
    GitHubState,
    IssueComment,
    Item,
    RoadmapStore,
    StageRecordKey,
)
from devops_cli.roadmap.trust import trusted_replies
from devops_cli.security.sanitizer import mask_secrets

logger = logging.getLogger(__name__)

# A comment of this many characters or fewer is no reason for a rejection: `rejected` is one.
EVIDENCE_MIN_CHARS: Final[int] = 60


class RejectedPlan(BaseModel):
    """The record `stage.rejected`: the plan pull request that a person closed with no merge, the
    hash of the text of the item outside the refine section when the plan was made, the time at
    which the pull request closed, and the files that the reason names."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pull: int
    text_hash: str
    closed_at: datetime
    paths: tuple[str, ...] = ()

    @property
    def record(self) -> str:
        """The value of `stage.rejected`."""
        return self.model_dump_json()


def recorded_rejection(item: Item) -> RejectedPlan | None:
    """The rejection that the job record of `item` holds, or None when it holds none. A record
    that is no rejection is logged and read as none, so it never stops a round."""
    recorded = item.job_record.get(StageRecordKey.REJECTED)
    if not recorded:
        return None
    try:
        return RejectedPlan.model_validate_json(recorded)
    except ValueError:
        logger.warning("The rejected plan recorded on #%d is not a rejection.", item.number)
        return None


def hold_reason(store: RoadmapStore, item: Item, rejected: RejectedPlan) -> str | None:
    """Why the stage job leaves out `item` after a rejected plan, or None when the hold ended:
    the text of the item outside the refine section changed, or a commit on the default branch
    changed a file that the reason names, at or after the close of the pull request."""
    if body_hashes(item.body)[0] != rejected.text_hash:
        return None
    if changed_since(store, rejected.paths, rejected.closed_at):
        return None
    return MESSAGES.roadmap.stage_left_rejected.format(pull=rejected.pull)


def reason_comment(
    comments: Sequence[IssueComment], *, service_login: str | None
) -> IssueComment | None:
    """The newest comment on a closed plan pull request that is a reason, or None: its author is a
    person with write access (`trusted_replies`) and not the Service bot, it is no comment of a
    roadmap job, and it has more than `EVIDENCE_MIN_CHARS` characters."""
    return next(
        (
            comment
            for comment in reversed(trusted_replies(comments))
            if (service_login is None or comment.author_login != service_login)
            and not any(marker in comment.body for marker in CONST_ROADMAP_JOB_COMMENT_MARKERS)
            and len(comment.body.strip()) > EVIDENCE_MIN_CHARS
        ),
        None,
    )


def _reason_text(comment: IssueComment) -> str:
    """The text of `comment` with its secrets masked, cut to the token cap of a refine reply."""
    return truncate_to_token_limit(
        mask_secrets(comment.body.strip()), max_tokens=CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS
    )


def _quote(text: str) -> str:
    return "\n".join(f"> {line}".rstrip() for line in text.splitlines())


def comment_text(pull: int, reason: IssueComment | None) -> str:
    """The comment on the issue for the rejected plan pull request `pull`: the two markers, what
    the job does next, and the reason as a quotation, or the words that no comment gives one."""
    texts = MESSAGES.roadmap
    if reason is None:
        shown = texts.stage_rejected_no_reason
    else:
        shown = texts.stage_rejected_reason.format(
            author=reason.author_login or texts.refine_author_unknown,
            quote=_quote(_reason_text(reason)),
        )
    return texts.stage_rejected_comment.format(
        marker=CONST_ROADMAP_STAGE_COMMENT_MARKER,
        rejected_marker=CONST_ROADMAP_STAGE_REJECTED_MARKER,
        pull=pull,
        reason=shown,
    )


def rejected_reason(comments: Sequence[IssueComment]) -> str | None:
    """The text of the newest comment of a trusted author on the issue that holds the marker of a
    rejected plan, as `stage_comment_text` gives it, or None."""
    marked = [c for c in trusted_replies(comments) if CONST_ROADMAP_STAGE_REJECTED_MARKER in c.body]
    return stage_comment_text(marked[-1].body) if marked else None


@dataclass(frozen=True)
class ClosedPlan:
    """The plan pull request of `item` that closed with no merge, when it closed, and the comment
    that gives the reason, or None when no comment does."""

    item: Item
    pull: int
    closed_at: datetime
    reason: IssueComment | None

    def rejection(self) -> tuple[RejectedPlan, str]:
        """The record and the comment of the rejection. The hash is the one of the text that the
        plan came from (`stage.text_hash`), so an edit made before the job looks at the closed
        pull request ends the hold. A record that holds none has the hash of the text now."""
        paths = text_paths(_reason_text(self.reason)) if self.reason is not None else []
        planned = self.item.job_record.get(StageRecordKey.TEXT_HASH)
        plan = RejectedPlan(
            pull=self.pull,
            text_hash=planned or body_hashes(self.item.body)[0],
            closed_at=self.closed_at,
            paths=tuple(paths),
        )
        return plan, comment_text(self.pull, self.reason)


class ReadFailure(NamedTuple):
    """An item whose plan pull request could not be read, and the error."""

    item: Item
    error: DevOpsCLIError


class ClosedPlans(NamedTuple):
    """What a read of the staged plans found: the plans that closed with no merge, and the items
    whose pull request could not be read."""

    closed: tuple[ClosedPlan, ...]
    failures: tuple[ReadFailure, ...]


def staged_plans(
    items: Iterable[Item], planned: PlannedChanges, item_number: int | None = None
) -> list[tuple[Item, int]]:
    """Each open New or Ready item that holds a staged pull request and whose plan is not on the
    default branch, with that pull request. With `item_number` only that item."""
    found: list[tuple[Item, int]] = []
    for item in items:
        recorded = item.job_record.get(StageRecordKey.PR) or ""
        if item_number is not None and item.number != item_number:
            continue
        if item.state is not GitHubState.OPEN or not recorded.isdigit():
            continue
        if item.status not in (CONST_ROADMAP_STATUS_NEW, CONST_ROADMAP_STATUS_READY):
            continue
        if item.number in planned.active or item.number in planned.archived:
            continue
        found.append((item, int(recorded)))
    return found


def closed_plans(
    store: RoadmapStore,
    repo: str,
    staged: Sequence[tuple[Item, int]],
    *,
    stop: tuple[type[DevOpsCLIError], ...],
) -> ClosedPlans:
    """Read each staged pull request in `staged`, and the comments of each one that closed with no
    merge. A read that fails stops that item only, and a failure of a class in `stop` stops the
    run."""
    closed: list[ClosedPlan] = []
    failures: list[ReadFailure] = []
    service = load_settings().service.github_app.bot_login
    for item, pull in staged:
        try:
            status = get_github_session().client.get_pull_status(repo, pull)
            if status.state != "closed" or status.merged:
                continue
            reason = reason_comment(store.comments_on(pull), service_login=service)
        except stop:
            raise
        except DevOpsCLIError as exc:
            failures.append(ReadFailure(item, exc))
            continue
        closed.append(ClosedPlan(item, pull, status.closed_at or datetime.now(UTC), reason))
    return ClosedPlans(tuple(closed), tuple(failures))


def reasons_of(store: RoadmapStore, items: Iterable[Item]) -> Mapping[int, str]:
    """The reason of each item in `items` that holds a `stage.rejected` record and a comment of a
    rejected plan, by issue number: what the plan request holds as `rejected_plan`."""
    found: dict[int, str] = {}
    for item in items:
        if recorded_rejection(item) is None:
            continue
        if (reason := rejected_reason(store.comments_on(item.number))) is not None:
            found[item.number] = reason
    return found
