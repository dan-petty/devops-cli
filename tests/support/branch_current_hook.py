"""Run the `branch-current` pre-push hook of `.pre-commit-config.yaml` (#4670, #4969).

The test support reads the entry and runs it as pre-commit runs a `language: system` hook with no
file names. The read of the repository's config lives here, not in a test module (#6060).
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import yaml

from tests.support.paths import REPO_ROOT


def branch_current_hook() -> dict[str, object]:
    """The `branch-current` entry of `.pre-commit-config.yaml`."""
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    return next(
        hook for each in config["repos"] for hook in each["hooks"] if hook["id"] == "branch-current"
    )


def run_branch_current_hook(
    repo: Path, branch: str, *, path: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the hook for a push of `HEAD` to the remote ref `branch`."""
    hook = branch_current_hook()
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


def stub_git(directory: Path, fetch_status: int) -> Path:
    """A `git` that exits `fetch_status` for `git fetch` and 0 for every other call."""
    directory.mkdir()
    stub = directory / "git"
    stub.write_text(
        f'#!/bin/sh\nif [ "$1" = fetch ]; then exit {fetch_status}; fi\nexit 0\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return directory
