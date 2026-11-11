"""Why the stage job leaves an item out, as a bounded kind, and the log line of each new kind (#4521).

The kind is the `reason` label of `devops_cli_roadmap_stage_total` and a field of the log line,
so a person sees why a repository is idle with no clone. The Service logs the reason of an item
once, and again only when the kind changes: a reason that holds for days writes one line.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterable, Mapping
from enum import StrEnum

logger = logging.getLogger(__name__)


class LeftOutKind(StrEnum):
    """The rule that left an item out of a stage round. `NONE` is the label of an item that the
    round handled with another result."""

    NOT_ITEM = "not_item"
    CLOSED = "closed"
    NOT_READY = "not_ready"
    CLAIMED = "claimed"
    NO_OPENSPEC = "no_openspec"
    NEEDS_SPLIT = "needs_split"
    TRACKER = "tracker"
    AUTHOR = "author"
    UNJUDGED = "unjudged"
    TITLE_TYPE = "title_type"
    TITLE_LONG = "title_long"
    TITLE_SLUG = "title_slug"
    DEPENDENCY = "dependency"
    BLOCKED = "blocked"
    PLANNED = "planned"
    REJECTED = "rejected"
    HELD = "held"
    REDACTED = "redacted"
    RECORDED_SPLIT = "recorded_split"
    FAILED_LATELY = "failed_lately"
    QUEUE_FULL = "queue_full"
    RETURNED = "returned"
    OTHER = "other"
    NONE = "none"


_lock = threading.Lock()
_logged: dict[tuple[str, int], LeftOutKind] = {}


def log_left_out(
    repo: str, reasons: Mapping[int, tuple[LeftOutKind, str]], handled: Iterable[int]
) -> None:
    """Log the reason of each item in `reasons` whose kind differs from the kind this process
    logged last for it. An item of `handled` that `reasons` does not hold got another result, so
    its next reason logs again. An item that the round did not judge keeps its last kind."""
    with _lock:
        for number in handled:
            if number not in reasons:
                _logged.pop((repo, number), None)
        for number, (kind, detail) in reasons.items():
            if _logged.get((repo, number)) is kind:
                continue
            _logged[(repo, number)] = kind
            logger.info(
                "stage left out: repo=%s item=#%d reason=%s detail=%s",
                repo,
                number,
                kind.value,
                detail or "none",
            )


def reset_left_out_log() -> None:
    """Forget each logged reason, so the next round logs every reason again."""
    with _lock:
        _logged.clear()
