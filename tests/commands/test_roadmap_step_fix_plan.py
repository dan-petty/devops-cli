"""`devops roadmap step fix-plan`: the modes, the report and the dry run (#5061)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.roadmap.stage.stage_verify import PLAN_NEEDS_FIX_LABEL, Verification
from tests.support.roadmap_fix_plan import PLAN_PATH, needs_fix_plan, valid_changes
from tests.support.roadmap_stage import STAGE_REPO

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
    from tests.support.roadmap_stage import StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]


def _fix_plan(cli: Cli, repo: StageRepo, *args: str) -> Any:
    return cli(
        "roadmap", "step", "fix-plan", "--repo", STAGE_REPO, "--source", str(repo.clone), *args
    )


def test_without_confirm_the_command_prints_the_selection_and_writes_nothing(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(roadmap_store, stage_repo, github_api)

    result = _fix_plan(cli, stage_repo)

    assert result.exit_code == 0, result.output
    assert f"#{plan.pull}" in result.output
    assert "--confirm" in result.output
    assert model_fake.call_count == 0
    assert github_api.requested == [f"GET https://api.github.com{PLAN_PATH}"]


def test_confirm_with_item_runs_the_attempt(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    valid_changes(openspec_fake)
    plan = needs_fix_plan(roadmap_store, stage_repo, github_api)
    model_fake.answer(Verification())

    result = _fix_plan(cli, stage_repo, "--confirm", "--item", str(plan.number))

    assert result.exit_code == 0, result.output
    assert "dismissed" in result.output
    assert PLAN_NEEDS_FIX_LABEL not in roadmap_store._roadmap.issues[plan.pull].labels


def test_the_dry_run_makes_no_request_and_lists_the_reads_and_the_writes(
    cli: Cli,
    github_api: GitHubApiFake,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
) -> None:
    result = cli("roadmap", "step", "fix-plan", "--repo", STAGE_REPO, "--dry-run", "--item", "7")

    from devops_cli.lang import MESSAGES

    assert result.exit_code == 0, result.output
    assert "Dry run: no request was made" in result.output
    shown = result.output.replace("'", "")
    conditions = MESSAGES.roadmap.fix_plan_request_conditions
    for expected in (
        "GET https://api.github.com/repos/example/roadmap/pulls/<pull request>",
        "stage model",
        "--force-with-lease",
        "PATCH https://api.github.com/repos/example/roadmap/pulls/<pull request>",
        conditions["unreadable"],
        conditions["push"],
        conditions["unlabel"],
        conditions["comment"],
    ):
        assert expected in shown
    reads, writes = shown.split("With --confirm", 1)
    head, marks = reads.index("ls-tree -r --name-only -z <head>"), reads.index(conditions["marks"])
    assert head < marks
    assert writes.index(conditions["unreadable"]) < writes.index(conditions["marks"])
    assert (github_api.requested, model_fake.call_count, openspec_fake.calls) == ([], 0, [])


def test_dry_run_and_confirm_together_are_refused(cli: Cli, github_api: GitHubApiFake) -> None:
    result = cli("roadmap", "step", "fix-plan", "--repo", STAGE_REPO, "--dry-run", "--confirm")

    assert result.exit_code == 1
    assert github_api.requested == []
