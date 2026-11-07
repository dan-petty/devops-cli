"""`devops roadmap implement`: split an implement group over the model window (#3057)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS
from devops_cli.exceptions.roadmap import OverWindowError, RoadmapImplementError
from devops_cli.roadmap.implement.implement_step import build_step_inputs
from devops_cli.roadmap.stage.stage_change import GroupKind, StageGroup, StageSplit
from devops_cli.roadmap.stage.stage_criteria import StageCriterion
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    BRANCH,
    CHANGE,
    CHANGE_DIR,
    PULL,
    SHOUT,
    STAGE_NAME,
    JobWorld,
    branch_of,
    write_change,
)
from tests.support.roadmap_stage import StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store")

WINDOW = 80_000
TASKS_PATH = f"{CHANGE_DIR}/tasks.md"

THREE_CRITERIA_BODY = """\
## Problem or Motivation

The job needs resplit.

## Acceptance criteria

- First criterion.
- Second criterion.
- Third criterion.
"""

THREE_GROUPS_TASKS = """\
# Tasks

## 1. The first group

Reads: `CONTEXT.md`. Changes: `src/devops_cli/shout.py` (new).

- [ ] 1.1 First task
  - Verification: `$ uv run devops ci test tests/test_shout.py`

## 2. The second group

Reads: `src/devops_cli/heavy_0.py`, `src/devops_cli/heavy_1.py`, `src/devops_cli/heavy_2.py`, `src/devops_cli/heavy_3.py`, `src/devops_cli/heavy_4.py`, `src/devops_cli/heavy_5.py`. Changes: `src/devops_cli/shout.py`.

- [ ] 2.1 Heavy task reading `src/devops_cli/heavy_0.py`, `src/devops_cli/heavy_1.py`, `src/devops_cli/heavy_2.py`, `src/devops_cli/heavy_3.py`, `src/devops_cli/heavy_4.py`, `src/devops_cli/heavy_5.py`
  - Verification: `$ uv run devops ci test tests/test_shout.py`

## 3. The third group

Reads: `src/devops_cli/shout.py`. Changes: `CONTEXT.md`.

- [ ] 3.1 Document the function in `CONTEXT.md`
  - Verification: `$ uv run devops docs check`

## Criteria

- Group 1: First criterion.
- Group 2: Second criterion.
- Group 3: Third criterion.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
"""


class _SplitClientFake:
    def __init__(self, *replies: StageSplit) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, str, type[BaseModel], int]] = []

    def chat_structured(
        self,
        prompt: str,
        content: str,
        response_model: type[BaseModel],
        *,
        max_retries: int = 1,
    ) -> BaseModel:
        self.calls.append((prompt, content, response_model, max_retries))
        return self.replies.pop(0)


def _item(world: JobWorld, number: int = 1) -> tuple[str | None, dict[str, str | None]]:
    held = world.store.item(number)
    assert held is not None
    return held.status, {str(key): value for key, value in held.job_record.items()}


def set_staged_tasks(repo: StageRepo, tasks: str, number: int = 1) -> None:
    branch = branch_of(number)
    repo.git("checkout", "-B", branch, f"origin/{branch}")
    repo.git("rebase", "main")
    write_change(repo.clone, tasks, number)
    repo.git("add", "-A")
    repo.git("-c", f"user.name={STAGE_NAME}", "commit", "-q", "--amend", "-m", "fix(roadmap): plan")
    repo.git("push", "-q", "--force", "origin", branch)
    repo.git("switch", "-q", "main")
    repo.git("branch", "-q", "-D", branch)


def make_heavy_files(repo: StageRepo, count: int = 6) -> list[str]:
    names = [f"src/devops_cli/heavy_{i}.py" for i in range(count)]
    lines = [f"def heavy_func_{j}(x: int) -> int:\n    return x + {j}\n" for j in range(1200)]
    repo.track({name: "\n".join(lines) for name in names})
    return names


def _make_split_reply() -> StageSplit:
    group_a = StageGroup(
        title="Second group part one",
        kind=GroupKind.OTHER,
        reads=[
            "src/devops_cli/heavy_0.py",
            "src/devops_cli/heavy_1.py",
            "src/devops_cli/heavy_2.py",
        ],
        changes=["src/devops_cli/shout.py"],
        creates=[],
        test=None,
        implementation="Implement part one",
        documentation=None,
        verify="uv run devops ci test tests/test_shout.py",
        process=None,
    )
    group_b = StageGroup(
        title="Second group part two",
        kind=GroupKind.OTHER,
        reads=[
            "src/devops_cli/heavy_3.py",
            "src/devops_cli/heavy_4.py",
            "src/devops_cli/heavy_5.py",
        ],
        changes=["src/devops_cli/shout.py"],
        creates=[],
        test=None,
        implementation="Implement part two",
        documentation=None,
        verify="uv run devops ci test tests/test_shout.py",
        process=None,
    )
    return StageSplit(
        groups=[group_a, group_b],
        criteria=[
            StageCriterion(group=1, criterion="First criterion."),
            StageCriterion(group=2, criterion="Second criterion."),
            StageCriterion(group=4, criterion="Third criterion."),
        ],
    )


def test_build_step_inputs_with_window_under_measure_raises_over_window_error(
    implement_store: InMemoryRoadmapStore, implement_checkout: Path
) -> None:
    measured = build_step_inputs(
        implement_store, item=1, group=1, source=implement_checkout, window=WINDOW
    ).tokens
    window = CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS + 50
    limit = 50

    with pytest.raises(OverWindowError) as exc_info:
        build_step_inputs(
            implement_store, item=1, group=1, source=implement_checkout, window=window
        )

    err = exc_info.value
    assert isinstance(err, RoadmapImplementError)
    assert issubclass(OverWindowError, RoadmapImplementError)
    assert err.error_code == "ROADMAP_IMPLEMENT_REFUSED"
    assert err.measured == measured
    assert err.limit == limit
    assert err.message == (
        f"The inputs of the step measure {measured} tokens. The limit is {limit} tokens: the window "
        f"of {window} tokens minus {CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS} tokens for the "
        "turns of the run."
    )


def test_a_group_over_the_limit_is_split_once_with_groups_and_criteria_renumbered(
    job_world: JobWorld,
) -> None:
    job_world.store.write_issue_body(1, THREE_CRITERIA_BODY)
    make_heavy_files(job_world.repo, count=6)
    job_world.repo.track({"tests/test_shout.py": "# test shout\n"})
    set_staged_tasks(job_world.repo, THREE_GROUPS_TASKS)

    splitter = _SplitClientFake(_make_split_reply())

    # Script for 4 groups: Group 1, Group 2 (new), Group 3 (new), Group 4 (old 3 renumbered)
    script = ModelScript(
        # Group 1
        tool_calls(
            ("edit_file", {"path": TASKS_PATH, "old_text": "- [ ] 1.1", "new_text": "- [x] 1.1"}),
            ("write_file", {"path": "src/devops_cli/shout.py", "content": SHOUT}),
        ),
        say("Group 1 is done."),
        # Group 2 (new)
        tool_calls(
            ("edit_file", {"path": TASKS_PATH, "old_text": "- [ ] 2.1", "new_text": "- [x] 2.1"}),
        ),
        say("Group 2 is done."),
        # Group 3 (new)
        tool_calls(
            ("edit_file", {"path": TASKS_PATH, "old_text": "- [ ] 3.1", "new_text": "- [x] 3.1"}),
        ),
        say("Group 3 is done."),
        # Group 4 (old 3)
        tool_calls(
            ("edit_file", {"path": TASKS_PATH, "old_text": "- [ ] 4.1", "new_text": "- [x] 4.1"}),
            ("write_file", {"path": "CONTEXT.md", "content": "# Context\n"}),
        ),
        say("Group 4 is done."),
    )

    applied = job_world.run(script, splitter=splitter, window=WINDOW)

    assert applied.ready == (1,)
    assert len(splitter.calls) == 1

    # Verify tasks.md in origin
    tasks_content = job_world.repo.origin_git(
        "show", f"{BRANCH}:openspec/changes/archive/2026-10-29-{CHANGE}/tasks.md"
    )
    assert "## 1. The first group" in tasks_content
    assert "## 2. Second group part one" in tasks_content
    assert "## 3. Second group part two" in tasks_content
    assert "## 4. The third group" in tasks_content
    assert "- [x] 4.1 Document the function in `CONTEXT.md`" in tasks_content

    # Criteria section renumbered
    assert "- Group 1: First criterion." in tasks_content
    assert "- Group 2: Second criterion." in tasks_content
    assert "- Group 4: Third criterion." in tasks_content

    # Amendments section has bullet
    assert "## Amendments" in tasks_content
    assert "- Group 2, split:" in tasks_content

    # PR comment has split line
    pr_comments = [c["body"] for c in job_world.sent("POST", f"issues/{PULL}/comments")]
    assert any("- Group 2 amendment (split):" in c for c in pr_comments)


def test_a_split_reply_with_a_group_over_the_limit_stops_the_item_as_plan_defect(
    job_world: JobWorld,
) -> None:
    job_world.store.write_issue_body(1, THREE_CRITERIA_BODY)
    make_heavy_files(job_world.repo, count=6)
    job_world.repo.track({"tests/test_shout.py": "# test shout\n"})
    set_staged_tasks(job_world.repo, THREE_GROUPS_TASKS)

    # Split reply still has a group reading all 6 heavy files
    bad_split = StageSplit(
        groups=[
            StageGroup(
                title="Still heavy part",
                kind=GroupKind.OTHER,
                reads=[f"src/devops_cli/heavy_{i}.py" for i in range(6)],
                changes=["src/devops_cli/shout.py"],
                creates=[],
                test=None,
                implementation="Heavy part",
                documentation=None,
                verify="uv run devops ci test tests/test_shout.py",
                process=None,
            ),
            StageGroup(
                title="Light part",
                kind=GroupKind.OTHER,
                reads=[],
                changes=["src/devops_cli/shout.py"],
                creates=[],
                test=None,
                implementation="Light part",
                documentation=None,
                verify="uv run devops ci test tests/test_shout.py",
                process=None,
            ),
        ],
        criteria=[
            StageCriterion(group=1, criterion="First criterion."),
            StageCriterion(group=2, criterion="Second criterion."),
            StageCriterion(group=4, criterion="Third criterion."),
        ],
    )
    splitter = _SplitClientFake(bad_split)

    script = ModelScript(
        tool_calls(
            ("edit_file", {"path": TASKS_PATH, "old_text": "- [ ] 1.1", "new_text": "- [x] 1.1"}),
            ("write_file", {"path": "src/devops_cli/shout.py", "content": SHOUT}),
        ),
        say("Group 1 is done."),
    )

    applied = job_world.run(script, splitter=splitter, window=WINDOW)

    assert applied.stopped == (1,)
    status, record = _item(job_world)
    assert status == "Blocked"
    assert record.get("implement.failure") == "plan_defect"


def test_a_second_group_over_the_limit_stops_the_item_as_plan_defect(
    job_world: JobWorld,
) -> None:
    job_world.store.write_issue_body(1, THREE_CRITERIA_BODY)
    make_heavy_files(job_world.repo, count=6)
    job_world.repo.track({"tests/test_shout.py": "# test shout\n"})

    # Group 2 is heavy, and Group 3 is also heavy
    two_heavy_tasks = """\
# Tasks

## 1. The first group

Reads: `CONTEXT.md`. Changes: `src/devops_cli/shout.py` (new).

- [ ] 1.1 First task
  - Verification: `$ uv run devops ci test tests/test_shout.py`

## 2. The second group

Reads: `src/devops_cli/heavy_0.py`, `src/devops_cli/heavy_1.py`, `src/devops_cli/heavy_2.py`, `src/devops_cli/heavy_3.py`, `src/devops_cli/heavy_4.py`, `src/devops_cli/heavy_5.py`. Changes: `src/devops_cli/shout.py`.

- [ ] 2.1 Heavy task reading `src/devops_cli/heavy_0.py`, `src/devops_cli/heavy_1.py`, `src/devops_cli/heavy_2.py`, `src/devops_cli/heavy_3.py`, `src/devops_cli/heavy_4.py`, `src/devops_cli/heavy_5.py`
  - Verification: `$ uv run devops ci test tests/test_shout.py`

## 3. The third group

Reads: `src/devops_cli/heavy_0.py`, `src/devops_cli/heavy_1.py`, `src/devops_cli/heavy_2.py`, `src/devops_cli/heavy_3.py`, `src/devops_cli/heavy_4.py`, `src/devops_cli/heavy_5.py`. Changes: `src/devops_cli/shout.py`.

- [ ] 3.1 Another heavy task reading `src/devops_cli/heavy_0.py`, `src/devops_cli/heavy_1.py`, `src/devops_cli/heavy_2.py`, `src/devops_cli/heavy_3.py`, `src/devops_cli/heavy_4.py`, `src/devops_cli/heavy_5.py`
  - Verification: `$ uv run devops ci test tests/test_shout.py`

## Criteria

- Group 1: First criterion.
- Group 2: Second criterion.
- Group 3: Third criterion.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
"""
    set_staged_tasks(job_world.repo, two_heavy_tasks)

    # First split splits group 2 into two groups under the limit
    splitter = _SplitClientFake(_make_split_reply())

    script = ModelScript(
        # Group 1
        tool_calls(
            ("edit_file", {"path": TASKS_PATH, "old_text": "- [ ] 1.1", "new_text": "- [x] 1.1"}),
            ("write_file", {"path": "src/devops_cli/shout.py", "content": SHOUT}),
        ),
        say("Group 1 is done."),
        # Group 2
        tool_calls(
            ("edit_file", {"path": TASKS_PATH, "old_text": "- [ ] 2.1", "new_text": "- [x] 2.1"}),
        ),
        say("Group 2 is done."),
        # Group 3
        tool_calls(
            ("edit_file", {"path": TASKS_PATH, "old_text": "- [ ] 3.1", "new_text": "- [x] 3.1"}),
        ),
        say("Group 3 is done."),
    )

    applied = job_world.run(script, splitter=splitter, window=WINDOW)

    assert applied.stopped == (1,)
    status, record = _item(job_world)
    assert status == "Blocked"
    assert record.get("implement.failure") == "plan_defect"
    assert len(splitter.calls) == 1  # No second split call


def test_a_missing_splitter_stops_the_item_as_plan_defect(
    job_world: JobWorld,
) -> None:
    job_world.store.write_issue_body(1, THREE_CRITERIA_BODY)
    make_heavy_files(job_world.repo, count=6)
    job_world.repo.track({"tests/test_shout.py": "# test shout\n"})
    set_staged_tasks(job_world.repo, THREE_GROUPS_TASKS)

    script = ModelScript(
        tool_calls(
            ("edit_file", {"path": TASKS_PATH, "old_text": "- [ ] 1.1", "new_text": "- [x] 1.1"}),
            ("write_file", {"path": "src/devops_cli/shout.py", "content": SHOUT}),
        ),
        say("Group 1 is done."),
    )

    applied = job_world.run(script, splitter=None, window=WINDOW)

    assert applied.stopped == (1,)
    status, record = _item(job_world)
    assert status == "Blocked"
    assert record.get("implement.failure") == "plan_defect"
