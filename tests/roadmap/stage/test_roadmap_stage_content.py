"""`devops roadmap stage`: a plan holds no placeholder text, quotes its probe, gives the cost of
its own code, keeps its summary whole (#3200), names no What Changes path that no group lists
(#3411), states the work of each task once (#3456) and gives the test that accepts its own plan
when it adds a rule of the plan check (#3404)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from devops_cli.roadmap.stage.stage_change import (
    PLAN_FIELD_MIN_CHARS,
    GroupKind,
    StageGroup,
    StageProposal,
    check_proposal,
    content_problems,
    staging_title,
)
from devops_cli.roadmap.stage.stage_eval_cases import DefectType, GateName
from devops_cli.roadmap.stage.stage_eval_gates import gate_for
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal

PROBE = "def f(): pass"
TREE = StagedTree(["src/devops_cli/sample.py", "tests/test_sample.py"])
MESSAGES_FILE = "src/devops_cli/lang/en/messages.py"
PLAN_CHECK_FILE = "src/devops_cli/roadmap/stage/stage_change.py"
SELF_ACCEPTANCE_TEST = (
    "Write a test that builds the plan's own `StageProposal` and asserts that `content_problems` "
    "returns no problem for it"
)
LIVING_SPEC = "openspec/specs/roadmap-stage/spec.md"
LIVING_SPEC_TREE = TREE.with_files([LIVING_SPEC])


def _check(proposal: StageProposal, **keywords: Any) -> list[str]:
    return check_proposal(proposal, ["comment-thread"], TREE, **keywords)


def _plan_that_adds_a_rule(test: str) -> StageProposal:
    sample = make_stage_proposal()
    group = sample.groups[0].model_copy(
        update={"changes": [*sample.groups[0].changes, PLAN_CHECK_FILE], "test": test}
    )
    return make_stage_proposal(groups=[group])


def _group(**updates: Any) -> StageGroup:
    """The sample group with `updates`, which the schema does not check again."""
    return make_stage_proposal().groups[0].model_copy(update=updates)


def test_the_sample_plan_has_no_content_problem() -> None:
    assert content_problems(make_stage_proposal()) == []
    assert _check(make_stage_proposal()) == []


def test_a_why_of_x_is_refused_with_its_field_and_the_least_length() -> None:
    problems = _check(make_stage_proposal(why="x"))

    assert any(
        "of why has 1 characters" in p and f"least is {PLAN_FIELD_MIN_CHARS}" in p for p in problems
    )


def test_a_placeholder_existing_tool_is_refused_with_its_field_and_the_placeholder_rule() -> None:
    problems = _check(make_stage_proposal(existing_tool="todo"))

    assert any("existing_tool is the placeholder `todo`" in p for p in problems)


@pytest.mark.parametrize("text", ["TBD", "x", "None.", "placeholder"])
def test_a_placeholder_word_is_a_placeholder_for_the_rule_of_the_pull_request_form(
    text: str,
) -> None:
    problems = content_problems(make_stage_proposal(why=text))

    assert any("is the placeholder" in p for p in problems)


def test_a_short_real_sentence_is_accepted() -> None:
    assert content_problems(make_stage_proposal(why="No alternative.")) == []


@pytest.mark.parametrize("line", ["x", "ok"])
def test_a_short_line_of_feasibility_is_refused(line: str) -> None:
    problems = content_problems(make_stage_proposal(feasibility=[line]))

    assert any("of feasibility" in p for p in problems)


def test_a_short_decision_and_a_short_task_are_refused_with_their_field() -> None:
    sample = make_stage_proposal()
    group = sample.groups[0].model_copy(update={"implementation": "Do it"})
    decision = {"decision": "Short one", "reason": "A reason that is long enough."}

    problems = content_problems(make_stage_proposal(decisions=[decision], groups=[group]))

    assert [p.split(" has ")[0] for p in problems] == [
        "The text of decision",
        "The text of implementation of group 1",
    ]


def test_a_feasibility_with_no_probe_line_is_refused_when_there_are_probes() -> None:
    problems = content_problems(make_stage_proposal(feasibility=["The function exists."]), [PROBE])

    assert any("feasibility list quotes no line of the probes" in p for p in problems)


def test_a_feasibility_that_quotes_a_probe_line_is_accepted() -> None:
    plan = make_stage_proposal(feasibility=[f"The probe shows {PROBE}."])

    assert content_problems(plan, [PROBE]) == []


def test_a_quote_holds_when_the_white_space_differs() -> None:
    plan = make_stage_proposal(feasibility=["The probe shows `a`   exists at\nthe commit."])

    assert content_problems(plan, ["`a` exists   at the commit"]) == []


def test_a_job_that_read_no_probe_is_not_judged_on_the_quote() -> None:
    assert content_problems(make_stage_proposal(feasibility=["The function exists."])) == []


def test_check_proposal_passes_the_probes_to_the_content_check() -> None:
    plan = make_stage_proposal(feasibility=["The function exists."])

    assert any("quotes no line" in p for p in _check(plan, probes=[PROBE]))
    assert not any("quotes no line" in p for p in _check(plan))


def test_a_plan_that_builds_its_own_code_gives_a_token_count_and_a_time() -> None:
    plan = make_stage_proposal(builds_own=True, existing_tool="Pydantic can set a minimum length.")

    assert any("builds_own is true" in p for p in content_problems(plan))


@pytest.mark.parametrize(
    "cost",
    [
        "Cost to build: about 80k tokens and 4 hours.",
        "1200 tokens, 30 Minutes",
        "1.5K tokens, 2 hours",
    ],
)
def test_a_cost_with_tokens_and_a_time_is_accepted(cost: str) -> None:
    assert content_problems(make_stage_proposal(builds_own=True, existing_tool=cost)) == []


@pytest.mark.parametrize("cost", ["It costs 80k tokens to build.", "It takes 4 hours to build it."])
def test_a_cost_with_only_tokens_or_only_a_time_is_refused(cost: str) -> None:
    plan = make_stage_proposal(builds_own=True, existing_tool=cost)

    assert any("builds_own is true" in p for p in content_problems(plan))


def test_a_plan_that_adopts_a_tool_needs_no_cost() -> None:
    plan = make_stage_proposal(builds_own=False, existing_tool="Pydantic covers the need.")

    assert content_problems(plan) == []


def test_a_summary_over_the_bound_is_refused_by_the_schema() -> None:
    limit = StageProposal.model_json_schema()["properties"]["summary"]["maxLength"]

    with pytest.raises(ValidationError, match=f"limit is {limit}"):
        make_stage_proposal(summary="a" * (limit + 1))


def test_a_summary_that_ends_with_an_ellipsis_is_refused_by_the_schema() -> None:
    with pytest.raises(ValidationError, match=r"ends with `\.\.\.`"):
        make_stage_proposal(summary="Refuse a cut text...")


def test_the_staging_title_holds_the_whole_summary() -> None:
    assert staging_title(3200, "Refuse placeholder text") == (
        "docs(openspec): plan #3200 Refuse placeholder text"
    )


def test_the_replay_has_a_content_gate_for_the_other_type() -> None:
    assert gate_for(DefectType.OTHER) is GateName.CONTENT


def test_a_what_changes_path_that_no_group_lists_is_refused() -> None:
    plan = make_stage_proposal(what_changes=[f"`{MESSAGES_FILE}` gains a message."])

    problems = _check(plan)

    assert any(MESSAGES_FILE in p for p in problems)


def test_a_what_changes_path_that_a_group_changes_is_accepted() -> None:
    plan = make_stage_proposal(what_changes=["`src/devops_cli/sample.py` keeps the last comment."])

    assert not any("src/devops_cli/sample.py" in p for p in _check(plan))


def test_a_what_changes_path_that_a_group_creates_is_accepted() -> None:
    sample = make_stage_proposal()
    group = sample.groups[0].model_copy(
        update={
            "changes": [*sample.groups[0].changes, "src/devops_cli/new_check.py"],
            "creates": [*sample.groups[0].creates, "src/devops_cli/new_check.py"],
            "creates_lines": {**sample.groups[0].creates_lines, "src/devops_cli/new_check.py": 20},
        }
    )
    plan = make_stage_proposal(
        what_changes=["`src/devops_cli/new_check.py` refuses the plan."], groups=[group]
    )

    assert not any("src/devops_cli/new_check.py" in p for p in _check(plan))


def test_a_what_changes_item_with_no_path_is_accepted() -> None:
    plan = make_stage_proposal(what_changes=["The job keeps the last comment of a thread."])

    assert not any("What Changes" in p for p in _check(plan))


def test_a_what_changes_code_span_that_is_no_path_is_accepted() -> None:
    plan = make_stage_proposal(what_changes=["Run `uv run devops ci test` before the change."])

    assert not any("What Changes" in p for p in _check(plan))


def test_a_what_changes_path_under_the_living_spec_folder_is_accepted() -> None:
    plan = make_stage_proposal(what_changes=[f"`{LIVING_SPEC}` gains a scenario."])

    problems = check_proposal(plan, ["comment-thread"], LIVING_SPEC_TREE)

    assert not any(LIVING_SPEC in p for p in problems)


def test_a_what_changes_folder_that_a_group_writes_under_is_accepted() -> None:
    sample = make_stage_proposal()
    group = sample.groups[0].model_copy(
        update={
            "changes": [*sample.groups[0].changes, "src/devops_cli/sample/ready.py"],
            "creates": [*sample.groups[0].creates, "src/devops_cli/sample/ready.py"],
            "creates_lines": {
                **sample.groups[0].creates_lines,
                "src/devops_cli/sample/ready.py": 10,
            },
        }
    )
    plan = make_stage_proposal(
        what_changes=["Move the sample module into `src/devops_cli/sample/`."], groups=[group]
    )

    problems = _check(plan)

    assert not any("src/devops_cli/sample/" in p for p in problems)


# ── A citation of the staged file (#3422) ─────────────────────────────────────

CITED = "src/sample.py"
OTHER_CITED = "src/other.py"
CITED_FILES = {
    CITED: "\n".join(
        [
            "import os",
            "",
            "",
            "def f(): pass",
            "",
            "",
            "def f():",
            "    return 1",
            "",
            "class G:",
            "    pass",
        ]
    ),
    OTHER_CITED: "\n".join(["import os", "", "", "def g(): pass", "", "", "def g():"]),
}


def _cited(text: str, **overrides: Any) -> list[str]:
    plan = make_stage_proposal(feasibility=[text], **overrides)
    return check_proposal(plan, ["comment-thread"], TREE, read_text=CITED_FILES.get)


def test_the_sample_plan_cites_no_line_that_the_staged_file_lacks() -> None:
    assert (
        check_proposal(make_stage_proposal(), ["comment-thread"], TREE, read_text=CITED_FILES.get)
        == []
    )


def test_a_citation_of_a_line_that_holds_other_text_is_refused() -> None:
    problems = _cited(f"The probe shows `{CITED}:4:def g():` at the commit.")

    assert any("feasibility" in p and CITED in p for p in problems)


def test_a_citation_of_the_line_that_holds_the_text_is_accepted() -> None:
    problems = _cited(f"The probe shows `{CITED}:4:def f():` at the commit.")

    assert not any(CITED in p for p in problems)


def test_a_citation_of_a_line_past_the_end_is_refused() -> None:
    problems = _cited(f"The probe shows `{CITED}:99:def f():` at the commit.")

    assert any("feasibility" in p and CITED in p for p in problems)


def test_a_citation_of_an_absent_path_is_refused() -> None:
    problems = _cited("The probe shows `src/absent.py:1:def f():` at the commit.")

    assert any("feasibility" in p and "src/absent.py" in p for p in problems)


def test_a_citation_of_a_text_of_fewer_than_three_characters_is_refused() -> None:
    problems = _cited(f"The probe shows `{CITED}:4:de` at the commit.")

    assert any("feasibility" in p and CITED in p for p in problems)


def test_a_citation_of_a_symbol_is_accepted_when_the_file_defines_it() -> None:
    problems = _cited(f"The probe shows `{CITED}:def f` at line 7.")

    assert not any(CITED in p for p in problems)


def test_a_citation_of_a_class_is_accepted_when_the_file_defines_it() -> None:
    problems = _cited(f"The probe shows `{CITED}:class G` at line 10.")

    assert not any(CITED in p for p in problems)


def test_a_citation_of_an_absent_symbol_is_refused() -> None:
    problems = _cited(f"The probe shows `{OTHER_CITED}:def f` at the commit.")

    assert any("feasibility" in p and OTHER_CITED in p for p in problems)


def test_a_stale_citation_of_what_changes_names_that_field() -> None:
    plan = make_stage_proposal(what_changes=[f"The probe reads `{CITED}:4:def g():` now."])

    problems = check_proposal(plan, ["comment-thread"], TREE, read_text=CITED_FILES.get)

    assert any("what_changes" in p and CITED in p for p in problems)


def test_a_plan_with_no_reader_gets_no_citation_problem() -> None:
    plan = make_stage_proposal(feasibility=[f"The probe shows `{CITED}:4:def g():` at the commit."])

    assert not any(CITED in p for p in _check(plan))


def test_a_citation_holds_when_the_white_space_differs() -> None:
    problems = _cited(f"The probe shows `{CITED}:4:def   f():` at the commit.")

    assert not any(CITED in p for p in problems)


def test_a_rule_of_the_plan_check_needs_its_self_acceptance_test() -> None:
    plan = _plan_that_adds_a_rule(
        "Write `test_the_rule_refuses_the_plan` in `tests/roadmap/test_roadmap_stage_content.py`"
    )

    problems = content_problems(plan)

    assert any("StageProposal" in p and "content_problems" in p for p in problems)


def test_a_rule_of_the_plan_check_with_its_self_acceptance_test_is_accepted() -> None:
    assert content_problems(_plan_that_adds_a_rule(SELF_ACCEPTANCE_TEST)) == []


def test_a_plan_check_change_of_another_kind_needs_no_self_acceptance_test() -> None:
    sample = make_stage_proposal()
    group = sample.groups[0].model_copy(
        update={
            "kind": "other",
            "changes": [*sample.groups[0].changes, PLAN_CHECK_FILE],
            "test": None,
        }
    )

    assert content_problems(make_stage_proposal(groups=[group])) == []


def test_two_tasks_of_one_group_that_state_the_same_work_are_refused() -> None:
    group = _group(documentation="Keep the last comment in `src/devops_cli/sample.py`")

    problems = _check(make_stage_proposal(groups=[group]))

    assert any(
        "state the same work" in p and "1.2" in p and "1.3" in p and "group 1" in p
        for p in problems
    )


def test_two_tasks_of_two_groups_that_state_the_same_work_are_refused() -> None:
    first = _group()
    second = _group(
        title="Keep the first comment",
        test="Write `test_the_job_keeps_the_first_comment` in `tests/test_sample.py`",
    )

    problems = _check(make_stage_proposal(groups=[first, second]))

    assert any(
        "state the same work" in p and "1.2" in p and "2.2" in p and "groups 1 and 2" in p
        for p in problems
    )


def test_two_tasks_that_share_a_verification_command_are_accepted() -> None:
    first = _group()
    second = _group(
        title="Keep the first comment",
        test="Write `test_the_job_keeps_the_first_comment` in `tests/test_sample.py`",
        implementation="Keep the first comment in `src/devops_cli/sample.py`",
    )

    problems = _check(make_stage_proposal(groups=[first, second]))

    assert not any("state the same work" in p for p in problems)


def test_a_documents_task_that_repeats_a_work_text_is_refused() -> None:
    work = "Add the duplicate-task message to the roadmap catalog of `MESSAGES.roadmap`"
    group = _group(
        kind=GroupKind.OTHER,
        test=None,
        changes=[MESSAGES_FILE],
        creates=[],
        creates_lines={},
        implementation=work,
        documentation=work,
        verify="uv run devops ci test tests/roadmap/test_roadmap_stage_content.py",
    )
    plan = make_stage_proposal(
        what_changes=[f"`{MESSAGES_FILE}` gains the duplicate-task message."], groups=[group]
    )

    problems = check_proposal(plan, ["comment-thread"], TREE.with_files([MESSAGES_FILE]))

    assert any("state the same work" in p and "1.1" in p and "1.2" in p for p in problems)


def test_work_text_that_differs_only_in_case_and_spacing_is_refused() -> None:
    group = _group(documentation="keep  the LAST comment in `src/devops_cli/sample.py`")

    problems = _check(make_stage_proposal(groups=[group]))

    assert any("state the same work" in p and "1.2" in p and "1.3" in p for p in problems)
