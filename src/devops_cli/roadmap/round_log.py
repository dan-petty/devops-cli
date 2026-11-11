"""One log line with counts for each fix round and each failed item of the roadmap jobs (#4535).

A line holds numbers, names of steps, states and classes, and never a text of the model. Each
line ends with the devops-cli version of the process: the release workflow builds the Service
image only for a release, so the version names one image. An implement attempt also names the
digest of the runner image that its Job ran. One Loki query by event and round then gives the
pass rate of a return and of a review round for each image.
"""

from __future__ import annotations

import logging

from devops_cli import __version__

logger = logging.getLogger(__name__)


def log_gate_returns(item: int, returns: int, *, passed: bool) -> None:
    """Log the end of a stage reply that the checks refused at least once: the number of returns,
    and whether the last reply passed. A reply that passed with no return logs nothing."""
    if returns == 0:
        return
    logger.info(
        "stage gate returns: item=#%d returns=%d result=%s version=%s",
        item,
        returns,
        "passed" if passed else "refused",
        __version__,
    )


def log_review_round(item: int, round_: int, *, findings: int, returned: int, open_: int) -> None:
    """Log one model review of a stage plan: `round_` 0 is the first review, and each repair round
    adds 1. `returned` counts the findings that send the plan back, and `open_` those that stay
    open."""
    logger.info(
        "stage review round: item=#%d round=%d findings=%d returned=%d open=%d version=%s",
        item,
        round_,
        findings,
        returned,
        open_,
        __version__,
    )


def log_failed_item(item: int, step: str, failure_class: str) -> None:
    """Log one item that a stage round failed, with the step and the class of its error."""
    logger.info(
        "stage item failed: item=#%d step=%s class=%s version=%s",
        item,
        step,
        failure_class,
        __version__,
    )


def log_implement_attempt(
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
        "implement attempt: item=#%d state=%s class=%s repair_rounds=%d tokens=%d digest=%s "
        "version=%s",
        item,
        state,
        failure_class or "none",
        repair_rounds,
        tokens,
        digest or "none",
        __version__,
    )


__all__ = ["log_failed_item", "log_gate_returns", "log_implement_attempt", "log_review_round"]
