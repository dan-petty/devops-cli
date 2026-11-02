"""`devops roadmap eval verify`: the score of the verification pass on the golden set (#3153)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.roadmap.stage_eval_cases import (
    CASES_DIRECTORY,
    Defect,
    DefectType,
    GateName,
    Severity,
    StageCase,
    Verdict,
    load_cases,
)
from devops_cli.roadmap.stage_verify import Finding, Verification
from devops_cli.roadmap.stage_verify_eval import evaluate_cases, matched_defects
from tests.support.builders import make_stage_proposal
from tests.support.fakes.model import ModelFake
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_stage import StageRepo

if TYPE_CHECKING:
    from devops_cli.roadmap.stage import StageClient

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]
SET = REPO_ROOT / CASES_DIRECTORY
SAMPLE_QUOTE = "return comments[:-1]"


def _defect(kind: DefectType, severity: Severity = Severity.MAJOR) -> Defect:
    return Defect(
        type=kind,
        severity=severity,
        where="group 1",
        problem="The plan is wrong.",
        evidence="The review quoted it.",
        gate=GateName.NONE,
    )


def _finding(kind: DefectType) -> Finding:
    return Finding(type=kind, where="group 1", problem="The plan is wrong.", quote=SAMPLE_QUOTE)


@pytest.fixture(scope="module")
def cases() -> list[StageCase]:
    return load_cases(SET)


def _case(
    cases: list[StageCase], repo: StageRepo, name: str, defects: tuple[Defect, ...]
) -> StageCase:
    """A case about the sample repository at its head, whose plan cites its one source file."""
    base = next(case for case in cases if case.verdict is not Verdict.GOOD)
    return base.model_copy(
        update={
            "name": name,
            "issue": 1,
            "title": "fix(roadmap): the job drops a comment",
            "issue_body": "The job drops the last comment of a thread.",
            "change": "1-the-job-drops-a-comment",
            "base_commit": repo.git("rev-parse", "HEAD"),
            "verdict": Verdict.NEEDS_FIX if defects else Verdict.GOOD,
            "defects": defects,
            "plan": make_stage_proposal().model_dump(mode="json"),
        }
    )


def _write_set(tmp_path: Path, *written: StageCase) -> Path:
    folder = tmp_path / "set"
    for case in written:
        target = folder / case.name
        target.mkdir(parents=True)
        meta = case.model_dump(mode="json", exclude={"name", "issue_body", "plan", "facts"})
        (target / "case.json").write_text(json.dumps(meta), encoding="utf-8")
        (target / "issue.txt").write_text(case.issue_body, encoding="utf-8")
        (target / "plan.json").write_text(json.dumps(case.plan), encoding="utf-8")
        (target / "facts.json").write_text(case.facts.model_dump_json(), encoding="utf-8")
    return folder


def _client(fake: ModelFake) -> StageClient:
    return cast("StageClient", fake.checking_replies())


# ── The match ─────────────────────────────────────────────────────────────────


def test_a_finding_matches_one_defect_of_its_type() -> None:
    defects = (
        _defect(DefectType.FALSE_PREMISE),
        _defect(DefectType.FALSE_PREMISE),
        _defect(DefectType.MISSING_PATH),
    )

    found = matched_defects(defects, [_finding(DefectType.FALSE_PREMISE)])

    assert found == (defects[0],)


def test_a_finding_matches_the_most_serious_defect_of_its_type_first() -> None:
    minor = _defect(DefectType.OTHER, Severity.MINOR)
    blocker = _defect(DefectType.OTHER, Severity.BLOCKER)

    assert matched_defects((minor, blocker), [_finding(DefectType.OTHER)]) == (blocker,)


def test_a_finding_of_a_type_the_plan_lacks_matches_nothing() -> None:
    assert matched_defects((_defect(DefectType.OTHER),), [_finding(DefectType.TASK_ORDER)]) == ()


# ── The run ───────────────────────────────────────────────────────────────────


def test_the_score_counts_recall_by_type_and_the_findings_on_good_plans(
    cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    bad = _case(
        cases,
        stage_repo,
        "bad",
        (
            _defect(DefectType.FALSE_PREMISE, Severity.BLOCKER),
            _defect(DefectType.FALSE_PREMISE, Severity.MINOR),
            _defect(DefectType.MISSING_PATH, Severity.MAJOR),
        ),
    )
    good = _case(cases, stage_repo, "good-one", ())
    model_fake.answer(
        Verification(findings=[_finding(DefectType.FALSE_PREMISE)]),
        Verification(findings=[_finding(DefectType.MISSING_PATH), _finding(DefectType.OTHER)]),
    )

    score = evaluate_cases("m-1", [bad, good], _client(model_fake), stage_repo.clone)

    rows = {row.type: (row.labeled, row.found) for row in score.rows}
    assert rows[DefectType.FALSE_PREMISE] == (2, 1)
    assert rows[DefectType.MISSING_PATH] == (1, 0)
    assert (score.labeled, score.found, score.serious_labeled, score.serious_found) == (3, 1, 2, 1)
    assert (score.good_cases, score.good_findings, score.good_returning) == (1, 2, 1)
    assert score.failed == 0


def test_the_verifier_gets_the_cited_file_of_the_checkout_of_the_case(
    cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    case = _case(cases, stage_repo, "bad", (_defect(DefectType.OTHER),))
    model_fake.answer(Verification())

    evaluate_cases("m-1", [case], _client(model_fake), stage_repo.clone)

    request = json.loads(model_fake.calls[0].prompt)
    assert SAMPLE_QUOTE in request["files"]["src/devops_cli/sample.py"]
    assert request["body"] == "The job drops the last comment of a thread."


def test_a_failed_call_counts_as_no_defect_found_and_the_other_cases_run(
    cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    first = _case(cases, stage_repo, "a-first", (_defect(DefectType.OTHER),))
    second = _case(cases, stage_repo, "b-second", (_defect(DefectType.OTHER),))
    model_fake.answer(
        AIClientError("The model failed."), Verification(findings=[_finding(DefectType.OTHER)])
    )
    client = _client(model_fake)

    score = evaluate_cases("m-1", [first, second], client, stage_repo.clone)

    assert (score.failed, score.labeled, score.found) == (1, 2, 1)


def test_rejected_credentials_stop_the_run(
    cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    case = _case(cases, stage_repo, "bad", (_defect(DefectType.OTHER),))
    model_fake.route(lambda _: True, AICredentialsError("rejected"))

    with pytest.raises(AICredentialsError, match="rejected"):
        evaluate_cases("m-1", [case], _client(model_fake), stage_repo.clone)


# ── The command ───────────────────────────────────────────────────────────────


def _verify(cli: Cli, *args: str) -> Any:
    return cli("roadmap", "eval", "verify", *args)


def _stored(output: str) -> dict[str, Any]:
    path = output.split("Stored the report in ")[1].split(".json")[0] + ".json"
    return cast("dict[str, Any]", json.loads(Path(path.strip()).read_text(encoding="utf-8")))


def test_the_group_lists_the_verify_command(cli: Cli) -> None:
    result = cli("roadmap", "eval", "--help")

    assert result.exit_code == 0
    assert "verify" in result.output


def test_a_run_prints_the_recall_and_the_findings_on_good_plans_and_stores_the_score(
    cli: Cli,
    tmp_path: Path,
    cases: list[StageCase],
    stage_repo: StageRepo,
    model_fake: ModelFake,
) -> None:
    bad = _case(cases, stage_repo, "bad", (_defect(DefectType.FALSE_PREMISE),))
    good = _case(cases, stage_repo, "good-one", ())
    folder = _write_set(tmp_path, bad, good)
    model_fake.answer(
        Verification(findings=[_finding(DefectType.FALSE_PREMISE)]),
        Verification(findings=[_finding(DefectType.OTHER)]),
    )

    result = _verify(
        cli, "--cases", str(folder), "--source", str(stage_repo.clone), "--model", "m-1"
    )

    assert result.exit_code == 0, result.output
    assert "the verification model m-1" in result.output
    assert "Recall of the labeled defects: 1 of 1 (100%)" in result.output
    assert "Findings on the good plans: 1 on 1 plan(s)" in result.output
    report = _stored(result.output)
    assert (report["model"], report["labeled"], report["found"], report["good_findings"]) == (
        "m-1",
        1,
        1,
        1,
    )
    assert report["cases"][0]["findings"][0]["type"] == "false_premise"
    assert ".data" in result.output


def test_a_run_with_json_prints_the_report(
    cli: Cli, tmp_path: Path, cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    folder = _write_set(tmp_path, _case(cases, stage_repo, "bad", (_defect(DefectType.OTHER),)))
    model_fake.answer(Verification())

    result = _verify(cli, "--cases", str(folder), "--source", str(stage_repo.clone), "--json")

    assert result.exit_code == 0, result.output
    assert '"found": 0' in result.output


def test_a_run_with_a_failed_call_exits_1_after_the_other_cases(
    cli: Cli, tmp_path: Path, cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    first = _case(cases, stage_repo, "a-first", (_defect(DefectType.OTHER),))
    second = _case(cases, stage_repo, "b-second", (_defect(DefectType.OTHER),))
    folder = _write_set(tmp_path, first, second)
    model_fake.answer(AIClientError("The model failed."), Verification())

    result = _verify(cli, "--cases", str(folder), "--source", str(stage_repo.clone))

    assert result.exit_code == 1
    assert "1 case(s) could not run" in result.output
    assert model_fake.call_count == 2


def test_the_dry_run_makes_no_model_call_and_names_the_case(
    cli: Cli, model_fake: ModelFake, cases: list[StageCase]
) -> None:
    result = _verify(cli, "--dry-run", "--case", cases[0].name)

    assert result.exit_code == 0, result.output
    assert f"verification of the case {cases[0].name}" in result.output
    assert "Dry run: no request was made." in result.output
    assert model_fake.call_count == 0


def test_an_unknown_case_exits_1_and_names_it(cli: Cli) -> None:
    result = _verify(cli, "--case", "no-such-case")

    assert result.exit_code == 1
    assert "no-such-case" in result.output
