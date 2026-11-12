"""A roadmap job posts no comment that repeats its own recent comment (#4793).

Each comment of a roadmap job holds the marker of the job (`CONST_ROADMAP_JOB_COMMENT_MARKERS`).
A round that finds the same facts again posted the same text again: the census of 2026-11-11
found 34 repeats of refine on open items, and the implement job posted 73 comments with two texts
on one item in four days. Both stores call `refused_repeat` before they post a comment, so a
rerun after a stop of the Service posts no second copy either (ADR 0021).

The guard refuses a comment of a job when the same text is in the trailing run of comments that
hold the same marker: the comments after the last comment that holds no such marker. Only a
comment made in the last `_WINDOW` counts, so a wait that lasts longer gets one comment each
week. A person's reply or another job's comment ends the run, so the answer of the job to it
posts. A job that reads the replies after its last comment (`replies_after_marker`) thus reads
the same replies as when the repeat had posted.

Two texts are the same when their fingerprints are the same: the SHA-256 of the text, with each
run of white space made one space and each identifier of seven or more hexadecimal digits that
holds a digit made one placeholder. A round names the commit it read, an image digest or a run,
and these change while the facts stay the same.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from itertools import takewhile
from typing import Final

from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER,
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_INTAKE_REASON_MARKER,
    CONST_ROADMAP_REFINE_COMMENT_MARKER,
    CONST_ROADMAP_REFINE_OUTSIDE_MARKER,
    CONST_ROADMAP_RETITLE_COMMENT_MARKER,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
)
from devops_cli.roadmap.stores.store import IssueComment
from devops_cli.telemetry.instruments import ROADMAP_COMMENT_REPEATS_REFUSED_TOTAL, emit

logger = logging.getLogger(__name__)

# The marker of each roadmap job's comments, in the order of `CONST_ROADMAP_JOB_COMMENT_MARKERS`,
# and the job that the label `row` of a refused repeat names: the row of the job in the Service.
COMMENT_JOBS: Final[tuple[tuple[str, str], ...]] = (
    (CONST_ROADMAP_RETITLE_COMMENT_MARKER, "retitle"),
    (CONST_ROADMAP_REFINE_COMMENT_MARKER, "refine"),
    (CONST_ROADMAP_REFINE_OUTSIDE_MARKER, "refine"),
    (CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER, "alternatives"),
    (CONST_ROADMAP_INTAKE_REASON_MARKER, "intake"),
    (CONST_ROADMAP_STAGE_COMMENT_MARKER, "stage"),
    (CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER, "implement"),
)

# How long an earlier comment of a job refuses the same text.
_WINDOW: Final[timedelta] = timedelta(days=7)

# A commit, an image digest or a run ID: seven or more lower-case hexadecimal digits, one of them
# a digit, so a word such as `defaced` stays.
_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"\b(?=[0-9a-f]*[0-9])[0-9a-f]{7,}\b")


def comment_job(body: str) -> tuple[str, str] | None:
    """The marker of the job that wrote `body`, and the name of the job, or None for a comment
    that holds no job marker."""
    return next(((marker, job) for marker, job in COMMENT_JOBS if marker in body), None)


def fingerprint(body: str) -> str:
    """The SHA-256 of `body` with its white space made single spaces and its identifiers left
    out."""
    text = " ".join(_IDENTIFIER_RE.sub("<id>", body).split())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def repeats_recent(
    comments: Sequence[IssueComment], body: str, marker: str, *, now: datetime
) -> bool:
    """Whether a comment in the trailing run of `comments` (oldest first) that hold `marker`,
    made at or after `now` less the window, has the fingerprint of `body`."""
    run = takewhile(lambda comment: marker in comment.body, reversed(comments))
    wanted = fingerprint(body)
    since = now - _WINDOW
    return any(c.created_at > since and fingerprint(c.body) == wanted for c in run)


def refused_repeat(
    number: int,
    body: str,
    comments: Callable[[], Sequence[IssueComment]],
    *,
    now: datetime,
) -> bool:
    """Whether a store refuses to post `body` on issue `number`, as a repeat of a recent comment
    of the same job. `comments` reads the comments of the issue, oldest first; it is called only
    for a comment that holds a job marker. A refusal is logged and counted under the row of its job."""
    found = comment_job(body)
    if found is None:
        return False
    marker, job = found
    if not repeats_recent(comments(), body, marker, now=now):
        return False
    logger.info(
        "Refused a comment of the %s job on #%d: the job's last comment there has the same text.",
        job,
        number,
    )
    emit(ROADMAP_COMMENT_REPEATS_REFUSED_TOTAL, 1, {"row": job})
    return True
