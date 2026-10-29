"""The plans on the default branch (#2714): the folders of `openspec/changes/` that
`origin/<default>` holds, read with one `git ls-tree`. Git runs for real on a clone with an
`origin`."""

from __future__ import annotations

import subprocess

import pytest

from devops_cli.exceptions import GitOperationError
from devops_cli.roadmap.planned import PlannedChanges, read_planned_changes
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import git_for_real
from tests.support.roadmap_implement import merge_plan
from tests.support.roadmap_stage import StageRepo

OPERATION = "roadmap.test"


def _ls_trees(programs: ProcessFake) -> list[ProcessCall]:
    return [call for call in programs.calls if "ls-tree" in call.argv]


@pytest.fixture
def programs(process_fake: ProcessFake) -> ProcessFake:
    """The process edge, where git runs for real."""
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))
    return process_fake


def test_a_folder_is_matched_by_its_issue_number_and_an_archived_one_by_the_number_after_its_date(
    stage_repo: StageRepo, programs: ProcessFake
) -> None:
    merge_plan(stage_repo, 7, slug="stop-the-drop")
    merge_plan(stage_repo, 8, slug="old-work", archived=True)
    merge_plan(stage_repo, 12, slug="a-third-plan")

    planned = read_planned_changes(stage_repo.clone, operation=OPERATION)

    assert planned == PlannedChanges(
        default="main",
        active={7: "7-stop-the-drop", 12: "12-a-third-plan"},
        archived={8: "2026-10-28-8-old-work"},
    )


def test_a_round_reads_the_tree_with_one_ls_tree_of_the_two_directories(
    stage_repo: StageRepo, programs: ProcessFake
) -> None:
    merge_plan(stage_repo, 7)

    read_planned_changes(stage_repo.clone, operation=OPERATION)

    (read,) = _ls_trees(programs)
    assert read.argv[-3:] == ("origin/main", "openspec/changes/", "openspec/changes/archive/")
    assert "--name-only" in read.argv


def test_the_default_branch_is_fetched_before_its_tree_is_read(
    stage_repo: StageRepo, programs: ProcessFake
) -> None:
    other = stage_repo.origin.parent / "other"
    subprocess.run(
        ["git", "clone", "-q", str(stage_repo.origin), str(other)], check=True, capture_output=True
    )
    subprocess.run(["git", "-C", str(other), "config", "user.name", "Person"], check=True)
    subprocess.run(["git", "-C", str(other), "config", "user.email", "p@example.com"], check=True)
    merge_plan(StageRepo(stage_repo.origin, other), 9)

    planned = read_planned_changes(stage_repo.clone, operation=OPERATION)

    assert 9 in planned.active


def test_a_repository_with_no_plan_gives_empty_maps(
    stage_repo: StageRepo, programs: ProcessFake
) -> None:
    planned = read_planned_changes(stage_repo.clone, operation=OPERATION)

    assert (planned.active, planned.archived) == ({}, {})


def test_a_tree_that_cannot_be_read_names_the_command_and_the_reason_of_git(
    stage_repo: StageRepo, programs: ProcessFake
) -> None:
    def refuse(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            call.argv, 128, stdout="", stderr="fatal: Not a valid object name origin/main"
        )

    programs.answer(lambda call: "ls-tree" in call.argv, ProcessAnswer(side_effect=refuse))

    with pytest.raises(GitOperationError, match=r"ls-tree.*Not a valid object name origin/main"):
        read_planned_changes(stage_repo.clone, operation=OPERATION)
