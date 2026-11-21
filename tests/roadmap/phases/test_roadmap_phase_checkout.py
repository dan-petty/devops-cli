"""The clone of `prepare` (#6655): a plain clone of the issue branch in the run folder, as a developer
makes one, with the base and the lease that `prepare` reads itself."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

import pytest

from devops_cli.exceptions import GitOperationError
from devops_cli.roadmap.phases.checkout import clone_branch
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import git_for_real
from tests.support.roadmap_stage import STAGE_NAME, StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store")

BRANCH = "fix/1-sample"


@pytest.fixture
def world(
    stage_repo: StageRepo,
    app_slug: Callable[..., None],
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> StageRepo:
    """Real git, and the bot of the App as the identity of the session."""
    api, programs = github_api_and_gh
    programs.answer("git", ProcessAnswer(side_effect=git_for_real))
    api.route("GET", "/user", github_json({"login": STAGE_NAME}))
    api.route("GET", f"/users/{quote(STAGE_NAME, safe='')}", github_json({"id": 1}))
    return stage_repo


def _push_branch(repo: StageRepo, author: str) -> str:
    repo.git("switch", "-q", "-c", BRANCH)
    (repo.clone / "work.txt").write_text("work\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("-c", f"user.name={author}", "commit", "-q", "-m", "work")
    repo.git("push", "-q", "origin", BRANCH)
    repo.git("switch", "-q", "main")
    return repo.origin_git("rev-parse", BRANCH)


def test_a_pushed_branch_is_taken_with_its_tip_as_the_lease(
    world: StageRepo, tmp_path: Path
) -> None:
    tip = _push_branch(world, STAGE_NAME)

    clone = clone_branch(tmp_path / "work", url=str(world.origin), issue=1, branch=BRANCH)

    assert (clone.branch, clone.default, clone.lease) == (BRANCH, "main", tip)
    assert clone.base == world.origin_git("rev-parse", "main")
    assert clone.path.parent == tmp_path / "work"


def test_a_new_branch_starts_at_the_default_branch_with_no_lease(
    world: StageRepo, tmp_path: Path
) -> None:
    clone = clone_branch(tmp_path / "work", url=str(world.origin), issue=1, branch=BRANCH)

    assert (clone.lease, clone.base) == ("", world.origin_git("rev-parse", "main"))


def test_a_branch_with_a_commit_of_a_person_is_not_taken(world: StageRepo, tmp_path: Path) -> None:
    _push_branch(world, "a-person")

    with pytest.raises(GitOperationError, match="a-person"):
        clone_branch(tmp_path / "work", url=str(world.origin), issue=1, branch=BRANCH)
