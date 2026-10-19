"""Socratic inquiry and knowledge gap formulator for metacognitive task self-assessment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from devops_cli.ai.client import get_llm_client
from devops_cli.ai.research.models import (
    SocraticInquiryResult,
)
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.defaults import DEFAULT_AI_SOCRATIC_MAX_PROBES

_DEFAULT_SOCRATIC_SYSTEM = (
    "You are a metacognitive Socratic inquiry engine for software engineering tasks. "
    "Analyze the task to identify gaps, ambiguities, and underspecified contracts, "
    "and formulate concise, targeted clarifying questions and concrete code lookup instructions."
)


def _build_user_prompt(
    task: str,
    context: str | None = None,
    repo_root: Path | None = None,
    max_probes: int = DEFAULT_AI_SOCRATIC_MAX_PROBES,
) -> str:
    """Compose user prompt containing task, optional context, and probe constraints."""
    sections = [
        f"Task Description:\n{task}",
        f"Max Probes Constraint: Limit clarifying questions to at most {max_probes} "
        f"and code lookups to at most {max_probes}.",
    ]
    if context:
        sections.append(f"Context / Instructions:\n{context}")
    if repo_root:
        sections.append(f"Repository Root:\n{repo_root}")
    return "\n\n".join(sections)


def _bound_inquiry_result(
    result: SocraticInquiryResult,
    original_task: str,
    max_probes: int,
) -> SocraticInquiryResult:
    """Enforce bounded probe ceiling on questions and code lookup instructions."""
    bounded_questions = result.questions[:max_probes]
    bounded_lookups = result.lookups[:max_probes]
    return SocraticInquiryResult(
        task=original_task,
        summary=result.summary,
        gaps=result.gaps,
        questions=bounded_questions,
        lookups=bounded_lookups,
    )


def render_socratic_markdown(result: SocraticInquiryResult) -> str:
    """Render Socratic inquiry results as clean GitHub-flavored markdown."""
    lines: list[str] = [
        "# Socratic Inquiry & Knowledge Gap Analysis",
        "",
        f"**Task**: {result.task}",
        "",
    ]
    if result.summary:
        lines.extend(["## Metacognitive Summary", "", result.summary, ""])

    lines.extend(["## Knowledge Gaps & Ambiguities", ""])
    if not result.gaps:
        lines.extend(["*No knowledge gaps identified.*", ""])
    else:
        lines.extend(
            [
                "| Type | Description | Rationale |",
                "| :--- | :--- | :--- |",
            ]
        )
        for gap in result.gaps:
            desc = gap.description.replace("|", "\\|")
            rat = gap.rationale.replace("|", "\\|")
            lines.append(f"| `{gap.type}` | {desc} | {rat} |")
        lines.append("")

    lines.extend(["## Targeted Clarifying Questions", ""])
    if not result.questions:
        lines.extend(["*No clarifying questions required.*", ""])
    else:
        for idx, q in enumerate(result.questions, start=1):
            lines.extend(
                [
                    f"{idx}. **{q.question}**",
                    f"   - *Target Gap*: {q.target_gap}",
                    f"   - *Rationale*: {q.rationale}",
                ]
            )
        lines.append("")

    lines.extend(["## Concrete Code Lookup Instructions", ""])
    if not result.lookups:
        lines.extend(["*No code lookup instructions required.*", ""])
    else:
        for idx, lk in enumerate(result.lookups, start=1):
            lines.extend(
                [
                    f"{idx}. `{lk.target}` ({lk.lookup_type})",
                    f"   - *Target Gap*: {lk.target_gap}",
                    f"   - *Rationale*: {lk.rationale}",
                ]
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


class SocraticFormulator:
    """Metacognitive analyzer formulating knowledge gaps, questions, and lookups."""

    def __init__(
        self,
        client: Any | None = None,
        max_probes: int = DEFAULT_AI_SOCRATIC_MAX_PROBES,
    ) -> None:
        self.client = client
        self.max_probes = max_probes

    def formulate(
        self,
        task: str,
        context: str | None = None,
        repo_root: Path | None = None,
    ) -> SocraticInquiryResult:
        """Analyze task and context to formulate knowledge gaps and minimal probes."""
        stripped_task = task.strip()
        if not stripped_task:
            raise ValueError("Task description must not be empty.")

        client = self.client or get_llm_client(task="research")
        system_prompt = load_task_prompt("socratic_inquiry.md") or _DEFAULT_SOCRATIC_SYSTEM
        user_prompt = _build_user_prompt(
            stripped_task,
            context=context,
            repo_root=repo_root,
            max_probes=self.max_probes,
        )

        res = client.chat_structured(
            system=system_prompt,
            prompt=user_prompt,
            schema=SocraticInquiryResult,
        )
        return _bound_inquiry_result(res, stripped_task, self.max_probes)
