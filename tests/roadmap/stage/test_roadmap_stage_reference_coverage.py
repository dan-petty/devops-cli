"""`devops roadmap stage`: require files in quoted reference search to be covered (#3321)."""

from __future__ import annotations

from devops_cli.roadmap.stage.stage_change import StageDecision, check_proposal
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal

TREE = StagedTree(
    [
        "src/devops_cli/sample.py",
        "tests/test_sample.py",
        "tests/commands/k8s/test_k8s.py",
    ]
)


def test_a_quoted_reference_file_with_no_task_or_decision_is_refused() -> None:
    path = "tests/commands/k8s/test_k8s.py"
    feasibility = [
        "References to 'SingleBinary': files 1, lines 1.",
        f"{path}: 1 (line 12)",
    ]
    proposal = make_stage_proposal(feasibility=feasibility)

    problems = check_proposal(proposal, ["comment-thread"], TREE)

    matching = [p for p in problems if path in p]
    assert len(matching) == 1


def test_a_quoted_reference_file_named_in_a_decision_is_accepted() -> None:
    path = "tests/commands/k8s/test_k8s.py"
    feasibility = [
        "References to 'SingleBinary': files 1, lines 1.",
        f"{path}: 1 (line 12)",
    ]
    decisions = [
        StageDecision(
            decision=f"Leave `{path}` unchanged",
            reason="The file only holds a comment.",
        )
    ]
    proposal = make_stage_proposal(feasibility=feasibility, decisions=decisions)

    problems = check_proposal(proposal, ["comment-thread"], TREE)

    assert not any(path in p for p in problems)


def test_a_quoted_reference_file_under_archive_is_skipped() -> None:
    path = "openspec/changes/archive/2026-10-24-1000-old/proposal.md"
    feasibility = [
        "References to 'SingleBinary': files 1, lines 1.",
        f"{path}: 1 (line 12)",
    ]
    proposal = make_stage_proposal(feasibility=feasibility)

    problems = check_proposal(proposal, ["comment-thread"], TREE)

    assert not any(path in p for p in problems)
