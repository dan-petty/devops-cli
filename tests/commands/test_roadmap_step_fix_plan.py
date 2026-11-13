"""`devops roadmap step fix-plan`: the modes, the report and the dry run (#5061)."""

from __future__ import annotations

import signal
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.roadmap.stage.stage_verify import PLAN_NEEDS_FIX_LABEL, Verification
from devops_cli.roadmap.stores.store import FixPlanRecordKey
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


def test_confirm_writes_the_progress_and_the_result_lines_to_stderr(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    """A Job runs the command, and its log is what the command writes, so the lines of each round
    and the result line are in the log also when the deadline of the Job stops the pod (#5363)."""
    valid_changes(openspec_fake)
    plan = needs_fix_plan(roadmap_store, stage_repo, github_api)
    model_fake.answer(Verification())

    result = _fix_plan(cli, stage_repo, "--confirm", "--item", str(plan.number))

    assert result.exit_code == 0, result.output
    lines = result.stderr.splitlines()
    progress = [line for line in lines if line.startswith("fix-plan progress: ")]
    results = [line for line in lines if line.startswith("roadmap job result: job=fix_plan ")]
    assert (len(progress), len(results)) == (1, 1)
    assert "result=dismissed" in results[0]


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


@pytest.mark.parametrize(
    "args",
    [("--skip-wait", "--pull", "5"), ("--skip-wait", "--confirm")],
    ids=["no confirm", "no item"],
)
def test_skip_wait_needs_confirm_and_a_named_item(
    cli: Cli, github_api: GitHubApiFake, model_fake: ModelFake, args: tuple[str, ...]
) -> None:
    result = cli("roadmap", "step", "fix-plan", "--repo", STAGE_REPO, *args)

    assert result.exit_code == 1
    assert "--skip-wait" in result.output
    assert (github_api.requested, model_fake.call_count) == ([], 0)


def test_sigterm_during_the_attempt_exits_75_and_records_the_eviction(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    """Kubernetes sends SIGTERM to the pod of a Job for an eviction or a node drain. The command
    ends the attempt in the grace period: the attempt does not count, and the exit status 75 tells
    a retry policy that a new attempt is safe (#5413)."""
    valid_changes(openspec_fake)
    plan = needs_fix_plan(roadmap_store, stage_repo, github_api)
    before = signal.getsignal(signal.SIGTERM)

    def sigterm(_prompt: str) -> Verification:
        # Raise SIGTERM only under the handler of the command, so a defect does not end the worker.
        assert signal.getsignal(signal.SIGTERM) not in (before, signal.SIG_DFL, None)
        signal.raise_signal(signal.SIGTERM)
        return Verification()

    model_fake.answer(sigterm)

    result = _fix_plan(cli, stage_repo, "--confirm", "--pull", str(plan.pull))

    assert result.exit_code == 75, result.output
    item = roadmap_store.item(plan.number)
    assert item is not None
    assert (
        item.job_record.get(FixPlanRecordKey.RESULT),
        item.job_record.get(FixPlanRecordKey.ATTEMPTS),
        item.job_record.get(FixPlanRecordKey.EVICTED),
    ) == ("evicted", "0", "1")
    assert PLAN_NEEDS_FIX_LABEL in roadmap_store._roadmap.issues[plan.pull].labels
    assert signal.getsignal(signal.SIGTERM) == before
