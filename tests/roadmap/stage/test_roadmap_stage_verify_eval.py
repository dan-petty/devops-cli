"""`devops roadmap eval verify`: the score of the verification pass on the golden set (#3153)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from devops_cli.ai.client import factory
from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.commands.roadmap_eval_verify import _review_model
from devops_cli.config import settings
from devops_cli.roadmap.stage.stage_eval_cases import (
    CASES_DIRECTORY,
    NO_COMMIT,
    Defect,
    DefectType,
    GateName,
    Severity,
    StageCase,
    Verdict,
    load_cases,
)
from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
from devops_cli.roadmap.stage.stage_verify import Finding, Verification
from devops_cli.roadmap.stage.stage_verify_eval import (
    VerifyScore,
    evaluate_cases,
    matched_defects,
    planned_verify_calls,
)
from tests.support.builders import make_stage_proposal
from tests.support.fakes.model import ModelFake
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_stage import StageRepo
from tests.support.scripted_model import Script, call

if TYPE_CHECKING:
    from devops_cli.config.settings import AIConfig
    from devops_cli.roadmap.stage.stage import StageClient
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store", "openspec_fake")

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


def _evaluate(run: list[StageCase], fake: ModelFake, repo: StageRepo) -> VerifyScore:
    return evaluate_cases("m-1", run, _client(fake), repo.clone, toolbox=ToolboxModel(fake))


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

    score = _evaluate([bad, good], model_fake, stage_repo)

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

    _evaluate([case], model_fake, stage_repo)

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

    score = _evaluate([first, second], model_fake, stage_repo)

    assert (score.failed, score.labeled, score.found) == (1, 2, 1)


def test_rejected_credentials_stop_the_run(
    cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    case = _case(cases, stage_repo, "bad", (_defect(DefectType.OTHER),))
    model_fake.route(lambda _: True, AICredentialsError("rejected"))

    with pytest.raises(AICredentialsError, match="rejected"):
        _evaluate([case], model_fake, stage_repo)


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


def _set_with_a_case_that_holds_no_commit(
    tmp_path: Path, cases: list[StageCase], stage_repo: StageRepo
) -> Path:
    """A set of one case with a commit, `bad`, and one case that holds none, `a-no-commit`."""
    bad = _case(cases, stage_repo, "bad", (_defect(DefectType.FALSE_PREMISE),))
    unmerged = _case(cases, stage_repo, "a-no-commit", (_defect(DefectType.MISSING_PATH),))
    return _write_set(tmp_path, bad, unmerged.model_copy(update={"base_commit": NO_COMMIT}))


def test_a_run_leaves_out_a_case_that_holds_no_commit_and_names_it_and_exits_0(
    cli: Cli, tmp_path: Path, cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    folder = _set_with_a_case_that_holds_no_commit(tmp_path, cases, stage_repo)
    model_fake.answer(Verification(findings=[_finding(DefectType.FALSE_PREMISE)]))

    result = _verify(cli, "--cases", str(folder), "--source", str(stage_repo.clone))

    assert result.exit_code == 0, result.output
    assert "Left out of the run, as they hold no commit to check out: a-no-commit." in result.output
    assert "Recall of the labeled defects: 1 of 1 (100%)" in result.output
    report = _stored(result.output)
    assert (report["left_out"], report["labeled"], len(report["cases"])) == (["a-no-commit"], 1, 1)
    assert model_fake.call_count == 1


def test_a_run_that_leaves_out_no_case_has_an_empty_list(
    cli: Cli, tmp_path: Path, cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    folder = _write_set(tmp_path, _case(cases, stage_repo, "bad", (_defect(DefectType.OTHER),)))
    model_fake.answer(Verification())

    result = _verify(cli, "--cases", str(folder), "--source", str(stage_repo.clone))

    assert result.exit_code == 0, result.output
    assert "Left out" not in result.output
    assert _stored(result.output)["left_out"] == []


def test_the_dry_run_lists_the_runs_of_the_cases_with_a_commit_and_names_the_others(
    cli: Cli, tmp_path: Path, cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    folder = _set_with_a_case_that_holds_no_commit(tmp_path, cases, stage_repo)

    result = _verify(cli, "--dry-run", "--cases", str(folder))

    assert result.exit_code == 0, result.output
    assert "verifies 1 case(s)" in result.output
    assert "verification of the case bad" in result.output
    assert "verification of the case a-no-commit" not in result.output
    assert "Left out of the run, as they hold no commit to check out: a-no-commit." in result.output
    assert model_fake.call_count == 0


def test_a_selection_of_cases_that_hold_no_commit_exits_1_and_names_them(
    cli: Cli, tmp_path: Path, cases: list[StageCase], stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    folder = _set_with_a_case_that_holds_no_commit(tmp_path, cases, stage_repo)

    result = _verify(cli, "--cases", str(folder), "--case", "a-no-commit")

    assert result.exit_code == 1
    assert "a-no-commit" in result.output
    assert model_fake.call_count == 0


def test_the_golden_set_leaves_out_exactly_the_cases_that_read_no_commit(
    cli: Cli, cases: list[StageCase]
) -> None:
    unmerged = [case.name for case in cases if not case.has_commit]

    result = _verify(cli, "--dry-run")

    assert result.exit_code == 0, result.output
    assert f"verifies {len(cases) - len(unmerged)} case(s)" in result.output
    assert unmerged
    assert f"hold no commit to check out: {', '.join(unmerged)}." in result.output


def test_an_unknown_case_exits_1_and_names_it(cli: Cli) -> None:
    result = _verify(cli, "--case", "no-such-case")

    assert result.exit_code == 1
    assert "no-such-case" in result.output


def test_the_run_reads_the_checkout_of_each_case_with_the_read_tools(
    cases: list[StageCase], stage_repo: StageRepo
) -> None:
    case = _case(cases, stage_repo, "bad", (_defect(DefectType.OTHER),))
    script = Script(call("read_file", path="src/devops_cli/sample.py"), Verification())

    score = evaluate_cases(
        "m-1",
        [case],
        _client(ModelFake()),
        stage_repo.clone,
        toolbox=ToolboxModel(script.model()),
    )

    assert (score.failed, SAMPLE_QUOTE in script.tool_returns()[0]) == (0, True)


def test_read_spec_of_the_run_answers_from_the_spec(
    cases: list[StageCase], stage_repo: StageRepo, openspec_fake: OpenSpecFake
) -> None:
    openspec_fake.script(
        ("list", "--specs", "--json"), 0, json.dumps({"specs": [{"id": "sample"}]})
    )
    case = _case(cases, stage_repo, "bad", (_defect(DefectType.OTHER),))
    script = Script(call("read_spec"), Verification())

    score = evaluate_cases(
        "m-1",
        [case],
        _client(ModelFake()),
        stage_repo.clone,
        toolbox=ToolboxModel(script.model()),
    )

    (answer,) = script.tool_returns()
    assert (score.failed, answer) == (0, "sample")


def test_the_run_takes_its_window_from_the_task_verification(
    cases: list[StageCase], stage_repo: StageRepo, config: Callable[..., Path]
) -> None:
    window = 12_000
    config(
        ai={
            "tasks": {
                "stage": {"context_window": 262_144},
                "verification": {"context_window": window},
            }
        }
    )
    case = _case(cases, stage_repo, "bad", (_defect(DefectType.OTHER),))
    filler = " ".join(f"word{number}" for number in range(window))
    script = Script(call("search_code", text=filler), Verification())

    evaluate_cases(
        "m-1", [case], _client(ModelFake()), stage_repo.clone, toolbox=ToolboxModel(script.model())
    )

    request = json.loads(script.prompt())
    assert (request["files"], bool(script.tools_offered[0]), script.tools_offered[1]) == (
        {},
        True,
        [],
    )


def test_the_model_option_keeps_the_rest_of_the_verification_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved: list[AIConfig] = []
    monkeypatch.setattr(
        factory,
        "get_task_model",
        lambda task, *, settings: resolved.append(settings.ai.for_task(task)),
    )
    base = settings.load_settings()
    task = settings.AITaskOverride(provider="gateway", model="configured", temperature=0.25)
    tasks = base.ai.tasks.model_copy(update={"verification": task})
    chosen = base.model_copy(
        update={"ai": base.ai.model_copy(update={"provider": "ollama", "tasks": tasks})}
    )

    _review_model(chosen, "m-1")

    (config,) = resolved
    assert (config.model, config.provider, config.temperature) == ("m-1", "gateway", 0.25)


def test_a_run_states_the_recall_floor_of_the_blocker_and_major_defects(
    cli: Cli,
    tmp_path: Path,
    cases: list[StageCase],
    stage_repo: StageRepo,
    model_fake: ModelFake,
) -> None:
    bad = _case(cases, stage_repo, "bad", (_defect(DefectType.FALSE_PREMISE, Severity.BLOCKER),))
    folder = _write_set(tmp_path, bad)
    model_fake.answer(Verification(findings=[_finding(DefectType.FALSE_PREMISE)]))

    result = _verify(
        cli, "--cases", str(folder), "--source", str(stage_repo.clone), "--model", "m-1"
    )

    assert result.exit_code == 0, result.output
    assert (
        "Floor of the blocker and major defects: 90%. The recall of 100% reaches it."
        in result.output
    )


def test_the_dry_run_names_an_agent_run_for_each_case() -> None:
    planned = planned_verify_calls(load_cases()[:2], "https://gateway.example.com")

    assert (len(planned), all("agent run" in call.repeat for call in planned)) == (2, True)
