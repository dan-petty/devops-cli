"""The pre-push hook `branch-current` of `.pre-commit-config.yaml` (#4670).

The test runs the entry of the hook as pre-commit runs a `language: system` hook with no file
names, with the variables that pre-commit sets for a `git push`, in a real repository whose
`origin` is a bare repository in `tmp_path`.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from tests.support.paths import REPO_ROOT

Git = Callable[..., None]

# The entry of the hook is `sh -c`, so the test starts a real `sh`.
pytestmark = pytest.mark.live("sh")


def _hook(repo: Path, branch: str) -> subprocess.CompletedProcess[str]:
    """Run the hook for a push of `HEAD` to the remote ref `branch`."""
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hook = next(
        hook for each in config["repos"] for hook in each["hooks"] if hook["id"] == "branch-current"
    )
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    pushed = {
        "PRE_COMMIT_REMOTE_NAME": "origin",
        "PRE_COMMIT_REMOTE_BRANCH": branch,
        "PRE_COMMIT_TO_REF": head,
    }
    return subprocess.run(
        [*shlex.split(hook["entry"]), *hook.get("args", [])],
        cwd=repo,
        env={**os.environ, **pushed},
        capture_output=True,
        text=True,
        check=False,
    )


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
    refused = _hook(behind, "refs/heads/feature")
    git(behind, "rebase", "origin/main")
    rebased = _hook(behind, "refs/heads/feature")

    assert (refused.returncode, rebased.returncode) == (1, 0)
    assert "git fetch origin && git rebase origin/main" in refused.stdout


@pytest.mark.parametrize("branch", ["refs/tags/v1.0.0", ""])
def test_a_push_of_no_branch_passes(behind: Path, branch: str) -> None:
    """A tag, and a run that is no `git push`, as the scoped checks of the implement Job are."""
    assert _hook(behind, branch).returncode == 0
