"""The `stage` row logs one result line for each item that its round tried (#4845)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from devops_cli.roadmap.run import MODEL_LANE_ROWS
from devops_cli.roadmap.stage.stage_change import StageSplit
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_job_result import result_fields
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    heavy_group,
    no_findings,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

STAGE_ROW = next(row for row in MODEL_LANE_ROWS if row.name == "stage")
OPENED = github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201)
HEAD = ("job", "repo", "item", "result", "success", "class", "infra")
COUNTS = ("plan_calls", "gate_returns", "verify_rounds", "tokens", "seconds")


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    for name in ("1-the-job-drops-a-comment", "2-the-job-drops-a-label", "3-the-job-drops-a-tag"):
        openspec_fake.script_sequence(validate_args(name), (0, VALID_REPORT))
    return openspec_fake


def test_a_round_of_three_tried_items_and_one_left_out_logs_three_result_lines(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    github_api.route("POST", f"/repos/{STAGE_REPO}/pulls", OPENED)
    seed_stageable(store)
    seed_stageable(store, "fix(roadmap): the job drops a label")
    seed_stageable(store, "fix(roadmap): the job drops a tag")
    seed_stageable(store, "wip: no type")
    heavy = heavy_group(stage_repo)
    group = make_stage_proposal().groups[0]
    missing = make_stage_proposal(
        groups=[group.model_copy(update={"changes": [*group.changes, "tests/test_missing.py"]})]
    )
    no_findings(model_fake)
    model_fake.answer(
        make_stage_proposal(),
        make_stage_proposal(groups=[heavy]),
        StageSplit(groups=[heavy]),
        missing,
        missing,
    )
    config(roadmap={"stage": {"step_tokens": 6000, "limit": 4, "gate_returns": 1}})

    with caplog.at_level(logging.INFO):
        STAGE_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)

    fields = result_fields(caplog)
    assert [{key: line[key] for key in HEAD} for line in fields] == [
        {
            "job": "stage",
            "repo": STAGE_REPO,
            "item": f"#{number}",
            "result": result,
            "success": success,
            "class": failure,
            "infra": "false",
        }
        for number, result, success, failure in (
            (1, "staged", "true", "none"),
            (2, "needs_split", "false", "none"),
            (3, "failed", "false", "plan_defect"),
        )
    ]
    assert [list(line) for line in fields] == [[*HEAD, *COUNTS]] * 3
    assert [
        {key: line[key] for key in ("plan_calls", "gate_returns", "verify_rounds")}
        for line in fields
    ] == [
        {"plan_calls": "1", "gate_returns": "0", "verify_rounds": "1"},
        {"plan_calls": "1", "gate_returns": "0", "verify_rounds": "0"},
        {"plan_calls": "2", "gate_returns": "1", "verify_rounds": "0"},
    ]
    assert [int(line["tokens"]) > 0 for line in fields] == [True] * 3
