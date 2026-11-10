"""The trace gate reads the subject of `reads` (#4314).

A sentence that says what code does ("it reads `.github/labels.yml`") is no claim that the run
read a file. A claim of the run or of the author ("I read", "the run read") still is.
"""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.roadmap.agent_run import TraceFacts
from devops_cli.roadmap.stage.stage_change import StageProposal, check_proposal
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal

TREE = StagedTree(["src/devops_cli/sample.py", ".github/labels.yml"])
NO_CALLS = TraceFacts()


def _problems(sentence: str, trace: TraceFacts | None = NO_CALLS) -> list[str]:
    plan: StageProposal = make_stage_proposal(feasibility=[sentence])
    keywords: dict[str, Any] = {"trace": trace}
    return check_proposal(plan, ["comment-thread"], TREE, **keywords)


@pytest.mark.parametrize(
    "sentence",
    [
        "Precondition of `declared_labels(self.store, ref=None)`: a client of the GitHub "
        "service, because it reads `.github/labels.yml` of the default branch.",
        "The helper is the one which reads `.github/labels.yml` of the default branch.",
        "The function `declared_labels` reads `.github/labels.yml` of the default branch.",
        "The check `scope_check`, reading `.github/labels.yml`, needs a client.",
        "It is a client of the GitHub service, because it is reading `.github/labels.yml`.",
    ],
)
def test_code_that_reads_a_file_is_no_claim_that_the_run_read_it(sentence: str) -> None:
    assert _problems(sentence) == []


@pytest.mark.parametrize(
    "sentence",
    [
        "I read `src/devops_cli/sample.py` and found the function.",
        "The run read `src/devops_cli/sample.py` and found the function.",
        "The run reads `src/devops_cli/sample.py` and finds the function.",
        "After reading `src/devops_cli/sample.py`, the plan names the function.",
        "The run called `read_file` on `src/devops_cli/sample.py`.",
        "The function `declared_labels` is there, and I read `src/devops_cli/sample.py`.",
    ],
)
def test_a_claim_of_the_run_with_no_call_for_the_path_is_still_refused(sentence: str) -> None:
    problems = _problems(sentence)

    assert len(problems) == 1
    assert "did not read" in problems[0]


def test_a_claim_of_the_run_is_true_when_the_run_read_the_path() -> None:
    trace = TraceFacts(
        tools=frozenset({"read_file"}), paths=frozenset({"src/devops_cli/sample.py"})
    )

    assert _problems("I read `src/devops_cli/sample.py` and found it.", trace) == []
