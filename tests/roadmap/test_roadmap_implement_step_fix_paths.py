"""A fix step edits only the paths that the plan names (#3824): a fix step that touches another
path stops with the class `outside_plan`, resets the checkout and spends no repair round.

The model is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a checkout in
`tmp_path`, and every other program is answered by `process_fake`. The plan of the sample change
names `src/sample.py`, `tests/test_sample.py` and `docs/SAMPLE.md`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.implement_step import (
    FixRequest,
    StepOutcome,
    StepStatus,
    run_fix_step,
)
from devops_cli.roadmap.step_files import parse_task_groups
from tests.support.fakes.process import ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import (
    SHOUT_CODE,
    TEST_BODY,
    WINDOW,
    git,
    is_clean_at,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

CHANGE = "openspec/changes/1-sample-change"
PLAN = parse_task_groups(
    "## 1. The group\n\n"
    "Reads: `src/reads.py`. Changes: `src/sample.py`, `tests/test_sample.py` (new).\n\n"
    "- [ ] 1.1 Add the test `tests/test_sample.py`\n"
    "  - Verification: `uv run devops ci test tests/test_sample.py`\n"
    "\n## 2. The second group\n\n"
    "Reads: none. Changes: `docs/NOTES.md`.\n\n"
    "- [ ] 2.1 Write `docs/NOTES.md`\n"
)


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def _fix(store: InMemoryRoadmapStore, checkout: Path, script: ModelScript) -> StepOutcome:
    return run_fix_step(
        store,
        item=1,
        fix=FixRequest(check="Plan Check", log="Plan Check failed"),
        source=checkout,
        model=script.model(),
        window=WINDOW,
    )


def test_the_paths_of_the_reads_and_changes_lines_and_the_change_folder_are_planned() -> None:
    from devops_cli.roadmap.implement_strays import unplanned_paths

    changed = [
        "src/reads.py",
        "src/sample.py",
        "tests/test_sample.py",
        "docs/NOTES.md",
        f"{CHANGE}/proposal.md",
    ]

    assert unplanned_paths(changed, PLAN, CHANGE) == []


def test_a_path_that_no_line_of_the_plan_names_is_unplanned_whatever_its_directory() -> None:
    from devops_cli.roadmap.implement_strays import unplanned_paths

    changed = [
        "src/devops_cli/roadmap/plan_check.py",
        "docs/roadmap/plan-check.md",
        "src/sample.py",
    ]

    assert unplanned_paths(changed, PLAN, CHANGE) == [
        "src/devops_cli/roadmap/plan_check.py",
        "docs/roadmap/plan-check.md",
    ]


def test_a_fix_step_that_edits_a_path_the_plan_names_ends_done(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_calls(write_call("src/sample.py", SHOUT_CODE)), say("Fixed."))

    outcome = _fix(store, checkout, script)

    assert (outcome.status, outcome.failure_class) == (StepStatus.DONE, None)
    assert "src/sample.py" in git(checkout, "show", "--name-only", "--format=", "HEAD")


def test_a_fix_step_that_edits_an_unnamed_path_stops_and_resets_the_checkout(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")
    edits = tool_calls(
        write_call("src/sample.py", SHOUT_CODE), write_call("src/other.py", "OTHER = 2\n")
    )

    outcome = _fix(store, checkout, ModelScript(edits, say("Fixed.")))

    assert (outcome.status, outcome.failure_class, outcome.repair_rounds) == (
        StepStatus.STOPPED,
        FailureClass.OUTSIDE_PLAN,
        0,
    )
    assert "`src/other.py`" in outcome.reason
    assert "src/sample.py" not in outcome.reason
    assert "OTHER = 2" in outcome.diff
    assert is_clean_at(checkout, head)


def test_a_fix_step_that_adds_an_unnamed_test_file_stops(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    new = write_call("tests/test_sample_fix.py", TEST_BODY)

    outcome = _fix(store, checkout, ModelScript(tool_calls(new), say("Fixed.")))

    assert (outcome.status, outcome.failure_class) == (
        StepStatus.STOPPED,
        FailureClass.OUTSIDE_PLAN,
    )
    assert "`tests/test_sample_fix.py`" in outcome.reason


def test_a_fix_step_that_deletes_an_unnamed_file_stops(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    def agent_deletes() -> None:
        (checkout / "src" / "other.py").unlink()

    script = ModelScript(
        tool_calls(write_call("src/sample.py", SHOUT_CODE)),
        say("Fixed."),
        effects={2: agent_deletes},
    )

    outcome = _fix(store, checkout, script)

    assert (outcome.status, outcome.failure_class) == (
        StepStatus.STOPPED,
        FailureClass.OUTSIDE_PLAN,
    )
    assert "`src/other.py`" in outcome.reason
    assert (checkout / "src" / "other.py").exists()


def test_a_fix_step_may_edit_a_file_of_the_change_folder(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(
        tool_calls(
            write_call("src/sample.py", SHOUT_CODE),
            write_call(f"{CHANGE}/design.md", "# Design\n\nShout in capitals, twice.\n"),
        ),
        say("Fixed."),
    )

    outcome = _fix(store, checkout, script)

    assert (outcome.status, outcome.failure_class) == (StepStatus.DONE, None)
