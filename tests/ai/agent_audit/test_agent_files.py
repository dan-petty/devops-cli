"""Tests of the reader of the files that agents write under `.data/agent/` (#2346)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


def _agent_file(path: Path, lines: Sequence[str]) -> Path:
    """Write `lines` as an agent file at `path`, and make the directory of it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return path


def test_a_line_that_names_a_failure_is_kept(tmp_path: Path) -> None:
    """A line of an agent file that names a warning or an error is one record, and a line that
    names no failure is none (#2346)."""
    from devops_cli.ai.agent_audit.agent_files import parse_agent_files

    agent = tmp_path / ".data" / "agent"
    path = _agent_file(
        agent / "logs" / "run.log",
        [
            "uv run pytest -q",
            "warning: the project environment path does not match",
            "3 passed",
        ],
    )

    records = parse_agent_files(agent)

    assert [record.command for record in records] == [
        "warning: the project environment path does not match"
    ]
    assert records[0].session == "logs/run.log"
    assert records[0].file == path
    assert records[0].line == 2
    assert records[0].is_error is False


def test_two_files_are_two_sessions(tmp_path: Path) -> None:
    """A failure that two agent files name counts for each of them, because the session of a line
    is the file that holds it (#2346)."""
    from devops_cli.ai.agent_audit.agent_files import parse_agent_files
    from devops_cli.ai.agent_audit.finding import build_findings

    agent = tmp_path / ".data" / "agent"
    _agent_file(agent / "one.log", ["error: the same failure"])
    _agent_file(agent / "two.md", ["error: the same failure"])

    records = parse_agent_files(agent)

    assert [record.session for record in records] == ["one.log", "two.md"]
    assert [(finding.sessions, finding.recurrences) for finding in build_findings(records)] == [
        (2, 2)
    ]


def test_a_secret_of_an_agent_file_is_masked(tmp_path: Path) -> None:
    """A secret of a kept line is masked before the record leaves the reader (#2346)."""
    from devops_cli.ai.agent_audit.agent_files import parse_agent_files

    agent = tmp_path / ".data" / "agent"
    _agent_file(agent / "notes.md", ["error: the token ghp_1234567890abcdefghij was refused"])

    command = parse_agent_files(agent)[0].command

    assert "<masked-github-token>" in command
    assert "ghp_" not in command


def test_a_directory_that_does_not_exist_gives_no_record(tmp_path: Path) -> None:
    """A repository whose agents wrote no file gives no record, and the audit goes on (#2346)."""
    from devops_cli.ai.agent_audit.agent_files import parse_agent_files

    assert parse_agent_files(tmp_path / ".data" / "agent") == ()
