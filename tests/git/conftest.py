"""Fixtures of the tests that build real repositories and worktrees in `tmp_path`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., None]


@pytest.fixture
def repo(tmp_path: Path, git: Git) -> Path:
    """A repository with one commit on main, pushed to a bare `origin` at `example-org/app.git`."""
    bare = tmp_path / "example-org" / "app.git"
    bare.mkdir(parents=True)
    git(bare, "init", "--bare", "-b", "main")
    work = tmp_path / "repo"
    work.mkdir()
    git(work, "init", "-b", "main")
    (work / "file.txt").write_text("base\n", encoding="utf-8")
    git(work, "add", "file.txt")
    git(work, "commit", "-m", "init")
    git(work, "remote", "add", "origin", str(bare))
    git(work, "push", "origin", "main")
    return work


@pytest.fixture
def managed(isolate_data_dir: Path) -> Path:
    """The folder that `devops repos worktrees add` manages: `w-<issue>` goes under it."""
    return isolate_data_dir / "agent" / "worktrees"
