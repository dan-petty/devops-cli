"""One log line with counts for each fix round and each failed item of the roadmap jobs (#4535).

A line holds numbers, names of steps, states and classes, and never a text of the model. The one
exception is the subject of a refused finding: the path, the tool or the command that the message
of a gate names, masked and cut, and no other text of the plan or of the finding (#5433). Each
line ends with the devops-cli version of the process: the release workflow builds the Service
image only for a release, so the version names one image. An implement attempt also names the
digest of the runner image that its Job ran. One Loki query by event and round then gives the
pass rate of a return and of a review round for each image.

Each line names the repository before the item: the Service runs the rows of more than one
repository in one process, and two repositories can have an item with the same number. A run
with no repository writes `repo=none`.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import TYPE_CHECKING, Final

from devops_cli import __version__
from devops_cli.roadmap.stage.stage_findings import finding_subject
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from devops_cli.roadmap.stage.stage_findings import ReturnCounts, StageFinding

logger = logging.getLogger(__name__)

# The findings of one refused reply that `log_gate_returns` names, each on its own line (#5433).
# The trace gate refused 10 paths of the plan of #1976 on 2026-11-13. Each line gives the count of
# all the findings, so a reader sees how many findings are past this limit.
_FINDINGS_LOGGED: Final[int] = 20
# The characters of a subject that a line keeps, after the mask.
_SUBJECT_CHARS: Final[int] = 200


def _tally(names: Iterable[str]) -> str:
    """Each name with its count, as `name:count` in the order of the names, or `none`."""
    return ",".join(f"{name}:{count}" for name, count in sorted(Counter(names).items())) or "none"


def _subject(finding: StageFinding) -> str:
    """The subject of `finding` as a JSON string, masked first and then cut, or `none`."""
    subject = finding_subject(finding)
    if subject is None:
        return "none"
    return json.dumps(mask_secrets(subject)[:_SUBJECT_CHARS], ensure_ascii=False)


def log_gate_returns(
    repo: str, item: int, returns: int, *, passed: bool, findings: Sequence[StageFinding] = ()
) -> None:
    """Log the end of a stage reply that the checks refused at least once: the number of returns,
    whether the last reply passed, and the gates and the codes of the findings of the last refused
    reply, each with its count (#4846). Then log one line for each of the first `_FINDINGS_LOGGED`
    findings of that reply, with its place, its gate, its code and its subject (#5433), so that a
    reader can tell a fault of the plan from a fault of the gate. A reply that passed with no
    return logs nothing."""
    if returns == 0:
        return
    result = "passed" if passed else "refused"
    logger.info(
        "stage gate returns: repo=%s item=#%d returns=%d result=%s gates=%s codes=%s version=%s",
        repo or "none",
        item,
        returns,
        result,
        _tally(f.gate for f in findings),
        _tally(f.code for f in findings),
        __version__,
    )
    for place, finding in enumerate(findings[:_FINDINGS_LOGGED], start=1):
        logger.info(
            "stage gate refused finding: repo=%s item=#%d returns=%d result=%s finding=%d/%d "
            "gate=%s code=%s subject=%s version=%s",
            repo or "none",
            item,
            returns,
            result,
            place,
            len(findings),
            finding.gate,
            finding.code,
            _subject(finding),
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


def log_gate_extension(
    repo: str, item: int, returns: int, counts: ReturnCounts, *, never: int, result: str
) -> None:
    """Log the decision on a stage reply that the checks refused at the last gate return
    (#4851): the returns of the reply, the facts of the rule (the findings of the reply before,
    those gone, those stuck and the new ones, and the findings of a `never` code) and the result:
    `extended` or the stop."""
    logger.info(
        "stage gate extension: repo=%s item=#%d returns=%d in=%d gone=%d stuck=%d new=%d "
        "never=%d result=%s version=%s",
        repo or "none",
        item,
        returns,
        counts.before,
        counts.gone,
        counts.stuck,
        counts.new,
        never,
        result,
        __version__,
    )


def log_gate_extension_end(repo: str, item: int, returns: int, result: str) -> None:
    """Log the end of the extra return of a stage reply (#4851): `passed` or `refused` when the
    checks judged its reply, or `ended` when the run ended before that."""
    logger.info(
        "stage gate extension end: repo=%s item=#%d returns=%d result=%s version=%s",
        repo or "none",
        item,
        returns,
        result,
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


def log_review_extension(repo: str, item: int, round_: int, *, fixed: int, added: int) -> None:
    """Log one repair round of the model review past `roadmap.stage.verify_repair_rounds`: the
    last review marked `fixed` earlier findings `gone` and opened `added` new findings, fewer than
    it fixed (#5066, #5409). The review of the round logs its own `stage review round:` line."""
    logger.info(
        "stage review extended: repo=%s item=#%d round=%d fixed=%d added=%d version=%s",
        repo or "none",
        item,
        round_,
        fixed,
        added,
        __version__,
    )


def log_fix_plan_progress(
    repo: str, item: int, round_: int, *, open_: int, tokens: int, seconds: int, budget: int
) -> None:
    """Log one review of a fix-plan attempt (#5363): `round_` 0 is the review of the head and each
    later review adds 1, `open_` counts its open findings, `tokens` the input and output tokens of
    the plan runs and the review runs of the attempt so far, `seconds` the time since the step
    started, and `budget` the seconds of `roadmap.fix_plan.time_budget_seconds`. A pod that the
    deadline of its Job stops keeps these lines."""
    logger.info(
        "fix-plan progress: repo=%s item=#%d round=%d open=%d tokens=%d seconds=%d budget=%d "
        "version=%s",
        repo or "none",
        item,
        round_,
        open_,
        tokens,
        seconds,
        budget,
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
    "log_gate_extension",
    "log_gate_extension_end",
    "log_gate_findings",
    "log_gate_returns",
    "log_implement_attempt",
    "log_review_extension",
    "log_review_round",
]
