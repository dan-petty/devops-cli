"""Plan amendment (#3057): parse an agent's request and judge whether to apply it."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_REASON_CHARS
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement_shell_policy import (
    IMPLEMENT_ALLOWED_PROGRAMS,
    verification_problem,
)
from devops_cli.roadmap.stage_form import is_valid_verify
from devops_cli.roadmap.stage_paths import StagedTree
from devops_cli.roadmap.step_files import (
    MARKDOWN,
    TaskGroup,
    parse_task_groups,
)
from devops_cli.security.sanitizer import mask_secrets

Kind = Literal["path", "command", "task", "premise", "scope"]


class PlanRequest(BaseModel):
    """The request an agent sends in a fenced block to amend the plan."""

    model_config = ConfigDict(extra="forbid")

    kind: Kind
    group: int
    defect: str
    evidence: str
    old: str | None = None
    new: str | None = None
    verify: str | None = None


@dataclass(frozen=True)
class Amendment:
    """An amendment applied to the plan."""

    group: int
    kind: str
    defect: str
    evidence: str
    old: str = ""
    new: str = ""

    def bullet(self) -> str:
        """The plain bullet for the ## Amendments section of tasks.md."""
        texts = MESSAGES.roadmap
        change = f"`{self.old}` -> `{self.new}`" if self.old else f"`{self.new}`"
        raw = texts.implement_amend_bullet.format(
            group=self.group,
            kind=self.kind,
            defect=self.defect,
            evidence=self.evidence,
            change=change,
        )
        masked = mask_secrets(raw)
        one_line = " ".join(masked.split())
        return one_line[:CONST_ROADMAP_IMPLEMENT_REASON_CHARS]

    def line(self) -> str:
        """One line for the pull request comment."""
        texts = MESSAGES.roadmap
        change = f"`{self.old}` -> `{self.new}`" if self.old else f"`{self.new}`"
        return texts.implement_amend_comment_line.format(
            group=self.group,
            kind=self.kind,
            defect=self.defect,
            evidence=self.evidence,
            change=change,
        )


@dataclass(frozen=True)
class Applied:
    """The amendment was applied to tasks.md."""

    tasks_md: str
    amendment: Amendment


@dataclass(frozen=True)
class Refused:
    """The amendment was refused with a reason."""

    reason: str
    request: PlanRequest | None = None


def parse_request(message: str) -> PlanRequest | None:
    """The plan request in the last message of a step, or None.

    The request must be in a fenced code block with info 'plan-request' that ends the message.
    """
    tokens = MARKDOWN.parse(message)
    if not tokens:
        return None
    last = tokens[-1]
    if last.type != "fence" or last.info.strip() != "plan-request":
        return None
    try:
        data = json.loads(last.content)
        if not isinstance(data, dict):
            return None
        return PlanRequest.model_validate(data)
    except ValueError, ValidationError:
        return None


def _spans_in(text: str) -> set[str]:
    """The code spans of `text`."""
    tokens = MARKDOWN.parse(text)
    return {
        child.content
        for token in tokens
        if token.type == "inline" and token.children
        for child in token.children
        if child.type == "code_inline"
    }


def _replace_in_code_spans(text: str, old: str, new: str) -> str:
    """Replace `old` with `new` inside every code span of `text`."""
    return re.sub(
        r"`([^`]+)`",
        lambda m: f"`{m.group(1).replace(old, new)}`",
        text,
    )


def _judge_path(
    request: PlanRequest, target: TaskGroup, tree: StagedTree
) -> tuple[str, Amendment] | Refused:
    texts = MESSAGES.roadmap
    if not request.old or not request.new:
        return Refused(texts.implement_amend_refused_path_status, request=request)
    if PurePosixPath(request.new).name != PurePosixPath(request.old).name:
        return Refused(texts.implement_amend_refused_path_name, request=request)
    if request.old in tree.files or request.new not in tree.files:
        return Refused(texts.implement_amend_refused_path_status, request=request)
    for line in target.text.splitlines():
        if "Changes:" in line and (
            f"`{request.old}` (new)" in line or f"{request.old} (new)" in line
        ):
            return Refused(texts.implement_amend_refused_path_status, request=request)

    new_text = _replace_in_code_spans(target.text, request.old, request.new)
    amendment = Amendment(
        group=request.group,
        kind="path",
        defect=request.defect,
        evidence=request.evidence,
        old=request.old,
        new=request.new,
    )
    return new_text, amendment


def _judge_command(
    request: PlanRequest, target: TaskGroup, tree: StagedTree
) -> tuple[str, Amendment] | Refused:
    texts = MESSAGES.roadmap
    if not request.old or not request.new:
        return Refused(texts.implement_amend_refused_command_form, request=request)
    if request.old not in target.verification_commands or not is_valid_verify(request.new):
        return Refused(texts.implement_amend_refused_command_form, request=request)
    words = request.new.split()
    if not words or words[0] not in IMPLEMENT_ALLOWED_PROGRAMS:
        return Refused(texts.implement_amend_refused_command_form, request=request)
    if verification_problem(request.new) is not None:
        return Refused(texts.implement_amend_refused_command_form, request=request)
    if tree.paths_in(request.old) != tree.paths_in(request.new):
        return Refused(texts.implement_amend_refused_command_paths, request=request)

    new_text = _replace_in_code_spans(target.text, request.old, request.new)
    amendment = Amendment(
        group=request.group,
        kind="command",
        defect=request.defect,
        evidence=request.evidence,
        old=request.old,
        new=request.new,
    )
    return new_text, amendment


def _judge_task(request: PlanRequest, target: TaskGroup) -> tuple[str, Amendment] | Refused:
    texts = MESSAGES.roadmap
    if not request.new:
        return Refused(texts.implement_amend_refused_command_form, request=request)
    if request.verify:
        if not is_valid_verify(request.verify):
            return Refused(texts.implement_amend_refused_command_form, request=request)
        words = request.verify.split()
        if not words or words[0] not in IMPLEMENT_ALLOWED_PROGRAMS:
            return Refused(texts.implement_amend_refused_command_form, request=request)
        if verification_problem(request.verify) is not None:
            return Refused(texts.implement_amend_refused_command_form, request=request)

    task_num = f"{target.number}.{len(target.tasks) + 1}"
    task_lines = [f"- [ ] {task_num} {request.new}"]
    if request.verify:
        task_lines.append(f"  - Verification: `{request.verify}`")
    task_block = "\n".join(task_lines)
    new_text = target.text.rstrip() + f"\n{task_block}\n\n"
    amendment = Amendment(
        group=request.group,
        kind="task",
        defect=request.defect,
        evidence=request.evidence,
        old="",
        new=request.new,
    )
    return new_text, amendment


def _record_amendment(tasks_md: str, bullet: str) -> str:
    """Add the amendment bullet to the ## Amendments section of tasks.md."""
    if "## Amendments" in tasks_md:
        idx = tasks_md.index("## Amendments")
        next_header_idx = tasks_md.find("\n## ", idx + len("## Amendments"))
        if next_header_idx != -1:
            return (
                f"{tasks_md[:next_header_idx].rstrip()}\n{bullet}\n\n"
                f"{tasks_md[next_header_idx:].lstrip()}"
            )
        return f"{tasks_md.rstrip()}\n{bullet}\n"
    if "## Workflow follow-up" in tasks_md:
        idx = tasks_md.index("## Workflow follow-up")
        return f"{tasks_md[:idx].rstrip()}\n\n## Amendments\n\n{bullet}\n\n{tasks_md[idx:]}"
    return f"{tasks_md.rstrip()}\n\n## Amendments\n\n{bullet}\n"


def judge(request: PlanRequest, tasks_md: str, tree: StagedTree) -> Applied | Refused:
    """Judge a plan amendment request against the repository tree and tasks.md."""
    texts = MESSAGES.roadmap
    if request.kind == "scope":
        return Refused(texts.implement_amend_refused_scope, request=request)
    if request.kind == "premise":
        return Refused(texts.implement_amend_refused_premise, request=request)

    groups = parse_task_groups(tasks_md)
    target = next((g for g in groups if g.number == request.group), None)
    if target is None:
        return Refused(
            texts.implement_amend_refused_no_group.format(group=request.group), request=request
        )

    if target.tasks and all(task.ticked for task in target.tasks):
        return Refused(
            texts.implement_amend_refused_done.format(group=request.group), request=request
        )

    group_spans = _spans_in(target.text)
    if request.old is not None and not any(request.old in span for span in group_spans):
        return Refused(texts.implement_amend_refused_criteria, request=request)

    match request.kind:
        case "path":
            result = _judge_path(request, target, tree)
        case "command":
            result = _judge_command(request, target, tree)
        case "task":
            result = _judge_task(request, target)
        case _:
            return Refused(texts.implement_amend_refused_scope, request=request)

    if isinstance(result, Refused):
        return result

    new_target_text, amendment = result
    new_md = tasks_md.replace(target.text, new_target_text, 1)
    new_md = _record_amendment(new_md, amendment.bullet())
    return Applied(tasks_md=new_md, amendment=amendment)
