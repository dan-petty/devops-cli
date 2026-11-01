"""The fixtures of `devops roadmap eval implement` (#3030): what the loader reads, and what it
refuses."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions.roadmap import ImplementEvalError
from devops_cli.roadmap.implement_eval import Property, choose_cases, load_case, load_cases
from tests.support.implement_step import BODY, TASKS
from tests.support.roadmap_eval import (
    CHANGE,
    PLAN,
    case_data,
    good_diff,
    scratch_diff,
    write_fixture,
)


def _refusal(root: Path, **kwargs: Any) -> str:
    """The message with which the loader refuses the fixture written with `kwargs`."""
    folder = write_fixture(root, **kwargs)
    with pytest.raises(ImplementEvalError) as raised:
        load_case(folder)
    assert raised.value.error_code == "ROADMAP_EVAL_REFUSED"
    return str(raised.value)


def test_a_fixture_folder_loads_with_its_issue_plan_and_recorded_results(tmp_path: Path) -> None:
    loaded = load_case(write_fixture(tmp_path))

    assert (
        loaded.name,
        loaded.case.issue,
        loaded.case.changes,
        loaded.body,
        dict(loaded.plan),
        dict(loaded.diffs),
        loaded.tasks_path,
        loaded.group.title,
        [(r.name, r.fails) for r in loaded.case.results],
    ) == (
        "sample",
        1,
        ("tests/test_sample.py", "src/sample.py"),
        BODY,
        PLAN,
        {"good": good_diff(), "scratch": scratch_diff()},
        f"openspec/changes/{CHANGE}/tasks.md",
        "The first group",
        [("good", ()), ("scratch", (Property.DIFF_SCOPE, Property.NO_SCRATCH))],
    )
    assert PLAN["tasks.md"] == TASKS


def test_a_field_that_the_schema_lacks_is_refused(tmp_path: Path) -> None:
    message = _refusal(tmp_path, case=case_data(colour="red"))

    assert message.startswith("Fixture sample: colour: ")


def test_a_base_that_is_no_full_sha_is_refused(tmp_path: Path) -> None:
    assert _refusal(tmp_path, case=case_data(base="1545b85a")).startswith("Fixture sample: base: ")


def test_a_group_that_the_plan_lacks_is_refused(tmp_path: Path) -> None:
    assert _refusal(tmp_path, case=case_data(group=9)) == "Fixture sample: the plan has no group 9."


def test_a_changes_path_that_the_group_does_not_name_is_refused(tmp_path: Path) -> None:
    message = _refusal(tmp_path, case=case_data(changes=["src/other.py"]))

    assert message == (
        "Fixture sample: `changes` lists src/other.py, and no code span of group 1 names it."
    )


def test_a_result_without_a_diff_file_is_refused(tmp_path: Path) -> None:
    message = _refusal(tmp_path, diffs={"good.diff": good_diff()})

    assert message == (
        "Fixture sample: the result scratch names the diff results/scratch.diff, which is missing."
    )


def test_a_result_may_expect_a_command_property_to_fail(tmp_path: Path) -> None:
    results = [{"name": "good", "source": "a test", "diff": "good.diff", "fails": ["tests_pass"]}]
    folder = write_fixture(tmp_path, case=case_data(results=results))

    (recorded,) = load_case(folder).case.results

    assert [prop.value for prop in recorded.fails] == ["tests_pass"]


def test_a_lost_test_that_is_no_path_and_name_is_refused(tmp_path: Path) -> None:
    message = _refusal(tmp_path, case=case_data(allow_lost_tests=["test_dead"]))

    assert "allow_lost_tests holds test_dead, which is not path::name." in message


def test_a_folder_named_differently_from_its_case_is_refused(tmp_path: Path) -> None:
    message = _refusal(tmp_path, folder="other")

    assert message == (
        "Fixture other: the folder name must be the name in case.json, which is sample."
    )


def test_a_file_that_is_not_there_is_refused_with_its_name(tmp_path: Path) -> None:
    folder = write_fixture(tmp_path)
    (folder / "issue.md").unlink()

    with pytest.raises(ImplementEvalError) as raised:
        load_case(folder)

    assert str(raised.value).startswith("Fixture sample: cannot read issue.md: ")


def test_a_root_without_fixtures_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ImplementEvalError) as raised:
        load_cases(tmp_path / "none")

    assert str(raised.value) == f"No fixture folder at {tmp_path / 'none'}."


def test_the_cases_of_a_root_come_in_the_order_of_their_folders(tmp_path: Path) -> None:
    for name in ("b-case", "a-case"):
        write_fixture(tmp_path, folder=name, case=case_data(name=name))
    (tmp_path / "notes").mkdir()

    assert [case.name for case in load_cases(tmp_path)] == ["a-case", "b-case"]


def test_a_chosen_name_that_no_fixture_has_is_refused_and_the_known_names_are_listed(
    tmp_path: Path,
) -> None:
    for name in ("a-case", "b-case"):
        write_fixture(tmp_path, folder=name, case=case_data(name=name))
    cases = load_cases(tmp_path)

    assert [case.name for case in choose_cases(cases, ("b-case",))] == ["b-case"]
    assert choose_cases(cases, ()) == cases
    with pytest.raises(ImplementEvalError) as raised:
        choose_cases(cases, ("c-case",))
    assert str(raised.value) == "No fixture is named c-case. The fixtures are: a-case, b-case."
