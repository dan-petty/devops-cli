"""The test form that a task of `devops roadmap implement` names (#3451).

A task that says `parametrized` names a parametrized test, and may give its case count after
`parametrized test over` as a digit or as a number word from one to twenty. `named_forms` reads
that count for each test file that the task names, and `collected_items` counts the items of the
quiet output of `pytest --collect-only -q`. The step compares the two counts: pytest reports one
item for each parametrized case and one item for a loop over the same cases, so one rule covers
both forms. The functions are pure: they read text and do no I/O.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

from devops_cli.ci.fail_to_pass import is_test_file

_PARAMETRIZED: Final[str] = "parametrized"
_COUNT_AFTER: Final[re.Pattern[str]] = re.compile(
    r"parametrized\s+test\s+over\s+(?P<count>\d+|[a-z]+)"
)
# The number words that a task may write for its case count, as the plan format states them.
_NUMBER_WORDS: Final[Mapping[str, int]] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
_ITEM_MARK: Final[str] = "::"


@dataclass(frozen=True)
class TestForm:
    """The test form of one test file that a task names: the path, and the case count that the
    task states, or None when the task states none."""

    path: str
    count: int | None


def _named_count(text: str) -> int | None:
    """The case count that `text` states after `parametrized test over`, or None when it states
    none. A digit is its value, and a number word from one to twenty is its number."""
    found = _COUNT_AFTER.search(text)
    if found is None:
        return None
    token = found["count"]
    return int(token) if token.isdigit() else _NUMBER_WORDS.get(token)


def named_forms(text: str, paths: Sequence[str]) -> tuple[TestForm, ...]:
    """One form for each test file that `paths` names, when the task text `text` holds the word
    `parametrized`. A task with no such word names no form, and a path that is no test file gives
    no form."""
    folded = text.casefold()
    if _PARAMETRIZED not in folded:
        return ()
    count = _named_count(folded)
    return tuple(
        TestForm(path=path, count=count)
        for path in dict.fromkeys(paths)
        if is_test_file(PurePosixPath(path))
    )


def collected_items(output: str) -> int:
    """The number of items that a quiet pytest collection reported: the lines of `output` that
    hold a test id."""
    return sum(1 for line in output.splitlines() if _ITEM_MARK in line)


__all__ = ["TestForm", "collected_items", "named_forms"]
