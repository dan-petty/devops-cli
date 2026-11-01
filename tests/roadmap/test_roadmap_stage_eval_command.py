"""`devops roadmap eval stage`: the options, the modes, the report and the exit codes (#3028)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.roadmap.stage_eval_cases import CASES_DIRECTORY, StageCase, load_cases
from tests.support.builders import make_stage_proposal
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_stage import VALID_REPORT, StageRepo, validate_args

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
    assert "replay through the gates: 40 case(s), 3 good" in result.output
    assert "paths  #3010  missing_path" in result.output
    assert "Defects that wait for a gate" in result.output
    assert "Good plans that every gate accepts: 3 of 3." in result.output
    assert "Result: every gate refuses what it must refuse." in result.output


def test_the_replay_as_json_holds_the_totals_of_each_gate(cli: Cli) -> None:
    result = _eval(cli, "--replay", "--json")

    report = json.loads(result.output)
    assert result.exit_code == 0
    assert [(g["gate"], g["missed"]) for g in report["gates"]] == [("paths", 0), ("kind", 0)]
    assert report["failures"] == []


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
    assert "the analysis model m-1" in result.output
    assert "Defect type" in result.output
    assert "Score: the model avoided" in result.output
    assert "Cases by end: staged 1" in result.output
    stored = result.output.split("Stored the report in ")[1].split(".json")[0] + ".json"
    report = json.loads(Path(stored.strip()).read_text(encoding="utf-8"))
    assert (report["model"], report["cases"]) == ("m-1", 1)
    assert model_fake.call_count == 1


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
