"""The trace gate judges only the Feasibility sentences that a repair adds or changes (#5391).

The step `fix-plan` gives the gate the sentences of the plan of the head as `judged`: the trace
gate of the run that wrote the head passed them. The plan of the head of #5390 is the fixture. A
repair that keeps its sentences and reads none of their files again passes, and a sentence that
the repair adds or changes is judged on the reads of the repair.
"""

from __future__ import annotations

from typing import Any

from devops_cli.roadmap.agent_run import TraceFacts
from devops_cli.roadmap.plan_read import read_change
from devops_cli.roadmap.stage.stage_change import (
    ProposalGate,
    StageProposal,
    check_gates,
    feasibility_sentences,
)
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.paths import FIXTURES
from tests.support.roadmap_fix_plan import head_files

# The change folder of the plan pull request #5390 (item #5272) at its head 8d08977ffff4.
HEAD_5390 = FIXTURES / "roadmap" / "plan_heads" / "5390-8d08977ffff4"
DECISION_STEP = "src/devops_cli/roadmap/decision_step.py"
# A sentence of the Feasibility section of the head of #5390, which the stage run wrote.
GAP_2 = (
    f"`read_file {DECISION_STEP}` confirms gap 2: `{DECISION_STEP}:207:return "
    "asyncio.run(_decide_gathered(requests, model, model_name, settings, timeout))`."
)
# The same claim in the form that the fix-plan run on #5390 wrote: a `read_file` call with its
# start and end line.
GAP_2_RANGE = f"`read_file {DECISION_STEP} 50 215` confirms gap 2: `asyncio.run` stays."
# A file that the head of #5390 does not cite and that no run of the tests read.
UNREAD = "src/devops_cli/roadmap/decision_cuts.py"


def _head_5390() -> StageProposal:
    (folder,) = HEAD_5390.iterdir()
    return read_change(head_files(folder))


def _trace_problems(proposal: StageProposal, trace: TraceFacts, **options: Any) -> list[str]:
    """The problems of the trace gate alone. An empty registry keeps the registry gate from
    parsing each test file of the repository."""
    found = check_gates(
        proposal, ["decision-workflows"], StagedTree([]), trace=trace, registry=[], **options
    )
    return found[ProposalGate.TRACE]


def test_the_sentences_of_the_head_of_5390_pass_with_no_read_of_the_repair() -> None:
    head = _head_5390()

    refused = _trace_problems(head, TraceFacts())
    kept = _trace_problems(head, TraceFacts(), judged=feasibility_sentences(head))

    assert any(f"`{DECISION_STEP}` was read" in problem for problem in refused)
    assert kept == []


def test_a_sentence_that_the_repair_adds_is_judged_on_the_reads_of_the_repair() -> None:
    head = _head_5390()
    added = [*head.feasibility, GAP_2_RANGE, f"`read_file {UNREAD} 1 40` gives the cuts."]
    revision = head.model_copy(update={"feasibility": added})
    read = TraceFacts(tools=frozenset({"read_file"}), paths=frozenset({DECISION_STEP}))

    problems = _trace_problems(revision, read, judged=feasibility_sentences(head))

    assert problems == [
        f"The Feasibility section states that `{UNREAD}` was read, but the run did not read it."
    ]


def test_a_sentence_that_the_repair_changes_is_judged_again() -> None:
    head = _head_5390()
    assert GAP_2 in head.feasibility
    changed = [line.replace(":207:", ":209:") for line in head.feasibility]
    revision = head.model_copy(update={"feasibility": changed})

    problems = _trace_problems(revision, TraceFacts(), judged=feasibility_sentences(head))

    assert problems == [
        f"The Feasibility section states that `{DECISION_STEP}` was read, but the run did not "
        "read it."
    ]
