"""The scoped checks of the implement job (#3043): which commands they are, which paths the tests
get, and how a run reports a failed check.

The process edge is `process_fake`: it records the commands and answers them.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from devops_cli.commands.ci import get_check_specs
from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_SCOPED_ROWS,
    CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES,
)
from devops_cli.roadmap.implement_scoped_ci import (
    ScopedResult,
    ScopedTests,
    paths_for_tests,
    plan_tests,
    run_scoped_checks,
    scoped_checks,
)
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import command_text

CONFIG = Path("/data/cache/pre-commit-trusted-config.yaml")
PRE_PUSH = (
    "uv run pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD "
    f"--config {CONFIG}"
)
TESTS = ["tests/test_shout.py"]
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
    checks = scoped_checks("main", ["tests/test_shout.py", "tests/test_other.py"], config=CONFIG)

    assert [(check.name, " ".join(check.argv)) for check in checks] == [
        ("pre-push", PRE_PUSH),
        ("static", STATIC),
        (
            "tests",
            "uv run devops ci test tests/test_shout.py tests/test_other.py",
        ),
    ]


def test_a_change_with_no_test_module_has_no_test_check() -> None:
    checks = scoped_checks("main", [], config=CONFIG)

    assert [check.name for check in checks] == ["pre-push", "static"]


def test_the_pre_push_stage_names_the_default_branch() -> None:
    (first, *_rest) = scoped_checks("trunk", [], config=CONFIG)

    assert " ".join(first.argv).endswith(f"--from-ref origin/trunk --to-ref HEAD --config {CONFIG}")


def test_the_pre_push_check_has_the_hook_home_and_the_others_have_no_variable() -> None:
    pre_push, static, tests = scoped_checks("main", TESTS, config=CONFIG)

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
    checks = scoped_checks("main", ["tests/test_sample.py"], config=CONFIG)

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

    results = run_scoped_checks(
        implement_checkout, scoped_checks("main", ["tests/test_sample.py"], config=CONFIG)
    )

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

    (result,) = run_scoped_checks(implement_checkout, scoped_checks("main", [], config=CONFIG))

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

    results = run_scoped_checks(implement_checkout, scoped_checks("main", [], config=CONFIG))

    assert token not in _result(results, "static").log


def test_a_repository_with_no_hooks_has_no_pre_push_check() -> None:
    checks = scoped_checks("main", TESTS, config=None)

    assert [check.name for check in checks] == ["static", "tests"]


# ── The test modules of the tests check ───────────────────────────────────────────────────


def _repo(root: Path, modules: dict[str, str]) -> Path:
    """A checkout with the files `modules` (a path and its text) under `root`."""
    for name, text in modules.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _importers(count: int, module: str) -> dict[str, str]:
    """`count` test modules that import `module`."""
    return {
        f"tests/roadmap/test_user_{k}.py": f"from devops_cli.{module} import VALUE\n"
        for k in range(count)
    }


def test_a_source_with_a_covering_test_runs_that_test(tmp_path: Path) -> None:
    root = _repo(
        tmp_path,
        {
            "src/devops_cli/shout.py": "VALUE = 1\n",
            "tests/test_shout.py": "from devops_cli.shout import VALUE\n",
            "tests/test_other.py": "VALUE = 2\n",
        },
    )

    plan = plan_tests(root, ["src/devops_cli/shout.py"])

    assert plan == ScopedTests(("tests/test_shout.py",))


def test_a_changed_test_module_runs_itself(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"tests/test_shout.py": "VALUE = 1\n"})

    assert plan_tests(root, ["tests/test_shout.py"]) == ScopedTests(("tests/test_shout.py",))


def test_a_change_that_no_test_covers_has_no_test_check_and_says_so(tmp_path: Path) -> None:
    """The check is not a failure: no fix step can add a test that the item does not need."""
    root = _repo(tmp_path, {"src/devops_cli/lang/en/help.py": "VALUE = 1\n"})

    plan = plan_tests(root, ["src/devops_cli/lang/en/help.py"])

    assert plan.paths == ()
    assert "no test covers the changed files" in plan.note


def test_a_change_with_no_python_file_has_no_test_check_and_no_note(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"docs/SAMPLE.md": "text\n"})

    assert plan_tests(root, ["docs/SAMPLE.md", "pyproject.toml"]) == ScopedTests()


def test_a_shared_module_keeps_only_the_changed_test_modules(tmp_path: Path) -> None:
    """The constants module is imported by hundreds of tests: the check stays scoped."""
    count = CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES + 1
    root = _repo(
        tmp_path,
        {
            "src/devops_cli/config/constants.py": "VALUE = 1\n",
            "tests/roadmap/test_new.py": "VALUE = 1\n",
            **_importers(count, "config.constants"),
        },
    )

    plan = plan_tests(root, ["src/devops_cli/config/constants.py", "tests/roadmap/test_new.py"])

    assert plan.paths == ("tests/roadmap/test_new.py",)
    assert f"more than {CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES} test modules" in plan.note
    assert "only the changed test modules ran" in plan.note


def test_a_shared_module_with_no_changed_test_module_has_no_test_check(tmp_path: Path) -> None:
    root = _repo(
        tmp_path,
        {
            "src/devops_cli/config/constants.py": "VALUE = 1\n",
            **_importers(CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES + 1, "config.constants"),
        },
    )

    plan = plan_tests(root, ["src/devops_cli/config/constants.py"])

    assert plan.paths == ()
    assert "not run" in plan.note


def test_a_selection_at_the_limit_runs_every_module(tmp_path: Path) -> None:
    root = _repo(
        tmp_path,
        {
            "src/devops_cli/config/constants.py": "VALUE = 1\n",
            **_importers(CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES, "config.constants"),
        },
    )

    plan = plan_tests(root, ["src/devops_cli/config/constants.py"])

    assert (len(plan.paths), plan.note) == (CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES, "")


def test_a_change_that_forces_the_whole_suite_keeps_only_the_changed_test_modules(
    tmp_path: Path,
) -> None:
    """A `conftest.py` reaches every test by its name: the selector answers with the directory
    of the tests, which no scoped check runs."""
    root = _repo(
        tmp_path,
        {
            "src/devops_cli/conftest.py": "VALUE = 1\n",
            "tests/test_new.py": "VALUE = 1\n",
        },
    )

    plan = plan_tests(root, ["src/devops_cli/conftest.py", "tests/test_new.py"])

    assert plan.paths == ("tests/test_new.py",)
    assert "only the changed test modules ran" in plan.note
