"""The live run of the golden set and its score: the real stage planner on a case, with a faked
model (#3028)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import pytest

from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.exceptions import GitOperationError
from devops_cli.roadmap.stage import StagedChange, plan_item
from devops_cli.roadmap.stage_change import StageProposal
from devops_cli.roadmap.stage_eval_cases import (
    CASES_DIRECTORY,
    DefectType,
    GateName,
    StageCase,
    load_cases,
)
from devops_cli.roadmap.stage_eval_run import (
    CaseRun,
    Outcome,
    RecordingClient,
    checkout_at,
    item_of,
    run_case,
    run_cases,
)
from devops_cli.roadmap.stage_eval_score import score_runs
from tests.support.builders import make_stage_proposal
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_stage import VALID_REPORT, StageRepo, validate_args

if TYPE_CHECKING:
    from devops_cli.roadmap.stage import StageClient
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

CHANGE = "1-the-job-drops-a-comment"


@pytest.fixture(scope="module")
def cases() -> list[StageCase]:
    return load_cases(REPO_ROOT / CASES_DIRECTORY)


@pytest.fixture
def openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))
    return openspec_fake


def _live_case(cases: list[StageCase], repo: StageRepo) -> StageCase:
    """A case about issue #1 of the sample repository, staged on its head commit, with one known
    `missing_path` defect."""
    base = next(case for case in cases if case.defect_types() >= {DefectType.MISSING_PATH})
    defect = next(d for d in base.defects if d.type is DefectType.MISSING_PATH)
    return base.model_copy(
        update={
            "issue": 1,
            "title": "fix(roadmap): the job drops a comment",
            "issue_body": "The job drops the last comment of a thread.",
            "change": CHANGE,
            "base_commit": repo.git("rev-parse", "HEAD"),
            "defects": (defect,),
        }
    )


def _naming(path: str) -> StageProposal:
    """The sample proposal, with a second changed file `path` that no group creates."""
    group = make_stage_proposal().groups[0]
    return make_stage_proposal(
        groups=[group.model_copy(update={"changes": [*group.changes, path]})]
    )


def _client(_model_fake: ModelFake) -> StageClient:
    from devops_cli.ai.client import get_llm_client

    return get_llm_client(task="analysis")


def test_a_reply_with_a_missing_path_is_caught_and_the_second_reply_is_staged(
    cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake, openspec: OpenSpecFake
) -> None:
    case = _live_case(cases, stage_repo)
    stage_repo.track({"tests/security/test_sample.py": ""})
    model_fake.answer(_naming("tests/test_missing.py"), make_stage_proposal())

    run = run_case(case, _client(model_fake), stage_repo.clone)

    assert (run.outcome, run.calls) == (Outcome.STAGED, 2)
    assert run.first is not None
    assert run.first[GateName.KIND] == []
    assert "`tests/test_missing.py`" in run.first[GateName.PATHS][0]


def test_a_first_reply_that_passes_has_no_problem(
    cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake, openspec: OpenSpecFake
) -> None:
    case = _live_case(cases, stage_repo)
    model_fake.answer(make_stage_proposal())

    run = run_case(case, _client(model_fake), stage_repo.clone)

    assert (run.outcome, run.calls, run.first) == (
        Outcome.STAGED,
        1,
        {GateName.PATHS: [], GateName.KIND: []},
    )


def test_a_plan_that_the_checks_refuse_twice_ends_refused(
    cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake, openspec: OpenSpecFake
) -> None:
    case = _live_case(cases, stage_repo)
    model_fake.answer(_naming("tests/test_missing.py"))

    run = run_case(case, _client(model_fake), stage_repo.clone)

    assert (run.outcome, run.calls) == (Outcome.REFUSED, 2)
    assert "`tests/test_missing.py`" in run.reason


def test_a_failed_model_call_ends_the_case_failed_with_no_first_reply(
    cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake, openspec: OpenSpecFake
) -> None:
    case = _live_case(cases, stage_repo)
    model_fake.answer(AIClientError("the model is down"))

    run = run_case(case, _client(model_fake), stage_repo.clone)

    assert (run.outcome, run.reason, run.first) == (Outcome.FAILED, "AIClientError", None)


def test_rejected_credentials_stop_the_run(
    cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake, openspec: OpenSpecFake
) -> None:
    case = _live_case(cases, stage_repo)
    model_fake.answer(AICredentialsError("rejected"))

    with pytest.raises(AICredentialsError) as raised:
        run_cases([case, case], _client(model_fake), stage_repo.clone)
    assert raised.value.error_code == "LLM_INFERENCE_ERROR"
    assert model_fake.call_count == 1


def test_the_model_reads_the_issue_text_of_the_case(
    cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake, openspec: OpenSpecFake
) -> None:
    case = _live_case(cases, stage_repo)
    model_fake.answer(make_stage_proposal())

    run_case(case, _client(model_fake), stage_repo.clone)

    request: dict[str, Any] = json.loads(model_fake.calls[0].prompt)
    assert (request["number"], request["body"]) == (1, case.issue_body)
    assert item_of(case).title == case.title


def test_plan_item_plans_one_item_in_a_checkout_and_the_recorder_keeps_the_replies(
    cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake, openspec: OpenSpecFake
) -> None:
    case = _live_case(cases, stage_repo)
    model_fake.answer(make_stage_proposal())
    recorder = RecordingClient(_client(model_fake))

    planned = plan_item(
        item_of(case),
        client=recorder,
        checkout=stage_repo.clone,
        sha=case.base_commit,
    )

    assert isinstance(planned, StagedChange)
    assert (planned.target.change, recorder.calls, len(recorder.replies)) == (CHANGE, 1, 1)


def test_a_commit_that_the_repository_lacks_fails_and_leaves_no_worktree(
    stage_repo: StageRepo,
) -> None:
    with (
        pytest.raises(GitOperationError, match="worktree"),
        checkout_at(stage_repo.clone, "0" * 40),
    ):
        pass

    assert stage_repo.git("worktree", "list").count("\n") == 0


def test_a_checkout_is_the_tracked_files_of_the_commit_and_is_removed(
    stage_repo: StageRepo,
) -> None:
    sha = stage_repo.git("rev-parse", "HEAD")
    stage_repo.track({"later.txt": "later"})

    with checkout_at(stage_repo.clone, sha) as tree:
        names = {path.name for path in tree.rglob("*") if path.is_file()}
        assert "sample.py" in names
        assert "later.txt" not in names
    assert not tree.exists()


# ── The score ─────────────────────────────────────────────────────────────────


def _run(name: str, first: dict[GateName, list[str]] | None) -> CaseRun:
    outcome = Outcome.STAGED if first is not None else Outcome.FAILED
    return CaseRun(name, outcome, "", 1, first)


def test_the_score_counts_avoided_and_caught_defects_for_each_type_that_a_gate_catches(
    cases: list[StageCase],
) -> None:
    paths = [c for c in cases if DefectType.MISSING_PATH in c.defect_types()][:4]
    clean: dict[GateName, list[str]] = {GateName.PATHS: [], GateName.KIND: []}
    refused = {GateName.PATHS: ["a path is missing"], GateName.KIND: []}
    runs = [
        _run(paths[0].name, clean),
        _run(paths[1].name, clean),
        _run(paths[2].name, refused),
        _run(paths[3].name, None),
    ]

    score = score_runs("model-x", paths, runs)

    row = next(r for r in score.rows if r.type is DefectType.MISSING_PATH)
    assert (row.gate, row.cases, row.avoided, row.caught, row.rate) == (
        GateName.PATHS,
        4,
        2,
        1,
        0.5,
    )
    assert score.ended == {
        Outcome.STAGED: 3,
        Outcome.REFUSED: 0,
        Outcome.OVER_BUDGET: 0,
        Outcome.FAILED: 1,
    }


def test_a_type_with_no_gate_has_a_count_and_no_rate(cases: list[StageCase]) -> None:
    score = score_runs("model-x", cases, [])

    rows = {row.type: row for row in score.rows}

    assert rows[DefectType.FALSE_PREMISE].gate is GateName.PENDING
    assert rows[DefectType.FALSE_PREMISE].cases > 0
    assert (rows[DefectType.FALSE_PREMISE].avoided, rows[DefectType.FALSE_PREMISE].rate) == (
        None,
        None,
    )
    assert rows[DefectType.OTHER].gate is GateName.NONE


def test_the_total_is_the_share_of_avoided_defects_over_the_scored_types(
    cases: list[StageCase],
) -> None:
    kind = [c for c in cases if DefectType.CONTRIVED_TEST in c.defect_types()][:2]
    clean: dict[GateName, list[str]] = {GateName.PATHS: [], GateName.KIND: []}
    broken = {GateName.PATHS: [], GateName.KIND: ["a group breaks the schema"]}

    score = score_runs("m", kind, [_run(kind[0].name, clean), _run(kind[1].name, broken)])

    assert score.scored[1] >= 2
    assert cast("float", score.total) == score.scored[0] / score.scored[1]
    assert score_runs("m", [], []).total is None
