"""Plan amendment (#3057): parse an agent's request and judge whether to apply it."""

from __future__ import annotations

from devops_cli.lang.en.messages import MESSAGES
from devops_cli.roadmap.implement.implement_amend import (
    Amendment,
    Applied,
    PlanRequest,
    Refused,
    judge,
    parse_request,
)
from devops_cli.roadmap.stage.stage_paths import StagedTree

SAMPLE_TASKS = """\
# Tasks

## 1. First group

Reads: `src/devops_cli/sample.py`. Changes: `tests/commands/test_sample.py`, `src/devops_cli/new_file.py` (new).

- [ ] 1.1 In `tests/commands/test_sample.py`, write tests. Verify that `uv run pytest tests/commands/test_sample.py` passes
  - Verification: `$ uv run pytest tests/commands/test_sample.py`
- [ ] 1.2 Implement the change

## 2. Second group

Reads: `src/devops_cli/sample.py`. Changes: `src/devops_cli/sample.py`.

- [ ] 2.1 First task of group 2
  - Verification: `$ uv run devops ci test tests/roadmap/test_sample.py`
- [ ] 2.2 Second task of group 2
  - Verification: `$ uv run devops ci test tests/roadmap/test_sample.py`

## Criteria

- Some criterion naming `tests/commands/test_sample.py` and `tests/only_in_criteria.py`: group 1

## Workflow follow-up

- Review the diff in tuicr.
"""

DONE_TASKS = """\
# Tasks

## 1. First group

Reads: `src/devops_cli/sample.py`. Changes: `tests/roadmap/test_sample.py`.

- [x] 1.1 In `tests/roadmap/test_sample.py`, write tests
  - Verification: `$ uv run devops ci test tests/roadmap/test_sample.py`

## Workflow follow-up

- Review the diff in tuicr.
"""


def test_parse_request_returns_request_when_block_ends_message() -> None:
    message = (
        "I cannot find the file in commands/.\n\n"
        "```plan-request\n"
        "{\n"
        '  "kind": "path",\n'
        '  "group": 1,\n'
        '  "defect": "The test file is not in commands/",\n'
        '  "evidence": "git ls-files tests/commands/test_sample.py returned nothing",\n'
        '  "old": "tests/commands/test_sample.py",\n'
        '  "new": "tests/roadmap/test_sample.py"\n'
        "}\n"
        "```"
    )
    request = parse_request(message)
    assert request is not None
    assert request.kind == "path"
    assert request.group == 1
    assert request.defect == "The test file is not in commands/"
    assert request.evidence == "git ls-files tests/commands/test_sample.py returned nothing"
    assert request.old == "tests/commands/test_sample.py"
    assert request.new == "tests/roadmap/test_sample.py"


def test_parse_request_returns_none_when_no_block() -> None:
    message = "I cannot find the file in commands/."
    assert parse_request(message) is None


def test_parse_request_returns_none_when_text_follows_block() -> None:
    message = (
        "```plan-request\n"
        "{\n"
        '  "kind": "path",\n'
        '  "group": 1,\n'
        '  "defect": "Missing file",\n'
        '  "evidence": "ls failed",\n'
        '  "old": "tests/commands/test_sample.py",\n'
        '  "new": "tests/roadmap/test_sample.py"\n'
        "}\n"
        "```\n"
        "Please help fix this plan."
    )
    assert parse_request(message) is None


def test_parse_request_returns_none_when_bad_json() -> None:
    message = "```plan-request\n{ not valid json }\n```"
    assert parse_request(message) is None


def test_parse_request_returns_none_when_unknown_kind() -> None:
    message = (
        "```plan-request\n"
        "{\n"
        '  "kind": "rewrite",\n'
        '  "group": 1,\n'
        '  "defect": "Bad plan",\n'
        '  "evidence": "Does not work"\n'
        "}\n"
        "```"
    )
    assert parse_request(message) is None


def test_parse_request_returns_none_when_extra_key() -> None:
    message = (
        "```plan-request\n"
        "{\n"
        '  "kind": "path",\n'
        '  "group": 1,\n'
        '  "defect": "Missing file",\n'
        '  "evidence": "ls failed",\n'
        '  "spec": "extra_value",\n'
        '  "old": "tests/commands/test_sample.py",\n'
        '  "new": "tests/roadmap/test_sample.py"\n'
        "}\n"
        "```"
    )
    assert parse_request(message) is None


def test_judge_applies_path_request_for_tracked_file_with_same_name() -> None:
    tree = StagedTree(["src/devops_cli/sample.py", "tests/roadmap/test_sample.py"])
    request = PlanRequest(
        kind="path",
        group=1,
        defect="Wrong path",
        evidence="File is in tests/roadmap/",
        old="tests/commands/test_sample.py",
        new="tests/roadmap/test_sample.py",
    )
    outcome = judge(request, SAMPLE_TASKS, tree)
    assert isinstance(outcome, Applied)
    assert outcome.amendment == Amendment(
        group=1,
        kind="path",
        defect="Wrong path",
        evidence="File is in tests/roadmap/",
        old="tests/commands/test_sample.py",
        new="tests/roadmap/test_sample.py",
    )
    # Check that group 1 holds the new path in every code span
    assert "`tests/roadmap/test_sample.py`" in outcome.tasks_md
    assert "Changes: `tests/roadmap/test_sample.py`" in outcome.tasks_md
    assert "In `tests/roadmap/test_sample.py`" in outcome.tasks_md
    assert "Verify that `uv run pytest tests/roadmap/test_sample.py` passes" in outcome.tasks_md
    assert "Verification: `$ uv run pytest tests/roadmap/test_sample.py`" in outcome.tasks_md
    # Group 2 should be unchanged
    assert "## 2. Second group" in outcome.tasks_md
    # Criteria should keep the old path untouched
    assert "Some criterion naming `tests/commands/test_sample.py`" in outcome.tasks_md
    # Amendments section should be added before ## Workflow follow-up
    assert "## Amendments" in outcome.tasks_md
    idx_amend = outcome.tasks_md.index("## Amendments")
    idx_follow = outcome.tasks_md.index("## Workflow follow-up")
    assert idx_amend < idx_follow
    # Bullet has no checkbox and holds group, kind, defect, evidence, old, new
    amend_text = outcome.tasks_md[idx_amend:idx_follow]
    assert "- [ ]" not in amend_text
    assert "- [x]" not in amend_text
    assert "Group 1" in amend_text or "group 1" in amend_text
    assert "path" in amend_text
    assert "Wrong path" in amend_text
    assert "File is in tests/roadmap/" in amend_text
    assert "tests/commands/test_sample.py" in amend_text
    assert "tests/roadmap/test_sample.py" in amend_text


def test_judge_refuses_path_with_another_file_name() -> None:
    tree = StagedTree(["src/devops_cli/sample.py", "tests/roadmap/test_other.py"])
    request = PlanRequest(
        kind="path",
        group=1,
        defect="Wrong path",
        evidence="File does not exist",
        old="tests/commands/test_sample.py",
        new="tests/roadmap/test_other.py",
    )
    outcome = judge(request, SAMPLE_TASKS, tree)
    assert isinstance(outcome, Refused)
    assert "file name" in outcome.reason.casefold() or "name" in outcome.reason.casefold()


def test_judge_refuses_path_when_old_is_tracked() -> None:
    tree = StagedTree(
        [
            "src/devops_cli/sample.py",
            "tests/commands/test_sample.py",
            "tests/roadmap/test_sample.py",
        ]
    )
    request = PlanRequest(
        kind="path",
        group=1,
        defect="Wrong path",
        evidence="File does exist",
        old="tests/commands/test_sample.py",
        new="tests/roadmap/test_sample.py",
    )
    outcome = judge(request, SAMPLE_TASKS, tree)
    assert isinstance(outcome, Refused)
    assert outcome.reason == MESSAGES.roadmap.implement_amend_refused_path_status


def test_judge_refuses_path_when_old_is_marked_new() -> None:
    tree = StagedTree(["src/devops_cli/sample.py", "tests/roadmap/new_file.py"])
    request = PlanRequest(
        kind="path",
        group=1,
        defect="Wrong path",
        evidence="File is new",
        old="src/devops_cli/new_file.py",
        new="tests/roadmap/new_file.py",
    )
    outcome = judge(request, SAMPLE_TASKS, tree)
    assert isinstance(outcome, Refused)
    assert outcome.reason == MESSAGES.roadmap.implement_amend_refused_path_status


def test_judge_refuses_path_when_new_is_untracked() -> None:
    tree = StagedTree(["src/devops_cli/sample.py"])
    request = PlanRequest(
        kind="path",
        group=1,
        defect="Wrong path",
        evidence="File is untracked",
        old="tests/commands/test_sample.py",
        new="tests/roadmap/test_sample.py",
    )
    outcome = judge(request, SAMPLE_TASKS, tree)
    assert isinstance(outcome, Refused)
    assert outcome.reason == MESSAGES.roadmap.implement_amend_refused_path_status


def test_judge_applies_command_request_that_keeps_paths() -> None:
    tree = StagedTree(["src/devops_cli/sample.py", "tests/commands/test_sample.py"])
    request = PlanRequest(
        kind="command",
        group=1,
        defect="Wrong command",
        evidence="pytest is not allowed",
        old="uv run pytest tests/commands/test_sample.py",
        new="uv run devops ci test tests/commands/test_sample.py",
    )
    outcome = judge(request, SAMPLE_TASKS, tree)
    assert isinstance(outcome, Applied)
    assert "`uv run devops ci test tests/commands/test_sample.py`" in outcome.tasks_md
    # Ensure old command is not in group 1
    group_text = outcome.tasks_md.split("## Amendments")[0]
    assert "uv run pytest tests/commands/test_sample.py" not in group_text


def test_judge_refuses_command_that_drops_path() -> None:
    tree = StagedTree(["src/devops_cli/sample.py", "tests/commands/test_sample.py"])
    request = PlanRequest(
        kind="command",
        group=1,
        defect="Wrong command",
        evidence="Run docs check instead",
        old="uv run pytest tests/commands/test_sample.py",
        new="uv run devops docs check",
    )
    outcome = judge(request, SAMPLE_TASKS, tree)
    assert isinstance(outcome, Refused)
    assert "path" in outcome.reason.casefold()


def test_judge_refuses_command_with_unallowed_program() -> None:
    tree = StagedTree(["src/devops_cli/sample.py", "tests/commands/test_sample.py"])
    request = PlanRequest(
        kind="command",
        group=1,
        defect="Wrong command",
        evidence="Use python",
        old="uv run pytest tests/commands/test_sample.py",
        new="python -m pytest tests/commands/test_sample.py",
    )
    outcome = judge(request, SAMPLE_TASKS, tree)
    assert isinstance(outcome, Refused)
    assert outcome.reason == MESSAGES.roadmap.implement_amend_refused_command_form


def test_judge_applies_task_request_as_new_unticked_task() -> None:
    tree = StagedTree(["src/devops_cli/sample.py", "tests/roadmap/test_sample.py"])
    request = PlanRequest(
        kind="task",
        group=2,
        defect="Missing verification step",
        evidence="Need an extra task",
        new="Third task of group 2",
        verify="uv run devops ci test tests/roadmap/test_sample.py",
    )
    outcome = judge(request, SAMPLE_TASKS, tree)
    assert isinstance(outcome, Applied)
    assert "- [ ] 2.3 Third task of group 2" in outcome.tasks_md
    assert (
        "Verification: `$ uv run devops ci test tests/roadmap/test_sample.py`" in outcome.tasks_md
    )
    assert "- [ ] 2.1 First task of group 2" in outcome.tasks_md
    assert "- [ ] 2.2 Second task of group 2" in outcome.tasks_md


def test_judge_refuses_ticked_group() -> None:
    tree = StagedTree(["src/devops_cli/sample.py", "tests/roadmap/test_sample.py"])
    request = PlanRequest(
        kind="task",
        group=1,
        defect="Group is done",
        evidence="All tasks ticked",
        new="Another task",
        verify="uv run devops ci test tests/roadmap/test_sample.py",
    )
    outcome = judge(request, DONE_TASKS, tree)
    assert isinstance(outcome, Refused)
    assert outcome.reason == MESSAGES.roadmap.implement_amend_refused_done.format(group=1)


def test_judge_refuses_old_that_only_criteria_holds() -> None:
    tree = StagedTree(["src/devops_cli/sample.py", "tests/roadmap/test_sample.py"])
    request = PlanRequest(
        kind="path",
        group=1,
        defect="Wrong path in criteria",
        evidence="Missing file",
        old="tests/only_in_criteria.py",
        new="tests/roadmap/test_sample.py",
    )
    outcome = judge(request, SAMPLE_TASKS, tree)
    assert isinstance(outcome, Refused)
    assert outcome.reason == MESSAGES.roadmap.implement_amend_refused_criteria


def test_amendments_bullet_masks_secrets_and_has_no_checkbox() -> None:
    tree = StagedTree(["src/devops_cli/sample.py", "tests/roadmap/test_sample.py"])
    request = PlanRequest(
        kind="path",
        group=1,
        defect="Token found in secret ghp_ABC1234567890123456789012345678901234567",
        evidence="Evidence secret ghp_ABC1234567890123456789012345678901234567",
        old="tests/commands/test_sample.py",
        new="tests/roadmap/test_sample.py",
    )
    outcome = judge(request, SAMPLE_TASKS, tree)
    assert isinstance(outcome, Applied)
    assert "ghp_ABC1234567890123456789012345678901234567" not in outcome.tasks_md
    assert "<masked" in outcome.tasks_md
    idx = outcome.tasks_md.index("## Amendments")
    bullet_line = next(
        line for line in outcome.tasks_md[idx:].splitlines() if line.startswith("- ")
    )
    assert not bullet_line.startswith("- [")


def test_judge_refuses_scope_request() -> None:
    tree = StagedTree(["src/devops_cli/sample.py"])
    request = PlanRequest(
        kind="scope",
        group=1,
        defect="Requirement changed",
        evidence="Spec needs new feature",
    )
    outcome = judge(request, SAMPLE_TASKS, tree)
    assert isinstance(outcome, Refused)
    assert outcome.reason == MESSAGES.roadmap.implement_amend_refused_scope
