"""The test form that a task names and the items of a pytest collection (#3451).

`named_forms` reads the text of one task and the code spans it names, and gives one form for each
test file. `collected_items` counts the items of the quiet collection output. The functions are
pure: they read text and do no I/O. Each test imports the module that it checks, so a test fails on
the base commit, where the module does not exist, and not at the collection of this file.
"""

from __future__ import annotations

import pytest

TEST_FILE = "tests/roadmap/implement/test_roadmap_implement_test_form.py"
OTHER_TEST_FILE = "tests/output/test_network_table_color.py"
SOURCE_FILE = "src/devops_cli/roadmap/implement/implement_test_form.py"


def test_a_task_naming_six_statuses_gives_the_path_and_the_count_six() -> None:
    from devops_cli.roadmap.implement.implement_test_form import TestForm, named_forms

    text = f"Add a test in `{TEST_FILE}` with one parametrized test over six statuses."

    assert named_forms(text, (TEST_FILE,)) == (TestForm(path=TEST_FILE, count=6),)


def test_a_task_naming_a_digit_count_reads_the_digit() -> None:
    from devops_cli.roadmap.implement.implement_test_form import TestForm, named_forms

    text = f"Add a test in `{TEST_FILE}` with one parametrized test over 11 statuses."

    assert named_forms(text, (TEST_FILE,)) == (TestForm(path=TEST_FILE, count=11),)


@pytest.mark.parametrize(
    ("word", "count"),
    [
        ("one", 1),
        ("two", 2),
        ("three", 3),
        ("four", 4),
        ("five", 5),
        ("six", 6),
        ("seven", 7),
        ("eight", 8),
        ("nine", 9),
        ("ten", 10),
        ("eleven", 11),
        ("twelve", 12),
        ("thirteen", 13),
        ("fourteen", 14),
        ("fifteen", 15),
        ("sixteen", 16),
        ("seventeen", 17),
        ("eighteen", 18),
        ("nineteen", 19),
        ("twenty", 20),
    ],
)
def test_every_number_word_from_one_to_twenty_is_a_count(word: str, count: int) -> None:
    from devops_cli.roadmap.implement.implement_test_form import TestForm, named_forms

    text = f"Add a test in `{TEST_FILE}` with one parametrized test over {word} statuses."

    assert named_forms(text, (TEST_FILE,)) == (TestForm(path=TEST_FILE, count=count),)


def test_a_task_with_no_parametrized_word_gives_no_form() -> None:
    from devops_cli.roadmap.implement.implement_test_form import named_forms

    text = f"Add a test in `{TEST_FILE}` that the table is complete."

    assert named_forms(text, (TEST_FILE,)) == ()


def test_a_parametrized_task_with_no_count_gives_a_form_with_no_count() -> None:
    from devops_cli.roadmap.implement.implement_test_form import TestForm, named_forms

    text = f"Add a test in `{TEST_FILE}` with a parametrized test over the statuses."

    assert named_forms(text, (TEST_FILE,)) == (TestForm(path=TEST_FILE, count=None),)


def test_a_parametrized_task_names_a_form_for_each_test_file() -> None:
    from devops_cli.roadmap.implement.implement_test_form import TestForm, named_forms

    text = (
        f"Add a test in `{TEST_FILE}` and one in `{OTHER_TEST_FILE}` with one parametrized test "
        "over six statuses."
    )

    assert named_forms(text, (TEST_FILE, OTHER_TEST_FILE)) == (
        TestForm(path=TEST_FILE, count=6),
        TestForm(path=OTHER_TEST_FILE, count=6),
    )


def test_a_parametrized_task_gives_no_form_for_a_path_that_is_no_test_file() -> None:
    from devops_cli.roadmap.implement.implement_test_form import TestForm, named_forms

    text = (
        f"Change `{SOURCE_FILE}` and add a test in `{TEST_FILE}` with one parametrized test "
        "over six statuses."
    )

    assert named_forms(text, (SOURCE_FILE, TEST_FILE)) == (TestForm(path=TEST_FILE, count=6),)


def test_collected_items_counts_the_lines_that_hold_a_test_id() -> None:
    from devops_cli.roadmap.implement.implement_test_form import collected_items

    output = (
        "tests/output/test_network_table_color.py::test_the_network_table_colors_a_status"
        "[high]\n"
        "tests/output/test_network_table_color.py::test_the_network_table_colors_a_status"
        "[medium]\n"
        "tests/output/test_network_table_color.py::test_the_network_table_colors_a_status"
        "[low]\n"
        "\n"
        "3 tests collected in 0.01s\n"
    )

    assert collected_items(output) == 3


def test_collected_items_of_a_collection_with_no_item_is_zero() -> None:
    from devops_cli.roadmap.implement.implement_test_form import collected_items

    assert collected_items("no tests ran in 0.01s\n") == 0
