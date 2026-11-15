"""Name the files that the agent audit reads for each source, and read them (#2346).

The audit reads one source unless the run names another: the Claude Code transcripts of the
repository and of its worktrees, the shell history of the person, or the files that agents wrote
under `.data/agent/`. A transcript holds a command together with its output and its failure, so it
is the source that the audit reads by default; a shell history names no exit status, and an agent
file is a note that an agent wrote (design.md).

Claude Code keeps the sessions of a project below `<home>/.claude/projects/<project>/`, where
`<project>` is the absolute path of the project with each character that is not a letter or a digit
replaced by a hyphen. A session that runs in a worktree of the repository belongs to the same
project, so the audit reads the directory of the repository and the directory of each worktree of
it. A path outside those directories is never opened, which keeps a dry run to the named source.

`--since` bounds the transcripts alone: a transcript file that the cutoff leaves out is never
opened, so a run over a host whose transcripts total gigabytes stays within the time budget of a
check (AGENTS.md rule 5). The shell history and the agent files are small, and the audit reads the
start of each of them.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from devops_cli.ai.agent_audit.agent_files import AGENT_DIR, agent_file_paths, parse_agent_files
from devops_cli.ai.agent_audit.shell import history_paths, parse_shell_history
from devops_cli.ai.agent_audit.transcript import ToolCall, read_transcripts
from devops_cli.exceptions.validation import ValidationError

# The sources of the audit, by the name that the run gives. A transcript is the only source that
# holds a failure together with the command that met it, so it is the one that a run reads when it
# names none.
SOURCE_TRANSCRIPTS = "transcripts"
SOURCE_SHELL = "shell"
SOURCE_AGENT_FILES = "agent-files"
DEFAULT_SOURCE = SOURCE_TRANSCRIPTS
# The directory that Claude Code keeps the sessions of each project in, below the home directory.
_CLAUDE_PROJECTS = Path(".claude") / "projects"
# The worktrees of the repository, each of which a session of its own runs in.
_WORKTREES = Path(".data") / "agent" / "worktrees"
_NON_ALPHANUMERIC_RE = re.compile(r"[^A-Za-z0-9]")


@dataclass(frozen=True, slots=True)
class _Source:
    """One source of the audit: the files that it names, and the records that they give."""

    paths: Callable[[Path, Path], tuple[Path, ...]]
    records: Callable[[Path, Path, int | None], tuple[ToolCall, ...]]


def resolve_sources(value: str | None) -> tuple[str, ...]:
    """The sources that `value` names, in its order, or the default when it names none (#2346)."""
    names = [part.strip() for part in (value or "").split(",") if part.strip()]
    if not names:
        return (DEFAULT_SOURCE,)
    return tuple(dict.fromkeys(_checked(name) for name in names))


def source_paths(source: str, repo_dir: Path, home: Path) -> tuple[Path, ...]:
    """The files that `source` reads, for the repository at `repo_dir` and the home at `home`
    (#2346)."""
    return _source(source).paths(repo_dir, home)


def read_sources(
    sources: Iterable[str],
    repo_dir: Path,
    home: Path,
    since_days: int | None = None,
) -> tuple[ToolCall, ...]:
    """Each record of each of `sources`, in the order that the sources are named (#2346).

    `since_days` bounds the transcripts alone, which are the source whose files can be gigabytes
    old. The count of the records that the transcript reader does not know stays in the scan of
    `read_transcripts`, so a caller that reports it reads the transcripts itself.
    """
    return tuple(
        call for source in sources for call in _source(source).records(repo_dir, home, since_days)
    )


def _source(source: str) -> _Source:
    """The source that `source` names."""
    return _SOURCES[_checked(source)]


def _checked(source: str) -> str:
    """`source` when the audit reads it, and the error of a name outside the closed set."""
    if source == "files":
        source = SOURCE_AGENT_FILES
    if source not in _SOURCES:
        raise ValidationError(
            f"Unknown agent audit source {source!r}. Choose one of: {', '.join(SOURCES)}.",
            field="source",
        )
    return source


def _transcript_paths(repo_dir: Path, home: Path) -> tuple[Path, ...]:
    """The session files of the repository and of each worktree of it (#2346)."""
    projects = home / _CLAUDE_PROJECTS
    return tuple(
        path
        for root in _project_roots(repo_dir)
        for path in sorted((projects / _project_dir_name(root)).rglob("*.jsonl"))
    )


def _transcript_records(repo_dir: Path, home: Path, since_days: int | None) -> tuple[ToolCall, ...]:
    """The tool calls of the transcripts of the repository and of its worktrees."""
    return read_transcripts(_transcript_paths(repo_dir, home), since_days).calls


def _project_roots(repo_dir: Path) -> tuple[Path, ...]:
    """The repository, and each worktree of it that exists, each as its absolute path."""
    root = repo_dir.resolve()
    worktrees = root / _WORKTREES
    return (root, *sorted(path for path in worktrees.glob("*") if path.is_dir()))


def _project_dir_name(root: Path) -> str:
    """The name that Claude Code gives the project directory of `root` (#2346).

    The name is the absolute path of the project with each character that is not a letter or a
    digit replaced by a hyphen, so `/home/agent/repo` is `-home-agent-repo`.
    """
    return _NON_ALPHANUMERIC_RE.sub("-", str(root))


def _shell_paths(_repo_dir: Path, home: Path) -> tuple[Path, ...]:
    """The shell history of the person (#2346)."""
    return history_paths(home)


def _shell_records(_repo_dir: Path, home: Path, _since_days: int | None) -> tuple[ToolCall, ...]:
    """The commands of the shell history of the person."""
    return tuple(call for path in history_paths(home) for call in parse_shell_history(path))


def _agent_paths(repo_dir: Path, _home: Path) -> tuple[Path, ...]:
    """The files that the agents of the repository wrote (#2346)."""
    return agent_file_paths(repo_dir / AGENT_DIR)


def _agent_records(repo_dir: Path, _home: Path, _since_days: int | None) -> tuple[ToolCall, ...]:
    """The failure lines of the files that the agents of the repository wrote."""
    return parse_agent_files(repo_dir / AGENT_DIR)


# The sources of the audit, each with the files that it names and the records that they give. The
# table follows the functions that it holds, because a module-level value runs as the module loads.
_SOURCES: Mapping[str, _Source] = {
    SOURCE_TRANSCRIPTS: _Source(paths=_transcript_paths, records=_transcript_records),
    SOURCE_SHELL: _Source(paths=_shell_paths, records=_shell_records),
    SOURCE_AGENT_FILES: _Source(paths=_agent_paths, records=_agent_records),
}
SOURCES: tuple[str, ...] = tuple(_SOURCES)


__all__ = [
    "DEFAULT_SOURCE",
    "SOURCES",
    "SOURCE_AGENT_FILES",
    "SOURCE_SHELL",
    "SOURCE_TRANSCRIPTS",
    "read_sources",
    "resolve_sources",
    "source_paths",
]
