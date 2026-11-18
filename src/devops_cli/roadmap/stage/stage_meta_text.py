"""The Feasibility lines of a plan that name an earlier reply (#4111).

A model writes the plan, and a repair round can leave the text of that round in the Feasibility
section: a line that refers to an earlier reply, or that corrects the model. The section holds
system facts, file citations and the quotation of a probe, so the stage job refuses such a line
before it commits the proposal. A fenced code block and a block quotation carry evidence, and a
probe can quote the same words, so their lines are no violation.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from typing import Final

from devops_cli.lang import MESSAGES

# The bounded phrases that name an earlier reply or a self-correction. The list covers the defect
# that #4111 reports; a phrase that a later reply shows needs a case here and in the tests.
META_PHRASES: Final[tuple[str, ...]] = (
    "earlier reply",
    "previous reply",
    "prior reply",
    "this reply",
    "the reply above",
    "earlier answer",
    "previous turn",
    "I was wrong",
    "I was mistaken",
    "I apologize",
    "let me correct",
    "my earlier",
)

# A fence opens or closes a code block: three backticks or three tildes.
_FENCE: Final[re.Pattern[str]] = re.compile(r"^(?:```|~~~)")


def _prose_lines(lines: Sequence[str]) -> Iterator[tuple[int, str]]:
    """Each line of `lines` that holds prose, with its number from 1.

    A line inside a fenced code block, and a block quotation, carry evidence: the check skips both.
    """
    fenced = False
    for number, line in enumerate(lines, start=1):
        if _FENCE.match(line.lstrip()):
            fenced = not fenced
            continue
        if fenced or line.lstrip().startswith(">"):
            continue
        yield number, line


def _matched_phrase(line: str) -> str | None:
    """The first phrase of `META_PHRASES` that `line` holds, or `None`."""
    folded = line.casefold()
    return next((phrase for phrase in META_PHRASES if phrase.casefold() in folded), None)


def meta_text_problems(feasibility: Sequence[str]) -> list[str]:
    """One problem for each Feasibility line that names an earlier reply or a self-correction.

    The problem names the number of the line and the phrase, so one repair fixes every refused
    line.
    """
    problems: list[str] = []
    for number, line in _prose_lines(feasibility):
        phrase = _matched_phrase(line)
        if phrase is None:
            continue
        problems.append(MESSAGES.roadmap.stage_problem_meta_text.format(line=number, phrase=phrase))
    return problems
