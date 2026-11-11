"""The verify screen: the decision point `stage.verify_screen` before the model review of a plan
(pilot 1 of the decision steps, #4282, ADR 0019, ADR 0020).

The model review (`stage_verify`) is an agent with read tools, and it runs for every plan. The
screen gives, before it runs, one of three bands:

- *continue*: no question of the screen reaches its cut, so the review may be skipped;
- *review*: a question reaches its `continue_below` cut, so the review runs as before;
- *flag*: a question reaches its `flag_at` cut, so the review runs and the record names the
  question.

The evidence is a digest that code builds from the input of the review: the criteria of the issue,
the groups of the plan, and the facts of tools about each group (the paths that the repository
does not hold, and whether the verify command names a test file of the group). One request asks
the nine closed yes/no questions of `QUESTIONS` about the digest. The cuts of each question are
fitted on the golden set and stored in `jev_screen_cuts.json` (`devops roadmap eval screen`).

The registry of decision points runs the screen (`decision_point`). Its mode is
`roadmap.decisions["stage.verify_screen"]`, and the decision model is `ai.decision_model`. With the
mode `off` or no decision model, the screen sends no request and the review runs. With `shadow`,
the review always runs, and the record of the decision and the record of the result of the review
share an identifier. With `on`, the band *continue* skips the review. Any error, timeout or missing
answer runs the review (fail open). The screen never rejects a plan and is no security control:
the text of a plan can mislead the decision model.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from pydantic_ai.models.decision import DecisionRequest, NoulQuestion

from devops_cli.config.constants import CONST_ROADMAP_STAGE_JEV_TIMEOUT_SECONDS
from devops_cli.roadmap.decision_point import (
    DecisionPoint,
    DecisionRecord,
    ResolverChain,
    chain_of,
    record_outcome,
)
from devops_cli.roadmap.decision_step import Band, Thresholds
from devops_cli.roadmap.stage.stage_criteria import acceptance_criteria

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic_ai.models.decision import DecisionModel

    from devops_cli.config.settings import Settings
    from devops_cli.roadmap.stage.stage_verify import VerificationInput

CUTS_FILE: Final[Path] = Path(__file__).with_name("jev_screen_cuts.json")
# The size limits of the pieces of the digest, in characters.
_CRITERION_CHARS: Final[int] = 300
_CLAIM_CHARS: Final[int] = 220
_TEST_CHARS: Final[int] = 220
_WORK_CHARS: Final[int] = 260
_MAX_CLAIMS: Final[int] = 6

QUESTIONS: Final[Mapping[str, str]] = {
    "missing_path": (
        "Does a group change or read a path that is not found in the repository, and no earlier "
        "group creates it?"
    ),
    "false_premise": (
        "Does the plan claim a fact about the code, a tool or the system that the files or the "
        "issue contradict, or that nothing in the input supports?"
    ),
    "spec_delta_wrong": (
        "Does the spec delta change a requirement that does not exist, add one that duplicates "
        "another, or have a scenario that no test can assert?"
    ),
    "verify_form": "Does the verify command of a group not run the tests or the work of that group?",
    "task_order": (
        "Does a task need the result of a later task, or does a test come after the code it tests "
        "in a group of new behavior?"
    ),
    "criterion_dropped": "Does an acceptance criterion have no group that delivers it?",
    "ignores_existing_code": (
        "Does the plan build code that the files already hold, or that a library of the project "
        "already covers?"
    ),
    "contrived_test": "Does a test only repeat the code, test a mock, or pass whatever the code does?",
    "other": "Does the plan have a defect that fits no other question?",
}


def _groups(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = plan.get("groups")
    return [group for group in raw if isinstance(group, Mapping)] if isinstance(raw, list) else []


def _strings(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _group_row(
    index: int, group: Mapping[str, Any], known: Collection[str], created: set[str]
) -> dict[str, Any]:
    """The digest row of one group. `created` holds the paths that the earlier groups create; this
    call adds the paths of this group."""
    changes, creates = _strings(group.get("changes")), _strings(group.get("creates"))
    missing = [
        path
        for path in _strings(group.get("reads")) + changes
        if path not in known and path not in created
    ]
    created.update(creates)
    tests = [path for path in changes + creates if "test" in path]
    verify = str(group.get("verify") or "")
    return {
        "n": index,
        "title": group.get("title"),
        "kind": group.get("kind"),
        "changes": changes,
        "creates": creates,
        "paths_not_found_in_repo": missing,
        "verify": verify,
        "verify_names_a_test_file_of_the_group": any(
            path in verify or path.rsplit("/", 1)[-1] in verify for path in tests
        ),
        "test_task": str(group.get("test") or "")[:_TEST_CHARS],
        "work": str(group.get("implementation") or "")[:_WORK_CHARS],
    }


def digest(given: VerificationInput, known: Collection[str]) -> dict[str, Any]:
    """The evidence of the screen: a short document that code builds from the input of the review.
    `known` holds the paths that the repository has."""
    plan = given.plan
    created: set[str] = set()
    specs = plan.get("specs")
    requirements = [
        str(requirement.get("name"))
        for spec in (specs if isinstance(specs, list) else [])
        if isinstance(spec, Mapping)
        for key in ("added", "modified")
        for requirement in (spec.get(key) or [])
        if isinstance(requirement, Mapping)
    ]
    return {
        "issue_title": given.title,
        "acceptance_criteria": [
            text[:_CRITERION_CHARS] for text in acceptance_criteria(given.body)
        ],
        "plan_summary": plan.get("summary"),
        "feasibility_claims": [text[:_CLAIM_CHARS] for text in _strings(plan.get("feasibility"))][
            :_MAX_CLAIMS
        ],
        "spec_requirements": requirements,
        "groups": [
            _group_row(index, group, known, created) for index, group in enumerate(_groups(plan))
        ],
    }


@dataclass(frozen=True)
class ScreenCase:
    """The input of the screen: the input of the review, and the paths of the repository."""

    given: VerificationInput
    known: Collection[str]


def _evidence(case: ScreenCase) -> dict[str, Any]:
    return digest(case.given, case.known)


VERIFY_SCREEN: Final[DecisionPoint[ScreenCase]] = DecisionPoint(
    name="stage.verify_screen",
    questions={name: NoulQuestion(instructions=text) for name, text in QUESTIONS.items()},
    evidence=_evidence,
    bands={
        Band.CONTINUE: "Skip the model review of the plan.",
        Band.REVIEW: "Run the model review of the plan.",
        Band.FLAG: "Run the model review, and name the questions at their flag cut in the record.",
    },
    cuts=CUTS_FILE,
    timeout=CONST_ROADMAP_STAGE_JEV_TIMEOUT_SECONDS,
)


def request_of(given: VerificationInput, known: Collection[str]) -> DecisionRequest:
    """The one request of the screen: the digest and the questions of `QUESTIONS`. A digest that
    holds a secret raises `DecisionStepError`, because the request leaves the cluster for the
    hosted model (SECURITY.md)."""
    return VERIFY_SCREEN.request(digest(given, known))


def cuts() -> Thresholds:
    """The fitted cuts of the screen, from the data file of the repository."""
    return VERIFY_SCREEN.thresholds()


def screen_of(
    settings: Settings, *, model: DecisionModel[Any] | None = None
) -> ResolverChain[ScreenCase] | None:
    """The resolver chain of the screen under `settings`, or None when the point does not run."""
    return chain_of(VERIFY_SCREEN, settings, model=model)


def record_review(decision: DecisionRecord, open_findings: Sequence[object]) -> None:
    """Write the outcome record of `decision`: the review found an open defect, or none."""
    record_outcome(
        decision,
        must_run=bool(open_findings),
        weight=len(open_findings),
        result="found" if open_findings else "clean",
    )


__all__ = [
    "CUTS_FILE",
    "QUESTIONS",
    "VERIFY_SCREEN",
    "ScreenCase",
    "cuts",
    "digest",
    "record_review",
    "request_of",
    "screen_of",
]
