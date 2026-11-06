"""The review of refine's proposal for an item that a bot opened (#3502).

The Service App and the workflows of the repository open items that no person wrote, so refine
sets such an item Ready only when a review approves the issue and the proposal. The review is the
verification pass of the stage job (`stage_verify`) with the task slot `ai.tasks.verification`:
it gets the issue and the proposal with no tool, and an open finding, one of `JUDGE_OPEN_TYPES` or a
placeholder, that quotes a text of its input, refuses the item. A refusal keeps the item New and waits for
a body edit, and one comment lists each finding with its evidence. An approval is recorded in the
job record of the item (`RefineRecordKey.JUDGE`), and the stage job, the implement job and the
alternatives job take the item only with it.

The review is a model, so text in the item can mislead it: it is no security control. The login of
the author is (`trust`).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Final

from devops_cli.roadmap.body_hash import extract_section_and_outside
from devops_cli.roadmap.stage_eval_cases import DefectType
from devops_cli.roadmap.stage_verify import (
    OPEN_TYPES,
    VerificationInput,
    finding_line,
    open_findings,
    verify,
)
from devops_cli.roadmap.store import Item, JudgeVerdict, RefineRecordKey

if TYPE_CHECKING:
    from devops_cli.roadmap.refine import RefinementProposal
    from devops_cli.roadmap.stage import StageClient

# The open types of this review (#3039). A proposal of refine holds no task group and no verify
# command, so a `task_order`, a `verify_form` or a `criterion_dropped` finding on it is advice and
# refuses no item (#3448).
JUDGE_OPEN_TYPES: Final[frozenset[DefectType]] = OPEN_TYPES - {
    DefectType.TASK_ORDER,
    DefectType.VERIFY_FORM,
    DefectType.CRITERION_DROPPED,
}


def judge(
    client_of: Callable[[], StageClient],
    item: Item,
    body: str,
    proposal: RefinementProposal,
    source: Path,
    *,
    unchanged: bool,
) -> tuple[JudgeVerdict, tuple[str, ...]]:
    """The verdict on `proposal` for `item`, and the lines of the open findings that refuse it.

    `body` is the body that refine read. An item that the review approved before, and whose body is
    `unchanged` since, keeps its approval with no model call: the review looks again only after the
    body changes. `client_of` makes the client of the verification task, only when a call is made.
    """
    if unchanged and item.job_record.get(RefineRecordKey.JUDGE) == JudgeVerdict.APPROVED.value:
        return JudgeVerdict.APPROVED, ()
    given = VerificationInput.of(
        number=item.number,
        title=item.title,
        body=extract_section_and_outside(body)[0],
        plan=proposal.model_dump(mode="json"),
        source=source,
    )
    findings = open_findings(verify(client_of(), given), given, types=JUDGE_OPEN_TYPES)
    if not findings:
        return JudgeVerdict.APPROVED, ()
    return JudgeVerdict.REFUSED, tuple(finding_line(f).removeprefix("- ") for f in findings)
