"""Group the findings of the agent audit with one model, and draft the issue of a group (#2346).

A finding is one recurring problem of the agent sessions, counted across the sessions by
`finding.py`. Three failures of one broken command are one issue and not three, so the audit groups
the findings that share one cause. The grouping is the one job of the audit that needs a model: ADR
0005 keeps the counting, the ranking and the masking deterministic, and it gives the model the
judgment that a text comparison cannot make.

The model sees the masked signature of each finding and its counts, and nothing else: no line of a
transcript, no output, no path of the host and no secret (#2346, AGENTS.md rule 10). The stage makes
one `chat_structured` call for the whole run, so it holds one `devops ai` call at a time (AGENTS.md
rule 7), and no call at all when the run holds no finding. The groups that the reply names attach to
the findings, which `report.py` renders and `store.py` keeps.

`draft_body` writes the issue draft of one group in the structure of
`.github/ISSUE_TEMPLATE/bug_report.yml`, because a finding is a warning or a failed command and not
a new capability. The draft holds the masked signature and the counts of its group and no path of
the host that met the problem, because a transcript path below a home directory is private data
(#2346, AGENTS.md rule 10). The template's environment section is left out, because the audit reads
no environment of the host.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from devops_cli.ai.agent_audit.finding import Finding
from devops_cli.ai.agent_audit.transcript import sanitize_text

# The instruction to the model. It names the one job of the stage, the shape of its reply, and the
# rule that a signature comes back exactly as the request writes it, so a group attaches to a
# finding.
_SYSTEM_PROMPT = (
    "You group the recurring problems of the agent sessions of a software repository. Each finding "
    "holds the signature of a command or of a warning, the number of sessions that met it, and the "
    "number of its recurrences. A signature replaces each path and each number with a placeholder. "
    "Group the findings that share one cause into one group. Give each group a name of at most 60 "
    "characters that names the cause. Return each group with the signatures that it holds, copied "
    "exactly as the request writes them. Put a signature in at most one group, and leave out the "
    "signature that belongs to no other. Answer with the groups only."
)
# The headings of the issue draft, as the bug report template names its sections.
_DRAFT_PROBLEM = "### Problem Description"
_DRAFT_REPRODUCTION = "### Reproduction Steps"
_DRAFT_EXPECTED = "### Expected vs Actual Behavior"
_DRAFT_LOGS = "### Logs, Traces, or Terminal Output"


class GroupedSignatures(BaseModel):
    """One group of the reply: the name of a problem and the signatures that it holds."""

    model_config = ConfigDict(extra="forbid")

    name: str
    signatures: list[str]


class GroupingReply(BaseModel):
    """The model's reply to one request: the groups of the signatures that it was shown."""

    model_config = ConfigDict(extra="forbid")

    groups: list[GroupedSignatures]


class GroupingClient(Protocol):
    """What the grouping stage needs of `LLMClient`."""

    def chat_structured(
        self, system: str, prompt: str, schema: type[GroupingReply]
    ) -> GroupingReply: ...


@dataclass(frozen=True, slots=True)
class FindingGroup:
    """One group of the report: the name that the model gave it and the findings that it holds."""

    name: str
    findings: tuple[Finding, ...]

    @property
    def sessions(self) -> int:
        """The sessions of the group: the most that one of its findings met."""
        return max((each.sessions for each in self.findings), default=0)

    @property
    def recurrences(self) -> int:
        """The recurrences of the group: the runs of its findings together."""
        return sum(each.recurrences for each in self.findings)


def build_grouping_client() -> GroupingClient:
    """The model that groups the findings: the client of the `analysis` task of this checkout."""
    from devops_cli.ai.client import get_llm_client

    return get_llm_client(task="analysis")


def group_findings(
    findings: Sequence[Finding], client: GroupingClient | None = None
) -> tuple[Finding, ...]:
    """Each of `findings`, with the group that the model gave it (#2346).

    The stage makes one call for the whole run, and no call when the run holds no finding. A call
    that fails raises, so the command reports the failure rather than showing an ungrouped report as
    one that the model grouped.
    """
    if not findings:
        return tuple(findings)
    model = client if client is not None else build_grouping_client()
    reply = model.chat_structured(_SYSTEM_PROMPT, _request(findings), GroupingReply)
    names = _names_of(reply)
    return tuple(_with_group(each, names) for each in findings)


def groups_of(findings: Iterable[Finding]) -> tuple[FindingGroup, ...]:
    """The groups of `findings`, in the order that they appear, each with its findings.

    A finding that the model did not group belongs to no group, so the audit files no draft for it.
    """
    grouped: dict[str, list[Finding]] = {}
    for finding in findings:
        if not finding.group:
            continue
        grouped.setdefault(finding.group, []).append(finding)
    return tuple(FindingGroup(name=name, findings=tuple(each)) for name, each in grouped.items())


def draft_body(group: FindingGroup) -> str:
    """The body of the issue draft of `group`, in the structure of the bug report template (#2346).

    The draft names the masked signature and the counts of its group, and no path of the host that
    met the problem, so the audit files no private data (AGENTS.md rule 10).
    """
    name = sanitize_text(group.name)
    return (
        "\n\n".join(
            (
                _DRAFT_PROBLEM,
                _problem_text(name, group),
                _DRAFT_REPRODUCTION,
                _reproduction_text(group),
                _DRAFT_EXPECTED,
                _expected_text(group),
                _DRAFT_LOGS,
                _logs_text(group),
            )
        )
        + "\n"
    )


def _request(findings: Sequence[Finding]) -> str:
    """The user message of the call: the masked signature and the counts of each finding."""
    return json.dumps(
        {"findings": [_sent(each) for each in findings]}, ensure_ascii=False, indent=1
    )


def _sent(finding: Finding) -> dict[str, object]:
    """One finding as the model sees it: its masked signature and its counts, and nothing else."""
    return {
        "signature": sanitize_text(finding.signature),
        "sessions": finding.sessions,
        "recurrences": finding.recurrences,
    }


def _names_of(reply: GroupingReply) -> dict[str, str]:
    """The group name of each signature of `reply`, masked, with the first name that names it."""
    names: dict[str, str] = {}
    for group in reply.groups:
        name = sanitize_text(group.name)
        for signature in group.signatures:
            names.setdefault(sanitize_text(signature), name)
    return names


def _with_group(finding: Finding, names: Mapping[str, str]) -> Finding:
    """The finding with the group of its signature, or as it is when the reply names none."""
    name = names.get(finding.signature)
    return finding if name is None else replace(finding, group=name)


def _problem_text(name: str, group: FindingGroup) -> str:
    """The problem section: the group, the sessions that met it and the runs that it cost."""
    return (
        f"The agent sessions of this repository met one problem in {group.sessions} sessions, "
        f"over {group.recurrences} runs: {name}."
    )


def _reproduction_text(group: FindingGroup) -> str:
    """The reproduction section: one step for each signature of the group."""
    steps = [
        f"Run a command that matches `{sanitize_text(each.signature)}` in an agent session."
        for each in group.findings
    ]
    return "\n".join(f"{number}. {step}" for number, step in enumerate(steps, start=1))


def _expected_text(group: FindingGroup) -> str:
    """The section of what a run expects and what it met."""
    return (
        f"Expected: the problem does not return. Actual: the problem returns in {group.sessions} "
        f"sessions, over {group.recurrences} runs."
    )


def _logs_text(group: FindingGroup) -> str:
    """The logs section: a fenced block with the masked signature and the counts of each finding."""
    lines = [
        f"{sanitize_text(each.signature)}  (sessions: {each.sessions}, runs: {each.recurrences})"
        for each in group.findings
    ]
    return "\n".join(("```text", *lines, "```"))


__all__ = [
    "FindingGroup",
    "GroupedSignatures",
    "GroupingClient",
    "GroupingReply",
    "build_grouping_client",
    "draft_body",
    "group_findings",
    "groups_of",
]
