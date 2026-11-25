"""Shared implement job-record clear marks for returned items and rejected plans (#5251)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from devops_cli.roadmap.stores.store import ImplementRecordKey

if TYPE_CHECKING:
    from devops_cli.roadmap.stores.store import Item

# The keys of an implement delivery that a discard or runner return clears, keeping job/spend state
# for the Service report (#5251).
DELIVERY_CLEAR_KEYS: Final[tuple[ImplementRecordKey, ...]] = (
    ImplementRecordKey.GROUP,
    ImplementRecordKey.SHA,
    ImplementRecordKey.BRANCH,
    ImplementRecordKey.PR,
    ImplementRecordKey.BASE,
    ImplementRecordKey.PLAN_SUMMARY,
    ImplementRecordKey.CHECKED_SHA,
    ImplementRecordKey.PUBLISHED_SHA,
    ImplementRecordKey.RESULT,
)

# The run-level implement keys cleared when a plan pull request is rejected or an item is manually
# returned for a new plan, leaving non-run history (continuations, digest clears, spend) intact.
RUN_CLEAR_KEYS: Final[tuple[ImplementRecordKey, ...]] = (
    *DELIVERY_CLEAR_KEYS,
    ImplementRecordKey.JOB,
    ImplementRecordKey.JOB_STATE,
    ImplementRecordKey.STOPPED,
    ImplementRecordKey.FAILURE,
    ImplementRecordKey.LEFT_ACTION,
    ImplementRecordKey.CHECK,
    ImplementRecordKey.CHECK_LOG,
    ImplementRecordKey.CONFLICT,
    ImplementRecordKey.REPAIR_ROUNDS,
    ImplementRecordKey.NEEDS_FIX,
)


def run_clear_marks(item: Item | None = None) -> dict[ImplementRecordKey, None]:
    """Marks that clear present implement run keys when returning an item for a new plan (#5251)."""
    return {
        key: None for key in RUN_CLEAR_KEYS if item is None or item.job_record.get(key) is not None
    }


__all__ = ["DELIVERY_CLEAR_KEYS", "RUN_CLEAR_KEYS", "run_clear_marks"]
