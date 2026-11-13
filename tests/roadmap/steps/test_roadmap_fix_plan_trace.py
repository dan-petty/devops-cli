"""The trace gate of the step `fix-plan` judges only the Feasibility sentences that a repair adds
or changes (#5391).

The stage run that wrote the plan of the head read the files that the Feasibility section cites,
and its trace gate passed each sentence. No trace of that run is in the process of the step. On
2026-11-13 the fix-plan Job on #5390 kept the citations of the stage run, its own run did not read
them again, and the gate refused the plan 3 times (2.4M tokens). A sentence that the repair adds
or changes is still judged on the reads of the plan runs of the repair. The planner here is a
scripted toolbox model, so the trace gate judges the tool calls of its runs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from devops_cli.roadmap.stage.stage_change import StageProposal
from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
from devops_cli.roadmap.stage.stage_verify import PLAN_NEEDS_FIX_LABEL, Verification
from devops_cli.roadmap.steps.fix_plan import FixPlanResult, FixPlanRun, run_fix_plan
from tests.support.builders import make_stage_proposal
from tests.support.fakes.model import ModelFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_fix_plan import (
    PLAN_BRANCH,
    REPAIRED_WHY,
    needs_fix_plan,
    plan_files,
    valid_changes,
)
from tests.support.roadmap_stage import STAGE_REPO, StageRepo
from tests.support.scripted_model import Script, call

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store", "model_fake")

NOW = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)

SAMPLE = "src/devops_cli/sample.py"
# The Feasibility sentence of the plan of the head in the stage repository: the stage run that
# wrote it read `src/devops_cli/sample.py`.
STAGE_READ = (
    f"`read_file {SAMPLE}` confirms the fault: `{SAMPLE}:2:return comments[:-1]` drops the last "
    "comment."
)
MISSING_PATH = "tests/test_missing.py"


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def verifier() -> ModelFake:
    """The model edge of the verification task, apart from the model edge of the planner."""
    return ModelFake()


@pytest.fixture(autouse=True)
def openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    valid_changes(openspec_fake)
    return openspec_fake


# ── The step with a planner that calls the tools ─────────────────────────────


def _head(feasibility: list[str]) -> StageProposal:
    """A plan whose group changes `MISSING_PATH`, which the checks refuse, so the planner writes
    a new plan."""
    group = make_stage_proposal().groups[0]
    return make_stage_proposal(
        groups=[group.model_copy(update={"changes": [*group.changes, MISSING_PATH]})],
        feasibility=feasibility,
    )


def _run(
    store: InMemoryRoadmapStore, repo: StageRepo, script: Script, verifier: ModelFake
) -> FixPlanRun:
    """One attempt whose planner is the toolbox model of `script`, so the trace gate judges the
    tool calls of its runs."""
    return run_fix_plan(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        confirm=True,
        now=NOW,
        model=ToolboxModel(script.model()),
        verifier=ToolboxModel(verifier),
    )


def test_a_repair_keeps_a_citation_that_only_the_stage_run_read(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api, files=plan_files(_head([STAGE_READ])))
    verifier.answer(Verification())
    # The run of the repair reads no file and keeps the sentence of the stage run.
    script = Script(make_stage_proposal(why=REPAIRED_WHY, feasibility=[STAGE_READ]))

    run = _run(store, stage_repo, script, verifier)

    assert run.attempt is not None
    assert run.attempt.result == FixPlanResult.REGATED, run.attempt.reason
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) != plan.head
    assert PLAN_NEEDS_FIX_LABEL not in store._roadmap.issues[plan.pull].labels


def test_a_repair_that_cites_a_file_that_no_run_read_is_still_refused(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api, files=plan_files(_head([STAGE_READ])))
    added = [STAGE_READ, "`read_file openspec/config.yaml 1 20` gives the rules of a plan."]
    script = Script(make_stage_proposal(why=REPAIRED_WHY, feasibility=added))

    run = _run(store, stage_repo, script, verifier)

    assert run.attempt is not None
    assert run.attempt.result == FixPlanResult.FAILED
    assert "`openspec/config.yaml` was read, but the run did not read it" in run.attempt.reason
    assert f"`{SAMPLE}` was read" not in run.attempt.reason
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
    assert verifier.call_count == 0


def test_a_repair_that_reads_the_file_with_its_lines_passes(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    needs_fix_plan(store, stage_repo, github_api, files=plan_files(_head([STAGE_READ])))
    verifier.answer(Verification())
    added = [STAGE_READ, "`read_file openspec/config.yaml 1 20` gives the rules of a plan."]
    script = Script(
        call("read_file", path="openspec/config.yaml", start_line=1, end_line=20),
        make_stage_proposal(why=REPAIRED_WHY, feasibility=added),
    )

    run = _run(store, stage_repo, script, verifier)

    assert run.attempt is not None
    assert run.attempt.result == FixPlanResult.REGATED, run.attempt.reason
