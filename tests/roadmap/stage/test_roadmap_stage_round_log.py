"""The `stage` row of the Service logs one line with counts for each item that its round failed
(#4535), and one line for each finding of the last refused reply of a plan, with its gate, its
code and the subject that its message names, masked and cut (#5433)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Final

import pytest

from devops_cli.config.settings import RoadmapStageConfig
from devops_cli.exceptions import RoadmapStageError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.round_log import log_gate_returns
from devops_cli.roadmap.run import MODEL_LANE_ROWS
from devops_cli.roadmap.stage.stage_findings import (
    TITLE_GATE,
    StageFinding,
    check_findings,
    stage_finding,
)
from devops_cli.security.sanitizer import redact_text
from tests.support.builders import make_stage_proposal
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.github_token_samples import installation_token
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

STAGE_ROW = next(row for row in MODEL_LANE_ROWS if row.name == "stage")
TEXTS = MESSAGES.roadmap
MISSING: Final[str] = "tests/test_missing.py"
FINDING_EVENT: Final[str] = "stage gate refused finding: "
COUNTS_EVENT: Final[str] = "stage gate returns: "


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    openspec_fake.script_sequence(validate_args("1-the-job-drops-a-comment"), (0, VALID_REPORT))
    return openspec_fake


def _trace(path: str) -> StageFinding:
    return stage_finding("trace", TEXTS.stage_problem_trace_path.format(path=path))


def _lines(caplog: pytest.LogCaptureFixture, event: str) -> list[str]:
    """The fields of each `event` line, with the version cut off."""
    return [
        r.getMessage().removeprefix(event).rsplit(" version=", 1)[0]
        for r in caplog.records
        if r.getMessage().startswith(event)
    ]


def _subjects(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The subject of each finding line, read back from its JSON string."""
    return [json.loads(line.split(" subject=", 1)[1]) for line in _lines(caplog, FINDING_EVENT)]


def _log(findings: list[StageFinding], *, returns: int = 3, passed: bool = False) -> None:
    log_gate_returns(STAGE_REPO, 1976, returns, passed=passed, findings=findings)


def test_each_item_that_a_round_failed_logs_one_line_with_its_step_and_class(
    stage_repo: StageRepo, model_fake: ModelFake, caplog: pytest.LogCaptureFixture
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(store)
    group = make_stage_proposal().groups[0]
    missing = make_stage_proposal(
        groups=[group.model_copy(update={"changes": [*group.changes, MISSING]})]
    )
    model_fake.answer(missing, missing)

    with caplog.at_level(logging.INFO), pytest.raises(RoadmapStageError) as raised:
        STAGE_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)

    assert raised.value.failed_items == (number,)
    lines = [
        r.getMessage() for r in caplog.records if r.getMessage().startswith("stage item failed")
    ]
    assert [line.rsplit(" version=", 1)[0] for line in lines] == [
        f"stage item failed: repo={STAGE_REPO} item=#{number} step=plan class=plan_defect"
    ]


def test_a_failed_item_logs_the_path_of_each_finding_of_its_last_refused_reply(
    stage_repo: StageRepo, model_fake: ModelFake, caplog: pytest.LogCaptureFixture
) -> None:
    """The counts line stays as it was, so the queries of the shepherd keep their matches."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(store)
    group = make_stage_proposal().groups[0]
    missing = make_stage_proposal(
        groups=[group.model_copy(update={"changes": [*group.changes, MISSING]})]
    )
    model_fake.answer(missing, missing)

    with caplog.at_level(logging.INFO), pytest.raises(RoadmapStageError) as raised:
        STAGE_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)

    returns = RoadmapStageConfig().gate_returns
    assert raised.value.failed_items == (number,)
    assert _lines(caplog, COUNTS_EVENT) == [
        f"repo={STAGE_REPO} item=#{number} returns={returns} result=refused"
        " gates=paths:1 codes=stage_problem_path:1"
    ]
    assert _lines(caplog, FINDING_EVENT) == [
        f"repo={STAGE_REPO} item=#{number} returns={returns} result=refused finding=1/1"
        f' gate=paths code=stage_problem_path subject="{MISSING}"'
    ]


def test_a_refused_reply_logs_the_gate_code_and_path_of_each_trace_finding(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        _log([_trace("docs/CLUSTER.md"), _trace("src/devops_cli/roadmap/round_log.py")])

    assert _lines(caplog, FINDING_EVENT) == [
        f"repo={STAGE_REPO} item=#1976 returns=3 result=refused finding=1/2 gate=trace"
        ' code=stage_problem_trace_path subject="docs/CLUSTER.md"',
        f"repo={STAGE_REPO} item=#1976 returns=3 result=refused finding=2/2 gate=trace"
        ' code=stage_problem_trace_path subject="src/devops_cli/roadmap/round_log.py"',
    ]


def test_a_reply_that_passed_after_a_return_logs_the_findings_of_the_last_refused_reply(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        _log([_trace("docs/CLUSTER.md")], returns=1, passed=True)

    assert _lines(caplog, FINDING_EVENT) == [
        f"repo={STAGE_REPO} item=#1976 returns=1 result=passed finding=1/1 gate=trace"
        ' code=stage_problem_trace_path subject="docs/CLUSTER.md"'
    ]


def test_a_reply_with_no_return_logs_no_finding(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        _log([_trace("docs/CLUSTER.md")], returns=0, passed=True)

    assert _lines(caplog, FINDING_EVENT) == []


def test_a_subject_longer_than_200_characters_is_cut(caplog: pytest.LogCaptureFixture) -> None:
    path = "docs/" + "a" * 300 + ".md"

    with caplog.at_level(logging.INFO):
        _log([_trace(path)])

    assert _subjects(caplog) == [path[:200]]


def test_a_secret_in_a_subject_is_masked(caplog: pytest.LogCaptureFixture) -> None:
    token = installation_token()
    path = f"docs/{token}.md"
    assert redact_text(path) != path

    with caplog.at_level(logging.INFO):
        _log([_trace(path)])

    assert _subjects(caplog) == [redact_text(path)]
    assert token not in caplog.text


def test_a_secret_across_the_cut_is_masked_before_the_cut(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A cut first would keep the start of the token, which the mask no longer finds."""
    token = installation_token()
    path = "d" * 189 + "/" + token
    assert redact_text(path)[:200] != redact_text(path[:200])

    with caplog.at_level(logging.INFO):
        _log([_trace(path)])

    assert _subjects(caplog) == [redact_text(path)[:200]]


def test_a_finding_logs_the_tool_or_the_command_that_its_message_names(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A finding whose message names no path, tool or command logs the subject `none`."""
    findings = [
        stage_finding("trace", TEXTS.stage_problem_trace_tool.format(tool="search_code")),
        stage_finding(
            "citation",
            TEXTS.stage_problem_command_reference.format(
                command="devops ci docs --all", problem="the option `--all` does not exist"
            ),
        ),
        *check_findings(TITLE_GATE, ["The title is longer than 72 characters."]),
    ]

    with caplog.at_level(logging.INFO):
        _log(findings)

    assert _lines(caplog, FINDING_EVENT) == [
        f"repo={STAGE_REPO} item=#1976 returns=3 result=refused finding=1/3 gate=trace"
        ' code=stage_problem_trace_tool subject="search_code"',
        f"repo={STAGE_REPO} item=#1976 returns=3 result=refused finding=2/3 gate=citation"
        ' code=stage_problem_command_reference subject="devops ci docs --all"',
        f"repo={STAGE_REPO} item=#1976 returns=3 result=refused finding=3/3 gate=title"
        " code=title subject=none",
    ]


def test_a_reply_logs_at_most_20_findings(caplog: pytest.LogCaptureFixture) -> None:
    """Each line names its place and the count of all the findings, so a reader sees the rest."""
    findings = [_trace(f"docs/{n}.md") for n in range(25)]

    with caplog.at_level(logging.INFO):
        _log(findings)

    lines = _lines(caplog, FINDING_EVENT)
    assert (len(lines), _subjects(caplog)) == (20, [f"docs/{n}.md" for n in range(20)])
    assert [line.split(" finding=", 1)[1].split(" ", 1)[0] for line in lines] == [
        f"{n}/25" for n in range(1, 21)
    ]
