"""The patch of the agent phase (#6601): every file of the checkout, staged in a new git folder, so
no setting of the clone runs a program."""

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


def test_the_patch_holds_the_commits_and_the_new_files_and_runs_no_filter_of_the_clone(
    stage_repo: StageRepo, real_git: ProcessFake, tmp_path: Path
) -> None:
    """A commit of a fixer and a file that no commit holds are both in the patch. A clean filter
    that the clone defines does not run, as `git add` in the clone would run it (#3702)."""
    clone = stage_repo.clone
    base = run_git(clone, "rev-parse", "HEAD")
    marker = tmp_path / "filter-ran"
    run_git(clone, "config", "filter.spy.clean", f"touch {marker}; cat")
    (clone / ".gitattributes").write_text("*.txt filter=spy\n", encoding="utf-8")
    (clone / "fixed.py").write_text("print('fixed')\n", encoding="utf-8")
    run_git(clone, "add", "fixed.py")
    run_git(clone, "commit", "-q", "-m", "fix")
    (clone / "new.txt").write_text("new\n", encoding="utf-8")
    marker.unlink(missing_ok=True)
    patch = tmp_path / "agent.patch"

    write_patch(clone, base, patch)

    text = patch.read_text(encoding="utf-8")
    assert ("b/fixed.py" in text, "b/new.txt" in text, "b/.gitattributes" in text) == (
        True,
        True,
        True,
    )
    assert not marker.exists()
    applied = tmp_path / "applied"
    run_git(tmp_path, "clone", "-q", str(stage_repo.origin), str(applied))
    run_git(applied, "apply", "--check", str(patch))


def test_a_checkout_with_no_change_gives_an_empty_patch(
    stage_repo: StageRepo, real_git: ProcessFake, tmp_path: Path
) -> None:
    base = run_git(stage_repo.clone, "rev-parse", "HEAD")
    patch = tmp_path / "agent.patch"

    write_patch(stage_repo.clone, base, patch)

    assert patch.read_bytes() == b""
