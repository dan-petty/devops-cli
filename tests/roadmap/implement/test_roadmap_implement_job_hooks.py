"""The implement job runs the commit hooks on docs and archive commits (#4781).

When `.pre-commit-config.yaml` is on the default branch, `_commit_if_changed` runs the trusted
`pre-commit` stage on staged changes before committing. If a fixer hook modifies files, the files
are staged and the stage runs again. If the hook still fails, the item stops with the hook output
and makes no commit. If the checkout holds no change, zero hooks run.
"""

from __future__ import annotations

import subprocess

import pytest

from devops_cli.config.constants import CONST_PRE_COMMIT_COMMIT_STAGE
from tests.support.fakes.process import ProcessAnswer, ProcessCall
from tests.support.implement_step import command_text
from tests.support.roadmap_implement import (
    ARCHIVE_COMMIT,
    BRANCH,
    WORK_COMMIT,
    JobWorld,
    docs_effect,
    two_groups,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

STAGE_CMD = f"uv run --frozen pre-commit run --hook-stage {CONST_PRE_COMMIT_COMMIT_STAGE}"
PRE_COMMIT_CONFIG = """\
repos:
  - repo: local
    hooks:
      - id: trailing-whitespace
        name: trim trailing whitespace
        entry: echo trim
        language: system
"""


def _enable_hooks(world: JobWorld) -> None:
    """Commit `.pre-commit-config.yaml` to `main` on origin so `_hooks_config` finds it."""
    config_file = world.repo.clone / ".pre-commit-config.yaml"
    config_file.write_text(PRE_COMMIT_CONFIG, encoding="utf-8")
    world.repo.git("add", ".pre-commit-config.yaml")
    world.repo.git("commit", "-q", "-m", "Add pre-commit configuration")
    world.repo.git("push", "-q", "origin", "main")


def test_docs_commit_runs_commit_stage_and_commits_fixer_rewrite(job_world: JobWorld) -> None:
    """When docs generator writes trailing whitespace, the fixer trims it and the rewritten file is committed."""
    _enable_hooks(job_world)

    def docs_with_trailing_whitespace(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        assert call.cwd is not None
        target = call.cwd / "docs" / "GENERATED.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("Generated.   \n", encoding="utf-8")
        return subprocess.CompletedProcess(call.argv, 0, stdout="generated\n")

    job_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops docs generate"),
        ProcessAnswer(side_effect=docs_with_trailing_whitespace),
    )

    stage_calls: list[ProcessCall] = []

    def hook_fixer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        stage_calls.append(call)
        assert call.cwd is not None
        target = call.cwd / "docs" / "GENERATED.md"
        if target.exists() and "   " in target.read_text(encoding="utf-8"):
            target.write_text("Generated.\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                call.argv, 1, stdout="trim trailing whitespace...Failed\n"
            )
        return subprocess.CompletedProcess(
            call.argv, 0, stdout="trim trailing whitespace...Passed\n"
        )

    job_world.programs.answer(
        lambda call: STAGE_CMD in command_text(call),
        ProcessAnswer(side_effect=hook_fixer),
    )

    applied = job_world.run(two_groups())

    assert (applied.drafted, applied.stopped, applied.failed) == ((1,), (), ())
    assert job_world.origin_log() == [WORK_COMMIT, ARCHIVE_COMMIT]
    committed_content = job_world.repo.origin_git("show", f"{BRANCH}:docs/GENERATED.md")
    assert "   " not in committed_content
    assert committed_content.strip() == "Generated."
    assert len(stage_calls) >= 2


def test_hook_failure_on_docs_commit_stops_the_item(job_world: JobWorld) -> None:
    """When the commit stage fails twice on docs commit, the item stops and makes no docs commit."""
    _enable_hooks(job_world)

    job_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops docs generate"),
        ProcessAnswer(side_effect=docs_effect),
    )

    def hook_fail_on_docs(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        assert call.cwd is not None
        if (call.cwd / "docs" / "GENERATED.md").exists():
            return subprocess.CompletedProcess(
                call.argv, 1, stdout="ast-grep scan...Failed\nsyntax error\n"
            )
        return subprocess.CompletedProcess(call.argv, 0, stdout="passed\n")

    job_world.programs.answer(
        lambda call: STAGE_CMD in command_text(call),
        ProcessAnswer(side_effect=hook_fail_on_docs),
    )

    applied = job_world.run(two_groups())

    assert (applied.drafted, applied.stopped, applied.failed) == ((), (1,), ())
    assert "docs: regenerate the documentation (#1)" not in job_world.origin_log()
    assert "docs(openspec): archive the change (#1)" not in job_world.origin_log()

    item = job_world.store.item(1)
    assert item is not None
    assert item.status == "Blocked"
    assert item.job_record.get("implement.stopped") == "docs"

    comments = job_world.issue_comments(1)
    assert any(
        "The hooks of the stage pre-commit failed with the exit status 1" in c for c in comments
    )
    assert any("ast-grep scan...Failed" in c for c in comments)


def test_hook_failure_on_archive_commit_stops_the_item(job_world: JobWorld) -> None:
    """When the commit stage fails on archive commit, the docs commit stays and archive commit is not made."""
    _enable_hooks(job_world)

    job_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops docs generate"),
        ProcessAnswer(side_effect=docs_effect),
    )

    def hook_on_archive(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        assert call.cwd is not None
        archive_dir = call.cwd / "openspec" / "changes" / "archive"
        if archive_dir.exists() and any(archive_dir.iterdir()):
            return subprocess.CompletedProcess(call.argv, 1, stdout="openspec gate...Failed\n")
        return subprocess.CompletedProcess(call.argv, 0, stdout="passed\n")

    job_world.programs.answer(
        lambda call: STAGE_CMD in command_text(call),
        ProcessAnswer(side_effect=hook_on_archive),
    )

    applied = job_world.run(two_groups())

    assert (applied.drafted, applied.stopped, applied.failed) == ((), (1,), ())
    # The work commit of the bot holds the documents, and no archive commit follows (#3702).
    assert job_world.origin_log() == [WORK_COMMIT]
    assert job_world.repo.origin_git("show", f"{BRANCH}:docs/GENERATED.md").strip()

    item = job_world.store.item(1)
    assert item is not None
    assert item.status == "Blocked"
    assert item.job_record.get("implement.stopped") == "archive"


def test_no_change_runs_no_hook(job_world: JobWorld) -> None:
    """When docs generator produces no file changes, commit_stage is not run."""
    _enable_hooks(job_world)

    # Docs generator does not write any file
    job_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops docs generate"),
        ProcessAnswer(returncode=0, stdout="nothing to generate\n"),
    )

    stage_calls: list[ProcessCall] = []

    def record_hook(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        stage_calls.append(call)
        return subprocess.CompletedProcess(call.argv, 0, stdout="passed\n")

    job_world.programs.answer(
        lambda call: STAGE_CMD in command_text(call),
        ProcessAnswer(side_effect=record_hook),
    )

    applied = job_world.run(two_groups())

    assert (applied.drafted, applied.stopped, applied.failed) == ((1,), (), ())
    # Docs commit was skipped because there were no changes
    assert "docs: regenerate the documentation (#1)" not in job_world.origin_log()
    # Archive commit still ran
    assert "docs(openspec): archive the change (#1)" in job_world.origin_log()


def test_a_hook_that_fails_on_the_archive_commit_is_lint_and_no_plan_defect(
    job_world: JobWorld,
) -> None:
    """The archive of the change passes, and the `pre-commit` stage then fails on the archive
    commit. The stop has the class `lint`, which a fix step repairs, and not `plan_defect`,
    which is for an archive that fails (#6703)."""
    _enable_hooks(job_world)
    job_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops docs generate"),
        ProcessAnswer(side_effect=docs_effect),
    )

    def hook_on_archive(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        assert call.cwd is not None
        archive = call.cwd / "openspec" / "changes" / "archive"
        if archive.exists() and any(archive.iterdir()):
            return subprocess.CompletedProcess(call.argv, 1, stdout="markdownlint...Failed\n")
        return subprocess.CompletedProcess(call.argv, 0, stdout="passed\n")

    job_world.programs.answer(
        lambda call: STAGE_CMD in command_text(call),
        ProcessAnswer(side_effect=hook_on_archive),
    )

    job_world.run(two_groups())

    item = job_world.store.item(1)
    assert item is not None
    assert item.job_record.get("implement.failure") == "lint"
