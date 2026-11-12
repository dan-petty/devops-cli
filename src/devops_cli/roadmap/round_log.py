"""One log line with counts for each fix round and each failed item of the roadmap jobs (#4535).

A line holds numbers, names of steps, states and classes, and never a text of the model. Each
line ends with the devops-cli version of the process: the release workflow builds the Service
image only for a release, so the version names one image. An implement attempt also names the
digest of the runner image that its Job ran. One Loki query by event and round then gives the
pass rate of a return and of a review round for each image.

Each line names the repository before the item: the Service runs the rows of more than one
repository in one process, and two repositories can have an item with the same number. A run
with no repository writes `repo=none`.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

from devops_cli import __version__

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from devops_cli.roadmap.stage.stage_findings import ReturnCounts, StageFinding

logger = logging.getLogger(__name__)


def _tally(names: Iterable[str]) -> str:
    """Each name with its count, as `name:count` in the order of the names, or `none`."""
    return ",".join(f"{name}:{count}" for name, count in sorted(Counter(names).items())) or "none"


def log_gate_returns(
    repo: str, item: int, returns: int, *, passed: bool, findings: Sequence[StageFinding] = ()
) -> None:
    """Log the end of a stage reply that the checks refused at least once: the number of returns,
    whether the last reply passed, and the gates and the codes of the findings of the last refused
    reply, each with its count (#4846). A reply that passed with no return logs nothing."""
    if returns == 0:
        return
    logger.info(
        "stage gate returns: repo=%s item=#%d returns=%d result=%s gates=%s codes=%s version=%s",
        repo or "none",
        item,
        returns,
        "passed" if passed else "refused",
        _tally(f.gate for f in findings),
        _tally(f.code for f in findings),
        __version__,
    )


def log_gate_findings(repo: str, item: int, return_: int, counts: ReturnCounts) -> None:
    """Log the findings of the reply after return `return_` of a stage plan against those of the
    reply before it: the findings before, those gone, those stuck and the new ones (#4846)."""
    logger.info(
        "stage gate findings: repo=%s item=#%d return=%d in=%d gone=%d stuck=%d new=%d version=%s",
        repo or "none",
        item,
        return_,
        counts.before,
        counts.gone,
        counts.stuck,
        counts.new,
        __version__,
    )


def log_review_round(
    repo: str, item: int, round_: int, *, findings: int, returned: int, open_: int
) -> None:
    """Log one model review of a stage plan: `round_` 0 is the first review, and each repair round
    adds 1. `returned` counts the findings that send the plan back, and `open_` those that stay
    open. Each open finding sends the plan back (#5059), so the two counts are equal; the line
    keeps both fields for the log queries that read them."""
    logger.info(
        "stage review round: repo=%s item=#%d round=%d findings=%d returned=%d open=%d version=%s",
        repo or "none",
        item,
        round_,
        findings,
        returned,
        open_,
        __version__,
    )


def log_failed_item(repo: str, item: int, step: str, failure_class: str) -> None:
    """Log one item that a stage round failed, with the step and the class of its error."""
    logger.info(
        "stage item failed: repo=%s item=#%d step=%s class=%s version=%s",
        repo or "none",
        item,
        step,
        failure_class,
        __version__,
    )


def log_implement_attempt(
    repo: str,
    item: int,
    *,
    state: str,
    failure_class: str | None,
    repair_rounds: int,
    tokens: int,
    digest: str | None,
) -> None:
    """Log one implement Job that ended: its state, the class of its failure, its repair rounds,
    the tokens that it spent, and the digest of the runner image that it ran."""
    logger.info(
        "implement attempt: repo=%s item=#%d state=%s class=%s repair_rounds=%d tokens=%d "
        "digest=%s version=%s",
        repo or "none",
        item,
        state,
        failure_class or "none",
        repair_rounds,
        tokens,
        digest or "none",
        __version__,
    )


__all__ = [
    "log_failed_item",
    "log_gate_findings",
    "log_gate_returns",
    "log_implement_attempt",
    "log_review_round",
]
