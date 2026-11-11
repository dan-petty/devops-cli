"""`devops roadmap stage`: a plan holds no placeholder text, quotes its probe, gives the cost of
its own code, keeps its summary whole (#3200), names no What Changes path that no group lists
(#3411), states the work of each task once (#3456), gives the test that accepts its own plan when
it adds a rule of the plan check (#3404) and refuses a base requirement that names a command or an
option that an added requirement removes (#3287)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

try:
    from devops_cli.roadmap.agent_run import TraceFacts
except ImportError:
    TraceFacts = None  # type: ignore[misc,assignment]
from devops_cli.roadmap.stage.stage_change import (
    PLAN_FIELD_MIN_CHARS,
    GroupKind,
    StageGroup,
    StageProposal,
    StageReference,
    check_proposal,
    content_problems,
    render_change,
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
TEST_FILE = "tests/roadmap/stage/test_roadmap_stage_content.py"
SELF_ACCEPTANCE_TEST = (
    "Write a test that builds the plan's own `StageProposal` and asserts that `content_problems` "
    "returns no problem for it, and verify that `src/devops_cli/sample.py` fails on the base"
)
DEPENDENCY_ENTRY = "#3201: the check command"
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


def test_the_plan_of_this_change_passes_the_content_rule() -> None:
    """The plan of this change adds the issue form and changes the plan check, so it gives the test
    that accepts its own plan, and `content_problems` finds no problem in it (#3404)."""
    plan = _plan_that_adds_a_rule(SELF_ACCEPTANCE_TEST).model_copy(
        update={"dependencies": [DEPENDENCY_ENTRY]}
    )

    assert content_problems(plan) == []


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


# ── A base requirement that names a removed command (#3287) ───────────────────

OLD_COMMAND = "devops roadmap intake-eval"
OLD_OPTION = "--old"
STALE_REQUIREMENT = "The intake-eval command runs each case"
STALE_STATEMENT = f"`{OLD_COMMAND}` SHALL run each case of the folder."
REMOVED_COMMAND_TEXT = f"The `{OLD_COMMAND}` command MUST NOT exist."
NEW_COMMAND_STATEMENT = "The `devops roadmap eval intake` command SHALL run each case."


def _requirement(name: str, text: str) -> dict[str, Any]:
    """A requirement of a spec delta with one scenario."""
    return {
        "name": name,
        "text": text,
        "scenarios": [{"name": "The case", "when": "the command runs", "then": "the case runs"}],
    }


def _spec(*, added: str, modified: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The delta of the known capability `comment-thread`: one ADDED requirement with the text
    `added`, and the `modified` requirements."""
    return {
        "capability": "comment-thread",
        "added": [_requirement("The old command is gone", added)],
        "modified": modified or [],
    }


def _stale_problems(
    added: str, *, texts: dict[str, str], modified: list[dict[str, Any]] | None = None
) -> list[str]:
    plan = make_stage_proposal(specs=[_spec(added=added, modified=modified)])

    return _check(plan, requirement_texts={"comment-thread": texts})


def test_a_base_requirement_that_names_a_removed_command_is_refused() -> None:
    problems = _stale_problems(REMOVED_COMMAND_TEXT, texts={STALE_REQUIREMENT: STALE_STATEMENT})

    assert len(problems) == 1
    assert OLD_COMMAND in problems[0]
    assert STALE_REQUIREMENT in problems[0]


def test_a_base_requirement_modified_without_the_command_is_accepted() -> None:
    problems = _stale_problems(
        REMOVED_COMMAND_TEXT,
        texts={STALE_REQUIREMENT: STALE_STATEMENT},
        modified=[_requirement(STALE_REQUIREMENT, NEW_COMMAND_STATEMENT)],
    )

    assert problems == []


def test_a_modified_requirement_that_keeps_the_command_is_refused() -> None:
    problems = _stale_problems(
        REMOVED_COMMAND_TEXT,
        texts={STALE_REQUIREMENT: STALE_STATEMENT},
        modified=[_requirement(STALE_REQUIREMENT, STALE_STATEMENT)],
    )

    assert len(problems) == 1
    assert OLD_COMMAND in problems[0]
    assert STALE_REQUIREMENT in problems[0]


def test_an_added_requirement_that_removes_an_option_is_refused() -> None:
    problems = _stale_problems(
        f"The `{OLD_OPTION}` option MUST NOT exist.",
        texts={
            "The old option writes the plan": f"`devops roadmap stage {OLD_OPTION}` SHALL write it."
        },
    )

    assert len(problems) == 1
    assert OLD_OPTION in problems[0]


def test_a_call_with_no_base_requirement_text_gives_no_problem() -> None:
    plan = make_stage_proposal(specs=[_spec(added=REMOVED_COMMAND_TEXT)])

    assert _check(plan) == []


def test_the_plan_that_adds_the_stale_command_rule_accepts_its_own_plan() -> None:
    """The plan's own acceptance test (#3404): the plan builds its own `StageProposal` and asserts
    that `content_problems` returns no problem for it."""
    plan = make_stage_proposal(
        specs=[
            _spec(
                added=REMOVED_COMMAND_TEXT,
                modified=[_requirement(STALE_REQUIREMENT, NEW_COMMAND_STATEMENT)],
            )
        ]
    )

    assert content_problems(plan) == []
    assert (
        _check(plan, requirement_texts={"comment-thread": {STALE_REQUIREMENT: STALE_STATEMENT}})
        == []
    )


# ── Prompt-rule verification tests (#3347) ───────────────────────────────────

PROMPT_CHANGE = "src/devops_cli/ai/tasks/roadmap_stage_change.md"
PROMPT_SPLIT = "src/devops_cli/ai/tasks/roadmap_stage_split.md"
PROMPT_RULE_TEST = "tests/roadmap/stage/test_roadmap_stage_prompt_rules.py"


def _prompt_group(
    *,
    kind: GroupKind = GroupKind.OTHER,
    reads: list[str] | None = None,
    changes: list[str] | None = None,
    verify: str | None = f"uv run devops ci test {PROMPT_RULE_TEST}",
    process: str | None = None,
    test: str | None = None,
) -> StageGroup:
    group = make_stage_proposal().groups[0]
    effective_kind = GroupKind.BEHAVIOR if test is not None else kind
    return group.model_copy(
        update={
            "kind": effective_kind,
            "reads": reads if reads is not None else [PROMPT_CHANGE],
            "changes": changes if changes is not None else [PROMPT_CHANGE],
            "creates": [],
            "creates_lines": {},
            "verify": verify,
            "process": process,
            "test": test,
        }
    )


def test_a_prompt_change_with_no_prompt_rule_test_is_refused() -> None:
    problems = content_problems(make_stage_proposal(groups=[_prompt_group()]))

    assert len(problems) == 1
    assert PROMPT_CHANGE in problems[0]
    assert PROMPT_RULE_TEST in problems[0]


def test_a_prompt_change_that_verifies_another_command_is_refused() -> None:
    group = _prompt_group(
        reads=[PROMPT_RULE_TEST],
        changes=[PROMPT_SPLIT],
        verify="uv run devops ci docs",
    )

    problems = content_problems(make_stage_proposal(groups=[group]))

    assert len(problems) == 1
    assert PROMPT_SPLIT in problems[0]
    assert PROMPT_RULE_TEST in problems[0]


def test_a_prompt_change_that_gives_a_process_is_refused_once() -> None:
    group = _prompt_group(
        changes=[PROMPT_CHANGE, PROMPT_RULE_TEST],
        verify=None,
        process="Open both prompts and compare the sentence with the rule of the check.",
    )

    problems = content_problems(make_stage_proposal(groups=[group]))

    assert len(problems) == 1
    assert PROMPT_CHANGE in problems[0]
    assert PROMPT_RULE_TEST in problems[0]


def test_the_plan_check_accepts_the_plan_of_this_change() -> None:
    group = _prompt_group(
        reads=[PROMPT_RULE_TEST],
        changes=[PROMPT_CHANGE, PROMPT_RULE_TEST],
        verify=f"uv run devops ci test {PROMPT_RULE_TEST}",
        test=SELF_ACCEPTANCE_TEST,
    )
    plan = make_stage_proposal(
        summary="Refuse a prompt change with no prompt-rule test",
        why=(
            "Issue #3347: the stage job accepts a plan that changes a planner prompt and reads no "
            "prompt-rule test."
        ),
        what_changes=[
            f"`{PLAN_CHECK_FILE}` gains the prompt-rule check.",
            f"`{MESSAGES_FILE}` gains the message of the check.",
            f"`{PROMPT_CHANGE}` and `{PROMPT_SPLIT}` state the rule.",
            f"`{PROMPT_RULE_TEST}` pins the sentence of each prompt.",
        ],
        existing_tool=(
            "No open tool covers the check: about 60k tokens to build, 6k tokens to keep and "
            "about 3 hours of elapsed time."
        ),
        groups=[group],
    )

    assert content_problems(plan) == []


# ── Reference coverage and unchanged references (#3373) ──────────────────────


def test_check_proposal_refuses_uncovered_reference_and_accepts_changed() -> None:
    path = "tests/roadmap/test_x.py"
    tree = TREE.with_files([path])
    proposal = make_stage_proposal()

    # Uncovered probed reference is refused
    problems = check_proposal(proposal, ["comment-thread"], tree, references=[path])
    assert any(path in p for p in problems)

    # When a group changes that path, it is accepted
    group = proposal.groups[0].model_copy(update={"changes": [*proposal.groups[0].changes, path]})
    plan_with_change = make_stage_proposal(groups=[group])
    assert check_proposal(plan_with_change, ["comment-thread"], tree, references=[path]) == []

    # When marked unchanged with a reason, it is accepted
    ref = StageReference(
        path=path, kind="snapshot file", unchanged=True, reason="Legacy snapshot format kept."
    )
    plan_with_ref = make_stage_proposal(references=[ref])
    assert check_proposal(plan_with_ref, ["comment-thread"], tree, references=[path]) == []


def test_schema_refuses_unchanged_reference_with_no_reason() -> None:
    path = "tests/roadmap/test_x.py"
    with pytest.raises(ValidationError, match=path):
        StageReference(path=path, kind="snapshot file", unchanged=True, reason="")


def test_schema_accepts_a_null_reason_for_a_changed_reference() -> None:
    reply = {
        "path": "src/a.py",
        "kind": "import",
        "unchanged": False,
        "reason": None,
    }

    plan = make_stage_proposal(references=[reply])

    assert plan.references[0].unchanged is False
    assert not plan.references[0].reason


def test_schema_refuses_unchanged_reference_with_a_null_reason() -> None:
    path = "tests/roadmap/test_x.py"
    with pytest.raises(ValidationError, match=path):
        StageReference.model_validate(
            {"path": path, "kind": "snapshot file", "unchanged": True, "reason": None}
        )


def test_design_file_renders_unchanged_reference_path_kind_and_reason() -> None:
    path = "tests/snapshots/roadmap/test_x.ambr"
    kind = "snapshot file"
    reason = "Snapshot stays keyed by old path."
    ref = StageReference(path=path, kind=kind, unchanged=True, reason=reason)
    plan = make_stage_proposal(references=[ref])

    files = render_change("3373-a-move-plan", plan, ["comment-thread"], created=date(2026, 11, 8))
    design_text = files["openspec/changes/3373-a-move-plan/design.md"]

    assert path in design_text
    assert kind in design_text
    assert reason in design_text


# ── Test-only other group (#3433) ─────────────────────────────────────────────


def _test_only_group(**updates: Any) -> StageGroup:
    defaults: dict[str, Any] = {
        "title": "Keep the roadmap stage tests green",
        "kind": GroupKind.OTHER,
        "test": None,
        "changes": ["tests/roadmap/stage/test_roadmap_stage_content.py"],
        "creates": [],
        "creates_lines": {},
        "implementation": "Run the test suite and fix the test if it breaks.",
        "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py",
    }
    return _group(**(defaults | updates))


def test_a_test_only_other_group_with_no_named_test_is_refused() -> None:
    group = _test_only_group()
    problems = content_problems(make_stage_proposal(groups=[group]))

    assert len(problems) == 1
    assert "Keep the roadmap stage tests green" in problems[0]


def test_a_test_only_other_group_with_a_named_test_is_accepted() -> None:
    group = _test_only_group(
        implementation="Update `test_conditional_group` for the new rule.",
    )

    assert content_problems(make_stage_proposal(groups=[group])) == []


def test_a_test_only_other_group_with_a_named_test_after_a_path_is_accepted() -> None:
    group = _test_only_group(
        implementation=(
            "Update `tests/roadmap/stage/test_roadmap_stage_content.py::test_conditional_group`."
        ),
    )

    assert content_problems(make_stage_proposal(groups=[group])) == []


def test_an_other_group_with_a_source_path_and_no_named_test_is_accepted() -> None:
    group = _test_only_group(
        changes=[
            "tests/roadmap/stage/test_roadmap_stage_content.py",
            "src/devops_cli/roadmap/stage/stage_change.py",
        ],
        implementation="Update the stage change module and its test suite.",
    )

    assert content_problems(make_stage_proposal(groups=[group])) == []


def test_a_test_only_other_group_that_changes_a_test_helper_is_accepted() -> None:
    group = _test_only_group(
        title="Add the stage group builder",
        changes=["tests/support/builders.py"],
        implementation="Add `make_stage_group` to `tests/support/builders.py`.",
    )

    assert content_problems(make_stage_proposal(groups=[group])) == []


def test_a_test_only_other_group_that_names_only_a_test_file_path_is_refused() -> None:
    group = _test_only_group(
        implementation="Update `tests/roadmap/stage/test_roadmap_stage_content.py`.",
    )

    problems = content_problems(make_stage_proposal(groups=[group]))

    assert len(problems) == 1
    assert "Keep the roadmap stage tests green" in problems[0]


def test_a_feasibility_line_that_claims_a_read_without_trace_call_is_refused() -> None:
    agent_run = "src/devops_cli/roadmap/agent_run.py"
    plan = make_stage_proposal(feasibility=[f"The run read `{agent_run}` to check the premise."])
    trace = TraceFacts() if TraceFacts is not None else None

    problems = _check(plan, trace=trace)

    assert len(problems) == 1
    assert agent_run in problems[0]


def test_a_feasibility_line_that_claims_a_read_with_trace_call_passes() -> None:
    agent_run = "src/devops_cli/roadmap/agent_run.py"
    plan = make_stage_proposal(feasibility=[f"The run read `{agent_run}` to check the premise."])
    trace = (
        TraceFacts(tools=frozenset({"read_file"}), paths=frozenset({agent_run}))
        if TraceFacts is not None
        else None
    )

    assert _check(plan, trace=trace) == []


def test_a_feasibility_line_that_names_an_uncalled_toolbox_tool_is_refused() -> None:
    plan = make_stage_proposal(feasibility=["The run called `search_code` on the repository."])
    trace = TraceFacts() if TraceFacts is not None else None

    problems = _check(plan, trace=trace)

    assert len(problems) == 1
    assert "search_code" in problems[0]


def test_a_feasibility_line_that_negates_a_read_passes() -> None:
    agent_run = "src/devops_cli/roadmap/agent_run.py"
    plan = make_stage_proposal(
        feasibility=[f"The run did not read `{agent_run}` because of no tools."]
    )
    trace = TraceFacts() if TraceFacts is not None else None

    assert _check(plan, trace=trace) == []


def test_a_feasibility_line_with_no_trace_facts_passes() -> None:
    agent_run = "src/devops_cli/roadmap/agent_run.py"
    plan = make_stage_proposal(feasibility=[f"The run read `{agent_run}` to check the premise."])

    assert _check(plan, trace=None) == []


def test_content_problems_accepts_this_plans_own_proposal() -> None:
    sample = make_stage_proposal()
    group = sample.groups[0].model_copy(
        update={
            "title": "Refuse an unsupported feasibility claim in the gates",
            "kind": GroupKind.BEHAVIOR,
            "changes": [PLAN_CHECK_FILE, MESSAGES_FILE],
            "creates": [],
            "creates_lines": {},
            "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py",
            "test": (
                "Write a test that builds this plan's own `StageProposal` and asserts that "
                "`content_problems` returns no problem for it, and that `src/devops_cli/sample.py` "
                "fails on the base"
            ),
        }
    )
    plan = make_stage_proposal(
        summary="Refuse feasibility claims the run did not make",
        why=(
            "Issue #3266: the stage job accepts a plan whose Feasibility section cites a tool read "
            "that the run never made."
        ),
        what_changes=[
            f"`{PLAN_CHECK_FILE}` gains the trace check.",
            f"`{MESSAGES_FILE}` gains the messages of the check.",
        ],
        existing_tool=(
            "No open tool covers the check: about 80k tokens to build, 20k tokens to keep and "
            "about 4 hours of elapsed time."
        ),
        groups=[group],
    )
    assert content_problems(plan) == []


def test_content_problems_accepts_the_helper_rules_own_proposal() -> None:
    """The plan's own acceptance test (#3404): the plan builds its own `StageProposal` and asserts
    that `content_problems` returns no problem for it."""
    sample = make_stage_proposal()
    group = sample.groups[0].model_copy(
        update={
            "title": "Accept a test helper group in the plan check",
            "kind": GroupKind.BEHAVIOR,
            "changes": [PLAN_CHECK_FILE, TEST_FILE],
            "creates": [],
            "creates_lines": {},
            "verify": f"uv run devops ci test {TEST_FILE}",
            "test": (
                "Write `test_a_test_only_other_group_that_changes_a_test_helper_is_accepted` in "
                f"`{TEST_FILE}` first, build the plan's own `StageProposal`, assert that "
                "`content_problems` returns no problem for it, and verify that "
                "`src/devops_cli/sample.py` fails on the base"
            ),
        }
    )
    plan = make_stage_proposal(
        summary="Accept a test helper group in the plan check",
        why=(
            "Issue #3462: the plan check refuses an `other` group that changes only a test helper, "
            "because its implementation names a helper and no test function."
        ),
        what_changes=[
            f"`{PLAN_CHECK_FILE}` judges only an `other` group whose paths are test modules.",
            f"`{TEST_FILE}` gains the case of a helper group and of a path-only group.",
        ],
        groups=[group],
    )

    assert content_problems(plan) == []


def test_a_plan_that_adds_devops_review_to_job_without_runner_capability_is_refused() -> None:
    plan = make_stage_proposal(
        what_changes=["Run `devops review` in the implement job."],
        feasibility=["The code was checked with git grep."],
    )
    problems = content_problems(plan)
    assert any("devops review" in p and "Feasibility" in p for p in problems)


def test_a_plan_that_adds_devops_review_to_job_with_runner_capability_is_accepted() -> None:
    plan = make_stage_proposal(
        what_changes=["Run `devops review` in the implement job."],
        feasibility=["The runner pod carries review tools and bwrap sandbox."],
    )
    assert not any("devops review" in p for p in content_problems(plan))


def test_a_plan_whose_verify_runs_a_not_in_runner_program_without_capability_is_refused() -> None:
    group = (
        make_stage_proposal().groups[0].model_copy(update={"verify": "helm template k8s/devops"})
    )
    plan = make_stage_proposal(groups=[group], feasibility=["The code was checked."])
    problems = content_problems(plan)
    assert any("helm" in p and "NOT_IN_RUNNER" in p for p in problems)


def test_a_plan_whose_verify_runs_a_not_in_runner_program_with_capability_is_accepted() -> None:
    group = (
        make_stage_proposal().groups[0].model_copy(update={"verify": "helm template k8s/devops"})
    )
    plan = make_stage_proposal(
        groups=[group],
        feasibility=["The runner lacks helm (NOT_IN_RUNNER), verified manually."],
    )
    assert not any("helm" in p for p in content_problems(plan))
