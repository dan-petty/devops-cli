"""The scoped checks of the implement job (#3043): which commands they are, which paths the tests
get, and how a run reports a failed check.

The process edge is `process_fake`: it records the commands and answers them.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from devops_cli.commands.ci import get_check_specs
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_SCOPED_ROWS
from devops_cli.roadmap.implement_scoped_ci import (
    ScopedResult,
    paths_for_tests,
    run_scoped_checks,
    scoped_checks,
)
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import command_text

PRE_PUSH = "uv run pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD"
STATIC = "uv run devops ci --check --only constructs,docs,openspec"


def test_the_tests_get_the_changed_sources_and_test_modules_and_nothing_else() -> None:
    names = [
        "src/devops_cli/shout.py",
        "tests/test_shout.py",
        "tests/roadmap/test_deep.py",
        "tests/conftest.py",
        "tests/support/fakes/process.py",
        "tests/fixtures/data.json",
        "docs/SAMPLE.md",
        "scripts/probe.py",
        "pyproject.toml",
        "src/devops_cli/lang/en/messages.txt",
    ]

    assert paths_for_tests(names) == [
        "src/devops_cli/shout.py",
        "tests/test_shout.py",
        "tests/roadmap/test_deep.py",
    ]


def test_the_checks_are_the_pre_push_stage_the_static_rows_and_the_tests_in_that_order() -> None:
    checks = scoped_checks("main", ["src/devops_cli/shout.py", "tests/test_shout.py"])

    assert [(check.name, " ".join(check.argv)) for check in checks] == [
        ("pre-push", PRE_PUSH),
        ("static", STATIC),
        (
            "tests",
            "uv run devops ci test --no-fallback src/devops_cli/shout.py tests/test_shout.py",
        ),
    ]


def test_a_change_with_no_python_file_has_no_test_check() -> None:
    checks = scoped_checks("main", [])

    assert [check.name for check in checks] == ["pre-push", "static"]


def test_the_pre_push_stage_names_the_default_branch() -> None:
    (first, *_rest) = scoped_checks("trunk", [])

    assert " ".join(first.argv).endswith("--from-ref origin/trunk --to-ref HEAD")


def test_the_pre_push_check_has_the_hook_home_and_the_others_have_no_variable() -> None:
    pre_push, static, tests = scoped_checks("main", ["src/devops_cli/shout.py"])

    assert (set(pre_push.env), static.env, tests.env) == ({"PRE_COMMIT_HOME"}, {}, {})


def test_every_static_row_is_a_row_of_the_ci_table() -> None:
    """A row that `devops ci` drops fails here, not in a Job (#3043)."""
    rows = {spec.name for spec in get_check_specs()}

    assert set(CONST_ROADMAP_IMPLEMENT_SCOPED_ROWS) <= rows


def _result(results: list[ScopedResult], name: str) -> ScopedResult:
    return next(result for result in results if result.name == name)


def test_a_run_passes_when_every_check_exits_zero(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    checks = scoped_checks("main", ["src/sample.py"])

    results = run_scoped_checks(implement_checkout, checks)

    assert [(result.name, result.passed) for result in results] == [
        ("pre-push", True),
        ("static", True),
        ("tests", True),
    ]
    assert all(result.seconds >= 0 for result in results)
    assert {call.cwd for call in implement_programs.calls} == {implement_checkout}


def test_a_run_stops_at_the_first_failed_check_and_keeps_its_output(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    implement_programs.answer(
        lambda call: command_text(call) == STATIC,
        ProcessAnswer(returncode=1, stdout="ast-grep scan....Failed\n"),
    )

    results = run_scoped_checks(implement_checkout, scoped_checks("main", ["src/sample.py"]))

    assert [(result.name, result.passed) for result in results] == [
        ("pre-push", True),
        ("static", False),
    ]
    assert "ast-grep scan....Failed" in _result(results, "static").log
    assert "tests" not in {result.name for result in results}


def test_a_check_that_runs_out_of_time_is_a_failed_check(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    def hang(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(call.argv, 1)

    implement_programs.answer(lambda call: "pre-push" in call.argv, ProcessAnswer(side_effect=hang))

    (result,) = run_scoped_checks(implement_checkout, scoped_checks("main", []))

    assert (result.name, result.passed, "ran out of time" in result.log) == (
        "pre-push",
        False,
        True,
    )


def test_the_output_of_a_failed_check_is_masked(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    implement_programs.answer(
        lambda call: command_text(call) == STATIC,
        ProcessAnswer(returncode=1, stdout=f"token {token}\n"),
    )

    results = run_scoped_checks(implement_checkout, scoped_checks("main", []))

    assert token not in _result(results, "static").log
