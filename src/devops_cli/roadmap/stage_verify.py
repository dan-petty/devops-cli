"""The verification pass of the stage job: a model reads the plan before the draft opens (#3153).

The deterministic gates of the job (`check_proposal`, `openspec validate`) judge the shape of a
plan and its paths. A reviewer also finds false premises, code that already exists and tests that
prove nothing. The pass sends the issue, the plan and the start of each file that the plan cites
to the model of the task slot `ai.tasks.verification`, and gets findings of the nine defect types
of the golden set (`stage_eval_cases.DefectType`). A reply with another type fails the schema, and
`chat_structured` sends it back once.

A finding of type `missing_path`, `false_premise` or `ignores_existing_code` whose `quote` is a
text of the input (`VerificationInput.contains`) returns the plan to the planner once. An open
finding keeps the plan from staging as clean: a finding of an open type, or one that reports a
placeholder, keeps the plan in draft with the label `plan/needs-fix` (#3264). Every other
finding is advice: the job lists it in its comment. The pass never merges and never marks a
pull request ready. `devops roadmap eval verify` scores the pass on the golden set
(`stage_verify_eval`).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.context_budget import truncate_to_token_limit
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_VERIFY_BODY_MAX_TOKENS,
    CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS,
    CONST_ROADMAP_STAGE_VERIFY_MAX_FILES,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.pull_form import is_placeholder
from devops_cli.roadmap.stage_change import safe_text
from devops_cli.roadmap.stage_eval_cases import DefectType
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from devops_cli.roadmap.stage import StageClient

_VERIFY_TASK: Final[str] = "roadmap_stage_verify.md"
# A reply that fails the schema goes back to the model once, as every reply of the stage job does.
_REPLY_RETURNS: Final[int] = 1
# The types that return the plan to the planner when a finding quotes its evidence.
RETURN_TYPES: Final[frozenset[DefectType]] = frozenset(
    {DefectType.MISSING_PATH, DefectType.FALSE_PREMISE, DefectType.IGNORES_EXISTING_CODE}
)
# The types that keep the plan in draft when a finding quotes its evidence. `spec_delta_wrong`
# joins the return types, and a finding that reports a placeholder joins them all (#3264).
OPEN_TYPES: Final[frozenset[DefectType]] = RETURN_TYPES | {DefectType.SPEC_DELTA_WRONG}
# The label of a plan pull request with an open finding (#3264).
PLAN_NEEDS_FIX_LABEL: Final[str] = "plan/needs-fix"
# The keys of a group of the plan that name files.
_FILE_KEYS: Final[tuple[str, ...]] = ("reads", "changes")


class Finding(BaseModel):
    """One defect that the model found in a plan. `quote` is a text of the issue, the plan or a
    cited file that shows the defect, or empty when no text shows it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: DefectType
    where: str = Field(min_length=1)
    problem: str = Field(min_length=1)
    quote: str = ""


class Verification(BaseModel):
    """The reply of the pass: the findings, none for a plan with no defect."""

    model_config = ConfigDict(extra="forbid")

    findings: list[Finding] = Field(default_factory=list)


def _folded(text: str) -> str:
    """`text` with each run of white space as one space, so a quote survives a line break."""
    return " ".join(text.split())


def _strings(value: Any) -> Iterator[str]:
    """Every text in a JSON value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, Sequence):
        for item in value:
            yield from _strings(item)


def cited_paths(plan: Mapping[str, Any]) -> list[str]:
    """The paths that the groups of `plan` read or change, each once, in plan order. A plan that
    is not well formed names fewer paths, never fails."""
    groups = plan.get("groups")
    found: dict[str, None] = {}
    for group in groups if isinstance(groups, list) else ():
        for key in _FILE_KEYS:
            names = group.get(key) if isinstance(group, Mapping) else None
            found.update(dict.fromkeys(name for name in names or () if isinstance(name, str)))
    return list(found)


def _read(root: Path, name: str) -> str | None:
    """The start of file `name` of the checkout, with a secret masked, or None when it is no file inside
    the checkout."""
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    return mask_secrets(truncate_to_token_limit(text, CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS))


def cited_files(source: Path, plan: Mapping[str, Any]) -> dict[str, str]:
    """The start of each file that `plan` cites and the checkout `source` has, at most
    `CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` of them. A path that is no file inside the checkout is
    left out: the gates judge a missing path."""
    root = source.resolve()
    files: dict[str, str] = {}
    for name in cited_paths(plan):
        if len(files) == CONST_ROADMAP_STAGE_VERIFY_MAX_FILES:
            break
        text = _read(root, name)
        if text is not None:
            files[name] = text
    return files


@dataclass(frozen=True)
class VerificationInput:
    """What the model reads: the issue, the plan and the cited files."""

    number: int
    title: str
    body: str
    plan: Mapping[str, Any]
    files: Mapping[str, str]

    @classmethod
    def of(
        cls, *, number: int, title: str, body: str, plan: Mapping[str, Any], source: Path
    ) -> VerificationInput:
        """The input for `plan` of issue `number`, with the cited files read from `source`."""
        return cls(
            number,
            title,
            truncate_to_token_limit(body, CONST_ROADMAP_STAGE_VERIFY_BODY_MAX_TOKENS),
            plan,
            cited_files(source, plan),
        )

    def payload(self) -> dict[str, Any]:
        """The request as the JSON document that the prompt describes."""
        return {
            "number": self.number,
            "title": self.title,
            "body": self.body,
            "plan": dict(self.plan),
            "files": dict(self.files),
        }

    def texts(self) -> Iterable[str]:
        """The texts that a quote may come from."""
        yield from (self.title, self.body)
        yield from _strings(self.plan)
        yield from self.files.values()

    def contains(self, quote: str) -> bool:
        """Whether `quote`, with white space folded, is in a text of the input. An empty quote is
        in none."""
        wanted = _folded(quote)
        return bool(wanted) and any(wanted in _folded(text) for text in self.texts())


def verify(client: StageClient, given: VerificationInput) -> list[Finding]:
    """The findings of the model for `given`. A reply that fails the schema, such as a finding of
    an unknown type, goes back once, and a second one raises `StructuredOutputValidationError`."""
    reply = client.chat_structured(
        load_task_prompt(_VERIFY_TASK),
        json.dumps(given.payload(), ensure_ascii=False, indent=1),
        Verification,
        max_retries=_REPLY_RETURNS,
    )
    return list(reply.findings)


def returning(findings: Sequence[Finding], given: VerificationInput) -> list[Finding]:
    """The findings that return the plan to the planner: a type of `RETURN_TYPES` and a quote
    that is in the input."""
    return [f for f in findings if f.type in RETURN_TYPES and given.contains(f.quote)]


def _reports_placeholder(finding: Finding) -> bool:
    """Whether the quote of `finding` is a placeholder text, such as `placeholder` or `x`."""
    return is_placeholder(finding.quote)


def open_findings(findings: Sequence[Finding], given: VerificationInput) -> list[Finding]:
    """The findings that keep the plan in draft: a type of `OPEN_TYPES` or a placeholder, and a
    quote that is in the input (#3264). A finding without such a quote is advice."""
    return [
        f
        for f in findings
        if (f.type in OPEN_TYPES or _reports_placeholder(f)) and given.contains(f.quote)
    ]


def finding_line(finding: Finding) -> str:
    """The line that lists `finding` in a comment: its type, place and problem, and its quote with
    the secrets and the markup of the model's text made safe."""
    quote = (
        MESSAGES.roadmap.stage_finding_quote.format(quote=safe_text(finding.quote))
        if finding.quote.strip()
        else ""
    )
    return MESSAGES.roadmap.stage_finding.format(
        type=finding.type.value,
        where=safe_text(finding.where),
        problem=safe_text(finding.problem),
        quote=quote,
    )


def return_problem(findings: Sequence[Finding]) -> str:
    """The `problem` that sends the plan back to the planner: one line for each finding."""
    lines = "\n".join(finding_line(finding) for finding in findings)
    return MESSAGES.roadmap.stage_verify_return.format(findings=lines)


def findings_section(findings: Sequence[Finding]) -> str:
    """The section of the comment of the job that lists `findings`, or an empty text for none."""
    if not findings:
        return ""
    lines = "\n".join(finding_line(finding) for finding in findings)
    return MESSAGES.roadmap.stage_comment_findings.format(findings=lines)


def open_findings_section(findings: Sequence[Finding]) -> str:
    """The section of the comment that lists the open `findings` first, or an empty text for
    none (#3264)."""
    if not findings:
        return ""
    lines = "\n".join(finding_line(finding) for finding in findings)
    return MESSAGES.roadmap.stage_comment_open_findings.format(findings=lines)


__all__ = [
    "OPEN_TYPES",
    "PLAN_NEEDS_FIX_LABEL",
    "RETURN_TYPES",
    "Finding",
    "Verification",
    "VerificationInput",
    "cited_files",
    "cited_paths",
    "finding_line",
    "findings_section",
    "open_findings",
    "open_findings_section",
    "return_problem",
    "returning",
    "verify",
]
