"""The devops commands, options and MCP exposure table keys cited in a plan (#3302)."""

from __future__ import annotations

import pytest

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
    plan = make_stage_proposal(
        feasibility=['The plan cites the exposure table key ("ai", "ast-graph").']
    )

    problems = command_citation_problems(plan)

    assert len(problems) == 1
    assert '("ai", "ast-graph")' in problems[0]


def test_known_mcp_exposure_key_is_accepted() -> None:
    plan = make_stage_proposal(
        feasibility=['The plan cites the exposure table key ("ai", "ast", "graph").']
    )

    assert command_citation_problems(plan) == []


def test_a_quoted_tuple_of_another_table_is_no_mcp_key() -> None:
    # The live run of #4062 refused a tuple of the fixture table of `tests/conftest.py` (#4255).
    plan = make_stage_proposal(
        feasibility=['The fixture table in `tests/conftest.py` lists ("reset_logfire_bridge",).']
    )

    assert command_citation_problems(plan) == []


def test_the_sentence_of_the_tuple_decides_the_context() -> None:
    plan = make_stage_proposal(
        feasibility=['The exposure table has rows. The fixture lists ("ai", "ast-graph").']
    )

    assert command_citation_problems(plan) == []


def test_the_constant_name_gives_the_context() -> None:
    plan = make_stage_proposal(
        feasibility=['`CONST_MCP_EXPOSURE_TABLE` has no row ("ai", "ast-graph") today.']
    )

    problems = command_citation_problems(plan)

    assert len(problems) == 1
    assert '("ai", "ast-graph")' in problems[0]


def test_an_unknown_key_in_a_task_text_is_refused_with_the_context() -> None:
    group = make_stage_proposal().groups[0]
    update = {"implementation": 'Add the exposure table row ("ai", "ast-graph") to the table.'}
    plan = make_stage_proposal(groups=[group.model_copy(update=update)])

    assert len(command_citation_problems(plan)) == 1


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


def test_the_prose_after_a_command_in_a_sentence_is_no_argument() -> None:
    # The sentence of the recorded plan 2152: the gate read "to confirm ..." as a subcommand of
    # `devops ci` (#4956).
    plan = make_stage_proposal(
        feasibility=[
            "First checks the implementation runs: uv run pytest tests/test_reference_extractor.py"
            " tests/test_builtin_tools.py -k 'numeric or ip' to confirm existing tests pass before"
            " and after the change; uv run devops ci to confirm the full gate including the"
            " constructs row passes."
        ]
    )

    assert command_citation_problems(plan) == []


def test_the_prose_after_a_command_with_no_arguments_is_no_argument() -> None:
    # The task text of the recorded plan 2524 (#4956).
    group = make_stage_proposal().groups[0]
    update = {
        "implementation": "In the handoff step, replace the uv run devops roadmap intake command"
        " with gh issue create."
    }
    plan = make_stage_proposal(groups=[group.model_copy(update=update)])

    assert command_citation_problems(plan) == []


def test_a_text_that_starts_with_a_command_ends_it_at_the_prose() -> None:
    group = make_stage_proposal().groups[0]
    update = {"implementation": "uv run devops ci and confirm exit code 0."}
    plan = make_stage_proposal(groups=[group.model_copy(update=update)])

    assert command_citation_problems(plan) == []


def test_each_command_of_a_sentence_is_checked_on_its_own() -> None:
    plan = make_stage_proposal(
        feasibility=[
            "(1) uv run devops ci test tests/test_sample.py to confirm the test fails; (2) uv run"
            " devops gh pages verify --root_dir docs to confirm the pages."
        ]
    )

    problems = command_citation_problems(plan)

    assert len(problems) == 1
    assert "--root_dir" in problems[0]
    assert "uv run devops gh pages verify --root_dir`" in problems[0]


def test_an_unknown_option_in_prose_is_refused() -> None:
    plan = make_stage_proposal(
        feasibility=["Run uv run devops gh pages verify --root_dir docs to check the pages."]
    )

    problems = command_citation_problems(plan)

    assert len(problems) == 1
    assert "--root_dir" in problems[0]


def test_an_unknown_subcommand_of_a_group_in_prose_is_refused() -> None:
    plan = make_stage_proposal(
        feasibility=["Run uv run devops roadmap follow 3076 to see the job of the item."]
    )

    problems = command_citation_problems(plan)

    assert len(problems) == 1
    assert "'follow'" in problems[0]


@pytest.mark.parametrize(
    ("text", "token"),
    [
        # The spec scenario of #3302 and the defect of the recorded plan 2130, in a sentence.
        ("Run uv run devops ai ast-graph --help to see the options.", "'ast-graph'"),
        ("uv run devops ai ast-graph --help", "'ast-graph'"),
        ("Run uv run devops review scan --help to list the scanners.", "'scan'"),
        ("Run uv run devops ci fail-to-pas --base origin/main to prove it.", "'fail-to-pas'"),
    ],
)
def test_an_unknown_subcommand_before_an_option_in_prose_is_refused(text: str, token: str) -> None:
    # `devops ai`, `devops review` and `devops ci` run with no subcommand, but a sentence puts no
    # option after an English word, so the word before an option is a subcommand (#4956).
    plan = make_stage_proposal(feasibility=[text])

    problems = command_citation_problems(plan)

    assert len(problems) == 1
    assert f"unknown command {token}" in problems[0]


@pytest.mark.parametrize(
    "text",
    [
        "Run uv run devops pr monitor 4982 --bogus to watch it.",
        "Run uv run devops pr monitor <pr_number> --bogus to watch it.",
        "Run uv run devops ci fail-to-pass --base origin/main --bogus to prove it.",
        "Run uv run devops ci test tests/a.py tests/b.py --bogus to confirm the test fails.",
        "Run uv run devops roadmap stage 4956 --bogus to stage it.",
    ],
)
def test_an_unknown_option_after_an_argument_or_a_value_in_prose_is_refused(text: str) -> None:
    # The command keeps its declared arguments, the values of its known options and a word before
    # an option, so the check still sees the option after them (#4956).
    plan = make_stage_proposal(feasibility=[text])

    problems = command_citation_problems(plan)

    assert len(problems) == 1
    assert "unknown option '--bogus'" in problems[0]


@pytest.mark.parametrize(
    "text",
    [
        "Run uv run devops ci fail-to-pass --base origin/main to prove it.",
        "Run uv run devops pr monitor <pr_number> until all checks pass.",
        "Run uv run devops ci --check --only lint,format to confirm the rows.",
        "Run uv run devops ci test tests/a.py -k 'numeric or ip' to confirm the test fails.",
        "Run uv run devops ci again -- it checks all the rows.",
    ],
)
def test_the_arguments_and_values_of_a_command_in_prose_are_accepted(text: str) -> None:
    plan = make_stage_proposal(feasibility=[text])

    assert command_citation_problems(plan) == []


def test_check_proposal_refuses_unknown_command_under_citation_gate() -> None:
    plan = make_stage_proposal(feasibility=["The probe cites `uv run devops ai ast-graph --help`."])

    found = check_gates(plan, KNOWN, TREE, registry=())

    assert any("ast-graph" in p for p in found[ProposalGate.CITATION])
    assert any("ast-graph" in p for p in check_proposal(plan, KNOWN, TREE, registry=()))


def test_plan_passes_content_problems() -> None:
    from devops_cli.roadmap.stage.stage_change import content_problems

    plan = make_stage_proposal()
    assert content_problems(plan) == []
