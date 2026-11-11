"""The comparison of Jev with the triage model on intake's proposal fields (#4298).

Two sets of cases, the same for both models:

- the duplicate set of `duplicate_eval` (a candidate, the item it was compared with, and whether
  a person judged it a duplicate). False duplicates come first in the report: a false duplicate
  is worse than a missed one, and the setting `roadmap.intake.jev` stays off until Jev flags no
  more of them than the triage model.
- the label set (`intake_label_cases.json`): closed issues, each with the type, priority, Value
  and Effort that a person set. A model sees the title without its Conventional Commit prefix
  and the start of the body, no neighbour, and every `type/*` label of the checkout.

The run sends no GitHub request and no embedding request. A case that a model can't answer counts
as not agreed and is listed.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from importlib.resources import files

from pydantic import BaseModel, ConfigDict, TypeAdapter

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.commit_title import commit_summary
from devops_cli.roadmap.duplicate_eval import CaseText, DuplicateScore, Verdict
from devops_cli.roadmap.intake.intake_model import (
    IntakeModel,
    ModelProposal,
    ProposalRequest,
    UnusableProposalError,
)
from devops_cli.roadmap.title_labels import declared_label_specs
from devops_cli.roadmap.workflow_labels import WORKFLOW_TYPE_LABELS

# The label set, shipped with the package like the duplicate set.
LABEL_CASES = files("devops_cli.roadmap").joinpath("intake_label_cases.json")
LABEL_FIELDS = ("type", "priority", "value", "effort")


class Expected(BaseModel):
    """The values a person set on the issue."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: str
    priority: str
    value: str
    effort: str


class LabelCase(BaseModel):
    """One closed issue with the labels a person set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    source: str
    candidate: CaseText
    expected: Expected


@dataclass(frozen=True)
class LabelScore:
    """For each field, the cases whose value agrees with the person's, and the cases that a
    model could not answer."""

    cases: int
    agreed: dict[str, int] = field(default_factory=dict)
    failed: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelScores:
    """One model's score on both sets."""

    name: str
    duplicates: DuplicateScore
    labels: LabelScore


def load_label_cases() -> list[LabelCase]:
    """The cases of the label set."""
    raw = json.loads(LABEL_CASES.read_text(encoding="utf-8"))["cases"]
    return TypeAdapter(list[LabelCase]).validate_python(raw)


def _request(case: LabelCase, labels: str) -> ProposalRequest:
    specs = declared_label_specs(labels)
    types = WORKFLOW_TYPE_LABELS
    title = case.candidate.title
    return ProposalRequest(
        title=commit_summary(title) or title,
        body=case.candidate.body,
        shortlist=(),
        types=types,
        needs_type=True,
        type_notes=tuple((spec.name, spec.description) for spec in specs if spec.name in types),
    )


def _agrees(case: LabelCase, proposal: ModelProposal) -> dict[str, bool]:
    expected = case.expected
    return {
        "type": proposal.type == expected.type,
        "priority": proposal.priority == expected.priority,
        "value": proposal.value == expected.value,
        "effort": proposal.effort == expected.effort,
    }


def evaluate_labels(cases: Sequence[LabelCase], model: IntakeModel, labels: str) -> LabelScore:
    """Ask `model` for the proposal of each case, one at a time, and count the agreements."""
    agreed = dict.fromkeys(LABEL_FIELDS, 0)
    failed: list[str] = []
    for case in cases:
        try:
            proposal = model.propose(_request(case, labels))
        except UnusableProposalError:
            failed.append(case.name)
            continue
        for name, same in _agrees(case, proposal).items():
            agreed[name] += same
    return LabelScore(cases=len(cases), agreed=agreed, failed=tuple(failed))


def _ratio(part: int, whole: int) -> str:
    return f"{part}/{whole}"


def undecided(score: DuplicateScore) -> int:
    """The duplicate cases with no verdict of the model: intake skipped the candidate, as it does
    when a model has no usable proposal, or the case raised an error."""
    return score.failed + sum(result.verdict is Verdict.SKIPPED for result in score.results)


def jev_has_no_more_false_duplicates(scores: Sequence[ModelScores]) -> bool:
    """Whether the second score, Jev's, holds no more false duplicates than the first, and Jev
    decided every duplicate case. A case that Jev left to the fallback (a failed request, or a
    confidence below the least) has no Jev verdict, so a score with such a case is incomplete."""
    triage, jev = scores
    return (
        jev.duplicates.false_duplicates <= triage.duplicates.false_duplicates
        and undecided(jev.duplicates) == 0
    )


def render_comparison(
    scores: Sequence[ModelScores],
    *,
    duplicate_cases: int,
    label_cases: int,
    spend: str,
    least: float = 0.0,
) -> str:
    """The report: the false duplicates of each model first, then the duplicate score, the
    agreement of each label field and the verdict on the setting."""
    texts = MESSAGES.roadmap
    lines = [
        texts.jev_compare_title.format(duplicates=duplicate_cases, labels=label_cases),
        texts.jev_compare_least.format(least=least),
        "",
    ]
    lines.append(texts.jev_compare_duplicates_title)
    for score in scores:
        dup = score.duplicates
        lines.append(
            texts.jev_compare_duplicates_row.format(
                model=score.name,
                false=dup.false_duplicates,
                true=dup.true_duplicates,
                expected=dup.expected_duplicates,
                failed=undecided(dup),
            )
        )
    lines += ["", texts.jev_compare_labels_title]
    for score in scores:
        agreed = score.labels.agreed
        lines.append(
            texts.jev_compare_labels_row.format(
                model=score.name,
                **{name: _ratio(agreed[name], score.labels.cases) for name in LABEL_FIELDS},
                failed=len(score.labels.failed),
            )
        )
    triage, jev = scores
    if undecided(jev.duplicates):
        said = texts.jev_compare_verdict_incomplete.format(left=undecided(jev.duplicates))
    else:
        verdict = (
            texts.jev_compare_verdict_ok
            if jev_has_no_more_false_duplicates(scores)
            else texts.jev_compare_verdict_worse
        )
        said = verdict.format(
            triage=triage.duplicates.false_duplicates, jev=jev.duplicates.false_duplicates
        )
    lines += ["", spend, said]
    return "\n".join(lines) + "\n"


def render_dry_run(*, duplicate_cases: int, label_cases: int, gateway: str, limit: int) -> str:
    """The calls a run makes, making none."""
    texts = MESSAGES.roadmap
    calls = planned_calls(duplicate_cases, label_cases)
    return (
        texts.jev_compare_dry_run.format(
            gateway=gateway,
            duplicates=duplicate_cases,
            labels=label_cases,
            calls=calls,
            limit=limit,
        )
        + "\n"
    )


def planned_calls(duplicate_cases: int, label_cases: int) -> int:
    """The model calls of a run: one for each case and each of the two models."""
    return 2 * (duplicate_cases + label_cases)


__all__ = [
    "LABEL_CASES",
    "LabelCase",
    "LabelScore",
    "ModelScores",
    "evaluate_labels",
    "jev_has_no_more_false_duplicates",
    "load_label_cases",
    "planned_calls",
    "render_comparison",
    "render_dry_run",
]
