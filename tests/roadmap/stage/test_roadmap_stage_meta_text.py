"""`meta_text_problems`: a Feasibility line that names an earlier reply is refused (#4111).

The Feasibility section holds system facts, file citations and the quotation of a probe. A line
that refers to an earlier reply of the model, or that corrects the model, is no system fact, so the
`meta-text` gate refuses it with its line number and the phrase. A probe quotation holds the same
words, so a fenced code block and a block quotation are no violation.
"""

from __future__ import annotations

from devops_cli.lang import MESSAGES

DEFECT = "- The earlier reply was wrong to read the probe answer as a false premise."
FENCE = "```"


def _problem(line: int, phrase: str) -> str:
    """The problem of a Feasibility line, as the catalog writes it."""
    return MESSAGES.roadmap.stage_problem_meta_text.format(line=line, phrase=phrase)


def test_a_repair_phrase_in_a_feasibility_line_is_refused() -> None:
    """One problem, with the line number and the phrase, for a line that names an earlier reply;
    no problem for the same words inside a fenced code block or a block quotation."""
    # The module is new, so the test imports it here: on the base commit the test fails in its
    # call phase, and no collection error stands in for that failure (#3042).
    from devops_cli.roadmap.stage.stage_meta_text import meta_text_problems

    assert meta_text_problems([DEFECT]) == [_problem(1, "earlier reply")]

    assert meta_text_problems([FENCE, DEFECT, FENCE]) == []

    assert meta_text_problems([f"> {DEFECT}"]) == []

    assert (
        meta_text_problems(["- The probe line `The earlier reply was wrong` is the defect."]) == []
    )

    assert meta_text_problems(["- `a` shows nothing. The earlier reply was wrong."]) == [
        _problem(1, "earlier reply")
    ]
