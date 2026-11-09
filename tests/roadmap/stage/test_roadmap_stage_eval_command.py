"""`devops roadmap eval stage`: the options, the modes, the report and the exit codes (#3028)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.ai.client import factory
from devops_cli.roadmap.stage.stage_eval_cases import (
    CASES_DIRECTORY,
    NO_COMMIT,
    StageCase,
    load_cases,
)
from tests.support.builders import make_stage_proposal
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_stage import VALID_REPORT, StageRepo, validate_args
from tests.support.scripted_model import Script, call

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]
CHANGE = "1-the-job-drops-a-comment"
SET = REPO_ROOT / CASES_DIRECTORY


@pytest.fixture(scope="module")
def cases() -> list[StageCase]:
    return load_cases(SET)


def _eval(cli: Cli, *args: str) -> Any:
    return cli("roadmap", "eval", "stage", *args)


def _live_set(tmp_path: Path, repo: StageRepo, cases: list[StageCase]) -> Path:
    """A folder with one case about issue #1 of the sample repository, staged on its head."""
    base = next(c for c in cases if c.defects and c.defects[0].paths)
    case = base.model_copy(
        update={
            "issue": 1,
            "title": "fix(roadmap): the job drops a comment",
            "issue_body": "The job drops the last comment of a thread.",
            "change": CHANGE,
            "base_commit": repo.git("rev-parse", "HEAD"),
        }
    )
    folder = tmp_path / "set" / "live-case"
    folder.mkdir(parents=True)
    meta = case.model_dump(mode="json", exclude={"name", "issue_body", "plan", "facts"})
    (folder / "case.json").write_text(json.dumps(meta), encoding="utf-8")
    (folder / "issue.txt").write_text(case.issue_body, encoding="utf-8")
    (folder / "plan.json").write_text(json.dumps(case.plan), encoding="utf-8")
    (folder / "facts.json").write_text(case.facts.model_dump_json(), encoding="utf-8")
    return folder.parent


def test_the_group_lists_the_stage_command(cli: Cli) -> None:
    result = cli("roadmap", "eval", "--help")

    assert result.exit_code == 0
    assert "stage" in result.output


def test_the_replay_exits_0_and_lists_what_each_gate_caught(cli: Cli) -> None:
    result = _eval(cli, "--replay")

    assert result.exit_code == 0, result.output
    assert "replay through the gates: 56 case(s), 5 good" in result.output
    assert "paths    #3010" in result.output
    assert "spec_delta_wrong" in result.output
    assert "Defects that a gate judges: 81 of 317 (26%)." in result.output
    assert "Defects that wait for a gate" not in result.output
    assert "Good plans that every gate accepts: 5 of 5." in result.output
    assert "Result: every gate refuses what it must refuse." in result.output


def test_the_replay_as_json_holds_the_totals_of_each_gate(cli: Cli) -> None:
    result = _eval(cli, "--replay", "--json")

    report = json.loads(result.output)
    assert result.exit_code == 0
    assert [(g["gate"], g["missed"]) for g in report["gates"]] == [
        ("paths", 0),
        ("kind", 0),
        ("criteria", 0),
        ("content", 0),
        ("prompt_keys", 0),
    ]
    assert report["failures"] == []
    assert report["defects"] == {"judged": 81, "known": 317}
    assert {t["type"]: (t["caught"], t["missed"], t["unjudged"]) for t in report["types"]}[
        "verify_form"
    ] == (6, 0, 12)


def test_a_replay_of_a_broken_set_exits_1_and_names_the_case(
    cli: Cli, tmp_path: Path, cases: list[StageCase]
) -> None:
    case = next(c for c in cases if c.defects and c.defects[0].paths)
    shutil.copytree(SET / case.name, tmp_path / case.name)
    facts = json.loads((tmp_path / case.name / "facts.json").read_text(encoding="utf-8"))
    paths = [p for d in case.defects for p in d.paths]
    facts["tracked"] = [*facts["tracked"], *paths]
    (tmp_path / case.name / "facts.json").write_text(json.dumps(facts), encoding="utf-8")

    result = _eval(cli, "--replay", "--cases", str(tmp_path))

    assert result.exit_code == 1
    assert f"{case.name}: the gate `paths` no longer refuses" in result.output


def test_case_and_limit_pick_the_cases(cli: Cli, cases: list[StageCase]) -> None:
    one = _eval(cli, "--replay", "--case", str(cases[3].issue))
    two = _eval(cli, "--replay", "--limit", "2")

    assert "1 case(s)" in one.output
    assert "2 case(s)" in two.output


def test_an_unknown_case_exits_1_and_names_it(cli: Cli) -> None:
    result = _eval(cli, "--replay", "--case", "no-such-case")

    assert result.exit_code == 1
    assert "no-such-case" in result.output


def test_a_missing_folder_exits_1_and_says_so(cli: Cli, tmp_path: Path) -> None:
    result = _eval(cli, "--replay", "--cases", str(tmp_path / "nothing"))

    assert result.exit_code == 1
    assert "no case" in result.output


def test_the_dry_run_makes_no_model_call_and_names_the_case(
    cli: Cli, model_fake: ModelFake, cases: list[StageCase]
) -> None:
    result = _eval(cli, "--dry-run", "--case", cases[0].name)

    assert result.exit_code == 0, result.output
    assert f"plan of the case {cases[0].name}" in result.output
    assert "Dry run: no request was made." in result.output
    assert model_fake.call_count == 0


def test_a_live_run_prints_the_score_and_stores_the_report(
    cli: Cli,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
    cases: list[StageCase],
) -> None:
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))
    folder = _live_set(tmp_path, stage_repo, cases)
    model_fake.answer(make_stage_proposal())

    result = _eval(cli, "--cases", str(folder), "--source", str(stage_repo.clone), "--model", "m-1")

    assert result.exit_code == 0, result.output
    assert "the stage model m-1" in result.output
    assert "Defect type" in result.output
    assert "Score: the model avoided" in result.output
    assert "Cases by end: staged 1" in result.output
    stored = result.output.split("Stored the report in ")[1].split(".json")[0] + ".json"
    report = json.loads(Path(stored.strip()).read_text(encoding="utf-8"))
    assert (report["model"], report["cases"]) == ("m-1", 1)
    assert model_fake.call_count == 1


def _live_run(
    cli: Cli,
    tmp_path: Path,
    stage_repo: StageRepo,
    cases: list[StageCase],
    script: Script,
    monkeypatch: pytest.MonkeyPatch,
    *flags: str,
) -> tuple[Any, list[str]]:
    """A live run of one case whose model is `script`, and the names of the tasks whose pydantic-ai
    model the command asked for."""
    asked: list[str] = []

    def task_model(name: str, *, settings: Any = None) -> Any:
        asked.append(name)
        return script.model()

    monkeypatch.setattr(factory, "get_task_model", task_model)
    folder = _live_set(tmp_path, stage_repo, cases)
    result = _eval(
        cli, "--cases", str(folder), "--source", str(stage_repo.clone), "--model", "m-1", *flags
    )
    return result, asked


def test_a_live_run_plans_with_the_toolbox_unless_told_not_to(
    cli: Cli,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
    cases: list[StageCase],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))
    script = Script(call("read_file", path="src/devops_cli/sample.py"), make_stage_proposal())

    result, asked = _live_run(cli, tmp_path, stage_repo, cases, script, monkeypatch)

    assert result.exit_code == 0, result.output
    assert (asked, script.tools_offered[0][:2], model_fake.call_count) == (
        ["stage"],
        ["list_files", "read_file"],
        0,
    )
    assert "Cases by end: staged 1" in result.output


def test_a_live_run_with_no_toolbox_makes_one_request_and_offers_no_tool(
    cli: Cli,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
    cases: list[StageCase],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))
    model_fake.answer(make_stage_proposal())
    script = Script(make_stage_proposal())

    result, asked = _live_run(cli, tmp_path, stage_repo, cases, script, monkeypatch, "--no-toolbox")

    assert result.exit_code == 0, result.output
    assert (asked, script.seen, model_fake.call_count) == ([], [], 1)
    assert "Cases by end: staged 1" in result.output


def test_both_modes_store_a_report_of_the_same_shape(
    cli: Cli,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
    cases: list[StageCase],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT), (0, VALID_REPORT))
    model_fake.answer(make_stage_proposal())
    reports = []
    for flags in ((), ("--no-toolbox",)):
        result, _ = _live_run(
            cli,
            tmp_path / str(len(reports)),
            stage_repo,
            cases,
            Script(make_stage_proposal()),
            monkeypatch,
            *flags,
        )
        stored = result.output.split("Stored the report in ")[1].split(".json")[0] + ".json"
        reports.append(json.loads(Path(stored.strip()).read_text(encoding="utf-8")))

    assert reports[0].keys() == reports[1].keys()
    assert [row.keys() for row in reports[0]["rows"]] == [row.keys() for row in reports[1]["rows"]]


def test_the_dry_run_names_the_toolbox_and_the_option_that_turns_it_off(
    cli: Cli, cases: list[StageCase]
) -> None:
    on = _eval(cli, "--dry-run", "--case", cases[0].name)
    off = _eval(cli, "--dry-run", "--no-toolbox", "--case", cases[0].name)

    assert "with the read-only toolbox" in on.output
    assert "with one call and no tool" in off.output


def test_a_live_run_with_a_failed_case_exits_1(
    cli: Cli,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
    cases: list[StageCase],
) -> None:
    from devops_cli.ai.client.models import AIClientError

    folder = _live_set(tmp_path, stage_repo, cases)
    model_fake.answer(AIClientError("the model is down"))

    result = _eval(cli, "--cases", str(folder), "--source", str(stage_repo.clone), "--json")

    assert result.exit_code == 1
    assert "1 case(s) could not run" in result.output


def _copy_of_the_live_case(folder: Path, name: str, **changes: str) -> None:
    """Add the case `name` to the set `folder`: a copy of `live-case` with `changes` in its
    `case.json`."""
    shutil.copytree(folder / "live-case", folder / name)
    path = folder / name / "case.json"
    path.write_text(
        json.dumps({**json.loads(path.read_text(encoding="utf-8")), **changes}), encoding="utf-8"
    )


def test_a_live_run_leaves_out_a_case_that_holds_no_commit_and_names_it_and_exits_0(
    cli: Cli,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
    cases: list[StageCase],
) -> None:
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))
    folder = _live_set(tmp_path, stage_repo, cases)
    _copy_of_the_live_case(folder, "a-no-commit", base_commit=NO_COMMIT, merge_commit=NO_COMMIT)
    model_fake.answer(make_stage_proposal())

    result = _eval(cli, "--cases", str(folder), "--source", str(stage_repo.clone), "--model", "m-1")

    assert result.exit_code == 0, result.output
    assert "Left out of the run, as they hold no commit to check out: a-no-commit." in result.output
    assert "Cases by end: staged 1" in result.output
    report = _stored_report(result)
    assert (report["cases"], report["left_out"]) == (1, ["a-no-commit"])
    assert model_fake.call_count == 1


def test_a_run_that_leaves_out_no_case_has_an_empty_list(
    cli: Cli,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
    cases: list[StageCase],
) -> None:
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))
    folder = _live_set(tmp_path, stage_repo, cases)
    model_fake.answer(make_stage_proposal())

    result = _eval(cli, "--cases", str(folder), "--source", str(stage_repo.clone))

    assert result.exit_code == 0, result.output
    assert "Left out" not in result.output
    assert _stored_report(result)["left_out"] == []


def test_the_dry_run_lists_the_calls_of_the_cases_with_a_commit_and_names_the_others(
    cli: Cli,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    cases: list[StageCase],
) -> None:
    folder = _live_set(tmp_path, stage_repo, cases)
    _copy_of_the_live_case(folder, "a-no-commit", base_commit=NO_COMMIT, merge_commit=NO_COMMIT)

    result = _eval(cli, "--dry-run", "--cases", str(folder))

    assert result.exit_code == 0, result.output
    assert "plans 1 case(s)" in result.output
    assert "plan of the case live-case" in result.output
    assert "plan of the case a-no-commit" not in result.output
    assert "Left out of the run, as they hold no commit to check out: a-no-commit." in result.output
    assert model_fake.call_count == 0


def test_a_selection_of_cases_that_hold_no_commit_exits_1_and_names_them(
    cli: Cli,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    cases: list[StageCase],
) -> None:
    folder = _live_set(tmp_path, stage_repo, cases)
    _copy_of_the_live_case(folder, "a-no-commit", base_commit=NO_COMMIT, merge_commit=NO_COMMIT)

    result = _eval(cli, "--cases", str(folder), "--case", "a-no-commit")

    assert result.exit_code == 1
    assert "a-no-commit" in result.output
    assert model_fake.call_count == 0


def test_the_replay_keeps_a_case_that_holds_no_commit(cli: Cli, cases: list[StageCase]) -> None:
    unmerged = next(case for case in cases if not case.has_commit and case.pull != 3205)

    result = _eval(cli, "--replay", "--case", unmerged.name)

    assert result.exit_code == 0, result.output
    assert "1 case(s)" in result.output


def test_a_commit_that_the_repository_lacks_ends_its_case_and_the_other_case_is_stored(
    cli: Cli,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
    cases: list[StageCase],
) -> None:
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))
    folder = _live_set(tmp_path, stage_repo, cases)
    _copy_of_the_live_case(folder, "z-lacking", base_commit="1" * 40)
    model_fake.answer(make_stage_proposal())

    result = _eval(cli, "--cases", str(folder), "--source", str(stage_repo.clone))

    assert result.exit_code == 1
    assert "1 case(s) could not run" in result.output
    report = _stored_report(result)
    assert (report["cases"], report["ended"]["staged"], report["ended"]["failed"]) == (2, 1, 1)


def _stored_report(result: Any) -> dict[str, Any]:
    stored = result.output.split("Stored the report in ")[1].split(".json")[0] + ".json"
    report: dict[str, Any] = json.loads(Path(stored.strip()).read_text(encoding="utf-8"))
    return report


def test_the_report_of_a_toolbox_run_holds_the_tokens_and_the_spend_of_the_run(
    cli: Cli,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
    cases: list[StageCase],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from genai_prices import Usage, calc_price

    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))
    script = Script(call("read_file", path="src/devops_cli/sample.py"), make_stage_proposal())
    folder = _live_set(tmp_path, stage_repo, cases)
    monkeypatch.setattr(factory, "get_task_model", lambda name, *, settings=None: script.model())

    result = _eval(
        cli,
        "--cases",
        str(folder),
        "--source",
        str(stage_repo.clone),
        "--model",
        "claude-sonnet-5-5",
    )

    usage = _stored_report(result)["usage"]
    assert result.exit_code == 0, result.output
    assert usage["input_tokens"] > 0
    assert usage["output_tokens"] > 0
    price = calc_price(
        Usage(input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"]),
        "claude-sonnet-5-5",
    )
    assert usage["spend_usd"] == pytest.approx(float(price.total_price))
    assert f"Tokens: {usage['input_tokens']} in, {usage['output_tokens']} out" in result.output


def test_the_report_names_no_spend_for_a_model_that_has_no_price(
    cli: Cli,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
    cases: list[StageCase],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))
    script = Script(make_stage_proposal())
    folder = _live_set(tmp_path, stage_repo, cases)
    monkeypatch.setattr(factory, "get_task_model", lambda name, *, settings=None: script.model())

    result = _eval(
        cli, "--cases", str(folder), "--source", str(stage_repo.clone), "--model", "no-such-model-1"
    )

    assert result.exit_code == 0, result.output
    assert _stored_report(result)["usage"]["spend_usd"] is None
    assert "Spend: no price for the model." in result.output
