"""`devops roadmap eval implement` (#3030): what the command layer owns, the options, the output,
the exit code, the dry run and the report file. The run itself is tested in
`tests/roadmap/test_roadmap_implement_eval_run.py`."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.client import factory
from devops_cli.config.settings import load_settings
from devops_cli.core.repo import resolve_data_path
from devops_cli.roadmap.implement_eval_run import eval_model
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import command_text, the_whole_group
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_eval import case_data, eval_repo, write_fixture

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]


@pytest.fixture
def fixtures(tmp_path: Path) -> Path:
    """A folder of two fixtures, each with a good and a scratch result."""
    root = tmp_path / "fixtures"
    root.mkdir()
    write_fixture(root, folder="a-case", case=case_data(name="a-case"))
    write_fixture(root, folder="b-case", case=case_data(name="b-case"))
    return root


def _eval(cli: Cli, fixtures: Path, *flags: str, source: Path | None = None) -> Any:
    args = ["roadmap", "eval", "implement", "--fixtures", str(fixtures), *flags]
    if source is not None:
        args += ["--source", str(source)]
    return cli(*args)


def test_a_dry_run_lists_the_steps_and_makes_no_request(
    cli: Cli, fixtures: Path, process_fake: ProcessFake
) -> None:
    result = _eval(cli, fixtures, "--dry-run", "--model", "example-model")

    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines()[0:4] == [
        "Dry run: no request was made, nothing was cloned and no model ran. The steps are:",
        "- a-case: issue #1, group 1, base 0123456789ab",
        "- b-case: issue #1, group 1, base 0123456789ab",
        "",
    ]
    assert "1. model request example-model for group 1 of item #1 (fixture a-case)" in result.stdout
    assert process_fake.calls == []


def test_a_chosen_fixture_alone_is_listed(cli: Cli, fixtures: Path) -> None:
    result = _eval(cli, fixtures, "--dry-run", "--fixture", "b-case")

    assert "- b-case: " in result.stdout
    assert "a-case" not in result.stdout


def test_a_fixture_that_does_not_exist_exits_1_and_lists_the_known_names(
    cli: Cli, fixtures: Path
) -> None:
    result = _eval(cli, fixtures, "--dry-run", "--fixture", "c-case")

    assert result.exit_code == 1
    assert "No fixture is named c-case. The fixtures are: a-case, b-case." in result.output


def test_a_check_of_recorded_results_exits_0_when_every_result_behaves_as_recorded(
    cli: Cli, fixtures: Path, process_fake: ProcessFake
) -> None:
    result = _eval(cli, fixtures, "--check-only")

    assert result.exit_code == 0, result.output
    assert "Implement eval of recorded results: 4 result(s)." in result.stdout
    assert "a-case / scratch: recorded (issue #1, group 1)" in result.stdout
    assert "Properties: 12 passed, 4 failed, 0 skipped." in result.stdout
    assert process_fake.calls == []


def test_a_check_exits_1_for_a_result_that_fails_other_properties_than_recorded(
    cli: Cli, tmp_path: Path
) -> None:
    results = [{"name": "good", "source": "a test", "diff": "good.diff", "fails": ["diff_scope"]}]
    root = tmp_path / "fixtures"
    root.mkdir()
    write_fixture(root, folder="odd", case=case_data(name="odd", results=results))

    result = _eval(cli, root, "--check-only")

    assert result.exit_code == 1
    assert "Not as recorded: expected to fail diff_scope, failed nothing." in result.stdout
    assert "1 recorded result(s) differ from their record." in result.stdout


def test_a_check_prints_the_report_as_json(cli: Cli, fixtures: Path) -> None:
    result = _eval(cli, fixtures, "--check-only", "--json", "--fixture", "a-case")

    printed = json.loads(result.stdout)
    assert (result.exit_code, printed["model"], [r["result"] for r in printed["results"]]) == (
        0,
        "",
        ["good", "scratch"],
    )


def test_a_check_with_commands_clones_the_base_and_runs_the_command_properties(
    cli: Cli, tmp_path: Path, implement_programs: ProcessFake
) -> None:
    repo, base = eval_repo(tmp_path / "repo")
    root = tmp_path / "fixtures"
    root.mkdir()
    write_fixture(root, folder="a-case", case=case_data(name="a-case", base=base))

    result = _eval(cli, root, "--check-only", "--run-commands", source=repo)

    assert result.exit_code == 0, result.output
    assert "pass    tests_pass" in result.stdout
    assert "pass    verify_passes" in result.stdout


@pytest.mark.parametrize(("recorded", "exit_code"), [([], 1), (["verify_passes"], 0)])
def test_a_check_with_commands_exits_1_when_a_command_property_differs_from_the_record(
    cli: Cli,
    tmp_path: Path,
    implement_programs: ProcessFake,
    recorded: list[str],
    exit_code: int,
) -> None:
    implement_programs.answer(
        lambda call: command_text(call) == "uv run devops docs check", ProcessAnswer(returncode=1)
    )
    repo, base = eval_repo(tmp_path / "repo")
    results = [{"name": "good", "source": "a test", "diff": "good.diff", "fails": recorded}]
    root = tmp_path / "fixtures"
    root.mkdir()
    write_fixture(root, folder="a-case", case=case_data(name="a-case", base=base, results=results))

    result = _eval(cli, root, "--check-only", "--run-commands", source=repo)

    assert result.exit_code == exit_code, result.output
    assert "fail    verify_passes" in result.stdout


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        (["--check-only", "--dry-run"], "--check-only and --dry-run cannot be used together."),
        (["--check-only", "--model", "x"], "--check-only and --model cannot be used together."),
        (["--run-commands"], "--run-commands needs --check-only."),
    ],
)
def test_options_that_cannot_go_together_exit_1(
    cli: Cli, fixtures: Path, flags: list[str], message: str
) -> None:
    result = _eval(cli, fixtures, *flags)

    assert result.exit_code == 1
    assert message in result.output


def test_a_run_prints_the_report_and_writes_the_json_report_under_the_data_directory(
    cli: Cli, tmp_path: Path, implement_programs: ProcessFake
) -> None:
    repo, base = eval_repo(tmp_path / "repo")
    root = tmp_path / "fixtures"
    root.mkdir()
    write_fixture(root, folder="a-case", case=case_data(name="a-case", base=base))
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."))
    factory.set_llm_client_override(script.model())

    result = _eval(cli, root, source=repo)

    reports = sorted(
        (resolve_data_path(load_settings().data.dir) / "eval" / "implement").glob(
            "implement-*.json"
        )
    )
    assert result.exit_code == 0, result.output
    assert "a-case / step: done (issue #1, group 1)" in result.stdout
    assert "Running fixture a-case (1 of 1)." in result.stderr
    assert len(reports) == 1
    written = json.loads(reports[0].read_text(encoding="utf-8"))
    assert [(r["fixture"], r["status"], r["tool_calls"]) for r in written["results"]] == [
        ("a-case", "done", 3)
    ]
    assert f"Report: {reports[0]}" in result.stderr


def test_a_run_that_fails_on_the_second_fixture_still_writes_the_report_of_the_first(
    cli: Cli, tmp_path: Path, implement_programs: ProcessFake
) -> None:
    repo, base = eval_repo(tmp_path / "repo")
    root = tmp_path / "fixtures"
    root.mkdir()
    for name in ("a-case", "b-case"):
        write_fixture(root, folder=name, case=case_data(name=name, base=base))
    script = ModelScript(tool_calls(*the_whole_group()), say("Done."), ValueError("model broke"))
    factory.set_llm_client_override(script.model())

    result = _eval(cli, root, source=repo)

    reports = sorted(
        (resolve_data_path(load_settings().data.dir) / "eval" / "implement").glob(
            "implement-*.json"
        )
    )
    assert result.exit_code != 0
    assert len(reports) == 1
    written = json.loads(reports[0].read_text(encoding="utf-8"))
    assert [(r["fixture"], r["status"]) for r in written["results"]] == [("a-case", "done")]
    assert "a-case / step: done" in result.stdout
    assert f"Report: {reports[0]}" in result.stderr


def test_the_chosen_model_replaces_the_model_of_the_implement_task(
    config: Callable[..., Path],
) -> None:
    config(ai={"tasks": {"implement": {"model": "task-model", "context_window": 9000}}})
    factory.set_llm_client_override(ModelScript(say("x")).model())

    _, window, name = eval_model("chosen-model")
    _, same_window, task_name = eval_model(None)

    assert (name, window, task_name, same_window) == ("chosen-model", 9000, "task-model", 9000)
