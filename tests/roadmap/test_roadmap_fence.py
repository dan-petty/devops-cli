"""The fence of a code block in a comment (#3091)."""

from __future__ import annotations

import pytest

from devops_cli.roadmap.fence import code_fence


@pytest.mark.parametrize(
    ("text", "fence"),
    [
        ("", "```"),
        ("a line\nand another\n", "```"),
        ("one ` tick and `` two", "```"),
        ("a run ``` of three", "````"),
        ("a run ````` of five", "``````"),
    ],
)
def test_the_fence_is_three_backticks_or_one_more_than_the_longest_run(
    text: str, fence: str
) -> None:
    assert code_fence(text) == fence
