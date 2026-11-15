"""Read the files that agents write under `.data/agent/` for the problems that they name (#2346).

An agent writes its logs, its notes and its bodies under `.data/agent/`. Such a file holds no tool
result, so the audit cannot read an exit status from it: it keeps each line that names a failure,
which is the line of a warning or of an error that the agent met, and it counts that line as the
problem. The session of such a line is the path of its file below the directory, so two files count
as two sessions.

The directory holds two trees that the audit never reads: `worktrees/`, which is a checkout of the
repository rather than a file that an agent wrote, and `audit/`, which is the store of this audit.
A file that the OS refuses to read gives no record, because the audit reports the problems of the
sessions and not the permissions of the host.

Each kept line passes through `sanitize_text`, so a secret, a private host name and an email address
never reach the report, the store or a model (#2346, AGENTS.md rule 10).
"""

from __future__ import annotations

import re
from pathlib import Path

from devops_cli.ai.agent_audit.transcript import ToolCall, sanitize_text

# The directory that the agents of this repository write to.
AGENT_DIR = Path() / ".data" / "agent"
# The trees below `AGENT_DIR` that hold no file of an agent: the checkouts of the worktrees, and
# the store of the counts of this audit.
_SKIPPED_DIRS: tuple[str, ...] = ("audit", "worktrees")
# The words that name a failure on the line of a log, a note or a body. A word must stand whole, so
# a longer word that holds one of them, such as `terraformed`, names no failure.
_FAILURE_RE = re.compile(
    r"\b(?:error|errors|failed|failure|fatal|traceback|warning|warnings)\b", re.IGNORECASE
)
# A log of an agent can grow large, and the audit reads within the time budget of a check (AGENTS.md
# rule 5), so it reads the start of each file and no more.
_MAX_BYTES = 1024 * 1024


def agent_file_paths(agent_dir: Path) -> tuple[Path, ...]:
    """Each file below `agent_dir` that the audit reads, in path order (#2346)."""
    if not agent_dir.is_dir():
        return ()
    skipped = tuple(agent_dir / name for name in _SKIPPED_DIRS)
    return tuple(
        sorted(
            path
            for path in agent_dir.rglob("*")
            if path.is_file() and not any(path.is_relative_to(each) for each in skipped)
        )
    )


def parse_agent_files(agent_dir: Path) -> tuple[ToolCall, ...]:
    """Each line of a file below `agent_dir` that names a failure, in path order (#2346)."""
    return tuple(
        record for path in agent_file_paths(agent_dir) for record in _file_records(agent_dir, path)
    )


def _file_records(agent_dir: Path, path: Path) -> list[ToolCall]:
    """The records of the lines of `path` that name a failure."""
    session = path.relative_to(agent_dir).as_posix()
    return [
        _record(session, path, number, line)
        for number, line in enumerate(_lines(path), start=1)
        if _FAILURE_RE.search(line)
    ]


def _record(session: str, path: Path, number: int, line: str) -> ToolCall:
    """The record of one failure line of an agent file."""
    return ToolCall(
        session=session,
        file=path,
        line=number,
        timestamp="",
        command=sanitize_text(line.strip()),
        output="",
        is_error=False,
    )


def _lines(path: Path) -> list[str]:
    """The lines of `path`, up to the bound of a read, and none when the OS refuses it."""
    try:
        with path.open("rb") as agent_file:
            text = agent_file.read(_MAX_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return []
    return text.splitlines()


__all__ = ["AGENT_DIR", "agent_file_paths", "parse_agent_files"]
