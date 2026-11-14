"""The stage job moves its clone to the staged commit (#3592): a clone that is ahead of the
staged commit keeps its HEAD, and the run stops with the commit that it kept."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from devops_cli.exceptions import GitOperationError
from devops_cli.roadmap.stage.stage import _move_clone


def _git(path: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=path, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _clone(root: Path) -> tuple[Path, str, str]:
    """A clone with two commits, and the hashes of the base and the local commit."""
    clone = root / "clone"
    clone.mkdir()
    _git(clone, "init", "-q", "-b", "main")
    _git(clone, "config", "user.email", "test@example.com")
    _git(clone, "config", "user.name", "Test")
    (clone / "a.txt").write_text("a", encoding="utf-8")
    _git(clone, "add", ".")
    _git(clone, "commit", "-qm", "The base commit")
    base = _git(clone, "rev-parse", "HEAD")
    (clone / "b.txt").write_text("b", encoding="utf-8")
    _git(clone, "add", ".")
    _git(clone, "commit", "-qm", "The local commit")
    return clone, base, _git(clone, "rev-parse", "HEAD")


def test_an_ahead_clone_stops_the_run_with_the_commit_that_it_kept(tmp_path: Path) -> None:
    clone, base, head = _clone(tmp_path)
    short = _git(clone, "rev-parse", "--short", head)

    with pytest.raises(GitOperationError) as raised:
        _move_clone(clone, base)

    message = str(raised.value)
    assert (base in message, short in message, "The local commit" in message) == (
        True,
        True,
        True,
    )
    assert _git(clone, "rev-parse", "HEAD") == head


def test_a_clone_behind_the_staged_commit_moves_to_it(tmp_path: Path) -> None:
    clone, base, head = _clone(tmp_path)
    _git(clone, "reset", "-q", "--hard", base)

    _move_clone(clone, head)

    assert _git(clone, "rev-parse", "HEAD") == head
