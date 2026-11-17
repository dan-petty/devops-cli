"""The pre-push hook `branch-current` of `.pre-commit-config.yaml` (#4670).

The test runs the entry of the hook as pre-commit runs a `language: system` hook with no file
names, with the variables that pre-commit sets for a `git push`, in a real repository whose
`origin` is a bare repository in `tmp_path`.
"""

from __future__ import annotations

import os
import re
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

# The agent shell stops a push at 120 seconds, and the pre-push hooks run in sequence.
_PRE_PUSH_BUDGET_SECONDS = 120


def _config() -> dict[str, object]:
    return yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))


def _branch_current_hook() -> dict[str, object]:
    config = _config()
    return next(
        hook for each in config["repos"] for hook in each["hooks"] if hook["id"] == "branch-current"
    )


def _hook(repo: Path, branch: str, *, path: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run the hook for a push of `HEAD` to the remote ref `branch`."""
    hook = _branch_current_hook()
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    pushed = {
        "PRE_COMMIT_REMOTE_NAME": "origin",
        "PRE_COMMIT_REMOTE_BRANCH": branch,
        "PRE_COMMIT_TO_REF": head,
    }
    env = {**os.environ, **pushed}
    if path is not None:
        env["PATH"] = f"{path}{os.pathsep}{env['PATH']}"
    return subprocess.run(
        [*shlex.split(str(hook["entry"])), *hook.get("args", [])],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _stub_git(directory: Path, fetch_status: int) -> Path:
    """A `git` that exits `fetch_status` for `git fetch` and 0 for every other call."""
    directory.mkdir()
    stub = directory / "git"
    stub.write_text(
        f'#!/bin/sh\nif [ "$1" = fetch ]; then exit {fetch_status}; fi\nexit 0\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return directory


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


def test_the_hook_bounds_its_fetch_with_45_seconds() -> None:
    script = "\n".join(_branch_current_hook().get("args", []))
    assert "timeout 45 git fetch --quiet --no-tags origin main" in script


def test_a_fetch_that_runs_out_of_time_names_the_limit(behind: Path, tmp_path: Path) -> None:
    """A slow fetch is no proof that origin is unavailable, so the message names the limit."""
    result = _hook(behind, "refs/heads/feature", path=_stub_git(tmp_path / "bin", 124))
    assert (
        result.returncode,
        "45 seconds" in result.stdout,
        "origin is available" in result.stdout,
    ) == (1, True, False)


def test_a_fetch_that_fails_names_an_unavailable_origin(behind: Path, tmp_path: Path) -> None:
    result = _hook(behind, "refs/heads/feature", path=_stub_git(tmp_path / "bin", 128))
    assert (
        result.returncode,
        "origin is available" in result.stdout,
        "45 seconds" in result.stdout,
    ) == (1, True, False)


def test_the_pre_push_hooks_stay_below_the_agent_shell_budget() -> None:
    """The nested limits end first: the sum of the pre-push limits stays under 120 seconds."""
    limits = [
        int(match.group(1))
        for each in _config()["repos"]
        for hook in each["hooks"]
        if "pre-push" in hook.get("stages", [])
        for text in [hook.get("entry", ""), *hook.get("args", [])]
        for match in [re.search(r"timeout (\d+)", text)]
        if match
    ]
    assert (limits, sum(limits) < _PRE_PUSH_BUDGET_SECONDS) == ([45, 40, 30], True)
