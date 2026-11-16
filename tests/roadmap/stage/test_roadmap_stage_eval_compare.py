"""The comparison of the stage toolsets: the engine that measures a toolset, its row and its table
(#3239)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.roadmap.stage.stage_eval_cases import (
    CASES_DIRECTORY,
    STAGED_CASES_DIRECTORY,
    StageCase,
    Verdict,
    load_cases,
    load_staged_cases,
)
from tests.support.builders import make_stage_proposal
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_stage import VALID_REPORT, StageRepo, run_git, validate_args
from tests.support.scripted_model import Script, call

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage import StageClient
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
    """A case about issue #1 of the sample repository, staged on its head commit."""
    base = next(case for case in cases if case.has_commit)
    return base.model_copy(
        update={
            "issue": 1,
            "title": "fix(roadmap): the job drops a comment",
            "issue_body": "The job drops the last comment of a thread.",
            "change": CHANGE,
            "base_commit": repo.git("rev-parse", "HEAD"),
        }
    )


def _client(_model_fake: ModelFake) -> StageClient:
    from devops_cli.ai.client import get_llm_client

    return get_llm_client(task="analysis")


def test_the_engine_measures_each_toolset(
    cases: list[StageCase],
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec: OpenSpecFake,
) -> None:
    from genai_prices import Usage, calc_price

    from devops_cli.roadmap.stage.stage_eval_compare import run_toolset

    case = _live_case(cases, stage_repo)
    base_script = Script(call("read_file", path="src/devops_cli/sample.py"), make_stage_proposal())
    extended_script = Script(
        call("read_file", path="src/devops_cli/sample.py"), make_stage_proposal()
    )

    base = run_toolset(
        "base",
        [case],
        _client(model_fake),
        stage_repo.clone,
        toolbox=base_script.model(),
        model="claude-sonnet-5-5",
    )
    extended = run_toolset(
        "extended",
        [case],
        _client(model_fake),
        stage_repo.clone,
        toolbox=extended_script.model(),
        model="claude-sonnet-5-5",
    )

    assert (base.toolset, extended.toolset) == ("base", "extended")
    assert [measure.case for measure in base.measures] == [case.name]
    assert (base.gate_defects, base.verification_defects) == (0, None)
    assert (base.tool_calls, base.requests, extended.tool_calls, extended.requests) == (
        1,
        2,
        1,
        2,
    )
    assert base.input_tokens > 0
    assert base.output_tokens > 0
    assert len(base_script.tools_offered[0]) < len(extended_script.tools_offered[0])
    assert base.cost == pytest.approx(
        float(
            calc_price(
                Usage(input_tokens=base.input_tokens, output_tokens=base.output_tokens),
                "claude-sonnet-5-5",
            ).total_price
        )
    )


def test_the_table_shows_one_row_for_each_toolset_and_a_delta_line_to_the_first() -> None:
    from devops_cli.roadmap.stage.stage_eval_compare import Measure, render_compare, row_of

    base = row_of("base", [Measure("case-a", 1, None, 2, 4, 100, 50, 1.0, 0.5)])
    extended = row_of("extended", [Measure("case-a", 0, None, 3, 6, 300, 70, 2.0, 1.5)])

    text = render_compare([base, extended])

    assert "Gate defects" in text
    assert "Verification defects" in text
    assert "Tool calls" in text
    assert "Input tokens" in text
    assert "Output tokens" in text
    assert "Elapsed time" in text
    assert "Cost" in text
    assert "not run" in text
    delta_line = next(line for line in text.splitlines() if "extended - base" in line)
    assert delta_line.split()[3:] == ["-1", "not", "run", "1", "2", "200", "20", "1.00", "1.0000"]
    # The table keeps the raw values of each row beside the delta line.
    base_line = next(line for line in text.splitlines() if line.startswith("base"))
    assert base_line.split()[4:8] == ["2", "4", "100", "50"]


def test_the_table_names_a_model_that_has_no_price() -> None:
    from devops_cli.roadmap.stage.stage_eval_compare import Measure, render_compare, row_of

    row = row_of("base", [Measure("case-a", 0, None, 1, 2, 10, 5, 0.5, None)])

    assert "unpriced" in render_compare([row])


def test_the_spread_states_the_minimum_and_the_maximum_of_each_value() -> None:
    from devops_cli.roadmap.stage.stage_eval_compare import Measure, spread

    measures = [
        Measure("case-a", 1, None, 2, 4, 100, 50, 1.0, 0.5),
        Measure("case-a", 3, None, 5, 8, 300, 90, 2.0, 1.5),
    ]

    values = spread(measures)

    assert (values.gate_defects, values.tool_calls, values.requests) == ((1, 3), (2, 5), (4, 8))
    assert (values.input_tokens, values.output_tokens) == ((100, 300), (50, 90))
    assert (values.seconds, values.cost) == ((1.0, 2.0), (0.5, 1.5))
    assert values.verification_defects == (None, None)


def _write_case(folder: Path, case: StageCase) -> None:
    """Write `case` in the case format of the golden set, at `folder`."""
    folder.mkdir(parents=True)
    meta = case.model_dump(mode="json", exclude={"name", "issue_body", "plan", "facts"})
    (folder / "case.json").write_text(json.dumps(meta), encoding="utf-8")
    (folder / "issue.txt").write_text(case.issue_body, encoding="utf-8")
    (folder / "plan.json").write_text(json.dumps(case.plan), encoding="utf-8")
    (folder / "facts.json").write_text(case.facts.model_dump_json(), encoding="utf-8")


def _live_set(tmp_path: Path, repo: StageRepo, cases: list[StageCase]) -> Path:
    """A folder with one case about issue #1 of the sample repository, staged on its head."""
    folder = tmp_path / "set" / "live-case"
    _write_case(folder, _live_case(cases, repo))
    return folder.parent


def _staged_set(tmp_path: Path, repo: StageRepo, cases: list[StageCase]) -> Path:
    """A folder with one staged-item replay case about issue #1 of the sample repository."""
    folder = tmp_path / "staged-set" / "staged-case"
    _write_case(folder, _live_case(cases, repo))
    return folder.parent


@pytest.fixture
def no_staged_cases(tmp_path: Path) -> Path:
    """An empty folder of staged-item replay cases, so a test pins the golden set alone."""
    folder = tmp_path / "no-staged-cases"
    folder.mkdir()
    return folder


def test_the_compare_form_prints_one_table_with_a_fake_client(
    cli: Any,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec: OpenSpecFake,
    cases: list[StageCase],
    no_staged_cases: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devops_cli.ai.client import factory

    script = Script(call("read_file", path="src/devops_cli/sample.py"), make_stage_proposal())
    monkeypatch.setattr(factory, "get_task_model", lambda name, *, settings=None: script.model())
    folder = _live_set(tmp_path, stage_repo, cases)

    result = cli(
        "roadmap",
        "eval",
        "stage",
        "compare",
        "base",
        "extended",
        "--cases",
        str(folder),
        "--staged-cases",
        str(no_staged_cases),
        "--source",
        str(stage_repo.clone),
        "--model",
        "claude-sonnet-5-5",
    )

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert "Verification defects" in result.output
    assert "Tool calls" in result.output
    assert any(line.startswith("base") for line in lines)
    assert any(line.startswith("extended") for line in lines)
    assert any("extended - base" in line for line in lines)


def _three_runs_script() -> Script:
    """A script whose runs call the read tool once, twice and three times, so the tokens and the
    requests of the three runs of a case differ. Two toolsets read the same three runs in turn."""
    responses: list[Any] = []
    for calls in (1, 2, 3):
        responses += [call("read_file", path="src/devops_cli/sample.py")] * calls
        responses.append(make_stage_proposal())
    return Script(*(responses * 2))


def test_three_runs_state_the_count_and_the_spread(
    cli: Any,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec: OpenSpecFake,
    cases: list[StageCase],
    no_staged_cases: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devops_cli.ai.client import factory

    script = _three_runs_script()
    monkeypatch.setattr(factory, "get_task_model", lambda name, *, settings=None: script.model())
    folder = _live_set(tmp_path, stage_repo, cases)

    result = cli(
        "roadmap",
        "eval",
        "stage",
        "compare",
        "base",
        "extended",
        "--runs",
        "3",
        "--cases",
        str(folder),
        "--staged-cases",
        str(no_staged_cases),
        "--source",
        str(stage_repo.clone),
        "--model",
        "claude-sonnet-5-5",
    )

    assert result.exit_code == 0, result.output
    case_lines = [line for line in result.output.splitlines() if "runs=3" in line]
    assert len(case_lines) == 2
    base_line = next(line for line in case_lines if line.startswith("base/"))
    assert "tool calls 1..3" in base_line
    assert "requests 2..4" in base_line
    tokens = re.search(r"input tokens (\d+)\.\.(\d+)", base_line)
    assert tokens is not None
    assert int(tokens.group(1)) < int(tokens.group(2))


def test_the_verification_column_shows_not_run_without_a_pass(
    cli: Any,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec: OpenSpecFake,
    cases: list[StageCase],
    no_staged_cases: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devops_cli.ai.client import factory
    from devops_cli.roadmap.stage.stage_eval_cases import DefectType, Severity
    from devops_cli.roadmap.stage.stage_verify import Finding, Locator, PlanPart, Verification

    plan = Script(call("read_file", path="src/devops_cli/sample.py"), make_stage_proposal())
    review = Script(
        Verification(
            findings=[
                Finding(
                    type=DefectType.MISSING_PATH,
                    severity=Severity.BLOCKER,
                    where=Locator(part=PlanPart.TASKS, section="1.1"),
                    problem="The group reads a path that the plan does not name.",
                    quote="src/devops_cli/sample.py",
                )
            ]
        )
    )
    monkeypatch.setattr(
        factory,
        "get_task_model",
        lambda name, *, settings=None: review.model() if name == "stage_review" else plan.model(),
    )
    folder = _live_set(tmp_path, stage_repo, cases)
    common = (
        "roadmap",
        "eval",
        "stage",
        "compare",
        "base",
        "extended",
        "--runs",
        "1",
        "--cases",
        str(folder),
        "--staged-cases",
        str(no_staged_cases),
        "--source",
        str(stage_repo.clone),
        "--model",
        "claude-sonnet-5-5",
    )

    without = cli(*common)
    with_verify = cli(*common, "--verify")

    assert without.exit_code == 0, without.output
    unverified = next(line for line in without.output.splitlines() if line.startswith("base"))
    assert "not run" in unverified
    assert with_verify.exit_code == 0, with_verify.output
    verified = next(line for line in with_verify.output.splitlines() if line.startswith("base"))
    assert "not run" not in verified
    assert verified.split()[2] == "1"


def test_the_compare_dry_run_states_the_plan_and_the_cost_with_no_model_call(
    cli: Any,
    tmp_path: Path,
    stage_repo: StageRepo,
    cases: list[StageCase],
    no_staged_cases: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from genai_prices import Usage, calc_price

    from devops_cli.ai.client import factory
    from devops_cli.config.constants import (
        CONST_ROADMAP_STAGE_EVAL_ESTIMATE_INPUT_TOKENS,
        CONST_ROADMAP_STAGE_EVAL_ESTIMATE_OUTPUT_TOKENS,
    )

    script = Script(RuntimeError("the dry run called the model"))
    monkeypatch.setattr(factory, "get_task_model", lambda name, *, settings=None: script.model())
    folder = _live_set(tmp_path, stage_repo, cases)

    result = cli(
        "roadmap",
        "eval",
        "stage",
        "compare",
        "base",
        "extended",
        "--dry-run",
        "--cases",
        str(folder),
        "--staged-cases",
        str(no_staged_cases),
        "--model",
        "claude-sonnet-5-5",
    )

    assert result.exit_code == 0, result.output
    assert script.seen == []
    assert "1 case(s)" in result.output
    assert "3 run(s)" in result.output
    assert "base, extended" in result.output
    estimate = float(
        calc_price(
            Usage(
                input_tokens=CONST_ROADMAP_STAGE_EVAL_ESTIMATE_INPUT_TOKENS * 6,
                output_tokens=CONST_ROADMAP_STAGE_EVAL_ESTIMATE_OUTPUT_TOKENS * 6,
            ),
            "claude-sonnet-5-5",
        ).total_price
    )
    assert f"{estimate:.4f} USD" in result.output
    unpriced = cli(
        "roadmap",
        "eval",
        "stage",
        "compare",
        "base",
        "extended",
        "--dry-run",
        "--cases",
        str(folder),
        "--staged-cases",
        str(no_staged_cases),
        "--model",
        "no-such-model",
    )
    assert unpriced.exit_code == 0, unpriced.output
    assert "no price for the model no-such-model" in unpriced.output


def test_the_comparison_runs_a_golden_case_and_a_staged_item_case(
    cli: Any,
    tmp_path: Path,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec: OpenSpecFake,
    cases: list[StageCase],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devops_cli.ai.client import factory

    script = Script(make_stage_proposal())
    monkeypatch.setattr(factory, "get_task_model", lambda name, *, settings=None: script.model())
    golden = _live_set(tmp_path, stage_repo, cases)
    staged = _staged_set(tmp_path, stage_repo, cases)

    result = cli(
        "roadmap",
        "eval",
        "stage",
        "compare",
        "base",
        "extended",
        "--runs",
        "3",
        "--cases",
        str(golden),
        "--staged-cases",
        str(staged),
        "--source",
        str(stage_repo.clone),
        "--model",
        "claude-sonnet-5-5",
    )

    assert result.exit_code == 0, result.output
    case_lines = [line for line in result.output.splitlines() if "runs=" in line]
    assert {line.split()[0] for line in case_lines} == {
        "base/live-case",
        "base/staged-case",
        "extended/live-case",
        "extended/staged-case",
    }
    assert all("runs=3" in line for line in case_lines)


STAGED_CASE = "3239-the-toolset-comparison"
STAGED_CHANGE = "3239-add-toolset-comparison-to-stage-planner"
CASE_FILES = ("case.json", "facts.json", "issue.txt", "plan.json")


def _tracked_case_files(name: str) -> list[str]:
    """The files of the case `name` that git tracks, so a run reads the case from a checkout."""
    folder = f"{STAGED_CASES_DIRECTORY}/{name}"
    return sorted(run_git(REPO_ROOT, "ls-files", "--", folder).splitlines())


def test_the_staged_item_case_loads_with_its_commit() -> None:
    """The staged-item replay set holds the plan of #3239 on the commit it was staged on, so a run
    can check it out, and the case is committed, because a run reads the cases of a checkout and a
    file that only the working tree holds is no case of the set."""
    staged = load_staged_cases()

    assert [case.name for case in staged] == [STAGED_CASE]
    (case,) = staged
    assert (case.issue, case.change) == (3239, STAGED_CHANGE)
    assert case.has_commit
    assert (case.merge_commit, case.base_commit) == (
        "8476ca294b3fefc894e7210e83ce42ceb5c644f2",
        "5a7238d4683b5dd245917b8e2476d9815c464a7f",
    )
    assert case.verdict is Verdict.GOOD
    assert case.defects == ()
    assert "src/devops_cli/commands/roadmap_eval_stage.py" in case.facts.tracked
    assert all(not path.startswith("/") for path in case.facts.tracked)
    assert len(case.groups) == 11
    folder = f"{STAGED_CASES_DIRECTORY}/{STAGED_CASE}"
    assert _tracked_case_files(STAGED_CASE) == [f"{folder}/{file}" for file in CASE_FILES]


def test_the_compare_form_refuses_a_lone_toolset_and_a_name_outside_the_setting(cli: Any) -> None:
    one = cli("roadmap", "eval", "stage", "compare", "base", "--dry-run", "--limit", "1")
    unknown = cli(
        "roadmap", "eval", "stage", "compare", "base", "nope", "--dry-run", "--limit", "1"
    )
    wrong_form = cli("roadmap", "eval", "stage", "compare-to", "--dry-run")

    assert one.exit_code == 1
    assert "at least two toolsets" in one.output
    assert unknown.exit_code == 1
    assert "base, extended, research" in unknown.output
    assert wrong_form.exit_code == 1
    assert "no form of this command" in wrong_form.output
