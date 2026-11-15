"""Tests of the sources that the agent audit reads, and of the source that it reads by
default (#2346)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from devops_cli.exceptions.validation import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path
    from typing import Any

    TranscriptWriter = Callable[[Path, Sequence[Mapping[str, Any]]], Path]


def _project_dir(home: Path, project: Path) -> Path:
    """The directory that Claude Code keeps the sessions of `project` in, under `home`.

    Claude Code names the directory of a project by its absolute path, with each character that
    is not a letter or a digit replaced by a hyphen (#2346).
    """
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(project.resolve()))
    return home / ".claude" / "projects" / slug


def _tool_call(command: str) -> list[dict[str, Any]]:
    """The two records of one shell tool call of a transcript: the call and the result that
    answers it."""
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
                        "is_error": False,
                        "content": "Exit code 0",
                    }
                ],
            },
        },
    ]


def _agent_file(path: Path) -> Path:
    """Write a short agent file at `path`, and make the directory of it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("warning: a check failed\n", encoding="utf-8")
    return path


def test_source_transcripts_returns_no_shell_path(
    tmp_path: Path, transcript_writer: TranscriptWriter
) -> None:
    """The transcript source returns the session files of the repository, and it returns no shell
    history, which is a source of its own (#2346)."""
    from devops_cli.ai.agent_audit.sources import SOURCE_TRANSCRIPTS, source_paths

    home = tmp_path / "home"
    repo = tmp_path / "repo"
    transcript = transcript_writer(
        _project_dir(home, repo) / "session-a.jsonl", _tool_call("uv run pytest -q")
    )
    history = home / ".zsh_history"
    history.write_text(": 1700000000:0;uv run pytest -q\n", encoding="utf-8")

    paths = source_paths(SOURCE_TRANSCRIPTS, repo, home)

    assert paths == (transcript,)
    assert history not in paths


def test_source_shell_returns_the_history_file(tmp_path: Path) -> None:
    """The shell source returns the zsh history of the home directory, and nothing when the
    person keeps none (#2346)."""
    from devops_cli.ai.agent_audit.sources import SOURCE_SHELL, source_paths

    home = tmp_path / "home"
    home.mkdir()
    repo = tmp_path / "repo"
    history = home / ".zsh_history"
    history.write_text(": 1700000000:0;uv run pytest -q\n", encoding="utf-8")

    assert source_paths(SOURCE_SHELL, repo, home) == (history,)
    history.unlink()

    assert source_paths(SOURCE_SHELL, repo, home) == ()


def test_source_agent_files_returns_the_files_below_the_agent_directory(tmp_path: Path) -> None:
    """The agent-file source returns each file of `.data/agent/`, and it returns neither the store
    of the audit nor a worktree, which the audit never reads (#2346)."""
    from devops_cli.ai.agent_audit.sources import SOURCE_AGENT_FILES, source_paths

    repo = tmp_path / "repo"
    note = _agent_file(repo / ".data" / "agent" / "logs" / "run.log")
    _agent_file(repo / ".data" / "agent" / "audit" / "2026-01-01.json")
    _agent_file(repo / ".data" / "agent" / "worktrees" / "w-2346" / "README.md")

    assert source_paths(SOURCE_AGENT_FILES, repo, tmp_path / "home") == (note,)


def test_the_default_source_is_the_transcripts() -> None:
    """A run that names no source reads the transcripts only (#2346)."""
    from devops_cli.ai.agent_audit.sources import (
        DEFAULT_SOURCE,
        SOURCE_TRANSCRIPTS,
        resolve_sources,
    )

    assert DEFAULT_SOURCE == SOURCE_TRANSCRIPTS
    assert resolve_sources(None) == (SOURCE_TRANSCRIPTS,)


def test_a_named_source_list_keeps_its_order() -> None:
    """A run that names sources reads each of them, in the order that it names them (#2346)."""
    from devops_cli.ai.agent_audit.sources import (
        SOURCE_AGENT_FILES,
        SOURCE_SHELL,
        resolve_sources,
    )

    assert resolve_sources("shell, agent-files") == (SOURCE_SHELL, SOURCE_AGENT_FILES)


def test_the_transcripts_of_a_worktree_are_read(
    tmp_path: Path, transcript_writer: TranscriptWriter
) -> None:
    """A session that runs in a worktree of the repository counts for the audit too, so the
    transcript source reads the project directory of each worktree (#2346)."""
    from devops_cli.ai.agent_audit.sources import SOURCE_TRANSCRIPTS, source_paths

    home = tmp_path / "home"
    repo = tmp_path / "repo"
    worktree = repo / ".data" / "agent" / "worktrees" / "w-2346"
    worktree.mkdir(parents=True)
    main = transcript_writer(
        _project_dir(home, repo) / "session-main.jsonl", _tool_call("uv run pytest -q")
    )
    branch = transcript_writer(
        _project_dir(home, worktree) / "session-branch.jsonl", _tool_call("git status")
    )

    assert source_paths(SOURCE_TRANSCRIPTS, repo, home) == (main, branch)


def test_a_source_that_the_audit_does_not_know_is_refused(tmp_path: Path) -> None:
    """A source name outside the closed set of sources is refused, and the error names the ones
    that the audit reads (#2346)."""
    from devops_cli.ai.agent_audit.sources import resolve_sources, source_paths

    with pytest.raises(ValidationError, match="gemini"):
        source_paths("gemini", tmp_path / "repo", tmp_path / "home")
    with pytest.raises(ValidationError, match="gemini"):
        resolve_sources("transcripts,gemini")


def test_read_sources_reads_each_named_source(
    tmp_path: Path, transcript_writer: TranscriptWriter
) -> None:
    """A run reads the records of each source that it names: a command of a transcript, of the
    shell history and of an agent file (#2346)."""
    from devops_cli.ai.agent_audit.sources import read_sources, resolve_sources

    home = tmp_path / "home"
    repo = tmp_path / "repo"
    transcript_writer(_project_dir(home, repo) / "session-a.jsonl", _tool_call("uv run pytest -q"))
    (home / ".zsh_history").write_text(": 1700000000:0;git status\n", encoding="utf-8")
    _agent_file(repo / ".data" / "agent" / "logs" / "run.log")

    records = read_sources(resolve_sources("transcripts,shell,agent-files"), repo, home)

    assert [record.command for record in records] == [
        "uv run pytest -q",
        "git status",
        "warning: a check failed",
    ]
