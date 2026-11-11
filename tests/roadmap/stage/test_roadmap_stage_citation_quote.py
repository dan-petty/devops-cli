"""A line citation holds its quoted text in the code span that follows `path:line:`.

The stage prompt asks for `path:line:text` "with the text of that line in a code span". A plan
writes it as one span, or as the path and the line and then the text in a span of its own.
"""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.roadmap.stage.stage_change import check_proposal
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal

CITED = "src/sample.py"
FILES = {CITED: "import os\n\n\ndef f(): pass\n\n\ndef g(): return 1\n"}
TREE = StagedTree(["src/devops_cli/sample.py", CITED])


def _cited(text: str, **overrides: Any) -> list[str]:
    plan = make_stage_proposal(feasibility=[text], **overrides)
    return check_proposal(plan, ["comment-thread"], TREE, read_text=FILES.get, registry=())


@pytest.mark.parametrize(
    "text",
    [
        f"The probe shows `{CITED}:4:def f(): pass` at the commit.",
        f"The probe shows `{CITED}:4:` `def f(): pass` at the commit.",
        f"The probe shows {CITED}:4: `def f(): pass` at the commit.",
        f"The probe shows {CITED}:4:`def f(): pass`.",
    ],
)
def test_a_text_in_the_code_span_after_the_line_is_the_cited_text(text: str) -> None:
    assert not any(CITED in problem for problem in _cited(text))


@pytest.mark.parametrize(
    "text",
    [
        f"The probe shows {CITED}:4: `def g(): return 1` at the commit.",
        f"The probe shows `{CITED}:4:` `de` at the commit.",
        f"The probe shows `{CITED}:4:` and then no quote, but `def f(): pass` later.",
        f"The probe shows {CITED}:4: at the commit.",
    ],
)
def test_a_text_that_the_line_lacks_or_that_is_too_short_is_still_refused(text: str) -> None:
    assert any(CITED in problem for problem in _cited(text))
