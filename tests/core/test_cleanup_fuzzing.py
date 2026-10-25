"""Property-based fuzzing tests for git worktree porcelain parsing in cleanup.

Grounds property assertions in git-worktree(1) porcelain format specification:
Each worktree record starts with `worktree <path>`, followed by attributes
(`HEAD <commit>`, `branch <ref>`, `bare`, `detached`, `locked`, `prunable`),
terminated by a newline.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from hypothesis import Phase, example, given, settings
from hypothesis import strategies as st

from devops_cli.core.cleanup import _listed_worktrees

_FUZZ_SETTINGS = settings(
    phases=[Phase.explicit, Phase.generate],
    derandomize=True,
    max_examples=35,
    deadline=None,
)


@_FUZZ_SETTINGS
@given(
    paths=st.lists(
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_ -/.",
            min_size=1,
            max_size=40,
        ).filter(lambda p: not p.startswith(" ") and not p.endswith(" ")),
        min_size=0,
        max_size=5,
    ),
    hashes=st.lists(
        st.text(alphabet="0123456789abcdef", min_size=40, max_size=40),
        min_size=0,
        max_size=5,
    ),
)
@example(paths=[], hashes=[])
@example(
    paths=["/var/worktrees/main", "/var/worktrees/feat-1"],
    hashes=["0123456789abcdef0123456789abcdef01234567"] * 2,
)
@example(
    paths=["/var/worktrees/path with spaces/repo"],
    hashes=["abcdefabcdefabcdefabcdefabcdefabcdefabcd"],
)
@example(
    paths=["/var/worktrees/üñîçødé_path"],
    hashes=["1234567890123456789012345678901234567890"],
)
def test_git_worktree_porcelain_parsing_specification(
    paths: list[str],
    hashes: list[str],
) -> None:
    """git-worktree(1) porcelain format: entry begins with 'worktree <path>' line.

    Non-worktree lines (HEAD, branch, bare, detached, locked) must not be treated as worktrees,
    and paths must resolve correctly.
    """
    records: list[str] = []
    for idx, path in enumerate(paths):
        h = hashes[idx % len(hashes)] if hashes else "0" * 40
        records.append(f"worktree {path}\0HEAD {h}\0branch refs/heads/branch-{idx}\0")

    stdout_text = "\0".join(records)
    proc = subprocess.CompletedProcess(
        args=["git", "worktree", "list", "--porcelain", "-z"],
        returncode=0,
        stdout=stdout_text,
        stderr="",
    )

    with patch("devops_cli.core.cleanup.run_subprocess", return_value=proc):
        result = _listed_worktrees(Path("/dummy/main"))

    expected = [Path(p).resolve() for p in paths]
    assert result == expected


@_FUZZ_SETTINGS
@given(exit_code=st.integers(min_value=1, max_value=255))
@example(exit_code=1)
@example(exit_code=128)
def test_git_worktree_porcelain_failure_specification(exit_code: int) -> None:
    """git-worktree(1): non-zero exit code indicates not a repository or git error, returning empty list."""
    proc = subprocess.CompletedProcess(
        args=["git", "worktree", "list", "--porcelain", "-z"],
        returncode=exit_code,
        stdout="fatal: not a git repository",
        stderr="fatal: not a git repository",
    )

    with patch("devops_cli.core.cleanup.run_subprocess", return_value=proc):
        result = _listed_worktrees(Path("/dummy/main"))

    assert result == []
