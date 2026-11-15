"""Tests of the reader of the Claude Code session transcripts of the agent audit (#2346)."""

from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

    TranscriptWriter = Callable[[Path, Sequence[Mapping[str, Any]]], Path]


def _tool_use(
    command: str, *, call_id: str = "toolu_01", session_id: str = "session"
) -> dict[str, Any]:
    """An assistant record that calls a shell tool with `command`."""
    return {
        "type": "assistant",
        "sessionId": session_id,
        "timestamp": "2026-01-01T00:00:00.000Z",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": call_id,
                    "name": "Bash",
                    "input": {"command": command},
                }
            ],
        },
    }


def _tool_result(
    output: str, *, is_error: bool = False, call_id: str = "toolu_01"
) -> dict[str, Any]:
    """A user record that answers the call `call_id` with `output`."""
    return {
        "type": "user",
        "sessionId": "session",
        "timestamp": "2026-01-01T00:00:01.000Z",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": call_id,
                    "is_error": is_error,
                    "content": output,
                }
            ],
        },
    }


def test_unknown_record_type_does_not_stop_the_reader(tmp_path: Path) -> None:
    """A record of a type that the reader does not know is skipped and counted, and the call that
    follows it still reaches the scan (#2346)."""
    from devops_cli.ai.agent_audit.transcript import read_transcripts

    path = tmp_path / "projects" / "example" / "session-a.jsonl"
    path.parent.mkdir(parents=True)
    records: list[dict[str, Any]] = [
        {"type": "api-request-blob", "blob": "aGVsbG8="},
        {
            "type": "assistant",
            "sessionId": "session-a",
            "timestamp": "2026-01-01T00:00:00.000Z",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_01",
                        "name": "Bash",
                        "input": {"command": "uv run devops ci test tests/ai/test_x.py"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "sessionId": "session-a",
            "timestamp": "2026-01-01T00:00:02.000Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_01",
                        "is_error": True,
                        "content": "Exit code 1\nFAILED tests/ai/test_x.py::test_y",
                    }
                ],
            },
        },
    ]
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")

    scan = read_transcripts([path])

    assert scan.unknown_records == 1
    assert [call.command for call in scan.calls] == ["uv run devops ci test tests/ai/test_x.py"]
    assert scan.calls[0].output.startswith("Exit code 1")
    assert scan.calls[0].is_error is True
    assert scan.calls[0].session == "session-a"
    assert scan.calls[0].line == 2


def test_tokens_emails_and_private_hosts_are_masked(
    tmp_path: Path, transcript_writer: TranscriptWriter
) -> None:
    """A token, a private host name or address, and an email address of a kept line are masked
    before the call leaves the reader (#2346)."""
    from devops_cli.ai.agent_audit.transcript import read_transcripts

    path = transcript_writer(
        tmp_path / "projects" / "example" / "session-b.jsonl",
        [
            _tool_use(
                'curl -H "Authorization: Bearer ghp_1234567890abcdefghij" '
                "http://192.168.1.10:8080/health"
            ),
            _tool_result(
                "fatal: contact admin@example.com on build-box.internal\nExit code 7",
                is_error=True,
            ),
        ],
    )

    scan = read_transcripts([path])

    call = scan.calls[0]
    assert "<masked-github-token>" in call.command
    assert "<masked-host>" in call.command
    assert "ghp_" not in call.command
    assert "192.168.1.10" not in call.command
    assert "<masked-email>" in call.output
    assert "<masked-host>" in call.output
    assert "example.com" not in call.output
    assert "build-box.internal" not in call.output


def test_subagent_transcripts_roll_into_parent_session(
    tmp_path: Path, transcript_writer: TranscriptWriter
) -> None:
    """A transcript under `<session>/subagents/` counts for the session that started the
    subagent, whatever session its own records name (#2346)."""
    from devops_cli.ai.agent_audit.transcript import read_transcripts

    project = tmp_path / "projects" / "example"
    parent = transcript_writer(
        project / "session-c.jsonl",
        [_tool_use("uv run pytest -q"), _tool_result("Exit code 0")],
    )
    subagent = transcript_writer(
        project / "session-c" / "subagents" / "agent-01.jsonl",
        [
            _tool_use("uv run ruff check src/", session_id="agent-01"),
            _tool_result("Exit code 1", is_error=True),
        ],
    )

    scan = read_transcripts([parent, subagent])

    assert {call.session for call in scan.calls} == {"session-c"}
    assert [call.is_error for call in scan.calls] == [False, True]


def test_mtime_filter_skips_older_files(
    tmp_path: Path, transcript_writer: TranscriptWriter
) -> None:
    """A transcript that `since_days` leaves out is not opened (#2346)."""
    from devops_cli.ai.agent_audit.transcript import read_transcripts

    project = tmp_path / "projects" / "example"
    fresh = transcript_writer(
        project / "session-d.jsonl",
        [_tool_use("uv run pytest -q"), _tool_result("Exit code 0")],
    )
    old = transcript_writer(
        project / "session-e.jsonl",
        [_tool_use("uv run pytest -q"), _tool_result("Exit code 1", is_error=True)],
    )
    old_mtime = time.time() - 40 * 86_400
    os.utime(old, (old_mtime, old_mtime))

    scan = read_transcripts([fresh, old], since_days=30)

    assert scan.files_read == 1
    assert [call.file for call in scan.calls] == [fresh]
