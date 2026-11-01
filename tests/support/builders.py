"""Builders of the objects tests make most often (#1312, #1307 Q20).

Each is a plain function whose keyword-only overrides replace its defaults, and whose defaults
make a valid object. Each builds through the type's own constructor, so an override the type
refuses raises the type's own error: pydantic's `ValidationError` for a model. A model builder
takes only the model's field names, so a typo or an alias such as `file=` raises `TypeError`
naming it. URLs are on `example.com`, and an Item's or a candidate's default URL follows its
number.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, overload

from pydantic import BaseModel

from devops_cli.ai.review.adjudication import Verdict
from devops_cli.ai.review_schema import Finding, SavedFinding
from devops_cli.config.constants import CONST_STATUS_VERIFIED
from devops_cli.review.report import ReportInput
from devops_cli.roadmap.stage_change import StageProposal
from devops_cli.roadmap.store import Candidate, Item, Milestone
from devops_cli.security.normalization import NormalizedFinding

_ISSUES_URL = "https://example.com/octo/repo/issues"

_FINDING: dict[str, Any] = {
    "severity": "HIGH",
    "location": "src/app.py:10",
    "title": "SQL injection in search",
    "description": "User input reaches the query unchecked.",
    "fix": "Bind the value as a query parameter.",
}

_NORMALIZED_FINDING: dict[str, Any] = {
    "tool": "bandit",
    "rule_id": "B602",
    "severity": "HIGH",
    "message": "subprocess call with shell=True",
    "path": "src/app.py",
    "line": 4,
}


@overload
def make_finding(*, saved: Literal[False] = False, **overrides: Any) -> Finding: ...


@overload
def make_finding(*, saved: Literal[True], **overrides: Any) -> SavedFinding: ...


@overload
def make_finding(*, saved: bool, **overrides: Any) -> Finding: ...


def make_finding(*, saved: bool = False, **overrides: Any) -> Finding:
    """A review finding with a severity, a location, a title, a description and a fix; with
    `saved`, the `SavedFinding` a review session writes."""
    return _validated(SavedFinding if saved else Finding, _FINDING, overrides)


def make_normalized_finding(**overrides: Any) -> NormalizedFinding:
    """A scanner finding as `security.normalization` gives it: bandit's B602 at `src/app.py:4`,
    severity HIGH."""
    return NormalizedFinding(**{**_NORMALIZED_FINDING, **overrides})


def make_verdict(**overrides: Any) -> Verdict:
    """A person's verdict on a finding: VERIFIED, with a reason."""
    return Verdict(**{"status": CONST_STATUS_VERIFIED, "reason": "Reproduced.", **overrides})


def make_item(**overrides: Any) -> Item:
    """An open Item, #1, with no fields set."""
    number = overrides.get("number", 1)
    defaults = {"number": number, "title": "An item", "url": f"{_ISSUES_URL}/{number}"}
    return _validated(Item, defaults, overrides)


def make_milestone(**overrides: Any) -> Milestone:
    """An open milestone, number 1, titled `2026-11-05`, with no due date."""
    return _validated(Milestone, {"number": 1, "title": "2026-11-05"}, overrides)


def make_candidate(**overrides: Any) -> Candidate:
    """An open issue with no priority label, #2, in no milestone."""
    number = overrides.get("number", 2)
    defaults = {"number": number, "title": "A candidate", "url": f"{_ISSUES_URL}/{number}"}
    return _validated(Candidate, defaults, overrides)


def make_report_input(**overrides: Any) -> ReportInput:
    """The report input of session `20261028-120000` with no finding, no dependency, no network
    reference and nothing from the run: no analyzer, no coverage, no history."""
    defaults: dict[str, Any] = {
        "session_id": "20261028-120000",
        "session_name": "20261028-120000",
        "generated_at": "2026-10-28T12:00:00+00:00",
        "report_path": Path("reviews/20261028-120000/review.md"),
        "findings_path": Path("reviews/20261028-120000/findings.json"),
        "reportable_findings": (),
    }
    return ReportInput(**{**defaults, **overrides})


_STAGE_PROPOSAL: dict[str, Any] = {
    "summary": "Stop the job dropping a comment",
    "pull_request_body": "The job keeps every comment it reads. It dropped the last one.",
    "why": "Issue #1: the job drops the last comment of a thread.",
    "what_changes": ["`src/devops_cli/sample.py` keeps the last comment."],
    "skip_specs": False,
    "feasibility": ["`src/devops_cli/sample.py` shows the fault at the first line."],
    "existing_tool": "The standard library covers the need, so the change builds no helper.",
    "decisions": [{"decision": "Keep the list", "reason": "It is the simplest fix."}],
    "rejected": [{"alternative": "A new class", "evidence": "The list already holds the data."}],
    "specs": [
        {
            "capability": "comment-thread",
            "purpose": "Defines how the job reads the comments of a thread, so none is lost.",
            "added": [
                {
                    "name": "The job keeps every comment",
                    "text": "The job SHALL keep every comment of a thread.",
                    "scenarios": [
                        {
                            "name": "The last comment",
                            "when": "a thread has two comments",
                            "then": "both comments are kept",
                        }
                    ],
                }
            ],
        }
    ],
    "groups": [
        {
            "title": "Keep the last comment",
            "kind": "behavior",
            "reads": ["src/devops_cli/sample.py"],
            "changes": ["src/devops_cli/sample.py", "tests/test_sample.py"],
            "creates": ["tests/test_sample.py"],
            "test": "Write `test_the_job_keeps_the_last_comment` in `tests/test_sample.py`",
            "implementation": "Keep the last comment in `src/devops_cli/sample.py`",
            "documentation": None,
            "verify": "uv run devops ci test tests/test_sample.py",
        }
    ],
}


def make_stage_proposal(**overrides: Any) -> StageProposal:
    """The model's plan of a change for the stage job: one group that reads and changes
    `src/devops_cli/sample.py` and creates `tests/test_sample.py`, and a spec delta that creates the capability `comment-thread`."""
    return _validated(StageProposal, _STAGE_PROPOSAL, overrides)


def _validated[ModelT: BaseModel](
    model: type[ModelT], defaults: dict[str, Any], overrides: dict[str, Any]
) -> ModelT:
    """`model` validated from `defaults` with `overrides` over them, refusing a key that is no
    field of `model` rather than letting validation drop it or read it as an alias."""
    unknown = sorted(overrides.keys() - model.model_fields.keys())
    if unknown:
        raise TypeError(f"{model.__name__} has no field named {', '.join(unknown)}")
    return model.model_validate({**defaults, **overrides})
