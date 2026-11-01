"""The fence of a fenced code block in a comment of the Service (#3091)."""

from __future__ import annotations

import re

_BACKTICK_RUN = re.compile(r"`+")
_MIN_FENCE = 3


def code_fence(text: str) -> str:
    """The fence of a block that holds `text`: backticks, one more than the longest run of
    backticks in `text`, and at least three. CommonMark ends a fenced block only at a fence at
    least as long as its opening, so no line of `text` can end the block."""
    longest = max((len(run) for run in _BACKTICK_RUN.findall(text)), default=0)
    return "`" * max(_MIN_FENCE, longest + 1)
