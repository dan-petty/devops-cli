"""Tests of the daily counts that the agent audit stores (#2346)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Sequence

    from devops_cli.ai.agent_audit.finding import Finding

_DAY = date(2026, 1, 2)
_SIGNATURE = "uv run devops ci test <path> | exit 1: failed <path>"


def _finding(
    sessions: Sequence[str],
    *,
    signature: str = _SIGNATURE,
    line: int = 2,
    recurrences: int | None = None,
) -> Finding:
    """One finding of `sessions`, with the pointer of a session file and line for each of them."""
    from devops_cli.ai.agent_audit.finding import Finding, Pointer

    return Finding(
        signature=signature,
        sessions=len(sessions),
        recurrences=len(sessions) if recurrences is None else recurrences,
        elapsed_seconds=0.0,
        pointers=tuple(
            Pointer(session=session, file=Path(f"{session}.jsonl"), line=line)
            for session in sessions
        ),
    )


def _stored(path: Path) -> dict[str, dict[str, Any]]:
    """The stored record of each signature of the counts file at `path`."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {record["signature"]: record for record in payload["signatures"]}


def test_a_second_run_keeps_the_count() -> None:
    """Two runs that read the same session files on one date leave the count of each signature as
    it was, so the stored counts do not grow with the number of runs (#2346)."""
    from devops_cli.ai.agent_audit.store import merge_counts, store_path

    path = store_path(_DAY)
    findings = [_finding(["session-a", "session-b", "session-c"])]

    merge_counts(path, findings)
    first = _stored(path)
    merge_counts(path, findings)
    second = _stored(path)

    assert second == first
    assert second[_SIGNATURE]["sessions"] == 3
    assert second[_SIGNATURE]["recurrences"] == 3
    assert len(second[_SIGNATURE]["pointers"]) == 3


def test_the_store_of_a_day_is_a_file_under_the_audit_store(isolate_data_dir: Path) -> None:
    """The counts of a day live in a file named by the date, under the store name `agent/audit` of
    the data directory (#2346)."""
    from devops_cli.ai.agent_audit.store import store_path

    path = store_path(_DAY)

    assert path.is_relative_to(isolate_data_dir)
    assert path.name == "2026-01-02.json"
    assert path.parent.parts[-2:] == ("agent", "audit")


def test_the_stored_counts_mask_a_secret_and_hold_no_raw_line() -> None:
    """A token, a private host name and an email address of a signature reach the counts file
    masked, and the file holds no raw line of a transcript (#2346, AGENTS.md rule 10)."""
    from devops_cli.ai.agent_audit.store import merge_counts, store_path

    path = store_path(_DAY)

    merge_counts(
        path,
        [
            _finding(
                ["session-a"],
                signature=(
                    "echo ghp_1234567890abcdefghij | exit 1: fatal on build-box.internal "
                    "for admin@example.com"
                ),
            )
        ],
    )

    text = path.read_text(encoding="utf-8")

    assert "<masked-github-token>" in text
    assert "<masked-host>" in text
    assert "<masked-email>" in text
    assert "ghp_" not in text
    assert "build-box.internal" not in text
    assert "admin@example.com" not in text


def test_a_session_that_the_store_does_not_hold_raises_the_count() -> None:
    """A run that meets a signature in a session that the store does not hold adds one recurrence,
    and it keeps the one that the store held (#2346)."""
    from devops_cli.ai.agent_audit.store import merge_counts, store_path

    path = store_path(_DAY)

    merge_counts(path, [_finding(["session-a"])])
    merge_counts(path, [_finding(["session-a", "session-b"])])

    record = _stored(path)[_SIGNATURE]

    assert record["sessions"] == 2
    assert record["recurrences"] == 2
    assert [pointer["session"] for pointer in record["pointers"]] == ["session-a", "session-b"]
    assert [pointer["line"] for pointer in record["pointers"]] == [2, 2]


def test_a_line_that_the_store_does_not_hold_raises_the_count() -> None:
    """A second run whose session meets the signature at another line adds a recurrence, because
    the store counts a session file and a line, not a run (#2346)."""
    from devops_cli.ai.agent_audit.store import merge_counts, store_path

    path = store_path(_DAY)

    merge_counts(path, [_finding(["session-a"], line=2)])
    merge_counts(path, [_finding(["session-a"], line=9)])

    record = _stored(path)[_SIGNATURE]

    assert record["sessions"] == 1
    assert record["recurrences"] == 2
    assert [pointer["line"] for pointer in record["pointers"]] == [2, 9]


def test_a_counts_file_that_the_audit_cannot_read_is_refused() -> None:
    """A counts file that holds no record the store wrote is refused rather than replaced, so a
    damaged file cannot erase the counts of the day (#2346)."""
    from devops_cli.ai.agent_audit.store import merge_counts, store_path
    from devops_cli.exceptions.validation import ValidationError

    path = store_path(_DAY)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"signatures": [{"signature": "unreadable"}]}', encoding="utf-8")

    with pytest.raises(ValidationError, match="stored agent audit counts"):
        merge_counts(path, [_finding(["session-a"])])

    assert "unreadable" in path.read_text(encoding="utf-8")
