"""Tests of the reader of the shell history of the agent audit (#2346)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


def _history(path: Path, lines: Sequence[str]) -> Path:
    """Write `lines` as the shell history at `path`."""
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return path


def test_an_extended_entry_names_its_command_and_its_time(tmp_path: Path) -> None:
    """An entry of the zsh extended format gives one command, with the time that its epoch names
    (#2346)."""
    from devops_cli.ai.agent_audit.shell import parse_shell_history

    path = _history(tmp_path / ".zsh_history", [": 1700000000:0;uv run pytest -q"])

    records = parse_shell_history(path)

    assert [record.command for record in records] == ["uv run pytest -q"]
    assert records[0].timestamp == "2023-11-14T22:13:20+00:00"
    assert records[0].line == 1
    assert records[0].session == ".zsh_history"
    assert records[0].file == path
    assert records[0].is_error is False


def test_a_line_without_the_extended_prefix_is_a_command(tmp_path: Path) -> None:
    """A history that the shell wrote without time gives one command for each line that holds one,
    and it keeps no timestamp (#2346)."""
    from devops_cli.ai.agent_audit.shell import parse_shell_history

    path = _history(
        tmp_path / ".zsh_history",
        ["git status", "", ": 1700000000:0;", "uv run ruff check src/"],
    )

    records = parse_shell_history(path)

    assert [record.command for record in records] == ["git status", "uv run ruff check src/"]
    assert [record.timestamp for record in records] == ["", ""]
    assert [record.line for record in records] == [1, 4]


def test_a_command_over_several_lines_is_one_record(tmp_path: Path) -> None:
    """zsh writes a command that the person typed over several lines with a backslash before each
    line break, and the audit counts it as the one command that it is (#2346)."""
    from devops_cli.ai.agent_audit.shell import parse_shell_history

    path = _history(
        tmp_path / ".zsh_history",
        [": 1700000000:0;uv run devops \\", "roadmap intake"],
    )

    records = parse_shell_history(path)

    assert [record.command for record in records] == ["uv run devops roadmap intake"]


def test_a_secret_and_a_private_host_are_masked(tmp_path: Path) -> None:
    """A secret and a private host of a history command are masked before the record leaves the
    reader (#2346)."""
    from devops_cli.ai.agent_audit.shell import parse_shell_history

    path = _history(
        tmp_path / ".zsh_history",
        [
            ': 1700000000:0;curl -H "Authorization: Bearer ghp_1234567890abcdefghij" '
            "http://192.168.1.10:8080/health"
        ],
    )

    command = parse_shell_history(path)[0].command

    assert "<masked-github-token>" in command
    assert "<masked-host>" in command
    assert "ghp_" not in command
    assert "192.168.1.10" not in command


def test_a_history_that_does_not_exist_gives_no_record(tmp_path: Path) -> None:
    """A person who keeps no history file gives no record, and the audit goes on (#2346)."""
    from devops_cli.ai.agent_audit.shell import parse_shell_history

    assert parse_shell_history(tmp_path / ".zsh_history") == ()
