"""`devops roadmap stage`: the named paths that the default branch changed after the base (#3309).

Git runs for real in `tmp_path`, as the other tests of the stage job answer it at the process edge.
`_moved` imports the module under test, so this file collects on a tree that lacks it and each test
fails there in the call phase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import git_for_real
from tests.support.roadmap_stage import StageRepo

if TYPE_CHECKING:
    from collections.abc import Sequence

    from devops_cli.roadmap.stage_moved import MovedPath

SAMPLE = "src/devops_cli/sample.py"
OTHER = "docs/OTHER.md"
BRANCH = "origin/main"


def _commit(repo: StageRepo, files: dict[str, str], message: str) -> str:
    """Write `files` (text by path), commit them to `main` of the clone with `message`, push, and
    return the short hash of the commit."""
    for name, text in files.items():
        (repo.clone / name).parent.mkdir(parents=True, exist_ok=True)
        (repo.clone / name).write_text(text, encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", message)
    repo.git("push", "-q", "origin", "main")
    return repo.git("rev-parse", "--short", "HEAD")


def _moved(repo: StageRepo, base: str, paths: Sequence[str]) -> list[MovedPath]:
    """The paths of `paths` that `origin/main` of the clone changed after `base`, each with its
    commits. The module under test is imported here, so this file collects on a tree that lacks
    it."""
    from devops_cli.roadmap.stage_moved import moved_paths

    return moved_paths(repo.clone, base, BRANCH, paths)


def test_two_later_commits_that_changed_a_named_path_give_both_in_log_order(
    stage_repo: StageRepo, process_fake: ProcessFake
) -> None:
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))
    base = stage_repo.git("rev-parse", "main")
    older = _commit(stage_repo, {SAMPLE: "def keep(comments):\n    return comments\n"}, "drop")
    newer = _commit(stage_repo, {SAMPLE: "def keep(comments):\n    return comments[1:]\n"}, "keep")

    (moved,) = _moved(stage_repo, base, [SAMPLE])

    assert (moved.path, moved.commits) == (SAMPLE, (f"{newer} keep", f"{older} drop"))


def test_a_commit_that_changed_an_unnamed_path_gives_nothing(
    stage_repo: StageRepo, process_fake: ProcessFake
) -> None:
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))
    base = stage_repo.git("rev-parse", "main")
    _commit(stage_repo, {OTHER: "another text\n"}, "change another file")

    assert _moved(stage_repo, base, [SAMPLE]) == []


def test_a_commit_that_changed_a_named_path_and_another_lists_the_named_path_alone(
    stage_repo: StageRepo, process_fake: ProcessFake
) -> None:
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))
    base = stage_repo.git("rev-parse", "main")
    short = _commit(stage_repo, {SAMPLE: "a text\n", OTHER: "another text\n"}, "change two files")

    (moved,) = _moved(stage_repo, base, [SAMPLE])

    assert (moved.path, moved.commits) == (SAMPLE, (f"{short} change two files",))


def test_a_base_at_the_tip_of_the_branch_gives_an_empty_list(
    stage_repo: StageRepo, process_fake: ProcessFake
) -> None:
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))
    base = stage_repo.git("rev-parse", "main")

    assert _moved(stage_repo, base, [SAMPLE]) == []


def test_a_plan_that_names_no_path_runs_no_git_command(
    stage_repo: StageRepo, process_fake: ProcessFake
) -> None:
    assert (_moved(stage_repo, "HEAD", []), process_fake.calls) == ([], [])
