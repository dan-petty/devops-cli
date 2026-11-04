"""Which tests of a changed test file the pull request changed (#3124)."""

from __future__ import annotations

import pytest

from devops_cli.ci.changed_tests import is_test_changed, parse_tests

BASE = '''\
"""Module docstring."""

import pytest


def helper():
    return 1


def test_kept():
    assert helper() == 1


def test_edited():
    assert helper() == 1


class TestGroup:
    def test_method(self):
        assert helper() == 1

    def test_method_edited(self):
        assert helper() == 1
'''

HEAD = '''\
"""Module docstring."""

import pytest


def helper():
    return 1


def test_kept():
    # A comment and a blank line change no statement.

    assert helper() == 1


def test_edited():
    assert helper() == 2


def test_added():
    assert helper() == 2


class TestGroup:
    def test_method(self):
        assert helper() == 1

    def test_method_edited(self):
        assert helper() == 2
'''


@pytest.mark.parametrize(
    ("class_path", "name", "changed"),
    [
        ((), "test_kept", False),
        ((), "test_edited", True),
        ((), "test_added", True),
        (("TestGroup",), "test_method", False),
        (("TestGroup",), "test_method_edited", True),
        ((), "test_missing_from_head", True),
        (("TestOther",), "test_method", True),
    ],
    ids=[
        "comment-only",
        "body-edited",
        "added",
        "method-unchanged",
        "method-edited",
        "not-in-head",
        "other-class",
    ],
)
def test_a_test_is_changed_when_its_function_differs_or_is_new(
    class_path: tuple[str, ...], name: str, changed: bool
) -> None:
    """A test is unchanged only when its function of the base has the same statements, whatever
    the layout and comments, and a test the head does not hold is not known unchanged."""
    assert is_test_changed(class_path, name, parse_tests(BASE), parse_tests(HEAD)) is changed


@pytest.mark.parametrize(
    "head",
    [
        HEAD.replace("return 1", "return 2", 1),
        HEAD.replace("import pytest", "import pytest\nimport os", 1),
        HEAD.replace("def helper():", "@pytest.fixture\ndef helper():", 1),
    ],
    ids=["helper-body", "import", "decorator"],
)
def test_a_change_around_the_tests_makes_every_test_changed(head: str) -> None:
    """A helper, import or fixture that changes is code that each test of the file runs, so a
    test that fails on base after it is no test the fix left alone."""
    assert is_test_changed((), "test_kept", parse_tests(BASE), parse_tests(head)) is True


@pytest.mark.parametrize(
    ("base", "head"),
    [(None, HEAD), (BASE, None), ("def test_kept(:\n", HEAD), (BASE, "def test_kept(:\n")],
    ids=["new-file", "no-head", "base-cannot-parse", "head-cannot-parse"],
)
def test_a_test_with_a_source_that_cannot_be_compared_is_changed(
    base: str | None, head: str | None
) -> None:
    """The check refuses a replay for a test it knows to be unchanged only."""
    assert is_test_changed((), "test_kept", parse_tests(base), parse_tests(head)) is True
