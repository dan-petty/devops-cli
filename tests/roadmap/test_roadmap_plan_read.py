"""The plan reader reads a rendered change folder back into the gates' inputs (#3201)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from devops_cli.roadmap.plan_read import PlanReadError, read_change
from devops_cli.roadmap.stage_change import (
    GroupKind,
    StageGroup,
    StageProposal,
    render_change,
)
from devops_cli.roadmap.stage_criteria import PENDING_PERSON
from tests.support.builders import make_stage_proposal
from tests.support.paths import REPO_ROOT

CREATED = datetime(2026, 11, 4, tzinfo=UTC).date()
CHANGE = "1-keep-the-last-comment"


def _files(proposal: StageProposal, known: set[str] | None = None) -> dict[str, str]:
    return render_change(CHANGE, proposal, known or {"comment-thread"}, created=CREATED)


def _same_group(dropped: StageGroup) -> StageGroup:
    """The original group with one estimated line for each created path, as the writer drops the
    estimate of a created file and the reader gives it one."""
    return dropped.model_copy(update={"creates_lines": dict.fromkeys(dropped.creates, 1)})


def test_a_rendered_change_reads_back() -> None:
    original = make_stage_proposal()

    read = read_change(_files(original))

    assert (read.specs, read.skip_specs, read.criteria) == (
        original.specs,
        original.skip_specs,
        original.criteria,
    )
    assert read.groups == [_same_group(group) for group in original.groups]


def test_a_change_folder_with_no_criteria_section_reads_back_with_no_criterion() -> None:
    files = _files(make_stage_proposal())
    tasks = files[f"openspec/changes/{CHANGE}/tasks.md"]
    files[f"openspec/changes/{CHANGE}/tasks.md"] = tasks.partition("## Criteria")[0]

    assert read_change(files).criteria == []


def test_the_reader_reads_a_process_group_and_a_documented_group() -> None:
    original = make_stage_proposal(
        groups=[
            {
                "title": "Change a page",
                "kind": "other",
                "changes": ["docs/roadmap/plan-check.md"],
                "implementation": "Write the page about the plan check",
                "documentation": "Regenerate the command reference",
                "verify": "uv run devops ci docs",
            },
            {
                "title": "Read the output",
                "kind": "other",
                "reads": ["src/devops_cli/roadmap/plan_check.py"],
                "changes": ["src/devops_cli/roadmap/plan_check.py"],
                "implementation": "Read the output of the command by hand",
                "process": "Run the command on a plan pull request and read each line.",
            },
        ]
    )
    files = _files(original, known=set())

    read = read_change(files)

    assert read.groups == [_same_group(group) for group in original.groups]


def test_a_documents_task_without_the_regeneration_step_reads_back_with_its_verb() -> None:
    original = make_stage_proposal(
        groups=[
            {
                "title": "Name the disclosure contact",
                "kind": "other",
                "changes": ["SECURITY.md"],
                "implementation": "Name the disclosure contact in `SECURITY.md`",
                "documentation": "SECURITY.md",
                "verify": "uv run devops ci docs",
            }
        ]
    )

    read = read_change(_files(original, known=set()))

    assert [group.documentation for group in read.groups] == ["Edit `SECURITY.md`"]


def test_the_reader_reads_each_kind_of_criterion() -> None:
    original = make_stage_proposal(
        criteria=[
            {"criterion": "The command prints one line for each problem", "group": 1},
            {
                "criterion": "A person reads the output",
                "group": PENDING_PERSON,
                "reason": "A person decides whether the plan is right.",
            },
        ]
    )

    assert read_change(_files(original)).criteria == original.criteria


def test_the_reader_infers_the_kind_of_a_group_from_its_verification() -> None:
    original = make_stage_proposal(
        groups=[
            {
                "title": "Keep the last comment",
                "kind": "behavior",
                "changes": ["src/devops_cli/sample.py"],
                "test": "Write a failing test for the last comment",
                "implementation": "Keep the last comment in the sample",
                "verify": "uv run devops ci test tests/test_sample.py",
            }
        ]
    )

    (group,) = read_change(_files(original)).groups

    assert group.kind is GroupKind.BEHAVIOR


def test_a_folder_with_more_than_one_change_is_refused() -> None:
    files = _files(make_stage_proposal())
    files["openspec/changes/2-another-change/.openspec.yaml"] = "schema: spec-driven\n"

    with pytest.raises(PlanReadError) as found:
        read_change(files)

    assert found.value.path == "/.openspec.yaml"


def test_a_change_folder_with_no_proposal_is_refused() -> None:
    files = _files(make_stage_proposal())
    del files[f"openspec/changes/{CHANGE}/proposal.md"]

    with pytest.raises(PlanReadError) as found:
        read_change(files)

    assert found.value.path == f"openspec/changes/{CHANGE}/proposal.md"


def test_a_requirement_with_no_scenario_is_refused() -> None:
    files = _files(make_stage_proposal())
    path = f"openspec/changes/{CHANGE}/specs/comment-thread/spec.md"
    files[path] = files[path].partition("#### Scenario:")[0]

    with pytest.raises(PlanReadError) as found:
        read_change(files)

    assert "comment-thread" in found.value.path


def test_a_plan_with_inline_verification_reads_as_the_kind_it_names() -> None:
    files = _files(make_stage_proposal())
    files[f"openspec/changes/{CHANGE}/tasks.md"] = (
        "# Tasks\n\n## 1. Keep the last comment\n\n"
        "Kind: behavior. Reads: `src/devops_cli/sample.py`. "
        "Changes: `src/devops_cli/sample.py`, `tests/test_sample.py` (new).\n\n"
        "- [ ] 1.1 Write the failing test. Verify that "
        "`uv run devops ci test tests/test_sample.py` fails on the base\n"
        "- [ ] 1.2 Keep the last comment. Verify that "
        "`uv run devops ci test tests/test_sample.py` passes\n"
    )

    (group,) = read_change(files).groups

    assert (group.kind, group.verify) == (
        GroupKind.BEHAVIOR,
        "uv run devops ci test tests/test_sample.py",
    )
    assert group.test == "Write the failing test"
    assert group.implementation == "Keep the last comment"


def _tasks_with(group_text: str) -> dict[str, str]:
    files = _files(make_stage_proposal())
    files[f"openspec/changes/{CHANGE}/tasks.md"] = f"# Tasks\n\n{group_text}\n"
    return files


# The group of #3187: `Changes:` names no file in a code span.
NO_CHANGED_FILE = (
    "## 1. Prove the move\n\n"
    "Reads: `src/devops_cli/roadmap/store.py`. Changes: each module that names an old path.\n\n"
    "- [ ] 1.1 Prove the move. Verify that `uv run devops ci test tests/test_sample.py` passes\n"
)
# The group of #3308: `Changes:` names a file of the change folder.
CHANGE_FOLDER_FILE = (
    "## 1. Fix the plan\n\n"
    f"Reads: `src/devops_cli/roadmap/store.py`. Changes: `openspec/changes/{CHANGE}/proposal.md`.\n\n"
    "- [ ] 1.1 Fix the plan. Verify that `uv run devops ci test tests/test_sample.py` passes\n"
)


@pytest.mark.parametrize("group", [NO_CHANGED_FILE, CHANGE_FOLDER_FILE])
def test_a_group_that_pydantic_refuses_is_a_read_error(group: str) -> None:
    with pytest.raises(PlanReadError) as found:
        read_change(_tasks_with(group))

    assert found.value.path == "tasks.md"
    assert found.value.reason


def test_the_reader_raises_only_a_read_error_over_each_change_folder_of_the_tree() -> None:
    folders = sorted(
        path
        for path in (REPO_ROOT / "openspec" / "changes").iterdir()
        if path.is_dir() and path.name != "archive"
    )
    escaped: list[str] = []
    for folder in folders:
        files = {
            path.relative_to(REPO_ROOT).as_posix(): path.read_text(encoding="utf-8")
            for path in folder.rglob("*")
            if path.is_file()
        }
        try:
            read_change(files)
        except PlanReadError:
            continue
        except Exception as exc:
            escaped.append(f"{folder.name}: {type(exc).__name__}")

    assert escaped == []


def _two_tasks(second_verification: str) -> dict[str, str]:
    return _tasks_with(
        "## 1. Render the values\n\n"
        "Reads: `src/devops_cli/roadmap/store.py`. Changes: `k8s/loki-values.yaml`.\n\n"
        "- [ ] 1.1 Change the values.\n"
        "  - Verification: `uv run devops ci docs`\n"
        "- [ ] 1.2 Document the values.\n"
        f"  - Verification: `{second_verification}`\n"
    )


def test_the_reader_reports_a_refused_span_of_a_later_task() -> None:
    command = "helm template loki"

    with pytest.raises(PlanReadError) as found:
        read_change(_two_tasks(command))

    assert command in found.value.reason
    assert found.value.path == "tasks.md"


def test_the_reader_reads_a_plan_whose_spans_the_step_runs() -> None:
    (group,) = read_change(_two_tasks("uv run devops ci test tests/test_sample.py")).groups

    assert group.verify == "uv run devops ci docs"
