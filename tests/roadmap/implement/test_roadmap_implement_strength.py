"""The strength check of the implement job (#3051): the assertion scan of the new test files, the
bounded mutation run, and the coverage delta of the changed files.

The process edge is `process_fake`: it records the commands and answers them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import command_text

SCAN = "uv run ast-grep scan --rule .ast-grep/rules/test-function-has-assertion.yml --json"
MESSAGE = "Test function has no assert, no pytest.raises, and no assertion or double check."


def _match(path: str, line: int) -> dict[str, object]:
    """One match of the assertion rule, as `ast-grep scan --json` prints it, for the 1-based `line`
    of its function."""
    return {"file": path, "range": {"start": {"line": line - 1}}, "message": MESSAGE}


def test_a_new_test_file_that_asserts_nothing_is_flagged(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    from devops_cli.roadmap.implement.implement_strength import (
        AssertionFinding,
        assertion_failures,
    )

    sample = "tests/test_sample.py"
    (implement_checkout / sample).write_text(
        "def test_shout() -> None:\n    shout()\n", encoding="utf-8"
    )
    implement_programs.answer(
        lambda call: command_text(call).startswith(SCAN),
        ProcessAnswer(returncode=1, stdout=json.dumps([_match(sample, 1)])),
    )

    assert assertion_failures(implement_checkout, [sample]) == (
        AssertionFinding(sample, 1, MESSAGE),
    )


SELECTION_KEY = "pytest_add_cli_args_test_selection"
# The table of a checkout that has one: a comment and an array over several lines, as the
# `[tool.mutmut]` table of this repository has.
MUTMUT_TABLE = (
    '[project]\nname = "sample"\n\n[tool.mutmut]\n'
    "# The tests that read src as data.\n"
    f'{SELECTION_KEY} = [\n    "--ignore=tests/test_docs.py",\n]\n'
)


def _selection(checkout: Path) -> list[str]:
    """The test selection that mutmut reads from the `pyproject.toml` of `checkout`."""
    import tomllib

    table = tomllib.loads((checkout / "pyproject.toml").read_text(encoding="utf-8"))
    return list(table["tool"]["mutmut"].get(SELECTION_KEY, []))


def test_the_mutation_run_stops_at_command_timeout_seconds_and_keeps_its_survivors(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    import subprocess

    from devops_cli.ci.mutate import MutationTarget
    from devops_cli.roadmap.implement.implement_strength import (
        MutationOutcome,
        run_mutation,
    )

    target = MutationTarget(path="src/sample.py", line=1, class_name=None, name="shout")
    seen: list[list[str]] = []

    def out_of_time(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        seen.append(_selection(implement_checkout))
        raise subprocess.TimeoutExpired(cmd="uv", timeout=1)

    implement_programs.answer(
        lambda call: "mutmut run" in command_text(call),
        ProcessAnswer(side_effect=out_of_time),
    )
    implement_programs.answer(
        lambda call: "mutmut results" in command_text(call),
        ProcessAnswer(stdout="sample.x_shout__mutmut_1: survived\n"),
    )

    outcome = run_mutation(implement_checkout, [target], ["tests/test_sample.py"])
    assert outcome == MutationOutcome(
        survivors=(("sample.x_shout__mutmut_1", target),),
        timeout=True,
        skipped_files=(),
    )
    # A checkout with no `pyproject.toml` gets one for the run, and has none after it.
    assert seen == [["tests/test_sample.py"]]
    assert not (implement_checkout / "pyproject.toml").exists()


def test_the_mutation_run_sets_no_environment_key_that_the_process_runner_refuses(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    """`run_subprocess` refuses `PYTEST_ADDOPTS` in `build_subprocess_env` before the child starts
    (#2747). The process fake records the environment and checks nothing, so this test gives the
    recorded environment of the mutation run to the real check (#5887)."""
    from devops_cli.ci.mutate import MutationTarget
    from devops_cli.core.process import build_subprocess_env
    from devops_cli.roadmap.implement.implement_strength import run_mutation

    target = MutationTarget(path="src/sample.py", line=1, class_name=None, name="shout")

    run_mutation(implement_checkout, [target], ["tests/test_sample.py"])

    run_call = next(call for call in implement_programs.calls if "mutmut run" in command_text(call))
    child = build_subprocess_env(
        env=run_call.env,
        isolate_env=run_call.isolate_env,
        extra_allowed_keys=run_call.extra_allowed_env,
    )
    assert "PYTEST_ADDOPTS" not in child


def test_the_mutation_run_adds_the_scoped_tests_to_the_mutmut_table_and_restores_the_file(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    """`mutmut run` 3.8.1 takes no pytest argument, and reads the test selection of its stats
    run from `pytest_add_cli_args_test_selection` of `[tool.mutmut]`. The run adds the scoped
    test modules after the entries of the table, and the file holds its bytes again after it."""
    import subprocess

    from devops_cli.ci.mutate import MutationTarget
    from devops_cli.roadmap.implement.implement_strength import run_mutation

    pyproject = implement_checkout / "pyproject.toml"
    pyproject.write_text(MUTMUT_TABLE, encoding="utf-8")
    target = MutationTarget(path="src/sample.py", line=1, class_name=None, name="shout")
    seen: list[list[str]] = []

    def read_table(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        seen.append(_selection(implement_checkout))
        return subprocess.CompletedProcess([], 0, "", "")

    implement_programs.answer(
        lambda call: "mutmut run" in command_text(call),
        ProcessAnswer(side_effect=read_table),
    )

    run_mutation(implement_checkout, [target], ["tests/test_sample.py", "tests/test_other.py"])

    assert seen == [["--ignore=tests/test_docs.py", "tests/test_sample.py", "tests/test_other.py"]]
    assert pyproject.read_text(encoding="utf-8") == MUTMUT_TABLE


def test_more_changed_files_than_max_scoped_test_modules_are_named(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES
    from devops_cli.roadmap.implement.implement_strength import mutation_targets
    from tests.support.implement_step import git

    git(implement_checkout, "update-ref", "refs/remotes/origin/main", "HEAD")

    changed_files: list[str] = []
    count = CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES + 1
    for i in range(count):
        rel = f"src/sample_{i}.py"
        (implement_checkout / rel).write_text(
            f"def func_{i}() -> int:\n    return {i}\n", encoding="utf-8"
        )
        changed_files.append(rel)

    targets, skipped = mutation_targets(implement_checkout, changed_files, "main")
    assert len(skipped) == 1
    assert skipped == (changed_files[-1],)
    assert len({t.path for t in targets}) == CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES
    assert changed_files[-1] not in {t.path for t in targets}


def test_the_coverage_run_measures_the_scoped_test_modules(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    from devops_cli.roadmap.implement.implement_strength import coverage_delta

    sample = "tests/test_sample.py"
    implement_programs.answer(
        lambda call: "pytest" in command_text(call),
        ProcessAnswer(returncode=0),
    )
    implement_programs.answer(
        lambda call: "coverage xml" in command_text(call),
        ProcessAnswer(returncode=0),
    )
    implement_programs.answer(
        lambda call: "diff-cover" in command_text(call),
        ProcessAnswer(returncode=0, stdout="# Coverage: 100%\n"),
    )

    delta = coverage_delta(implement_checkout, "main", [sample])
    assert delta.passed is True
    assert "# Coverage: 100%" in delta.report

    commands = [command_text(call) for call in implement_programs.calls]
    assert any(
        "uv run pytest --cov=src --cov-report= --cov-fail-under=0 tests/test_sample.py" in cmd
        for cmd in commands
    )
    assert any("uv run coverage xml -q" in cmd for cmd in commands)
    assert any(
        "uv run diff-cover .data/coverage.xml --compare-branch=origin/main --fail-under 90 --format markdown:.data/coverage.md"
        in cmd
        for cmd in commands
    )


def test_an_uncovered_changed_line_is_in_the_coverage_report(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    from devops_cli.roadmap.implement.implement_strength import coverage_delta

    sample = "tests/test_sample.py"
    report_text = "# Diff Coverage\n## src/sample.py (0.0%)\nMissing lines: 2\n"
    implement_programs.answer(
        lambda call: "pytest" in command_text(call),
        ProcessAnswer(returncode=0),
    )
    implement_programs.answer(
        lambda call: "coverage xml" in command_text(call),
        ProcessAnswer(returncode=0),
    )
    implement_programs.answer(
        lambda call: "diff-cover" in command_text(call),
        ProcessAnswer(returncode=1, stdout=report_text),
    )

    delta = coverage_delta(implement_checkout, "main", [sample])
    assert delta.passed is False
    assert "Missing lines: 2" in delta.report


def test_each_test_module_path_is_one_argument_of_the_coverage_run(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    from devops_cli.roadmap.implement.implement_strength import coverage_delta

    test_modules = ["tests/test_a.py", "tests/test_b.py"]
    coverage_delta(implement_checkout, "main", test_modules)

    pytest_call = next(call for call in implement_programs.calls if "pytest" in call.argv)
    for mod in test_modules:
        assert mod in pytest_call.argv
    assert "tests/test_a.py tests/test_b.py" not in pytest_call.argv


def test_a_group_of_kind_other_is_left_out_with_its_reason(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    from devops_cli.roadmap.implement.implement_strength import (
        report_lines,
        strength_report,
        strength_scope,
    )
    from tests.support.implement_step import git

    tasks_md = """# Tasks

## 1. Documentation
Kind: other. Changes: docs/TESTING.md.
- [ ] 1.1 Update docs/TESTING.md

## 2. Code change
Kind: behavior. Changes: src/sample.py.
- [ ] 2.1 Update src/sample.py
"""
    changed = ["docs/TESTING.md", "src/sample.py"]
    active, skipped = strength_scope(tasks_md, changed)
    assert active == ("src/sample.py",)
    assert any(group_num == 1 for group_num, _ in skipped)

    git(implement_checkout, "update-ref", "refs/remotes/origin/main", "HEAD")

    report = strength_report(
        implement_checkout,
        tasks_md,
        changed,
        "main",
        ["tests/test_sample.py"],
    )
    lines = report_lines(report)
    assert any("group 1" in line and "other" in line for line in lines)


def test_a_surviving_mutant_fails_the_strength_check(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    from devops_cli.roadmap.implement.implement_strength import strength_report
    from tests.support.implement_step import git

    git(implement_checkout, "update-ref", "refs/remotes/origin/main", "HEAD")
    (implement_checkout / "src" / "sample.py").write_text(
        "def shout(text: str) -> str:\n    return text.upper()\n", encoding="utf-8"
    )

    tasks_md = """# Tasks

## 1. Behavior
Kind: behavior. Changes: src/sample.py.
- [ ] 1.1 Implement shout
"""
    implement_programs.answer(
        lambda call: "mutmut results" in command_text(call),
        ProcessAnswer(stdout="sample.x_shout__mutmut_1: survived\n"),
    )

    report = strength_report(
        implement_checkout,
        tasks_md,
        ["src/sample.py"],
        "main",
        ["tests/test_sample.py"],
    )
    assert report.passed is False
    assert len(report.surviving_mutants) == 1
    assert report.surviving_mutants[0][0] == "sample.x_shout__mutmut_1"


def test_a_failed_strength_report_is_a_failed_scoped_result() -> None:
    from devops_cli.roadmap.implement.implement_strength import (
        AssertionFinding,
        StrengthReport,
        scoped_result,
    )

    finding = AssertionFinding("tests/test_sample.py", 1, "missing assert")
    report = StrengthReport(passed=False, assertion_findings=(finding,))
    result = scoped_result(report)
    assert result.name == "strength"
    assert result.passed is False
    assert result.status == 1
    assert "missing assert" in result.log

    report_pass = StrengthReport(passed=True)
    result_pass = scoped_result(report_pass)
    assert result_pass.name == "strength"
    assert result_pass.passed is True
    assert result_pass.status == 0
    assert result_pass.log == ""


def test_the_comment_shows_the_strength_report_and_the_skip_reason(
    implement_checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import MagicMock

    from devops_cli.roadmap.implement.implement_run import _ItemRun
    from devops_cli.roadmap.implement.implement_strength import StrengthReport

    client = MagicMock()
    client.list_issue_comments.return_value = []
    session = MagicMock(client=client)
    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_run.get_github_session", lambda: session
    )

    target = MagicMock()
    target.item.job_record = {}
    target.pull = 123

    run = _ItemRun(
        store=MagicMock(),
        repo="org/repo",
        path=implement_checkout,
        target=target,
        model=None,
        window=1000,
        default="main",
        origin=MagicMock(),
    )
    run.strength = StrengthReport(
        passed=True,
        skipped_groups=((1, "kind other"),),
    )
    run._comment(123)

    assert client.comment_on_pull.called
    _repo, _pull, comment_body = client.comment_on_pull.call_args[0]
    assert "group 1" in comment_body
    assert "kind other" in comment_body


def test_mutation_targets_empty(implement_checkout: Path) -> None:
    from devops_cli.roadmap.implement.implement_strength import mutation_targets

    targets, skipped = mutation_targets(implement_checkout, [], "main")
    assert targets == ()
    assert skipped == ()


def test_mutation_targets_additional_files_in_all_targets(
    implement_checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.ci.mutate import MutationTarget
    from devops_cli.roadmap.implement.implement_strength import mutation_targets

    target1 = MutationTarget(path="src/a.py", line=1, class_name=None, name="a")
    target2 = MutationTarget(path="src/b.py", line=1, class_name=None, name="b")
    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_strength.select_targets",
        lambda *args, **kwargs: (target1, target2),
    )
    targets, _skipped = mutation_targets(implement_checkout, ["src/a.py"], "main")
    assert target1 in targets
    assert target2 in targets


def test_coverage_delta_empty_tests(implement_checkout: Path) -> None:
    from devops_cli.roadmap.implement.implement_strength import coverage_delta

    delta = coverage_delta(implement_checkout, "main", [])
    assert delta.passed is True


def test_coverage_delta_pytest_failure(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    from devops_cli.roadmap.implement.implement_strength import coverage_delta

    implement_programs.answer(
        lambda call: "pytest" in command_text(call),
        ProcessAnswer(returncode=1, stderr="pytest syntax error"),
    )
    delta = coverage_delta(implement_checkout, "main", ["tests/test_sample.py"])
    assert delta.passed is False
    assert "pytest syntax error" in delta.log


def test_coverage_delta_coverage_xml_failure(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    from devops_cli.roadmap.implement.implement_strength import coverage_delta

    implement_programs.answer(
        lambda call: "pytest" in command_text(call),
        ProcessAnswer(returncode=0),
    )
    implement_programs.answer(
        lambda call: "coverage xml" in command_text(call),
        ProcessAnswer(returncode=1, stderr="coverage xml error"),
    )
    delta = coverage_delta(implement_checkout, "main", ["tests/test_sample.py"])
    assert delta.passed is False
    assert "coverage xml error" in delta.log


def test_coverage_delta_diff_cover_failure_from_stdout(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    from devops_cli.roadmap.implement.implement_strength import coverage_delta

    implement_programs.answer(
        lambda call: "pytest" in command_text(call),
        ProcessAnswer(returncode=0),
    )
    implement_programs.answer(
        lambda call: "coverage xml" in command_text(call),
        ProcessAnswer(returncode=0),
    )
    implement_programs.answer(
        lambda call: "diff-cover" in command_text(call),
        ProcessAnswer(returncode=1, stdout="Diff coverage failure output"),
    )
    delta = coverage_delta(implement_checkout, "main", ["tests/test_sample.py"])
    assert delta.passed is False
    assert "Diff coverage failure output" in delta.report


def test_coverage_delta_reads_report_file(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    import subprocess

    from devops_cli.roadmap.implement.implement_strength import coverage_delta

    def write_report(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        (implement_checkout / ".data").mkdir(parents=True, exist_ok=True)
        (implement_checkout / ".data" / "coverage.md").write_text(
            "# Coverage file content\n", encoding="utf-8"
        )
        return subprocess.CompletedProcess(call.argv, 0, stdout="")

    implement_programs.answer(
        lambda call: "pytest" in command_text(call),
        ProcessAnswer(returncode=0),
    )
    implement_programs.answer(
        lambda call: "coverage xml" in command_text(call),
        ProcessAnswer(returncode=0),
    )
    implement_programs.answer(
        lambda call: "diff-cover" in command_text(call),
        ProcessAnswer(side_effect=write_report),
    )
    delta = coverage_delta(implement_checkout, "main", ["tests/test_sample.py"])
    assert delta.passed is True
    assert "# Coverage file content" in delta.report


def test_strength_report_fails_on_uncovered_lines(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    from devops_cli.roadmap.implement.implement_strength import strength_report
    from tests.support.implement_step import git

    git(implement_checkout, "update-ref", "refs/remotes/origin/main", "HEAD")
    (implement_checkout / "src" / "sample.py").write_text(
        "def shout(text: str) -> str:\n    return text.upper()\n", encoding="utf-8"
    )

    tasks_md = """# Tasks

## 1. Behavior
Kind: behavior. Changes: src/sample.py.
- [ ] 1.1 Implement shout
"""
    report_text = "# Diff Coverage\n## src/sample.py (0.0%)\nMissing lines: 2, 3-5\n"
    implement_programs.answer(
        lambda call: "diff-cover" in command_text(call),
        ProcessAnswer(returncode=1, stdout=report_text),
    )

    report = strength_report(
        implement_checkout,
        tasks_md,
        ["src/sample.py"],
        "main",
        ["tests/test_sample.py"],
    )
    assert report.passed is False
    assert "src/sample.py:2" in report.uncovered_lines
    assert "src/sample.py:3-5" in report.uncovered_lines


def test_report_lines_formats_all_failure_and_outcome_types() -> None:
    from devops_cli.ci.mutate import MutationTarget
    from devops_cli.roadmap.implement.implement_strength import (
        AssertionFinding,
        CoverageDelta,
        MutationOutcome,
        StrengthReport,
        report_lines,
    )

    target = MutationTarget(path="src/sample.py", line=10, class_name=None, name="foo")
    report = StrengthReport(
        passed=False,
        assertion_findings=(AssertionFinding("tests/test_a.py", 5, "no assert"),),
        surviving_mutants=(("mutant_1", target),),
        mutation_outcome=MutationOutcome(timeout=True, skipped_files=("src/skip.py",)),
        coverage_delta=CoverageDelta(passed=False, report="", log="coverage dropped"),
        uncovered_lines=("src/sample.py:12",),
        skipped_groups=((2, "kind other"),),
        note="note message",
    )
    lines = report_lines(report)
    assert "- missing assertion in tests/test_a.py:5: no assert" in lines
    assert "- surviving mutant in src/sample.py:10: mutant_1" in lines
    assert "- uncovered changed line in src/sample.py:12" in lines
    assert "- mutation run reached command timeout bound" in lines
    assert "- mutation run skipped file over bound: src/skip.py" in lines
    assert "- group 2: skipped, kind other" in lines
    assert "- note message" in lines

    report_cov_report = StrengthReport(
        passed=False,
        coverage_delta=CoverageDelta(passed=False, report="diff report details", log=""),
    )
    cov_report_lines = report_lines(report_cov_report)
    assert any("diff report details" in line for line in cov_report_lines)

    report_cov_log = StrengthReport(
        passed=False,
        coverage_delta=CoverageDelta(passed=False, report="", log="failed log"),
    )
    cov_log_lines = report_lines(report_cov_log)
    assert any("failed log" in line for line in cov_log_lines)
