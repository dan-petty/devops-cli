"""Unit tests for detached git worktree management (#1047), on the git fake (#2146)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from devops_cli.git.worktree import (
    add_detached_worktree,
    fetch_pr_head,
    get_user_worktrees_dir,
    remove_worktree,
    review_worktrees_context,
)
from tests.support.fakes.git import GitFake
from tests.support.git_recording import load_transcript


def _git_words(fake: GitFake, repo: Path) -> list[list[str]]:
    """The arguments each git call had after `git -C <repo>`."""
    return [list(call.argv[3:]) for call in fake.calls if call.argv[2] == str(repo)]


def test_get_user_worktrees_dir(monkeypatch: object, tmp_path: Path) -> None:
    """get_user_worktrees_dir honors environment override and creates directory."""
    custom_root = tmp_path / "custom_data"
    with patch.dict(os.environ, {"DEVOPS_CLI_USER_DATA_ROOT": str(custom_root)}):
        wt_dir = get_user_worktrees_dir()
        assert (wt_dir.is_dir(), wt_dir) == (True, custom_root / "worktrees")


def test_add_and_remove_detached_worktree(git_fake: GitFake, tmp_path: Path) -> None:
    """add_detached_worktree adds a detached worktree of the revision; remove_worktree removes it
    and prunes the record of it."""
    git_fake.replay("worktree_add_and_remove")
    repo, dest = tmp_path / "repo", tmp_path / "worktrees" / "wt1"

    added = add_detached_worktree(repo, "main", dest)
    remove_worktree(repo, dest)

    assert (added, _git_words(git_fake, repo)) == (
        True,
        [
            ["worktree", "add", "--detach", str(dest), "main"],
            ["worktree", "remove", "--force", str(dest)],
            ["worktree", "prune"],
        ],
    )


def test_fetch_pr_head_gives_the_fetched_commit_or_none(git_fake: GitFake, tmp_path: Path) -> None:
    """fetch_pr_head fetches refs/pull/N/head and reads FETCH_HEAD; a pull request git does not
    have gives None."""
    git_fake.replay("pull_request_head")
    repo = tmp_path / "repo"
    recorded = load_transcript("pull_request_head")["result"]

    assert (fetch_pr_head(repo, 42), fetch_pr_head(repo, 43)) == (recorded["found"], None)
    assert _git_words(git_fake, repo) == [
        ["fetch", "origin", "refs/pull/42/head"],
        ["rev-parse", "FETCH_HEAD"],
        ["fetch", "origin", "refs/pull/43/head"],
    ]


def test_review_worktrees_context_lifecycle(git_fake: GitFake, tmp_path: Path) -> None:
    """review_worktrees_context adds a worktree for the commit and one for the base under the
    user data root, and removes both on exit."""
    git_fake.replay("review_worktrees")
    repo = tmp_path / "repo"
    commit_dir = tmp_path / "user-data" / "worktrees" / "review-ctx-commit"
    base_dir = tmp_path / "user-data" / "worktrees" / "review-ctx-base"

    with review_worktrees_context(
        repo, commit_rev="main", base_rev="main", session_id="ctx"
    ) as worktrees:
        inside = (worktrees.commit_worktree, worktrees.base_worktree, worktrees.partial_context)
        started = len(git_fake.calls)

    assert (inside, started) == ((commit_dir, base_dir, False), 2)
    assert _git_words(git_fake, repo)[2:] == [
        ["worktree", "remove", "--force", str(commit_dir)],
        ["worktree", "prune"],
        ["worktree", "remove", "--force", str(base_dir)],
        ["worktree", "prune"],
    ]
