"""The names of the tests in a file and the tests that a step loses (#2804). The functions are pure:
they read the text of a file, and they do no I/O."""

from __future__ import annotations

import pytest

from devops_cli.roadmap.implement_test_names import defined_tests, lost_tests

TESTS = """\
import sys

import pytest


def test_plain() -> None: ...


async def test_async() -> None: ...


@pytest.mark.parametrize("n", [1, 2, 3])
def test_cases(n: int) -> None: ...


def helper() -> None:
    def test_inside_a_function() -> None: ...


class TestOuter:
    def test_method(self) -> None: ...

    async def test_async_method(self) -> None: ...

    def not_a_test(self) -> None: ...

    class TestInner:
        def test_deep(self) -> None: ...


if sys.platform == "linux":
    def test_on_linux() -> None: ...
else:
    def test_elsewhere() -> None: ...

try:
    import tomllib
except ImportError:
    def test_without_toml() -> None: ...

with open("x") as stream:
    def test_in_a_block() -> None: ...

test_value = 1
"""


def test_defined_tests_lists_the_qualified_names_of_every_test() -> None:
    assert defined_tests(TESTS) == frozenset(
        {
            "test_plain",
            "test_async",
            "test_cases",
            "TestOuter.test_method",
            "TestOuter.test_async_method",
            "TestOuter.TestInner.test_deep",
            "test_on_linux",
            "test_elsewhere",
            "test_without_toml",
            "test_in_a_block",
        }
    )


@pytest.mark.parametrize("text", ["def test_a(:\n", "def test_a():\n  x = 1\n y = 2\n", "\0"])
def test_defined_tests_of_a_file_that_does_not_parse_is_none(text: str) -> None:
    assert defined_tests(text) is None


def test_defined_tests_ignores_a_byte_order_mark_at_the_start() -> None:
    assert defined_tests("\ufeffdef test_a(): pass\n") == frozenset({"test_a"})


def test_defined_tests_of_an_empty_file_is_empty() -> None:
    assert defined_tests("") == frozenset()


def _names(*names: str) -> frozenset[str]:
    return frozenset(names)


def test_a_file_that_drops_a_test_loses_it() -> None:
    before = {"tests/test_a.py": _names("test_a", "test_b")}
    after = {"tests/test_a.py": _names("test_a", "test_c")}

    assert lost_tests(before, after) == {"tests/test_a.py": ["test_b"]}


def test_a_file_that_adds_tests_loses_none() -> None:
    before = {"tests/test_a.py": _names("test_a")}
    after = {"tests/test_a.py": _names("test_a", "test_b")}

    assert lost_tests(before, after) == {}


def test_a_deleted_file_loses_all_its_tests_in_order() -> None:
    before = {"tests/test_a.py": _names("test_b", "test_a", "TestC.test_d")}

    assert lost_tests(before, {}) == {"tests/test_a.py": ["TestC.test_d", "test_a", "test_b"]}


def test_a_new_file_loses_nothing() -> None:
    assert lost_tests({}, {"tests/test_new.py": _names("test_a")}) == {}


def test_a_test_that_moves_to_another_file_is_lost() -> None:
    """Every test stays in its file, even when the other file holds a test of the same name."""
    before = {"tests/test_a.py": _names("TestA.test_x", "test_y")}
    after = {"tests/test_b.py": _names("TestA.test_x", "test_y")}

    assert lost_tests(before, after) == {"tests/test_a.py": ["TestA.test_x", "test_y"]}


def test_a_renamed_test_is_lost() -> None:
    before = {"tests/test_a.py": _names("test_old")}
    after = {"tests/test_a.py": _names("test_new")}

    assert lost_tests(before, after) == {"tests/test_a.py": ["test_old"]}


def test_a_file_that_did_not_parse_at_the_start_is_skipped() -> None:
    before = {"tests/test_a.py": None}
    after = {"tests/test_a.py": _names("test_a")}

    assert lost_tests(before, after) == {}


def test_a_file_that_does_not_parse_after_the_run_is_skipped() -> None:
    before = {"tests/test_a.py": _names("test_a"), "tests/test_b.py": _names("test_b")}
    after: dict[str, frozenset[str] | None] = {"tests/test_a.py": None}

    assert lost_tests(before, after) == {"tests/test_b.py": ["test_b"]}
