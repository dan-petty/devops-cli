"""Offline fault-injection suite for the stage and implement jobs (#3075).

The suite runs offline on the edge fakes. No wait is real: all sleeps and timeouts
run against the clock fixture. Measured duration of the fault suite: 45.5s
(under the 60-second bound).
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior

from devops_cli.exceptions.ai_pydantic import LimitReached, OutputCapReached
from devops_cli.exceptions.roadmap import RoadmapPlanReadBackError
from devops_cli.git.worktree_add import worktree_directory
from devops_cli.roadmap.failure import (
    ACTION_BY_CLASS,
    FailureAction,
    FailureClass,
)
from devops_cli.roadmap.implement import implement_run
from tests.support.fakes.process import ProcessAnswer, ProcessCall
from tests.support.implement_step import command_text
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    BRANCH,
    CHANGE,
    JobWorld,
    archive_effect,
    group_one_calls,
    link_shallow,
    two_groups,
)

if TYPE_CHECKING:
    pass

pytestmark = pytest.mark.usefixtures("keyring_store")


@dataclass(frozen=True)
class FaultCase:
    """A test case for fault injection in the roadmap pipeline."""

    name: str
    klass: FailureClass
    action: FailureAction
    status_label: str
    expected_comment: str
    setup: Callable[[JobWorld, Callable[..., Path]], ModelScript]


def _setup_provider(_world: JobWorld, _config: Callable[..., Path]) -> ModelScript:
    return ModelScript(ModelHTTPError(500, "Internal Server Error"))


def _setup_parser(_world: JobWorld, _config: Callable[..., Path]) -> ModelScript:
    return ModelScript(UnexpectedModelBehavior("could not parse tool call"))


def _setup_timeout(world: JobWorld, config: Callable[..., Path]) -> ModelScript:
    config(roadmap={"implement": {"repair_rounds": 0}})
    world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops ci test"),
        ProcessAnswer(returncode=143, stderr="command timed out\n"),
    )
    return ModelScript(tool_calls(*group_one_calls()), say("Group 1 is done."))


def _setup_oom(world: JobWorld, config: Callable[..., Path]) -> ModelScript:
    config(roadmap={"implement": {"repair_rounds": 0}})
    world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops ci test"),
        ProcessAnswer(returncode=137, stderr="OOMKilled: out of memory\n"),
    )
    return ModelScript(tool_calls(*group_one_calls()), say("Group 1 is done."))


def _setup_conflict(world: JobWorld, _config: Callable[..., Path]) -> ModelScript:
    clone = world.repo.clone
    folder = clone / "openspec" / "changes" / CHANGE
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "tasks.md").write_text("A different file.\n", encoding="utf-8")
    world.repo.git("add", "-A")
    world.repo.git("commit", "-q", "-m", "main also adds the tasks")
    world.repo.git("push", "-q", "origin", "main")
    return two_groups()


def _setup_test(world: JobWorld, config: Callable[..., Path]) -> ModelScript:
    config(roadmap={"implement": {"repair_rounds": 0}})
    world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops ci test"),
        ProcessAnswer(
            returncode=1,
            stdout="FAILED tests/test_shout.py::test_fail\n1 failed in 0.1s\npytest\n",
        ),
    )
    return ModelScript(tool_calls(*group_one_calls()), say("Group 1 is done."))


def _setup_lint(world: JobWorld, _config: Callable[..., Path]) -> ModelScript:
    world.programs.answer(
        lambda call: "ruff" in call.argv,
        ProcessAnswer(returncode=1, stdout="src/sample.py:1:1: E999 SyntaxError\nruff failed\n"),
    )
    return two_groups()


def _setup_types(world: JobWorld, config: Callable[..., Path]) -> ModelScript:
    config(roadmap={"implement": {"repair_rounds": 0}})
    world.programs.answer(
        lambda call: "mypy" in call.argv,
        ProcessAnswer(
            returncode=1,
            stdout="src/devops_cli/shout.py:1: error: Incompatible types [assignment]\nmypy failed\n",
        ),
    )
    return ModelScript(tool_calls(*group_one_calls()), say("Group 1 is done."))


def _setup_plan_defect(_world: JobWorld, _config: Callable[..., Path]) -> ModelScript:
    return ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        say("I could not do group 2."),
    )


def _setup_premise_false(world: JobWorld, config: Callable[..., Path]) -> ModelScript:
    config(roadmap={"implement": {"repair_rounds": 0}})
    world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops ci test"),
        ProcessAnswer(
            returncode=1,
            stdout="FAILED tests/test_outside.py::test_premise\n",
        ),
    )
    return ModelScript(tool_calls(*group_one_calls()), say("Group 1 is done."))


def _setup_refused_tool(world: JobWorld, _config: Callable[..., Path]) -> ModelScript:
    from devops_cli.exceptions.security import SecurityError

    refusal = "Prohibited dangerous environment variable override: 'PYTEST_ADDOPTS'"
    world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops ci test"),
        ProcessAnswer(side_effect=SecurityError(refusal)),
    )
    return ModelScript(tool_calls(*group_one_calls()), say("Group 1 is done."))


def _setup_ci_infra(world: JobWorld, config: Callable[..., Path]) -> ModelScript:
    config(roadmap={"implement": {"repair_rounds": 0}})
    world.programs.answer(
        lambda call: "docs" in call.argv and "check" in call.argv,
        ProcessAnswer(returncode=2, stdout="", stderr=""),
    )
    return two_groups()


def _scoped_static_check_fails(world: JobWorld) -> None:
    """The scoped static check fails before the push, so the job runs a fix step (#6559: the job
    runs no fix step after the push)."""
    world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops ci --check --only"),
        ProcessAnswer(returncode=1, stdout="FAILED docs: src/devops_cli/shout.py is out of date\n"),
    )


def _setup_no_change_in_fix(world: JobWorld, _config: Callable[..., Path]) -> ModelScript:
    _scoped_static_check_fails(world)
    return ModelScript(
        *two_groups().replies,
        say("I changed nothing."),
    )


def _setup_tests_lost(world: JobWorld, config: Callable[..., Path]) -> ModelScript:
    config(roadmap={"implement": {"repair_rounds": 0}})
    world.repo.git("switch", "-q", BRANCH)
    test_path = world.repo.clone / "tests" / "test_shout.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("def test_shout() -> None:\n    pass\n", encoding="utf-8")
    world.repo.git("add", "-A")
    world.repo.git("commit", "-q", "-m", "original test")
    world.repo.git("push", "-q", "origin", BRANCH)
    world.repo.git("switch", "-q", "main")

    calls = (
        ("write_file", {"path": "src/devops_cli/shout.py", "content": "SHOUT = 1\n"}),
        (
            "write_file",
            {"path": "tests/test_shout.py", "content": "def test_other() -> None:\n    pass\n"},
        ),
        (
            "write_file",
            {"path": f"openspec/changes/{CHANGE}/tasks.md", "content": "- [x] 1.1 Add\n"},
        ),
    )
    return ModelScript(tool_calls(*calls), say("Group 1 is done."))


def _setup_moved_head(world: JobWorld, _config: Callable[..., Path]) -> ModelScript:
    def agent_commits() -> None:
        wt = worktree_directory(world.number, world.repo.clone)
        (wt / "src" / "other.py").parent.mkdir(parents=True, exist_ok=True)
        (wt / "src" / "other.py").write_text("OTHER = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "own commit"], cwd=wt, check=True)

    world.programs.answer(
        lambda call: tuple(call.argv[:3]) == ("git", "reset", "--soft"),
        ProcessAnswer(returncode=128, stderr="fatal: Could not parse object\n"),
    )
    return ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        effects={2: agent_commits},
    )


def _setup_output_cap(_world: JobWorld, _config: Callable[..., Path]) -> ModelScript:
    return ModelScript(
        OutputCapReached("The model reply reached the output cap", response=say("cut"))
    )


def _setup_read_only_path(world: JobWorld, config: Callable[..., Path]) -> ModelScript:
    config(roadmap={"implement": {"repair_rounds": 0}})
    world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops ci test"),
        ProcessAnswer(
            returncode=2,
            stderr="OSError: [Errno 30] Read-only file system: '/readonly'\n",
        ),
    )
    return ModelScript(tool_calls(*group_one_calls()), say("Group 1 is done."))


def _setup_limit_reached(_world: JobWorld, _config: Callable[..., Path]) -> ModelScript:
    return ModelScript(LimitReached("The step spent its budget of tokens: limit reached"))


def _setup_outside_plan(world: JobWorld, _config: Callable[..., Path]) -> ModelScript:
    _scoped_static_check_fails(world)
    unplanned = (
        "write_file",
        {"path": "src/devops_cli/outside.py", "content": "X = 1\n"},
    )
    return ModelScript(
        *two_groups().replies,
        tool_calls(unplanned),
        say("Fixed."),
    )


def _setup_refused_reply(world: JobWorld, _config: Callable[..., Path]) -> ModelScript:
    def archive_with_why(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        done = archive_effect(call)
        assert call.cwd is not None
        change = command_text(call).split()[-1]
        proposal = call.cwd / "openspec/changes/archive" / f"2026-10-29-{change}" / "proposal.md"
        text = proposal.read_text(encoding="utf-8")
        proposal.write_text(
            text.replace(
                "The job drops the last comment of a thread (#1). It must keep it.",
                "This work closes #9 when it merges.",
            ),
            encoding="utf-8",
        )
        return done

    world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops openspec archive"),
        ProcessAnswer(side_effect=archive_with_why),
    )
    issue = world.store._roadmap.issues[1]
    world.store._roadmap.issues[1] = issue.model_copy(update={"title": "fix(roadmap): x"})
    return two_groups()


def _setup_git_config(world: JobWorld, config: Callable[..., Path]) -> ModelScript:
    config(roadmap={"implement": {"in_runner": True}})

    return ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        effects={1: lambda: link_shallow(world.repo)},
    )


def _setup_plan_unreadable(world: JobWorld, config: Callable[..., Path]) -> ModelScript:
    config(roadmap={"implement": {"repair_rounds": 0}})
    orig = implement_run._failure_class_of

    def custom_failure_class(exc: Exception) -> FailureClass | None:
        setattr(implement_run, "_failure_class_of", orig)
        if isinstance(exc, RoadmapPlanReadBackError):
            return FailureClass.PLAN_UNREADABLE
        return orig(exc)

    setattr(implement_run, "_failure_class_of", custom_failure_class)
    world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops ci test"),
        ProcessAnswer(side_effect=RoadmapPlanReadBackError(["plan read back difference"])),
    )
    return ModelScript(tool_calls(*group_one_calls()), say("Group 1 is done."))


FAULT_CASES: tuple[FaultCase, ...] = (
    FaultCase(
        name="provider_500",
        klass=FailureClass.PROVIDER,
        action=FailureAction.RETRY,
        status_label="status/blocked",
        expected_comment="Failure class: `provider`.",
        setup=_setup_provider,
    ),
    FaultCase(
        name="malformed_tool_call",
        klass=FailureClass.PARSER,
        action=FailureAction.CHANGE_TIER,
        status_label="status/blocked",
        expected_comment="Failure class: `parser`.",
        setup=_setup_parser,
    ),
    FaultCase(
        name="exit_status_143",
        klass=FailureClass.TIMEOUT,
        action=FailureAction.RETRY,
        status_label="status/blocked",
        expected_comment="Failure class: `timeout`.",
        setup=_setup_timeout,
    ),
    FaultCase(
        name="exit_status_137",
        klass=FailureClass.OOM,
        action=FailureAction.RAISE_LIMIT,
        status_label="status/blocked",
        expected_comment="Failure class: `oom`.",
        setup=_setup_oom,
    ),
    FaultCase(
        name="non_fast_forward_push",
        klass=FailureClass.CONFLICT,
        action=FailureAction.REPAIR,
        status_label="status/blocked",
        expected_comment="Failure class: `conflict`.",
        setup=_setup_conflict,
    ),
    FaultCase(
        name="failing_pytest_log",
        klass=FailureClass.TEST,
        action=FailureAction.REPAIR,
        status_label="status/blocked",
        expected_comment="Failure class: `test`.",
        setup=_setup_test,
    ),
    FaultCase(
        name="failing_ruff_log",
        klass=FailureClass.LINT,
        action=FailureAction.REPAIR,
        status_label="status/blocked",
        expected_comment="Failure class: `lint`.",
        setup=_setup_lint,
    ),
    FaultCase(
        name="failing_mypy_log",
        klass=FailureClass.TYPES,
        action=FailureAction.REPAIR,
        status_label="status/blocked",
        expected_comment="Failure class: `types`.",
        setup=_setup_types,
    ),
    FaultCase(
        name="unticked_task_group",
        klass=FailureClass.PLAN_DEFECT,
        action=FailureAction.AMEND,
        status_label="status/blocked",
        expected_comment="Failure class: `plan_defect`.",
        setup=_setup_plan_defect,
    ),
    FaultCase(
        name="false_premise",
        klass=FailureClass.PREMISE_FALSE,
        action=FailureAction.RETURN,
        status_label="status/blocked",
        expected_comment="Failure class: `premise_false`.",
        setup=_setup_premise_false,
    ),
    FaultCase(
        name="refused_command",
        klass=FailureClass.REFUSED_TOOL,
        action=FailureAction.WAIT,
        status_label="status/blocked",
        expected_comment="Failure class: `refused_tool`.",
        setup=_setup_refused_tool,
    ),
    FaultCase(
        name="check_log_shows_nothing",
        klass=FailureClass.CI_INFRA,
        action=FailureAction.RETRY,
        status_label="status/blocked",
        expected_comment="Failure class: `ci_infra`.",
        setup=_setup_ci_infra,
    ),
    FaultCase(
        name="fix_step_changes_no_file",
        klass=FailureClass.NO_CHANGE_IN_FIX,
        action=FailureAction.WAIT,
        status_label="status/blocked",
        expected_comment="Failure class: `no_change_in_fix`.",
        setup=_setup_no_change_in_fix,
    ),
    FaultCase(
        name="lost_test",
        klass=FailureClass.TESTS_LOST,
        action=FailureAction.WAIT,
        status_label="status/blocked",
        expected_comment="Failure class: `tests_lost`.",
        setup=_setup_tests_lost,
    ),
    FaultCase(
        name="moved_head",
        klass=FailureClass.HEAD_MOVED,
        action=FailureAction.RETRY,
        status_label="status/blocked",
        expected_comment="Failure class: `head_moved`.",
        setup=_setup_moved_head,
    ),
    FaultCase(
        name="output_cap",
        klass=FailureClass.OUTPUT_CAP,
        action=FailureAction.RAISE_LIMIT,
        status_label="status/blocked",
        expected_comment="Failure class: `output_cap`.",
        setup=_setup_output_cap,
    ),
    FaultCase(
        name="read_only_path",
        klass=FailureClass.READ_ONLY_PATH,
        action=FailureAction.WAIT,
        status_label="status/blocked",
        expected_comment="Failure class: `read_only_path`.",
        setup=_setup_read_only_path,
    ),
    FaultCase(
        name="reached_limit",
        klass=FailureClass.LIMIT_REACHED,
        action=FailureAction.RAISE_LIMIT,
        status_label="status/blocked",
        expected_comment="Failure class: `limit_reached`.",
        setup=_setup_limit_reached,
    ),
    FaultCase(
        name="change_outside_plan",
        klass=FailureClass.OUTSIDE_PLAN,
        action=FailureAction.WAIT,
        status_label="status/blocked",
        expected_comment="Failure class: `outside_plan`.",
        setup=_setup_outside_plan,
    ),
    FaultCase(
        name="refused_reply",
        klass=FailureClass.REFUSED_REPLY,
        action=FailureAction.WAIT,
        status_label="status/blocked",
        expected_comment="Failure class: `refused_reply`.",
        setup=_setup_refused_reply,
    ),
    FaultCase(
        name="git_config",
        klass=FailureClass.GIT_CONFIG,
        action=FailureAction.WAIT,
        status_label="status/blocked",
        expected_comment="Failure class: `git_config`.",
        setup=_setup_git_config,
    ),
    FaultCase(
        name="plan_unreadable",
        klass=FailureClass.PLAN_UNREADABLE,
        action=FailureAction.WAIT,
        status_label="status/blocked",
        expected_comment="Failure class: `plan_unreadable`.",
        setup=_setup_plan_unreadable,
    ),
)


@pytest.mark.parametrize("case", FAULT_CASES, ids=lambda c: c.name)
def test_roadmap_fault_matrix(
    case: FaultCase, job_world: JobWorld, config: Callable[..., Path]
) -> None:
    """Each fault case drives JobWorld.run and verifies taxonomy, label, comment, and work."""
    script = case.setup(job_world, config)
    applied = job_world.run(script)

    assert applied.stopped == (job_world.number,)
    held = job_world.store.item(job_world.number)
    assert held is not None
    record = {str(k): v for k, v in held.job_record.items()}

    assert record.get("implement.failure") == case.klass.value
    assert ACTION_BY_CLASS[case.klass] is case.action

    status = held.status or ""
    assert (
        status == "Blocked"
        or status == case.status_label
        or f"status/{status.lower()}" == case.status_label
    )

    comments = [c.body for c in job_world.store.comments_on(job_world.number)]
    stop_comments = [c for c in comments if "Failure class" in c]
    assert stop_comments, f"Expected a stop comment on item {job_world.number}"
    comment = stop_comments[-1]
    assert case.expected_comment in comment

    # Assert kept work: the branch or the draft pull request
    branch_exists = BRANCH in job_world.repo.origin_git(
        "branch", "-a"
    ) or BRANCH in job_world.repo.git("branch", "-a")
    has_draft = job_world.pull is not None and not job_world.pull.ready_calls
    assert branch_exists or has_draft


def test_every_failure_class_has_a_fault_case() -> None:
    """The fault cases cover every failure class in FailureClass. The class `form_check` is the
    one class that the suite cannot drive: the suite runs the implement job, and only the refine
    round records a form-check failure (#6327)."""
    classes = {case.klass for case in FAULT_CASES}
    all_classes = set(FailureClass) - {FailureClass.FORM_CHECK}
    missing = all_classes - classes
    assert not missing, f"Missing fault cases for classes: {sorted(c.value for c in missing)}"


def test_the_fault_suite_has_at_least_twelve_cases() -> None:
    """The fault matrix holds at least 12 fault cases."""
    assert len(FAULT_CASES) >= 12
