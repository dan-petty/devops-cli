"""The trace gate reads a path in the forms that the stage prompt asks a plan to cite.

A plan cites a line as `path:line:text` and a symbol as `path:def name`. The trace gate judges the
path of such a citation, and a word `read` inside a quoted line is no claim that the run read a file.
"""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.roadmap.agent_run import TraceFacts
from devops_cli.roadmap.stage.stage_change import StageProposal, check_proposal
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal

CONSTANTS = "src/devops_cli/config/constants.py"
TREE = StagedTree(["src/devops_cli/sample.py", CONSTANTS])
READ_CONSTANTS = TraceFacts(tools=frozenset({"read_file"}), paths=frozenset({CONSTANTS}))


def _problems(sentence: str, trace: TraceFacts | None) -> list[str]:
    plan: StageProposal = make_stage_proposal(feasibility=[sentence])
    keywords: dict[str, Any] = {"trace": trace}
    return check_proposal(plan, ["comment-thread"], TREE, **keywords)


@pytest.mark.parametrize(
    "span",
    [
        f"{CONSTANTS}:308:DEFAULT_LIMIT = 60",
        f"{CONSTANTS}:def load_constants",
        f"{CONSTANTS}:class Limits",
        f"./{CONSTANTS}",
        "src/devops_cli/config/constants.py",
        "config/constants.py",
        "constants.py",
    ],
)
def test_a_claim_in_a_citation_form_of_a_read_path_passes(span: str) -> None:
    assert _problems(f"The run read `{span}` and found the line.", READ_CONSTANTS) == []


@pytest.mark.parametrize(
    "span",
    [
        "src/devops_cli/config/other.py:12:value = 1",
        "src/devops_cli/config/other.py:def other",
        "src/other/constants.py",
        "other_constants.py",
    ],
)
def test_a_claim_in_a_citation_form_of_an_unread_path_is_refused(span: str) -> None:
    problems = _problems(f"The run read `{span}` and found the line.", READ_CONSTANTS)

    assert len(problems) == 1
    assert "did not read" in problems[0]


def test_the_refusal_names_the_path_and_not_the_whole_citation() -> None:
    other = "src/devops_cli/config/other.py"

    problems = _problems(f"The run read `{other}:12:value = 1` and found it.", READ_CONSTANTS)

    assert other in problems[0]
    assert "value = 1" not in problems[0]


def test_the_word_read_in_a_quoted_line_is_no_claim_of_a_read() -> None:
    sentence = f'The probe shows `{CONSTANTS}:308:(("ai", "read"), 60.0, True)` for the limit.'

    assert _problems(sentence, TraceFacts()) == []


def test_the_name_of_the_read_tool_in_a_code_span_still_makes_the_claim() -> None:
    problems = _problems("The run called `read_file` on `src/devops_cli/other.py`.", TraceFacts())

    assert len(problems) == 1
    assert "src/devops_cli/other.py" in problems[0]
