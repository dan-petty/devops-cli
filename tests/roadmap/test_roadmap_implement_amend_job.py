"""`devops roadmap implement`: replays of plan amendments in the implement job (#3057)."""

from __future__ import annotations

import pytest

from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    BRANCH,
    CHANGE,
    CHANGE_DIR,
    PULL,
    SHOUT,
    SHOUT_DOC,
    STAGE_NAME,
    JobWorld,
    branch_of,
    write_change,
)
from tests.support.roadmap_stage import StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store")

WRONG_PATH_TASKS = """\
# Tasks

## 1. The first group

- [ ] Add `src/devops_cli/shout.py`
  - Verification: `uv run devops ci test tests/commands/test_shout.py`

## 2. The second group

- [ ] Document the function in `CONTEXT.md`
  - Verification: `uv run devops docs check`
"""

COMMAND_TASKS = """\
# Tasks

## 1. The first group

- [ ] Add `src/devops_cli/shout.py`
  - Verification: `uv run pytest tests/test_shout.py`

## 2. The second group

- [ ] Document the function in `CONTEXT.md`
  - Verification: `uv run devops docs check`
"""

TASKS_PATH = f"{CHANGE_DIR}/tasks.md"


def _item(world: JobWorld, number: int = 1) -> tuple[str | None, dict[str, str | None]]:
    held = world.store.item(number)
    assert held is not None
    return held.status, {str(key): value for key, value in held.job_record.items()}


def set_staged_tasks(repo: StageRepo, tasks: str, number: int = 1) -> None:
    branch = branch_of(number)
    repo.git("checkout", "-B", branch, f"origin/{branch}")
    write_change(repo.clone, tasks, number)
    repo.git("add", "-A")
    repo.git("-c", f"user.name={STAGE_NAME}", "commit", "-q", "--amend", "-m", "fix(roadmap): plan")
    repo.git("push", "-q", "--force", "origin", branch)
    repo.git("switch", "-q", "main")
    repo.git("branch", "-q", "-D", branch)


def test_wrong_test_path_ends_in_delivered_pr_with_corrected_path(
    job_world: JobWorld,
) -> None:
    job_world.repo.track({"tests/test_shout.py": "# test shout\n"})
    set_staged_tasks(job_world.repo, WRONG_PATH_TASKS)

    path_request = (
        "The test path is wrong.\n\n"
        "```plan-request\n"
        "{\n"
        '  "kind": "path",\n'
        '  "group": 1,\n'
        '  "defect": "tests/commands/test_shout.py does not exist",\n'
        '  "evidence": "tests/test_shout.py is the tracked file",\n'
        '  "old": "tests/commands/test_shout.py",\n'
        '  "new": "tests/test_shout.py"\n'
        "}\n"
        "```"
    )

    ticked_g1 = WRONG_PATH_TASKS.replace("commands/test_shout.py", "test_shout.py").replace(
        "- [ ] Add", "- [x] Add"
    )
    ticked_g2 = ticked_g1.replace("- [ ] Document", "- [x] Document")

    script = ModelScript(
        # Group 1 turn 1: ask for amendment
        say(path_request),
        # Group 1 turn 2 (after amendment): do group 1
        tool_calls(
            ("write_file", {"path": "src/devops_cli/shout.py", "content": SHOUT}),
            ("write_file", {"path": TASKS_PATH, "content": ticked_g1}),
        ),
        say("Group 1 is done."),
        # Group 2: do group 2
        tool_calls(
            ("write_file", {"path": "CONTEXT.md", "content": SHOUT_DOC}),
            ("write_file", {"path": TASKS_PATH, "content": ticked_g2}),
        ),
        say("Group 2 is done."),
    )

    applied = job_world.run(script)
    assert (applied.ready, applied.stopped, applied.failed) == ((1,), (), ())
    assert job_world.origin_log() == [
        "fix(roadmap): plan",
        "docs(openspec): amend the plan of group 1 (#1)",
        "fix(roadmap): The first group (#1)",
        "fix(roadmap): The second group (#1)",
        "docs: regenerate the documentation (#1)",
        "docs(openspec): archive the change (#1)",
    ]

    archived_tasks = job_world.repo.origin_git(
        "show", f"{BRANCH}:openspec/changes/archive/2026-10-29-{CHANGE}/tasks.md"
    )
    assert "tests/test_shout.py" in archived_tasks
    assert "## Amendments" in archived_tasks
    assert "tests/commands/test_shout.py" in archived_tasks

    comments = job_world.sent("POST", f"issues/{PULL}/comments")
    assert len(comments) >= 1
    comment_body = comments[0]["body"]
    assert "path" in comment_body
    assert "tests/commands/test_shout.py" in comment_body
    assert "tests/test_shout.py" in comment_body
    assert "tests/test_shout.py is the tracked file" in comment_body


def test_command_request_and_task_request_give_amendment(
    job_world: JobWorld,
) -> None:
    job_world.repo.track({"tests/test_shout.py": "# test shout\n"})
    set_staged_tasks(job_world.repo, COMMAND_TASKS)

    cmd_request = (
        "The verification command is wrong.\n\n"
        "```plan-request\n"
        "{\n"
        '  "kind": "command",\n'
        '  "group": 1,\n'
        '  "defect": "pytest is not allowed",\n'
        '  "evidence": "Verification command must use devops ci test",\n'
        '  "old": "uv run pytest tests/test_shout.py",\n'
        '  "new": "uv run devops ci test tests/test_shout.py"\n'
        "}\n"
        "```"
    )

    ticked_g1 = COMMAND_TASKS.replace("pytest", "devops ci test").replace("- [ ] Add", "- [x] Add")
    ticked_g2 = ticked_g1.replace("- [ ] Document", "- [x] Document")

    script = ModelScript(
        say(cmd_request),
        tool_calls(
            ("write_file", {"path": "src/devops_cli/shout.py", "content": SHOUT}),
            ("write_file", {"path": TASKS_PATH, "content": ticked_g1}),
        ),
        say("Group 1 is done."),
        tool_calls(
            ("write_file", {"path": "CONTEXT.md", "content": SHOUT_DOC}),
            ("write_file", {"path": TASKS_PATH, "content": ticked_g2}),
        ),
        say("Group 2 is done."),
    )

    applied = job_world.run(script)
    assert (applied.ready, applied.stopped, applied.failed) == ((1,), (), ())
    assert "docs(openspec): amend the plan of group 1 (#1)" in job_world.origin_log()


def test_second_request_for_same_group_stops_item_blocked(
    job_world: JobWorld,
) -> None:
    job_world.repo.track({"tests/test_shout.py": "# test shout\n"})
    set_staged_tasks(job_world.repo, WRONG_PATH_TASKS)

    path_request = (
        "```plan-request\n"
        "{\n"
        '  "kind": "path",\n'
        '  "group": 1,\n'
        '  "defect": "first defect",\n'
        '  "evidence": "evidence 1",\n'
        '  "old": "tests/commands/test_shout.py",\n'
        '  "new": "tests/test_shout.py"\n'
        "}\n"
        "```"
    )
    second_request = (
        "```plan-request\n"
        "{\n"
        '  "kind": "path",\n'
        '  "group": 1,\n'
        '  "defect": "second defect",\n'
        '  "evidence": "evidence 2",\n'
        '  "old": "tests/test_shout.py",\n'
        '  "new": "tests/commands/test_shout.py"\n'
        "}\n"
        "```"
    )

    script = ModelScript(
        say(path_request),
        say(second_request),
    )

    applied = job_world.run(script)
    assert (applied.ready, applied.stopped, applied.failed) == ((), (1,), ())
    status, record = _item(job_world)
    assert status == "Blocked"
    assert record.get("implement.failure") == "plan_defect"
    stop_comment = job_world.issue_comments()[-1]
    assert "second defect" in stop_comment
    assert "Action left: `wait`: wait for a person." in stop_comment


def test_stop_with_no_request_stops_as_before(
    job_world: JobWorld,
) -> None:
    script = ModelScript(
        say("I cannot complete this group."),
    )

    applied = job_world.run(script)
    assert (applied.ready, applied.stopped, applied.failed) == ((), (1,), ())
    assert "docs(openspec): amend the plan" not in str(job_world.origin_log())
    status, _ = _item(job_world)
    assert status == "Blocked"


def test_stop_after_amendment_puts_line_in_pr_comment(
    job_world: JobWorld,
) -> None:
    job_world.repo.track({"tests/test_shout.py": "# test shout\n"})
    set_staged_tasks(job_world.repo, WRONG_PATH_TASKS)

    path_request = (
        "```plan-request\n"
        "{\n"
        '  "kind": "path",\n'
        '  "group": 1,\n'
        '  "defect": "tests/commands/test_shout.py does not exist",\n'
        '  "evidence": "tests/test_shout.py is the tracked file",\n'
        '  "old": "tests/commands/test_shout.py",\n'
        '  "new": "tests/test_shout.py"\n'
        "}\n"
        "```"
    )

    ticked_g1 = WRONG_PATH_TASKS.replace("commands/test_shout.py", "test_shout.py").replace(
        "- [ ] Add", "- [x] Add"
    )

    script = ModelScript(
        # Group 1 turn 1: amendment
        say(path_request),
        # Group 1 turn 2: succeed group 1
        tool_calls(
            ("write_file", {"path": "src/devops_cli/shout.py", "content": SHOUT}),
            ("write_file", {"path": TASKS_PATH, "content": ticked_g1}),
        ),
        say("Group 1 is done."),
        # Group 2: stop with no request
        say("I cannot do group 2."),
    )

    applied = job_world.run(script)
    assert (applied.ready, applied.stopped, applied.failed) == ((), (1,), ())
    status, _ = _item(job_world)
    assert status == "Blocked"

    comments = job_world.sent("POST", f"issues/{PULL}/comments")
    assert len(comments) >= 1
    assert any("tests/test_shout.py is the tracked file" in c.get("body", "") for c in comments)


def test_amended_group_that_stops_again_names_amend_taken_and_wait_left(
    job_world: JobWorld,
) -> None:
    job_world.repo.track({"tests/test_shout.py": "# test shout\n"})
    set_staged_tasks(job_world.repo, WRONG_PATH_TASKS)

    path_request = (
        "```plan-request\n"
        "{\n"
        '  "kind": "path",\n'
        '  "group": 1,\n'
        '  "defect": "tests/commands/test_shout.py does not exist",\n'
        '  "evidence": "tests/test_shout.py is the tracked file",\n'
        '  "old": "tests/commands/test_shout.py",\n'
        '  "new": "tests/test_shout.py"\n'
        "}\n"
        "```"
    )

    script = ModelScript(
        # Group 1 turn 1: amendment
        say(path_request),
        # Group 1 turn 2 (after amendment applied): changes no file again
        say("I cannot implement this group."),
    )

    applied = job_world.run(script)
    assert (applied.ready, applied.stopped, applied.failed) == ((), (1,), ())
    status, _ = _item(job_world)
    assert status == "Blocked"

    comments = job_world.issue_comments()
    assert len(comments) >= 1
    stop_comment = comments[-1]
    assert "Failure class: `plan_defect`." in stop_comment
    assert "Action taken: `amend`." in stop_comment
    assert "Action left: `wait`: wait for a person." in stop_comment


def test_false_premise_on_planned_item_returns_to_new(
    planned_world: JobWorld,
) -> None:
    premise_request = (
        "```plan-request\n"
        "{\n"
        '  "kind": "premise",\n'
        '  "group": 1,\n'
        '  "defect": "the premise is false",\n'
        '  "evidence": "the feature was already removed in #1234"\n'
        "}\n"
        "```"
    )
    script = ModelScript(say(premise_request))

    applied = planned_world.run(script)
    assert (applied.ready, applied.stopped, applied.failed) == ((), (), ())

    status, record = _item(planned_world)
    assert status == "New"
    assert record.get("implement.stopped") is None
    assert record.get("implement.group") is None
    assert record.get("implement.sha") is None
    assert record.get("implement.branch") is None
    assert record.get("implement.pr") is None

    comments = planned_world.issue_comments()
    assert len(comments) >= 1
    assert "the feature was already removed in #1234" in comments[-1]
    assert planned_world.repo.origin_git("branch", "--list", BRANCH) == ""
    assert planned_world.repo.git("worktree", "list").count("\n") == 0


def test_false_premise_on_staged_item_after_group_1_leaves_old_tip_and_clears_group(
    job_world: JobWorld,
) -> None:
    before_tip = job_world.repo.origin_git("rev-parse", BRANCH)

    ticked_g1 = WRONG_PATH_TASKS.replace("- [ ] Add", "- [x] Add")
    premise_request = (
        "```plan-request\n"
        "{\n"
        '  "kind": "premise",\n'
        '  "group": 2,\n'
        '  "defect": "the premise is false",\n'
        '  "evidence": "upstream removed API"\n'
        "}\n"
        "```"
    )

    script = ModelScript(
        # Group 1 passes
        tool_calls(
            ("write_file", {"path": "src/devops_cli/shout.py", "content": SHOUT}),
            ("write_file", {"path": TASKS_PATH, "content": ticked_g1}),
        ),
        say("Group 1 is done."),
        # Group 2 stops on premise
        say(premise_request),
    )

    applied = job_world.run(script)
    assert (applied.ready, applied.stopped, applied.failed) == ((), (), ())

    assert job_world.repo.origin_git("rev-parse", BRANCH) == before_tip
    status, record = _item(job_world)
    assert status == "New"
    assert record.get("implement.group") is None
    assert record.get("implement.stopped") is None


def test_premise_request_with_empty_evidence_stops_as_question_with_plan_defect(
    job_world: JobWorld,
) -> None:
    request = (
        "```plan-request\n"
        "{\n"
        '  "kind": "premise",\n'
        '  "group": 1,\n'
        '  "defect": "the premise is false",\n'
        '  "evidence": ""\n'
        "}\n"
        "```"
    )
    script = ModelScript(say(request))

    applied = job_world.run(script)
    assert (applied.ready, applied.stopped, applied.failed) == ((), (1,), ())

    status, record = _item(job_world)
    assert status == "Blocked"
    assert record.get("implement.failure") == "plan_defect"
    stop_comment = job_world.issue_comments()[-1]
    assert "Failure class: `plan_defect`." in stop_comment
    assert "Action left: `wait`: wait for a person." in stop_comment


def test_scope_request_stops_as_question_with_defect_and_evidence(
    job_world: JobWorld,
) -> None:
    request = (
        "```plan-request\n"
        "{\n"
        '  "kind": "scope",\n'
        '  "group": 1,\n'
        '  "defect": "requirement 2 is wrong",\n'
        '  "evidence": "spec was changed upstream"\n'
        "}\n"
        "```"
    )
    script = ModelScript(say(request))

    applied = job_world.run(script)
    assert (applied.ready, applied.stopped, applied.failed) == ((), (1,), ())

    status, record = _item(job_world)
    assert status == "Blocked"
    assert record.get("implement.failure") == "plan_defect"
    stop_comment = job_world.issue_comments()[-1]
    assert "requirement 2 is wrong" in stop_comment
    assert "spec was changed upstream" in stop_comment
    assert "Action left: `wait`: wait for a person." in stop_comment


def test_path_request_with_another_file_name_stops_as_question_with_rule(
    job_world: JobWorld,
) -> None:
    job_world.repo.track({"tests/test_other.py": "# test other\n"})
    set_staged_tasks(job_world.repo, WRONG_PATH_TASKS)

    request = (
        "```plan-request\n"
        "{\n"
        '  "kind": "path",\n'
        '  "group": 1,\n'
        '  "defect": "wrong path",\n'
        '  "evidence": "tests/test_other.py exists",\n'
        '  "old": "tests/commands/test_shout.py",\n'
        '  "new": "tests/test_other.py"\n'
        "}\n"
        "```"
    )
    script = ModelScript(say(request))

    applied = job_world.run(script)
    assert (applied.ready, applied.stopped, applied.failed) == ((), (1,), ())

    status, record = _item(job_world)
    assert status == "Blocked"
    assert record.get("implement.failure") == "plan_defect"
    stop_comment = job_world.issue_comments()[-1]
    assert "same file name" in stop_comment.lower()
    assert "Action left: `wait`: wait for a person." in stop_comment


def test_path_request_whose_old_is_only_in_criteria_changes_nothing(
    job_world: JobWorld,
) -> None:
    criteria_tasks = """\
# Tasks

## 1. The first group

- [ ] Add `src/devops_cli/shout.py`
  - Verification: `uv run devops ci test tests/test_shout.py`

## Criteria

- Some criterion naming `tests/criteria_only.py`.
"""
    set_staged_tasks(job_world.repo, criteria_tasks)

    request = (
        "```plan-request\n"
        "{\n"
        '  "kind": "path",\n'
        '  "group": 1,\n'
        '  "defect": "wrong path in criteria",\n'
        '  "evidence": "tests/test_shout.py exists",\n'
        '  "old": "tests/criteria_only.py",\n'
        '  "new": "tests/test_shout.py"\n'
        "}\n"
        "```"
    )
    script = ModelScript(say(request))

    applied = job_world.run(script)
    assert (applied.ready, applied.stopped, applied.failed) == ((), (1,), ())

    status, record = _item(job_world)
    assert status == "Blocked"
    assert record.get("implement.failure") == "plan_defect"
    stop_comment = job_world.issue_comments()[-1]
    assert "criteria" in stop_comment.lower()
    assert "Action left: `wait`: wait for a person." in stop_comment
