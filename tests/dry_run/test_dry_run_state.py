"""The dry-run state, the dry-run flag in an argv, and the dry-run output helpers."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from devops_cli.dry_run import (
    format_command,
    in_dry_run_invocation,
    is_dry_run,
    is_dry_run_requested,
    render_dry_run_result,
    set_dry_run,
)
from tests.support.paths import REPO_ROOT

# A start imports `devops_cli.dry_run.state`, which runs the package `__init__`. The names of the
# package load on first access, so the probe reads the loaded modules before it resolves them
# (#3550).
_DRY_RUN_START_PROBE = """\
import sys

import devops_cli.dry_run
import devops_cli.dry_run.state

loaded = sorted(
    name for name in ("pydantic", "devops_cli.dry_run.models") if name in sys.modules
)
unresolved = sorted(
    name for name in devops_cli.dry_run.__all__ if getattr(devops_cli.dry_run, name, None) is None
)
print(f"loaded={loaded} unresolved={unresolved}")
"""
_CHILD_TIMEOUT_SECONDS = 180


@pytest.mark.parametrize(
    ("argv", "requested"),
    [
        pytest.param(["--dry-run", "repos", "status"], True, id="flag-first"),
        pytest.param(["repos", "status", "--dry-run"], True, id="flag-last"),
        pytest.param(["repos", "status"], False, id="no-flag"),
        pytest.param([], False, id="no-argument"),
        pytest.param(
            ["k8s", "run-job", "--", "roadmap", "sync", "--dry-run"],
            False,
            id="flag-after-the-separator-belongs-to-the-passed-through-command",
        ),
        pytest.param(
            ["k8s", "run-job", "--dry-run", "--", "--version"],
            True,
            id="flag-before-the-separator-belongs-to-devops",
        ),
    ],
)
def test_a_dry_run_flag_is_requested_only_among_the_own_arguments(
    argv: list[str], requested: bool
) -> None:
    assert is_dry_run_requested(argv) is requested


def test_the_dry_run_state_follows_the_last_setting() -> None:
    set_dry_run(False)
    assert is_dry_run() is False
    set_dry_run(True)
    assert is_dry_run() is True
    set_dry_run(False)
    assert is_dry_run() is False


def test_the_dry_run_state_marks_the_invocation_as_a_dry_run() -> None:
    set_dry_run(False)
    assert in_dry_run_invocation() is False
    set_dry_run(True)
    assert in_dry_run_invocation() is True
    set_dry_run(False)
    assert in_dry_run_invocation() is False


def test_a_command_is_formatted_with_the_directory_it_runs_in(tmp_path: Path) -> None:
    repo = tmp_path / "repo"

    assert format_command(["git", "status"]) == "git status"
    assert format_command(["git", "status"], cwd=str(repo)) == f"(cd {repo} && git status)"


def test_a_dry_run_result_is_printed_as_json(
    capsys: pytest.CaptureFixture[str], snapshot: SnapshotAssertion
) -> None:
    render_dry_run_result(
        command="devops repos sync",
        action="sync",
        target="example/project",
        details={"branch": "main"},
    )

    assert capsys.readouterr().out == snapshot


@pytest.mark.live("python")
def test_a_start_that_imports_the_dry_run_state_loads_no_pydantic() -> None:
    """A start loads the dry-run state alone: the pydantic models load on first access (#3550)."""
    child = subprocess.run(
        [sys.executable, "-P", "-c", _DRY_RUN_START_PROBE],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=_CHILD_TIMEOUT_SECONDS,
        check=False,
    )

    assert child.returncode == 0, child.stderr
    assert child.stdout.strip() == "loaded=[] unresolved=[]"
