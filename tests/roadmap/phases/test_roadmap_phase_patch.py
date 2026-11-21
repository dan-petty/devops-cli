"""The patch of the agent phase (#6601, #3702): every file of the checkout from the base, in a
format that no diff setting of the clone changes."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.roadmap.phases.patch import write_patch
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import git_for_real
from tests.support.roadmap_stage import StageRepo, run_git

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture
def real_git(process_fake: ProcessFake) -> ProcessFake:
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))
    return process_fake


def _applies(stage_repo: StageRepo, tmp_path: Path, patch: Path) -> None:
    """Apply `patch` in a new clone of `origin`, as `publish` does."""
    applied = tmp_path / "applied"
    run_git(tmp_path, "clone", "-q", str(stage_repo.origin), str(applied))
    run_git(applied, "apply", "--index", "--binary", str(patch))


def test_the_patch_holds_the_commits_and_the_new_files_in_a_fixed_format(
    stage_repo: StageRepo, real_git: ProcessFake, tmp_path: Path
) -> None:
    """A commit of a fixer and a file that no commit holds are both in the patch. An external diff
    program, a path with no prefix, color and no context lines in the config of the clone do not
    change the patch, so `publish` applies a change in the middle of a file (#3702)."""
    clone = stage_repo.clone
    lines = [f"line {number}\n" for number in range(1, 11)]
    (clone / "long.txt").write_text("".join(lines), encoding="utf-8")
    run_git(clone, "add", "long.txt")
    run_git(clone, "commit", "-q", "-m", "a long file")
    run_git(clone, "push", "-q", "origin", "HEAD:main")
    base = run_git(clone, "rev-parse", "HEAD")
    run_git(clone, "config", "diff.external", "false")
    run_git(clone, "config", "diff.noprefix", "true")
    run_git(clone, "config", "color.ui", "always")
    run_git(clone, "config", "diff.context", "0")
    lines[5] = "line six, changed\n"
    (clone / "long.txt").write_text("".join(lines), encoding="utf-8")
    (clone / "fixed.py").write_text("print('fixed')\n", encoding="utf-8")
    run_git(clone, "add", "fixed.py")
    run_git(clone, "commit", "-q", "-m", "fix")
    (clone / "new.txt").write_text("new\n", encoding="utf-8")
    patch = tmp_path / "agent.patch"

    write_patch(clone, base, patch)

    text = patch.read_text(encoding="utf-8")
    assert ("b/fixed.py" in text, "b/new.txt" in text, "\x1b[" in text) == (True, True, False)
    assert " line 5\n" in text
    _applies(stage_repo, tmp_path, patch)


def test_a_patch_to_a_commit_leaves_out_the_later_work(
    stage_repo: StageRepo, real_git: ProcessFake, tmp_path: Path
) -> None:
    """The implement Job keeps the archive as its own commit: the work patch ends at the commit
    before the archive, and a file of the checkout after it is not in that patch (#3702)."""
    clone = stage_repo.clone
    base = run_git(clone, "rev-parse", "HEAD")
    (clone / "work.py").write_text("work = 1\n", encoding="utf-8")
    run_git(clone, "add", "work.py")
    run_git(clone, "commit", "-q", "-m", "work")
    head = run_git(clone, "rev-parse", "HEAD")
    (clone / "later.txt").write_text("later\n", encoding="utf-8")
    patch = tmp_path / "work.patch"

    write_patch(clone, base, patch, head=head)

    text = patch.read_text(encoding="utf-8")
    assert ("b/work.py" in text, "later.txt" in text) == (True, False)


def test_a_checkout_with_no_change_gives_an_empty_patch(
    stage_repo: StageRepo, real_git: ProcessFake, tmp_path: Path
) -> None:
    base = run_git(stage_repo.clone, "rev-parse", "HEAD")
    patch = tmp_path / "agent.patch"

    write_patch(stage_repo.clone, base, patch)

    assert patch.read_bytes() == b""
