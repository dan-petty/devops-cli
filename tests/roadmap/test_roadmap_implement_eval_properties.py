"""The properties of `devops roadmap eval implement` (#3030): what a diff and a tree decide about
the result of a step."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.roadmap.implement_eval import LoadedCase, Property, load_case
from devops_cli.roadmap.implement_eval_properties import (
    PropertyResult,
    Status,
    command_results,
    diff_results,
    no_tree,
)
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import (
    CHECK,
    DOCS,
    SAMPLE,
    TASKS,
    TASKS_PATH,
    command_text,
)
from tests.support.roadmap_eval import (
    CODE_PATH,
    TEST_PATH,
    case_data,
    good_diff,
    scratch_diff,
    unified,
    write_fixture,
)

TWO_TESTS = "def test_a() -> None:\n    pass\n\n\ndef test_b() -> None:\n    pass\n"
SWAPPED = "def test_b() -> None:\n    pass\n\n\ndef test_a() -> None:\n    pass\n"
RENAMED = TWO_TESTS.replace("test_b", "test_c")
ONE_TICK = TASKS.replace("- [ ] Add the failing test", "- [x] Add the failing test")


@pytest.fixture
def loaded(tmp_path: Path) -> LoadedCase:
    return load_case(write_fixture(tmp_path))


def _by_property(results: list[PropertyResult]) -> dict[Property, tuple[Status, str]]:
    return {result.prop: (result.status, result.detail) for result in results}


def _only(results: list[PropertyResult], prop: Property) -> tuple[Status, str]:
    return _by_property(results)[prop]


def test_a_diff_that_does_the_group_passes_the_four_diff_properties(loaded: LoadedCase) -> None:
    results = diff_results(loaded, good_diff())

    assert _by_property(results) == {
        Property.TESTS_KEPT: (Status.PASS, ""),
        Property.DIFF_SCOPE: (Status.PASS, ""),
        Property.NO_SCRATCH: (Status.PASS, ""),
        Property.TASKS_TICKED: (Status.PASS, ""),
    }


def test_a_scratch_file_at_the_root_fails_the_scope_and_the_scratch_property(
    loaded: LoadedCase,
) -> None:
    results = _by_property(diff_results(loaded, scratch_diff()))

    assert results == {
        Property.TESTS_KEPT: (Status.PASS, ""),
        Property.DIFF_SCOPE: (Status.FAIL, "Paths outside the group: scratch.py."),
        Property.NO_SCRATCH: (Status.FAIL, "Scratch files: scratch.py."),
        Property.TASKS_TICKED: (Status.PASS, ""),
    }


@pytest.mark.parametrize("path", [".data/agent/notes.md", "docs/plan.md.bak", "docs/x.orig"])
def test_a_scratch_file_below_the_root_is_found_by_its_place_or_its_suffix(
    loaded: LoadedCase, path: str
) -> None:
    diff = good_diff() + unified(path, None, "notes\n")

    assert _only(diff_results(loaded, diff), Property.NO_SCRATCH) == (
        Status.FAIL,
        f"Scratch files: {path}.",
    )


def test_a_new_file_that_the_group_names_is_no_scratch(tmp_path: Path) -> None:
    case = case_data(changes=[TEST_PATH, CODE_PATH, "notes.md"])
    tasks = TASKS.replace("for `src/sample.py`", "for `src/sample.py` and `notes.md`")
    named = load_case(write_fixture(tmp_path, case=case, tasks=tasks))
    diff = good_diff() + unified("notes.md", None, "notes\n")

    assert _only(diff_results(named, diff), Property.NO_SCRATCH) == (Status.PASS, "")
    assert _only(diff_results(named, diff), Property.DIFF_SCOPE) == (Status.PASS, "")


def test_a_path_outside_the_changes_paths_fails_the_scope(loaded: LoadedCase) -> None:
    diff = good_diff() + unified("src/other.py", "OTHER = 1\n", "OTHER = 2\n")

    assert _only(diff_results(loaded, diff), Property.DIFF_SCOPE) == (
        Status.FAIL,
        "Paths outside the group: src/other.py.",
    )


def test_a_deleted_test_file_fails_tests_kept_with_the_name_of_each_test(
    loaded: LoadedCase,
) -> None:
    diff = unified(TEST_PATH, TWO_TESTS, None)

    assert _only(diff_results(loaded, diff), Property.TESTS_KEPT) == (
        Status.FAIL,
        "Lost tests: tests/test_sample.py::test_a, tests/test_sample.py::test_b.",
    )


def test_a_renamed_test_is_a_lost_test(loaded: LoadedCase) -> None:
    diff = unified(TEST_PATH, TWO_TESTS, RENAMED)

    assert _only(diff_results(loaded, diff), Property.TESTS_KEPT) == (
        Status.FAIL,
        "Lost tests: tests/test_sample.py::test_b.",
    )


def test_a_test_that_moves_in_its_file_is_kept(loaded: LoadedCase) -> None:
    diff = unified(TEST_PATH, TWO_TESTS, SWAPPED)

    assert _only(diff_results(loaded, diff), Property.TESTS_KEPT) == (Status.PASS, "")


def test_an_async_test_and_a_test_with_a_decorator_count(loaded: LoadedCase) -> None:
    old = "@pytest.mark.slow\nasync def test_a() -> None:\n    pass\n"
    diff = unified(TEST_PATH, old, "")

    assert _only(diff_results(loaded, diff), Property.TESTS_KEPT) == (
        Status.FAIL,
        "Lost tests: tests/test_sample.py::test_a.",
    )


def test_a_lost_test_that_the_fixture_allows_is_not_lost(tmp_path: Path) -> None:
    case = case_data(allow_lost_tests=["tests/test_sample.py::test_a"])
    allowing = load_case(write_fixture(tmp_path, case=case))
    diff = unified(TEST_PATH, TWO_TESTS, TWO_TESTS.replace("def test_a", "def helper_a"))

    assert _only(diff_results(allowing, diff), Property.TESTS_KEPT) == (Status.PASS, "")


def test_a_file_outside_the_tests_folder_loses_no_test(loaded: LoadedCase) -> None:
    diff = unified("src/test_helpers.py", TWO_TESTS, None)

    assert _only(diff_results(loaded, diff), Property.TESTS_KEPT) == (Status.PASS, "")


def test_a_diff_that_ticks_one_of_two_tasks_fails_and_names_the_open_task(
    loaded: LoadedCase,
) -> None:
    diff = unified(TASKS_PATH, TASKS, ONE_TICK)

    status, detail = _only(diff_results(loaded, diff), Property.TASKS_TICKED)

    assert (status, detail) == (
        Status.FAIL,
        "Tasks not ticked: [ ] Add `shout` to `src/sample.py`.",
    )


def test_a_diff_that_leaves_the_tasks_file_alone_fails_the_ticks(loaded: LoadedCase) -> None:
    diff = unified(CODE_PATH, SAMPLE, SAMPLE + "X = 1\n")

    status, detail = _only(diff_results(loaded, diff), Property.TASKS_TICKED)

    assert (status, detail.startswith("Tasks not ticked: ")) == (Status.FAIL, True)


def test_a_hunk_that_the_plan_does_not_hold_fails_the_ticks(loaded: LoadedCase) -> None:
    diff = unified(TASKS_PATH, TASKS.replace("first group", "other group"), ONE_TICK)

    assert _only(diff_results(loaded, diff), Property.TASKS_TICKED) == (
        Status.FAIL,
        f"A hunk of {TASKS_PATH} does not match the plan.",
    )


def test_a_cut_diff_leaves_the_four_properties_skipped(loaded: LoadedCase) -> None:
    results = diff_results(loaded, good_diff()[:-40], cut=True)

    assert _by_property(results) == {
        prop: (Status.SKIPPED, "The diff is cut.")
        for prop in (
            Property.TESTS_KEPT,
            Property.DIFF_SCOPE,
            Property.NO_SCRATCH,
            Property.TASKS_TICKED,
        )
    }


def test_a_diff_that_does_not_parse_fails_the_four_properties(loaded: LoadedCase) -> None:
    results = diff_results(loaded, good_diff()[:-40])

    assert {result.status for result in results} == {Status.FAIL}
    assert all(result.detail.startswith("The diff does not parse: ") for result in results)


def test_an_empty_diff_fails_only_the_ticks(loaded: LoadedCase) -> None:
    results = _by_property(diff_results(loaded, ""))

    assert {prop: status for prop, (status, _) in results.items()} == {
        Property.TESTS_KEPT: Status.PASS,
        Property.DIFF_SCOPE: Status.PASS,
        Property.NO_SCRATCH: Status.PASS,
        Property.TASKS_TICKED: Status.FAIL,
    }


def test_the_command_properties_pass_when_every_command_exits_0(
    loaded: LoadedCase, tmp_path: Path, process_fake: ProcessFake
) -> None:
    results = _by_property(command_results(loaded, tmp_path))

    assert results == {
        Property.TESTS_PASS: (Status.PASS, ""),
        Property.VERIFY_PASSES: (Status.PASS, ""),
    }
    assert [command_text(call) for call in process_fake.calls] == [CHECK, CHECK, DOCS]


def test_a_failing_named_test_fails_tests_pass_and_names_the_command(
    loaded: LoadedCase, tmp_path: Path, process_fake: ProcessFake
) -> None:
    process_fake.answer(
        lambda call: command_text(call) == CHECK, ProcessAnswer(returncode=1, stdout="1 failed\n")
    )

    results = _by_property(command_results(loaded, tmp_path))

    assert results[Property.TESTS_PASS] == (Status.FAIL, f"{CHECK} exited with status 1.\n1 failed")
    assert results[Property.VERIFY_PASSES][0] is Status.FAIL


def test_a_fixture_with_no_named_tests_skips_tests_pass(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    fixture = load_case(write_fixture(tmp_path / "f", case=case_data(tests_pass=[])))

    results = _by_property(command_results(fixture, tmp_path))

    assert results[Property.TESTS_PASS] == (Status.SKIPPED, "There is no command to run.")
    assert results[Property.VERIFY_PASSES] == (Status.PASS, "")


def test_a_stopped_step_leaves_the_command_properties_skipped() -> None:
    results: Any = _by_property(no_tree("`ruff check` failed."))

    assert results == {
        Property.TESTS_PASS: (
            Status.SKIPPED,
            "The step stopped, so it left no tree: `ruff check` failed.",
        ),
        Property.VERIFY_PASSES: (
            Status.SKIPPED,
            "The step stopped, so it left no tree: `ruff check` failed.",
        ),
    }
