"""Tests of the cross-session findings that the agent audit counts (#2346)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.exceptions.validation import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from devops_cli.ai.agent_audit.transcript import ToolCall

    TranscriptWriter = Callable[[Path, Sequence[Mapping[str, Any]]], Path]


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


def _call(
    *,
    session: str,
    line: int,
    command: str,
    output: str = "",
    is_error: bool = False,
    timestamp: str = "2026-01-01T00:00:00.000Z",
) -> ToolCall:
    """One tool call of a session, as the transcript reader gives it."""
    from devops_cli.ai.agent_audit.transcript import ToolCall

    return ToolCall(
        session=session,
        file=Path(f"{session}.jsonl"),
        line=line,
        timestamp=timestamp,
        command=command,
        output=output,
        is_error=is_error,
    )


def _failed(
    *, session: str, line: int = 2, timestamp: str = "2026-01-01T00:00:00.000Z"
) -> ToolCall:
    """One failed test run of a session, which every fixture session meets in the same way."""
    return _call(
        session=session,
        line=line,
        timestamp=timestamp,
        command="uv run devops ci test tests/ai/test_x.py",
        output="Exit code 1\nFAILED tests/ai/test_x.py::test_y - assert 1 == 2",
        is_error=True,
    )


def test_one_finding_for_three_sessions(
    tmp_path: Path, transcript_writer: TranscriptWriter
) -> None:
    """Three sessions that meet one failure give one finding, with a count of 3 and a pointer for
    each session file (#2346)."""
    from devops_cli.ai.agent_audit.finding import build_findings
    from devops_cli.ai.agent_audit.transcript import read_transcripts

    project = tmp_path / "projects" / "example"
    paths = [
        transcript_writer(
            project / f"session-{name}.jsonl",
            _failed_call(
                "uv run devops ci test tests/ai/test_x.py",
                "Exit code 1\nFAILED tests/ai/test_x.py::test_y",
            ),
        )
        for name in ("a", "b", "c")
    ]

    findings = build_findings(read_transcripts(paths).calls)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.sessions == 3
    assert finding.recurrences == 3
    assert {pointer.file for pointer in finding.pointers} == set(paths)
    assert [pointer.session for pointer in finding.pointers] == [
        "session-a",
        "session-b",
        "session-c",
    ]


def test_a_session_that_meets_a_problem_twice_has_one_pointer() -> None:
    """A signature that one session met twice counts two recurrences and holds one pointer, so the
    session count does not grow with the number of runs (#2346)."""
    from devops_cli.ai.agent_audit.finding import build_findings

    findings = build_findings(
        [
            _failed(session="session-a", line=2),
            _failed(session="session-a", line=9),
        ]
    )

    assert len(findings) == 1
    assert findings[0].sessions == 1
    assert findings[0].recurrences == 2
    assert [(pointer.session, pointer.line) for pointer in findings[0].pointers] == [
        ("session-a", 2)
    ]


def test_two_different_failures_are_two_findings() -> None:
    """A failure of another exit status or another first error line is another problem, so it gets
    a finding of its own (#2346)."""
    from devops_cli.ai.agent_audit.finding import build_findings

    findings = build_findings(
        [
            _failed(session="session-a"),
            _call(
                session="session-b",
                line=2,
                command="uv run devops ci test tests/ai/test_x.py",
                output="Exit code 2\nno matches found: --include=*.py",
                is_error=True,
            ),
        ]
    )

    assert len(findings) == 2
    assert {finding.sessions for finding in findings} == {1}


def test_the_elapsed_time_spans_the_first_and_the_last_occurrence() -> None:
    """The elapsed time of a finding is the span over which it returned (#2346)."""
    from devops_cli.ai.agent_audit.finding import build_findings

    findings = build_findings(
        [
            _failed(session="session-a", timestamp="2026-01-01T00:00:00.000Z"),
            _failed(session="session-b", timestamp="2026-01-01T02:30:00.000Z"),
        ]
    )

    assert findings[0].elapsed_seconds == 2.5 * 3_600


def test_ranking_puts_a_finding_with_more_sessions_first() -> None:
    """A signature that three sessions met ranks above one that a single session met (#2346)."""
    from devops_cli.ai.agent_audit.finding import build_findings, rank_findings

    ranked = rank_findings(
        build_findings(
            [
                _failed(session="session-a"),
                _failed(session="session-b"),
                _failed(session="session-c"),
                _call(
                    session="session-d",
                    line=2,
                    command="uv run ruff check --include=src/",
                    output="Exit code 1\nno matches found",
                    is_error=True,
                ),
            ]
        )
    )

    assert [finding.sessions for finding in ranked] == [3, 1]
    assert ranked[0].signature.startswith("uv run devops ci test <path>")


def test_a_tie_of_sessions_is_broken_by_recurrences_then_by_time() -> None:
    """Two findings of one session count rank by recurrences, and two of the same count rank by the
    time over which they returned (#2346)."""
    from devops_cli.ai.agent_audit.finding import Finding, rank_findings

    def finding(signature: str, recurrences: int, elapsed: float) -> Finding:
        return Finding(
            signature=signature,
            sessions=2,
            recurrences=recurrences,
            elapsed_seconds=elapsed,
            pointers=(),
        )

    ranked = rank_findings(
        [
            finding("b", 2, 10.0),
            finding("a", 2, 60.0),
            finding("c", 5, 0.0),
        ]
    )

    assert [each.signature for each in ranked] == ["c", "a", "b"]


def test_the_json_report_holds_masked_text_and_each_pointer() -> None:
    """The report masks a token, an email address and a private host before it leaves the module,
    and it holds a pointer for each session (#2346)."""
    from devops_cli.ai.agent_audit.finding import build_findings
    from devops_cli.ai.agent_audit.report import render_report

    report = render_report(
        build_findings(
            [
                _call(
                    session=f"session-{name}",
                    line=2,
                    command="echo ghp_1234567890abcdefghij",
                    output="Exit code 1\nfatal: admin@example.com on build-box.internal",
                    is_error=True,
                )
                for name in ("a", "b", "c")
            ]
        ),
        "json",
    )

    payload = json.loads(report)
    assert len(payload["findings"]) == 1
    finding = payload["findings"][0]
    assert finding["sessions"] == 3
    assert "<masked-github-token>" in finding["signature"]
    assert "<masked-email>" in finding["signature"]
    assert "<masked-host>" in finding["signature"]
    assert [pointer["session"] for pointer in finding["pointers"]] == [
        "session-a",
        "session-b",
        "session-c",
    ]
    assert "ghp_" not in report
    assert "admin@example.com" not in report
    assert "build-box.internal" not in report


def test_the_table_report_names_each_finding_and_its_counts() -> None:
    """The table holds the counts, the elapsed time and the signature of a finding, and it says so
    when there is no finding (#2346)."""
    from devops_cli.ai.agent_audit.finding import Finding
    from devops_cli.ai.agent_audit.report import render_report

    finding = Finding(
        signature="uv run devops ci test <path> | exit 1: failed <path>",
        sessions=3,
        recurrences=4,
        elapsed_seconds=3_725.0,
        pointers=(),
    )

    report = render_report([finding])

    assert "Recurring problems" in report
    assert "SESSIONS" in report
    assert "1h 2m" in report
    assert finding.signature in report
    assert render_report([]) == "No recurring problem was found.\n"


def test_a_tracked_finding_renders_apart_from_the_new_ones() -> None:
    """A finding that an open issue names is not one of the new findings, and the report marks it
    as tracked (#2346)."""
    from devops_cli.ai.agent_audit.finding import Finding
    from devops_cli.ai.agent_audit.report import render_report

    tracked = Finding(
        signature="virtual_env does not match the project environment path",
        sessions=2,
        recurrences=2,
        elapsed_seconds=0.0,
        pointers=(),
        tracked=True,
    )
    fresh = Finding(
        signature="uv run devops ci test <path> | exit 1: failed <path>",
        sessions=1,
        recurrences=1,
        elapsed_seconds=0.0,
        pointers=(),
    )

    table = render_report([fresh, tracked])
    payload = json.loads(render_report([fresh, tracked], "json"))

    assert table.index("Recurring problems") < table.index("Tracked by an open issue")
    assert [each["signature"] for each in payload["findings"]] == [fresh.signature]
    assert [each["signature"] for each in payload["tracked"]] == [tracked.signature]


def test_the_report_holds_the_group_of_a_finding() -> None:
    """A finding that the model grouped shows its group in the table and in the JSON (#2346)."""
    from devops_cli.ai.agent_audit.finding import Finding
    from devops_cli.ai.agent_audit.report import render_report

    finding = Finding(
        signature="uv run devops ci test <path> | exit 1: failed <path>",
        sessions=2,
        recurrences=2,
        elapsed_seconds=0.0,
        pointers=(),
        group="Test runs that fail on a changed workspace",
    )

    table = render_report([finding])
    payload = json.loads(render_report([finding], "json"))

    assert "GROUP" in table
    assert "Test runs that fail on a changed workspace" in table
    assert payload["findings"][0]["group"] == "Test runs that fail on a changed workspace"


def test_an_unknown_report_format_is_refused() -> None:
    """A format that the report does not hold is refused rather than rendered as a table (#2346)."""
    from devops_cli.ai.agent_audit.report import render_report

    with pytest.raises(ValidationError, match="Unknown report format"):
        render_report([], "yaml")
