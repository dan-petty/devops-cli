"""`devops roadmap stage`: the options, the modes, the report and the exit codes (#2654)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.stage import dry_run_stage
from devops_cli.roadmap.store import StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    for name in ("1-the-job-drops-a-comment", "2-the-job-drops-a-label"):
        openspec_fake.script_sequence(validate_args(name), (0, VALID_REPORT))
    return openspec_fake


def _stage(cli: Cli, repo: StageRepo, *args: str) -> Any:
    return cli("roadmap", "stage", "--repo", STAGE_REPO, "--source", str(repo.clone), *args)


def test_a_plan_prints_the_report_and_writes_nothing(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    seed_stageable(roadmap_store)
    model_fake.answer(make_stage_proposal())

    result = _stage(cli, stage_repo, "--plan")

    assert result.exit_code == 0, result.output
    assert "# Stage plan for example/roadmap" in result.output
    assert "## To stage" in result.output
    assert (
        "- #1 fix(roadmap): the job drops a comment: branch `fix/1-the-job-drops-a-comment`, 1 task group(s)"
        in result.output
    )
    assert roadmap_store.comments_on(1) == []
    assert stage_repo.origin_git("branch", "--format=%(refname:short)") == "main"
    assert github_api.requested == []


def test_a_run_with_no_mode_flag_is_a_plan_and_says_so(
    cli: Cli, roadmap_store: InMemoryRoadmapStore, stage_repo: StageRepo
) -> None:
    result = _stage(cli, stage_repo)

    assert result.exit_code == 0
    assert "runs as --plan" in result.output
    assert "No item to stage." in result.output


def test_confirm_stages_the_item_and_reports_it(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    github_api.route(
        "POST",
        f"/repos/{STAGE_REPO}/pulls",
        github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201),
    )
    seed_stageable(roadmap_store)
    model_fake.answer(make_stage_proposal())

    result = _stage(cli, stage_repo, "--confirm", "--step-tokens", "30000")

    assert result.exit_code == 0, result.output
    assert (
        "Staged 1 item(s), stopped 0 on the budget, removed 0 staged branch(es)." in result.output
    )
    item = roadmap_store.item(1)
    assert item is not None
    assert item.job_record[StageRecordKey.PR] == "5"
    assert "budget of 30000 tokens" in roadmap_store.comments_on(1)[0].body


def test_a_left_out_item_is_reported_with_its_reason(
    cli: Cli, roadmap_store: InMemoryRoadmapStore, stage_repo: StageRepo
) -> None:
    seed_stageable(roadmap_store, "wip: no type")

    result = _stage(cli, stage_repo, "--plan")

    assert "## Left out" in result.output
    assert "- #1 wip: no type: The title has no Conventional Commit type" in result.output


def test_why_lists_the_items_that_matched_no_filter_apart_from_the_left_out_items(
    cli: Cli, roadmap_store: InMemoryRoadmapStore, stage_repo: StageRepo
) -> None:
    seed_stageable(roadmap_store)

    result = _stage(cli, stage_repo, "--plan", "--filter", "priority=p0-critical", "--why")

    assert result.exit_code == 0, result.output
    assert "## Matched no filter" in result.output
    assert (
        "- #1 fix(roadmap): the job drops a comment: The filter takes priority p0-critical. "
        "The item has priority p1-high." in " ".join(result.output.split())
    )
    assert "## Left out" not in result.output


def test_without_why_the_plan_has_no_section_for_the_items_that_matched_no_filter(
    cli: Cli, roadmap_store: InMemoryRoadmapStore, stage_repo: StageRepo
) -> None:
    seed_stageable(roadmap_store)

    result = _stage(cli, stage_repo, "--plan", "--filter", "priority=p0-critical")

    assert result.exit_code == 0, result.output
    assert "Matched no filter" not in result.output
    assert "No item to stage." in result.output


def test_the_items_that_matched_no_filter_are_not_counted_as_skipped() -> None:
    from devops_cli.roadmap.stage import LeftOut, StageApplied, StagePlan, stage_results

    plan = StagePlan(
        STAGE_REPO,
        left_out=(LeftOut(1, "reason"),),
        unmatched=(LeftOut(2, "The filter takes effort low. The item has effort high."),),
    )

    assert set(stage_results(plan, StageApplied())) == {1}


def test_a_failed_item_makes_the_command_exit_1_after_the_others(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
) -> None:
    seed_stageable(roadmap_store)
    model_fake.answer(make_stage_proposal(pull_request_body="Fixes #3 now."))

    result = _stage(cli, stage_repo, "--plan")

    assert result.exit_code == 1
    assert "## Failed" in result.output
    assert "Staging incomplete" in result.output
    assert "#1 (RoadmapStageError" in result.output


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--filter", "color=red"], "status, priority, type, value, effort"),
        (["--filter", "status"], "family=value"),
        (["--dry-run", "--confirm"], "Pass one of --dry-run, --plan and --confirm"),
        (["--plan", "--confirm"], "Pass one of --dry-run, --plan and --confirm"),
    ],
)
def test_a_bad_option_is_refused_before_any_request(
    cli: Cli,
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    model_fake: ModelFake,
    args: list[str],
    message: str,
) -> None:
    result = _stage(cli, stage_repo, *args)

    assert result.exit_code == 1
    assert message in result.output
    assert github_api.requested == []
    assert model_fake.call_count == 0


def test_the_dry_run_makes_no_request_and_lists_the_reads_the_git_commands_and_the_writes(
    cli: Cli,
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
) -> None:
    result = cli("roadmap", "stage", "--repo", STAGE_REPO, "--dry-run", "--limit", "2")

    assert result.exit_code == 0, result.output
    assert "Dry run: no request was made" in result.output
    shown = result.output.replace("'", "")
    for expected in (
        "git -C <model-clone> ls-remote --heads origin",
        "analysis model",
        "openspec validate <change> --strict",
        "git -C <worktree> push -q -u origin <branch>",
        "POST https://api.github.com/repos/example/roadmap/pulls",
        "git -C <model-clone> push origin --delete <branch>",
    ):
        assert expected in shown
    assert (github_api.requested, model_fake.call_count, openspec_fake.calls) == ([], 0, [])


def test_the_dry_run_returns_the_plan_marked_as_a_dry_run() -> None:
    plan = dry_run_stage(STAGE_REPO, item=7, limit=1)

    assert (plan.dry_run, plan.ready, bool(plan.requests), bool(plan.write_requests)) == (
        True,
        (),
        True,
        True,
    )
    assert any("issues/7" in request.line() for request in plan.requests)
