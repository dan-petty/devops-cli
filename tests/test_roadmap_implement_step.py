"""`devops roadmap implement` (#2664): the groups of a `tasks.md`, the inputs of a step, and the
run of one group in a checkout.

pydantic-ai's `FunctionModel` answers each model request from a script, so no test reaches a
model. Git runs on a temporary repository. The programs of the exit checks (`uv`, `ruff` and
`mypy`) are answered at the process edge by `process_fake`, and git passes through to the real
program.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.roadmap.implement_step import build_step_inputs, parse_task_groups
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import ItemField

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
WINDOW = 128000

_TASKS = """\
# Tasks

## 1. The first group

- [ ] Add the failing test `tests/test_sample.py` for `src/sample.py`
  - Verification: `uv run devops ci test tests/test_sample.py`
- [ ] Add `shout` to `src/sample.py`
  - Verification: `uv run devops ci test tests/test_sample.py` and `uv run devops docs check`

## 2. The second group

- [x] Document the function in `docs/SAMPLE.md`
  - Verification: `uv run devops docs check`

## Workflow follow-up

- A plain bullet with `src/other.py` in it.
"""

_BODY = """\
## Problem or Motivation

The sample cannot shout.

## Proposed Solution & Architectural Design

A long design that the step does not need.

## Acceptance criteria

- `shout("a")` returns `A!`.

## Target Subsystem

Nothing else.
"""

_SAMPLE = '''\
"""A sample module."""


def hello(name: str) -> str:
    """Greet `name`."""
    return f"hello {name}"
'''


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def make_checkout(root: Path, tasks: str = _TASKS) -> Path:
    """A git checkout whose one commit holds change `1-sample-change` and two source files."""
    checkout = root / "checkout"
    change = checkout / "openspec" / "changes" / "1-sample-change"
    change.mkdir(parents=True)
    (checkout / "src").mkdir()
    (checkout / "docs").mkdir()
    git(checkout, "init", "-q", "-b", "main")
    for key, value in (("user.email", "ci@example.com"), ("user.name", "CI")):
        git(checkout, "config", key, value)
    git(checkout, "config", "commit.gpgsign", "false")
    (change / "proposal.md").write_text("# Proposal\n\nWhy the sample shouts.\n", encoding="utf-8")
    (change / "design.md").write_text("# Design\n\nShout in capitals.\n", encoding="utf-8")
    (change / "tasks.md").write_text(tasks, encoding="utf-8")
    (checkout / "src" / "sample.py").write_text(_SAMPLE, encoding="utf-8")
    (checkout / "src" / "other.py").write_text("OTHER = 1\n", encoding="utf-8")
    (checkout / "docs" / "SAMPLE.md").write_text("The sample.\n", encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "init")
    return checkout


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    """A private roadmap whose item 1 is the sample item."""
    roadmap = InMemoryRoadmapStore(repo=REPO, is_private=True)
    roadmap.seed_issue(
        "Make the sample shout",
        body=_BODY,
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    return roadmap


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    return make_checkout(tmp_path)


# ── The groups of a tasks.md ──────────────────────────────────────────────────────────────


def test_a_tasks_file_holds_numbered_groups_with_their_tasks_commands_and_files() -> None:
    groups = parse_task_groups(_TASKS)

    assert [
        (
            group.number,
            group.title,
            [(task.text, task.ticked) for task in group.tasks],
            group.verification_commands,
            group.named_paths,
        )
        for group in groups
    ] == [
        (
            1,
            "The first group",
            [
                ("[ ] Add the failing test `tests/test_sample.py` for `src/sample.py`", False),
                ("[ ] Add `shout` to `src/sample.py`", False),
            ],
            (
                "uv run devops ci test tests/test_sample.py",
                "uv run devops docs check",
            ),
            ("tests/test_sample.py", "src/sample.py", "shout"),
        ),
        (
            2,
            "The second group",
            [("[x] Document the function in `docs/SAMPLE.md`", True)],
            ("uv run devops docs check",),
            ("docs/SAMPLE.md",),
        ),
    ]


def test_the_text_of_a_group_runs_from_its_heading_to_the_next_heading() -> None:
    first, second = parse_task_groups(_TASKS)

    assert (
        first.text.splitlines()[0],
        first.text.splitlines()[-1],
        second.text.splitlines()[0],
    ) == (
        "## 1. The first group",
        "  - Verification: `uv run devops ci test tests/test_sample.py` and `uv run devops docs check`",
        "## 2. The second group",
    )


def test_a_section_without_a_number_is_no_group() -> None:
    groups = parse_task_groups("# Tasks\n\n## Workflow follow-up\n\n- [ ] Not a task of a group\n")

    assert groups == []


# ── The inputs of a step ──────────────────────────────────────────────────────────────────


def test_the_inputs_hold_the_item_the_change_the_group_and_the_files_it_names(
    store: InMemoryRoadmapStore, checkout: Path, snapshot: object
) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    assert inputs.message == snapshot


def test_the_inputs_hold_no_file_that_the_group_does_not_name(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    assert ("OTHER = 1" in inputs.message, "The sample." in inputs.message) == (False, False)


def test_inputs_over_the_window_are_refused_with_the_measure_and_the_limit(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    measured = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW).tokens
    window = CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS + 50

    with pytest.raises(RoadmapImplementError) as refused:
        build_step_inputs(store, item=1, group=1, source=checkout, window=window)

    assert (refused.value.message, refused.value.exit_code, refused.value.error_code) == (
        f"The inputs of the step measure {measured} tokens. The limit is 50 tokens: the window "
        f"of {window} tokens minus {CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS} tokens for the "
        "turns of the run.",
        1,
        "ROADMAP_IMPLEMENT_REFUSED",
    )
    assert measured > 50


def test_a_checkout_with_no_change_folder_is_refused(
    store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    empty = tmp_path / "empty"
    (empty / "openspec" / "changes").mkdir(parents=True)

    with pytest.raises(RoadmapImplementError) as refused:
        build_step_inputs(store, item=1, group=1, source=empty, window=WINDOW)

    assert refused.value.message == "The checkout has no change folder that matches 1-*."


def test_a_checkout_with_two_change_folders_for_the_item_is_refused(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    (checkout / "openspec" / "changes" / "1-other-change").mkdir()

    with pytest.raises(RoadmapImplementError) as refused:
        build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    assert refused.value.message == (
        "The checkout has more than one change folder that matches 1-*: "
        "1-other-change, 1-sample-change."
    )


def test_a_group_that_the_change_lacks_is_refused(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    with pytest.raises(RoadmapImplementError) as refused:
        build_step_inputs(store, item=1, group=9, source=checkout, window=WINDOW)

    assert (
        refused.value.message == "The change 1-sample-change has no group 9. Its groups are 1, 2."
    )


def test_an_issue_that_is_no_item_is_refused(store: InMemoryRoadmapStore, checkout: Path) -> None:
    with pytest.raises(RoadmapImplementError) as refused:
        build_step_inputs(store, item=5, group=1, source=checkout, window=WINDOW)

    assert refused.value.message == "#5 is not an item of the roadmap."
