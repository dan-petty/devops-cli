"""The pre-push hook `branch-current` of `.pre-commit-config.yaml` (#4670).

The test runs the entry of the hook as pre-commit runs a `language: system` hook with no file
names, with the variables that pre-commit sets for a `git push`, in a real repository whose
`origin` is a bare repository in `tmp_path`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.support.branch_current_hook import run_branch_current_hook, stub_git

Git = Callable[..., None]

# The entry of the hook is `sh -c`, so the test starts a real `sh`.
pytestmark = pytest.mark.live("sh")


@pytest.fixture
def behind(repo: Path, git: Git) -> Path:
    """`repo` on the branch `feature`, one commit past a `main` that `origin` moved after it."""
    git(repo, "switch", "-c", "feature")
    (repo / "feature.txt").write_text("feature\n", encoding="utf-8")
    git(repo, "add", "feature.txt")
    git(repo, "commit", "-m", "feature")
    git(repo, "switch", "main")
    (repo / "main.txt").write_text("main\n", encoding="utf-8")
    git(repo, "add", "main.txt")
    git(repo, "commit", "-m", "main moves")
    git(repo, "push", "origin", "main")
    git(repo, "switch", "feature")
    return repo


def test_a_branch_behind_main_is_refused_with_the_fix_and_passes_after_a_rebase(
    behind: Path, git: Git
) -> None:
    refused = run_branch_current_hook(behind, "refs/heads/feature")
    git(behind, "rebase", "origin/main")
    rebased = run_branch_current_hook(behind, "refs/heads/feature")

    assert (refused.returncode, rebased.returncode) == (1, 0)
    assert "git fetch origin && git rebase origin/main" in refused.stdout


@pytest.mark.parametrize("branch", ["refs/tags/v1.0.0", ""])
def test_a_push_of_no_branch_passes(behind: Path, branch: str) -> None:
    """A tag, and a run that is no `git push`, as the scoped checks of the implement Job are."""
    assert run_branch_current_hook(behind, branch).returncode == 0


@pytest.mark.parametrize(
    ("fetch_status", "message", "absent"),
    [
        (124, "24 seconds", "origin is available"),
        (128, "origin is available", "24 seconds"),
    ],
    ids=["timeout", "fetch-failure"],
)
def test_a_fetch_that_does_not_finish_names_its_cause(
    behind: Path, tmp_path: Path, fetch_status: int, message: str, absent: str
) -> None:
    """A slow fetch is no proof that origin is unavailable, so a timeout names its own limit."""
    result = run_branch_current_hook(
        behind, "refs/heads/feature", path=stub_git(tmp_path / "bin", fetch_status)
    )
    assert (result.returncode, message in result.stdout, absent in result.stdout) == (
        1,
        True,
        False,
    )
