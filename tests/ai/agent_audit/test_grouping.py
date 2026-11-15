"""Tests of the model stage that groups the findings of the agent audit (#2346).

The stage sends the masked signature of each finding to one model of the `analysis` task and
attaches the groups that the model returns. The model edge is the `model_fake` of
`tests/support/fakes/model.py`, so no test reaches a network or a model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from devops_cli.ai.agent_audit.finding import Finding
    from tests.support.fakes.model import ModelFake

    TranscriptWriter = Callable[[Path, Sequence[Mapping[str, Any]]], Path]

# A token of the fixture transcript, which no request and no draft may hold.
_TOKEN = "ghp_1234567890abcdefghij"
# The group that the model answers for the failures of the fixture sessions.
_GROUP = "Test runs that fail on a changed workspace"
# A failure of a test run, as a signature reduces the line that the shell tool printed.
_SIGNATURE = "uv run devops ci test <path> | exit 1: failed <path>"


def _failed_call(command: str, output: str) -> list[dict[str, Any]]:
    """The two records of one failed shell call: the tool use and the result that answers it."""
    return [
        {
            "type": "assistant",
            "timestamp": "2026-01-01T00:00:00.000Z",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_01",
                        "name": "Bash",
                        "input": {"command": command},
                    }
                ],
            },
        },
        {
            "type": "user",
            "timestamp": "2026-01-01T00:00:01.000Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_01",
                        "is_error": True,
                        "content": output,
                    }
                ],
            },
        },
    ]


def _finding(signature: str, *, sessions: int = 1, recurrences: int = 1) -> Finding:
    """One finding, as `finding.py` gives it to the model stage."""
    from devops_cli.ai.agent_audit.finding import Finding

    return Finding(
        signature=signature,
        sessions=sessions,
        recurrences=recurrences,
        elapsed_seconds=0.0,
        pointers=(),
    )


def _grouped(model_fake: ModelFake, findings: Sequence[Finding]) -> tuple[Finding, ...]:
    """The findings with the group that `model_fake` answers for each of them."""
    from devops_cli.ai.agent_audit.grouping import (
        GroupedSignatures,
        GroupingReply,
        group_findings,
    )

    model_fake.answer(
        GroupingReply(
            groups=[
                GroupedSignatures(name=_GROUP, signatures=[each.signature for each in findings])
            ]
        )
    )
    return group_findings(findings)


def _fixture_findings(tmp_path: Path, transcript_writer: TranscriptWriter) -> tuple[Finding, ...]:
    """The findings of one fixture session whose failure holds a token, an email and a host."""
    from devops_cli.ai.agent_audit.finding import build_findings
    from devops_cli.ai.agent_audit.transcript import read_transcripts

    path = transcript_writer(
        tmp_path / "projects" / "example" / "session-a.jsonl",
        _failed_call(
            f"echo {_TOKEN}",
            "Exit code 1\nfatal: admin@example.com on build-box.internal",
        ),
    )
    return build_findings(read_transcripts([path]).calls)


def test_only_masked_signatures_reach_the_model(
    tmp_path: Path, transcript_writer: TranscriptWriter, model_fake: ModelFake
) -> None:
    """The request of the model stage holds the masked signature of each finding and no raw line
    of the transcript, and the group that the model returns reaches the finding (#2346)."""
    findings = _fixture_findings(tmp_path, transcript_writer)

    grouped = _grouped(model_fake, findings)

    request = model_fake.sent[0].prompt
    assert model_fake.factory_calls[0]["task"] == "analysis"
    assert model_fake.call_count == 1
    assert findings[0].signature in request
    assert "<masked-github-token>" in request
    assert "<masked-email>" in request
    assert "<masked-host>" in request
    assert _TOKEN not in request
    assert "admin@example.com" not in request
    assert "build-box.internal" not in request
    assert "fatal: admin@example.com on build-box.internal" not in request
    assert [each.group for each in grouped] == [_GROUP]


def test_the_report_holds_the_group_of_the_model(
    tmp_path: Path, transcript_writer: TranscriptWriter, model_fake: ModelFake
) -> None:
    """The group that the model returns reaches the report of the audit (#2346)."""
    from devops_cli.ai.agent_audit.report import render_report

    grouped = _grouped(model_fake, _fixture_findings(tmp_path, transcript_writer))

    payload = json.loads(render_report(grouped, "json"))

    assert [each["group"] for each in payload["findings"]] == [_GROUP]
    assert _GROUP in render_report(grouped)


def test_a_signature_that_no_finding_holds_is_left_ungrouped(model_fake: ModelFake) -> None:
    """A signature of the reply that no finding holds groups no finding, and a finding that no group
    names keeps no group (#2346)."""
    from devops_cli.ai.agent_audit.grouping import GroupedSignatures, GroupingReply, group_findings

    model_fake.answer(
        GroupingReply(
            groups=[
                GroupedSignatures(name=_GROUP, signatures=[_SIGNATURE]),
                GroupedSignatures(name="A signature of another run", signatures=["no such <path>"]),
            ]
        )
    )

    grouped = group_findings([_finding(_SIGNATURE), _finding("uv run ruff check <path>")])

    assert [each.group for each in grouped] == [_GROUP, None]


def test_a_run_with_no_finding_makes_no_call(model_fake: ModelFake) -> None:
    """A run that holds no finding asks no model, so a dry run of an empty audit opens no
    connection (#2346)."""
    from devops_cli.ai.agent_audit.grouping import group_findings

    grouped = group_findings([])

    assert grouped == ()
    assert model_fake.call_count == 0


def test_the_group_name_of_the_model_is_masked(model_fake: ModelFake) -> None:
    """A group name that holds a token reaches no finding, no report and no draft (#2346)."""
    from devops_cli.ai.agent_audit.grouping import (
        GroupedSignatures,
        GroupingReply,
        draft_body,
        group_findings,
        groups_of,
    )

    model_fake.answer(
        GroupingReply(
            groups=[GroupedSignatures(name=f"the {_TOKEN} token", signatures=[_SIGNATURE])]
        )
    )

    grouped = group_findings([_finding(_SIGNATURE)])
    body = draft_body(groups_of(grouped)[0])

    assert grouped[0].group == "the <masked-github-token> token"
    assert _TOKEN not in body
    assert "<masked-github-token>" in body


def test_the_groups_hold_their_findings_in_the_order_of_the_report() -> None:
    """The groups of a report hold the findings that each group names, and a finding that no group
    names belongs to none of them (#2346)."""
    from devops_cli.ai.agent_audit.finding import Finding
    from devops_cli.ai.agent_audit.grouping import groups_of

    first = Finding(
        signature=_SIGNATURE,
        sessions=3,
        recurrences=4,
        elapsed_seconds=0.0,
        pointers=(),
        group=_GROUP,
    )
    second = Finding(
        signature="uv run ruff check <path>",
        sessions=1,
        recurrences=2,
        elapsed_seconds=0.0,
        pointers=(),
        group=_GROUP,
    )
    ungrouped = _finding("uv run devops ci docs")

    groups = groups_of([first, second, ungrouped])

    assert [each.name for each in groups] == [_GROUP]
    assert groups[0].findings == (first, second)
    assert groups[0].sessions == 3
    assert groups[0].recurrences == 6


def test_the_draft_body_holds_the_sections_of_the_bug_report_template() -> None:
    """The draft of a group holds the sections of `.github/ISSUE_TEMPLATE/bug_report.yml`, its masked
    signature and its counts (#2346)."""
    from devops_cli.ai.agent_audit.grouping import FindingGroup, draft_body

    group = FindingGroup(
        name=_GROUP,
        findings=(_finding(_SIGNATURE, sessions=3, recurrences=4),),
    )

    body = draft_body(group)

    assert "### Problem Description" in body
    assert "### Reproduction Steps" in body
    assert "### Expected vs Actual Behavior" in body
    assert "### Logs, Traces, or Terminal Output" in body
    assert _GROUP in body
    assert _SIGNATURE in body
    assert "3 sessions" in body
    assert "4 runs" in body
