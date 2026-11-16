"""Tier 1 of the step `fix-checks` in a runner Job (#5971): the fixers of a lint failure, their
commit, and their checks again.

Git runs for real on a clone with an `origin` whose `main` declares the devops-cli toolchain. The
fixers and their checks are answered at the process edge: a ruff fix rewrites the file it names.
"""

from __future__ import annotations

import subprocess

import pytest

from devops_cli.roadmap.steps.fix_checks_repair import tier1_fix
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import command_text, git_for_real
from tests.support.roadmap_implement import STEPS_DECLARATION, STEPS_FILE
from tests.support.roadmap_stage import StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store")

SAMPLE = "src/devops_cli/sample.py"
LINT_LOG = f"{SAMPLE}:1:8: F401 [*] `os` imported but unused\nFound 1 error.\n"
TYPE_LOG = f'{SAMPLE}:2: error: Incompatible types in assignment (got "str")  [assignment]\n'
STATIC = "Static Analysis"


@pytest.fixture
def branch(stage_repo: StageRepo, process_fake: ProcessFake) -> StageRepo:
    """The clone on the branch of item 1, with one commit that adds an unused import."""
    stage_repo.track({STEPS_FILE: STEPS_DECLARATION})
    stage_repo.git("switch", "-q", "-c", "fix/1-sample")
    (stage_repo.clone / SAMPLE).write_text("import os\nVALUE = 1\n", encoding="utf-8")
    stage_repo.git("add", "-A")
    stage_repo.git("commit", "-q", "-m", "fix(roadmap): add the value")
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))
    process_fake.answer(lambda call: command_text(call).startswith("uv "), ProcessAnswer())
    return stage_repo


def _ruff_fix(call: ProcessCall) -> subprocess.CompletedProcess[str]:
    """What `ruff check --fix` does to the file: it drops the unused import."""
    assert call.cwd is not None
    (call.cwd / SAMPLE).write_text("VALUE = 1\n", encoding="utf-8")
    return subprocess.CompletedProcess(call.argv, 0, stdout="Found 1 error (1 fixed).")


def _uv_commands(fake: ProcessFake) -> list[str]:
    return [command_text(call) for call in fake.calls if call.argv[0] == "uv"]


def _fixes(fake: ProcessFake) -> None:
    fake.answer(
        lambda call: command_text(call).startswith("uv run ruff check --fix"),
        ProcessAnswer(side_effect=_ruff_fix),
    )


def test_tier1_commits_the_fixes_of_a_lint_failure_and_is_done_when_the_checks_pass(
    branch: StageRepo, process_fake: ProcessFake
) -> None:
    _fixes(process_fake)

    fixed = tier1_fix(branch.clone, 1, STATIC, LINT_LOG)

    assert fixed.done is True
    assert branch.git("log", "-1", "--format=%s") == (
        "style: apply the fixers of tier 1 for check Static Analysis (#1)"
    )
    assert branch.git("status", "--porcelain") == ""
    assert _uv_commands(process_fake) == [
        f"uv run ruff check --fix -- {SAMPLE}",
        f"uv run ruff format -- {SAMPLE}",
        "uv run devops docs generate",
        f"uv run ruff check -- {SAMPLE}",
        f"uv run ruff format --check -- {SAMPLE}",
        "uv run devops ci docs",
    ]


def test_a_tier1_commit_whose_check_still_fails_stays_for_the_model_fix(
    branch: StageRepo, process_fake: ProcessFake
) -> None:
    _fixes(process_fake)
    process_fake.answer(
        lambda call: command_text(call) == f"uv run ruff check -- {SAMPLE}",
        ProcessAnswer(returncode=1, stdout="E501 Line too long"),
    )

    fixed = tier1_fix(branch.clone, 1, STATIC, LINT_LOG)

    assert fixed.done is False
    assert "ruff check" in fixed.reason
    assert branch.git("log", "-1", "--format=%s").startswith("style: apply the fixers of tier 1")


def test_tier1_runs_no_fixer_for_a_failure_that_is_not_lint(
    branch: StageRepo, process_fake: ProcessFake
) -> None:
    head = branch.git("rev-parse", "HEAD")

    fixed = tier1_fix(branch.clone, 1, STATIC, TYPE_LOG)

    assert fixed.done is False
    assert (_uv_commands(process_fake), branch.git("rev-parse", "HEAD")) == ([], head)


def test_tier1_makes_no_commit_when_the_fixers_change_no_file(
    branch: StageRepo, process_fake: ProcessFake
) -> None:
    head = branch.git("rev-parse", "HEAD")

    fixed = tier1_fix(branch.clone, 1, STATIC, LINT_LOG)

    assert fixed.done is False
    assert "changed no file" in fixed.reason
    assert branch.git("rev-parse", "HEAD") == head
