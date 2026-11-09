"""The devops commands, options and MCP exposure table keys cited in a plan (#3302)."""

from __future__ import annotations

from devops_cli.roadmap.stage.stage_change import ProposalGate, check_gates, check_proposal
from devops_cli.roadmap.stage.stage_commands import command_citation_problems
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal

TREE = StagedTree(["src/devops_cli/sample.py"])
KNOWN = ["comment-thread"]


def test_unknown_subcommand_is_refused() -> None:
    plan = make_stage_proposal(feasibility=["The probe cites `uv run devops ai ast-graph --help`."])

    problems = command_citation_problems(plan)

    assert len(problems) == 1
    assert "ai ast-graph" in problems[0] or "ast-graph" in problems[0]


def test_known_subcommand_is_accepted() -> None:
    plan = make_stage_proposal(feasibility=["The probe cites `uv run devops ai ast graph --help`."])

    assert command_citation_problems(plan) == []


def test_unknown_option_is_refused() -> None:
    plan = make_stage_proposal(
        feasibility=["The probe cites `uv run devops gh pages verify --root_dir .`."]
    )

    problems = command_citation_problems(plan)

    assert len(problems) == 1
    assert "--root_dir" in problems[0]


def test_known_option_is_accepted() -> None:
    plan = make_stage_proposal(
        feasibility=["The probe cites `uv run devops gh pages verify --dir .`."]
    )

    assert command_citation_problems(plan) == []


def test_unknown_mcp_exposure_key_is_refused() -> None:
    plan = make_stage_proposal(feasibility=['The plan cites ("ai", "ast-graph").'])

    problems = command_citation_problems(plan)

    assert len(problems) == 1
    assert '("ai", "ast-graph")' in problems[0]


def test_known_mcp_exposure_key_is_accepted() -> None:
    plan = make_stage_proposal(feasibility=['The plan cites ("ai", "ast", "graph").'])

    assert command_citation_problems(plan) == []


def test_task_command_citation_is_checked() -> None:
    group = make_stage_proposal().groups[0]
    update = {"implementation": "Run `uv run devops gh pages verify --bad-opt` here"}
    plan = make_stage_proposal(groups=[group.model_copy(update=update)])

    problems = command_citation_problems(plan)

    assert len(problems) == 1
    assert "--bad-opt" in problems[0]


def test_placeholder_argument_is_accepted() -> None:
    plan = make_stage_proposal(feasibility=["Run `uv run devops openspec archive <change>`."])

    assert command_citation_problems(plan) == []


def test_check_proposal_refuses_unknown_command_under_citation_gate() -> None:
    plan = make_stage_proposal(feasibility=["The probe cites `uv run devops ai ast-graph --help`."])

    found = check_gates(plan, KNOWN, TREE)

    assert any("ast-graph" in p for p in found[ProposalGate.CITATION])
    assert any("ast-graph" in p for p in check_proposal(plan, KNOWN, TREE))


def test_plan_passes_content_problems() -> None:
    from devops_cli.roadmap.stage.stage_change import content_problems

    plan = make_stage_proposal()
    assert content_problems(plan) == []
