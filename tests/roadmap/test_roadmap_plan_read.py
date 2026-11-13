"""The plan reader reads a rendered change folder back into the gates' inputs (#3201)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.plan_read import PlanReadError, read_change, specs_at
from devops_cli.roadmap.stage.stage_change import (
    GroupKind,
    StageGroup,
    StageProposal,
    StageRemoval,
    StageRename,
    render_change,
)
from devops_cli.roadmap.stage.stage_criteria import PENDING_PERSON
from tests.support.builders import make_stage_proposal
from tests.support.paths import REPO_ROOT

if TYPE_CHECKING:
    from tests.support.roadmap_stage import StageRepo

CREATED = datetime(2026, 11, 4, tzinfo=UTC).date()
CHANGE = "1-keep-the-last-comment"
NESTED = "roadmap-stage/paths-gate"
GOLDEN = REPO_ROOT / "tests" / "fixtures" / "roadmap_eval" / "stage"
PLAN_HEADS = REPO_ROOT / "tests" / "fixtures" / "roadmap" / "plan_heads"
# The spec deltas of two archived changes of the repository: #5150 renames and modifies a
# requirement, and #4798 removes two requirements, each with a reason and a migration.
SPEC_DELTAS = REPO_ROOT / "tests" / "fixtures" / "roadmap" / "spec_deltas"
TASKS = f"openspec/changes/{CHANGE}/tasks.md"
DESIGN = f"openspec/changes/{CHANGE}/design.md"


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


def test_a_change_with_a_nested_capability_reads_back() -> None:
    spec = make_stage_proposal().specs[0].model_dump()
    original = make_stage_proposal(specs=[{**spec, "capability": NESTED, "purpose": None}])

    files = _files(original, {NESTED})

    assert f"openspec/changes/{CHANGE}/specs/{NESTED}/spec.md" in files
    assert read_change(files).specs == original.specs


def test_the_base_specs_at_a_commit_hold_a_nested_capability(stage_repo: StageRepo) -> None:
    stage_repo.track(
        {
            f"openspec/specs/{NESTED}/spec.md": (
                "# roadmap-stage/paths-gate Specification\n\n## Purpose\nThe path gate.\n\n"
                "## Requirements\n\n### Requirement: A path exists\nThe job SHALL check.\n"
            )
        }
    )

    capabilities, requirements = specs_at(stage_repo.clone, "HEAD", operation="plan read")

    assert capabilities == {NESTED, "roadmap-refine"}
    assert requirements[NESTED] == ("A path exists",)


def test_the_reader_reads_the_dependencies() -> None:
    original = make_stage_proposal(dependencies=["#3201: the check command"])

    assert read_change(_files(original)).dependencies == ["#3201: the check command"]


def test_a_plan_with_no_dependency_reads_as_no_entry() -> None:
    assert read_change(_files(make_stage_proposal())).dependencies == []


def test_the_reader_reads_the_security_section() -> None:
    original = make_stage_proposal(security="The egress rule is required for logging.")

    assert read_change(_files(original)).security == "The egress rule is required for logging."


def test_a_plan_with_no_security_reads_as_empty_text() -> None:
    assert read_change(_files(make_stage_proposal())).security == ""


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


def test_the_reader_reads_a_pending_person_criterion_with_commas() -> None:
    original = make_stage_proposal(
        criteria=[
            {
                "criterion": "The move has a backup of the database first, and a person runs the steps that change the cluster.",
                "group": PENDING_PERSON,
                "reason": "A backup and the cluster steps need a person and the live cluster; #3803 delivers them in one window.",
            },
        ]
    )

    assert read_change(_files(original)).criteria == original.criteria


def _with_criterion_group(number: int) -> dict[str, str]:
    original = make_stage_proposal(
        criteria=[{"criterion": "The command prints one line for each problem", "group": 1}]
    )
    files = _files(original)
    path = f"openspec/changes/{CHANGE}/tasks.md"
    files[path] = files[path].replace("Group 1:", f"Group {number}:")
    return files


def test_a_criterion_of_group_zero_is_a_read_error_that_names_the_line() -> None:
    with pytest.raises(PlanReadError) as found:
        read_change(_with_criterion_group(0))

    assert found.value.path == "tasks.md"
    assert "Group 0: The command prints one line for each problem" in found.value.reason
    assert "group" in found.value.reason


def test_a_criterion_of_group_one_reads_back_with_its_group() -> None:
    (criterion,) = read_change(_with_criterion_group(1)).criteria

    assert criterion.group == 1


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


# ── RENAMED and REMOVED deltas (#5340) ────────────────────────────────────────


def _with_delta(capability: str, delta: str) -> dict[str, str]:
    """The files of a rendered change whose only spec delta is `delta`, for `capability`."""
    files = _files(make_stage_proposal())
    del files[f"openspec/changes/{CHANGE}/specs/comment-thread/spec.md"]
    files[f"openspec/changes/{CHANGE}/specs/{capability}/spec.md"] = delta
    return files


def test_the_real_renamed_delta_of_5150_reads_back() -> None:
    delta = (SPEC_DELTAS / "5150-renamed.md").read_text(encoding="utf-8")

    (spec,) = read_change(_with_delta("roadmap-stage/fix-plan", delta)).specs

    new = "The review of the head counts the open findings before the repair"
    assert spec.renamed == [
        StageRename(from_name="The open findings come from the last plan comment", to_name=new)
    ]
    assert new in [requirement.name for requirement in spec.modified]


def test_the_real_removed_delta_of_4798_reads_back() -> None:
    delta = (SPEC_DELTAS / "4798-removed.md").read_text(encoding="utf-8")

    (spec,) = read_change(_with_delta("roadmap-refine", delta)).specs

    assert spec.removed == [
        StageRemoval(
            name="A refusal keeps the item New and lists each finding",
            reason="A refusal no longer waits on a person. It is a job failure, and the next "
            "round refines the item again with the findings (#4798).",
            migration='Read "A refusal of the review is a job failure that a later round fixes".',
        ),
        StageRemoval(
            name="The review looks again only after the body changes",
            reason="After a refusal, the next round reviews a new proposal on the same body. "
            "Only an approval of an unchanged body holds with no review call.",
            migration='Read "The review keeps the approval of an unchanged body" and "A refusal '
            'of the review is a job failure that a later round fixes".',
        ),
    ]


@pytest.mark.parametrize(
    "delta",
    [
        "## RENAMED Requirements\n\n- FROM: `### Requirement: Old name`\n",
        "## RENAMED Requirements\n\n- TO: `### Requirement: New name`\n",
        "## RENAMED Requirements\n\n- FROM: `### Requirement: A`\n- FROM: `### Requirement: B`\n"
        "- TO: `### Requirement: C`\n",
        "## REMOVED Requirements\n\n### Requirement: Old name\n",
        "## REMOVED Requirements\n\n### Requirement: Old name\n**Migration**: Read X.\n",
    ],
    ids=["from-alone", "to-alone", "two-froms", "no-reason", "migration-alone"],
)
def test_a_rename_or_a_removal_that_the_reader_cannot_pair_is_refused(delta: str) -> None:
    with pytest.raises(PlanReadError) as found:
        read_change(_with_delta("comment-thread", delta))

    assert found.value.path == f"openspec/changes/{CHANGE}/specs/comment-thread/spec.md"


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
    "Reads: `src/devops_cli/roadmap/stores/store.py`. Changes: each module that names an old path.\n\n"
    "- [ ] 1.1 Prove the move. Verify that `uv run devops ci test tests/test_sample.py` passes\n"
)
# The group of #3308: `Changes:` names a file of the change folder.
CHANGE_FOLDER_FILE = (
    "## 1. Fix the plan\n\n"
    f"Reads: `src/devops_cli/roadmap/stores/store.py`. Changes: `openspec/changes/{CHANGE}/proposal.md`.\n\n"
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
        "Reads: `src/devops_cli/roadmap/stores/store.py`. Changes: `k8s/loki-values.yaml`.\n\n"
        "- [ ] 1.1 Change the values.\n"
        "  - Verification: `$ uv run devops ci docs`\n"
        "- [ ] 1.2 Document the values.\n"
        f"  - Verification: `$ {second_verification}`\n"
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


# ── The kind of a group and the facts of the files (#5205) ────────────────────────────────

BEHAVIOR_GROUP: dict[str, Any] = {
    "title": "Keep the last comment",
    "kind": "behavior",
    "reads": ["src/devops_cli/sample.py"],
    "changes": ["src/devops_cli/sample.py", "tests/test_sample.py"],
    "creates": ["tests/test_sample.py"],
    "creates_lines": {"tests/test_sample.py": 40},
    "test": "Write `test_the_job_keeps_the_last_comment` in `tests/test_sample.py`",
    "implementation": "Keep the last comment in `src/devops_cli/sample.py`",
    "verify": "uv run devops ci test tests/test_sample.py",
}
# A rule and its promtool case: no path under `src/`, as group 3 of #4963 and groups 3 and 4 of
# #5032 change.
MANIFEST_GROUP: dict[str, Any] = {
    "title": "Alert on a stuck item",
    "kind": "manifest",
    "reads": ["k8s/monitoring/prometheus-values.yaml"],
    "changes": [
        "k8s/monitoring/prometheus-values.yaml",
        "tests/fixtures/prometheus_rules/stuck_item_tests.yaml",
    ],
    "creates": ["tests/fixtures/prometheus_rules/stuck_item_tests.yaml"],
    "creates_lines": {"tests/fixtures/prometheus_rules/stuck_item_tests.yaml": 30},
    "test": "Write the promtool case `A stuck item fires` in "
    "`tests/fixtures/prometheus_rules/stuck_item_tests.yaml`",
    "implementation": "Add the alert `RoadmapItemStuck` to `k8s/monitoring/prometheus-values.yaml`",
    "verify": "uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py",
}
OTHER_GROUP: dict[str, Any] = {
    "title": "Describe the alert",
    "kind": "other",
    "changes": ["k8s/README.md"],
    "implementation": "Add the row of the alert to the alert table of `k8s/README.md`",
    "verify": "uv run devops ci docs",
}
KIND_GROUPS: dict[str, dict[str, Any]] = {
    "behavior": BEHAVIOR_GROUP,
    "manifest": MANIFEST_GROUP,
    "other": OTHER_GROUP,
}


@pytest.mark.parametrize("kind", sorted(KIND_GROUPS))
def test_each_group_kind_reads_back(kind: str) -> None:
    original = make_stage_proposal(groups=[KIND_GROUPS[kind]])

    read = read_change(_files(original, known=set()))

    assert read.groups == [_same_group(group) for group in original.groups]
    assert [group.kind.value for group in read.groups] == [kind]


def test_a_manifest_group_writes_its_kind() -> None:
    from devops_cli.roadmap.stage.stage_change import group_text

    text = group_text(1, StageGroup.model_validate(MANIFEST_GROUP))

    assert text.splitlines()[2].startswith("Kind: manifest. Reads: ")


def test_the_problem_of_a_behavior_group_with_no_source_names_the_other_kinds() -> None:
    dashboard = {
        **MANIFEST_GROUP,
        "kind": "behavior",
        "changes": [
            "k8s/monitoring/dashboards/project-metrics.json",
            "tests/grafana/test_grafana_dashboards.py",
        ],
        "creates": [],
        "creates_lines": {},
    }

    with pytest.raises(ValidationError) as found:
        StageGroup.model_validate(dashboard)

    assert ("kind manifest" in str(found.value), "kind other" in str(found.value)) == (True, True)


# A hand-written group whose `Kind:` line says another kind than the tasks suggest: the first task
# of each "fails on the base", except for the behavior group, whose tasks both "pass".
EXPLICIT_KIND_GROUPS: dict[str, str] = {
    "behavior": (
        "## 1. Keep the last comment\n\n"
        "Kind: behavior. Reads: `src/devops_cli/sample.py`. "
        "Changes: `src/devops_cli/sample.py`, `tests/test_sample.py`.\n\n"
        "- [ ] 1.1 Write the failing test\n"
        "  - Verification: `$ uv run devops ci test tests/test_sample.py` passes\n"
        "- [ ] 1.2 Keep the last comment\n"
        "  - Verification: `$ uv run devops ci test tests/test_sample.py` passes\n"
    ),
    "manifest": (
        "## 1. Alert on a stuck item\n\n"
        "Kind: manifest. Reads: none. "
        "Changes: `src/devops_cli/sample.py`, `tests/fixtures/prometheus_rules/stuck_tests.yaml`.\n\n"
        "- [ ] 1.1 Write the promtool case of the stuck item\n"
        "  - Verification: `$ uv run devops ci test tests/test_sample.py` fails on the base\n"
        "- [ ] 1.2 Add the alert of the stuck item\n"
        "  - Verification: `$ uv run devops ci test tests/test_sample.py` passes\n"
    ),
    "other": (
        "## 1. Move the sample\n\n"
        "Kind: other. Reads: none. Changes: `src/devops_cli/sample.py`.\n\n"
        "- [ ] 1.1 Move the sample and keep its behavior\n"
        "  - Verification: `$ uv run devops ci test tests/test_sample.py` fails on the base\n"
    ),
}
EXPLICIT_KIND_TEXTS: dict[str, tuple[str | None, str]] = {
    "behavior": ("Write the failing test", "Keep the last comment"),
    "manifest": ("Write the promtool case of the stuck item", "Add the alert of the stuck item"),
    "other": (None, "Move the sample and keep its behavior"),
}


@pytest.mark.parametrize("kind", sorted(EXPLICIT_KIND_GROUPS))
def test_explicit_kind_line_sets_the_kind(kind: str) -> None:
    (group,) = read_change(_tasks_with(EXPLICIT_KIND_GROUPS[kind])).groups

    assert (group.kind.value, group.test, group.implementation, group.verify) == (
        kind,
        *EXPLICIT_KIND_TEXTS[kind],
        "uv run devops ci test tests/test_sample.py",
    )


# A hand-written group of the old form whose `Kind:` line names a word that is no kind: the head of
# #3164 says `Kind: documentation.` for a group of documents.
NO_KIND_WORDS: dict[str, tuple[str, str]] = {
    "documentation": (
        "## 1. Regenerate the tool reference\n\n"
        "Kind: documentation. Reads: none. Changes: `docs/MCP_TOOLS.md`.\n\n"
        "- [ ] 1.1 Regenerate the tool reference\n"
        "  - Verification: `$ uv run devops ci docs` passes\n",
        "other",
    ),
    "feature": (
        "## 1. Alert on a stuck item\n\n"
        "Kind: feature. Reads: none. Changes: `k8s/monitoring/prometheus-values.yaml`, "
        "`tests/fixtures/prometheus_rules/stuck_tests.yaml`.\n\n"
        "- [ ] 1.1 Write the promtool case of the stuck item\n"
        "  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`"
        " fails on the base\n"
        "- [ ] 1.2 Add the alert of the stuck item\n"
        "  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`"
        " passes\n",
        "manifest",
    ),
}


@pytest.mark.parametrize("word", sorted(NO_KIND_WORDS))
def test_a_word_that_is_no_kind_reads_as_the_old_form(word: str) -> None:
    text, kind = NO_KIND_WORDS[word]

    (group,) = read_change(_tasks_with(text)).groups

    assert group.kind.value == kind


UNCHANGED_REFERENCE: dict[str, Any] = {
    "path": "openspec/specs/roadmap-stage/task-groups/spec.md",
    "kind": "living spec",
    "unchanged": True,
    "reason": "`openspec archive` writes the living spec from the spec delta.",
}
CHANGED_REFERENCE: dict[str, Any] = {
    "path": "src/devops_cli/roadmap/plan_read.py",
    "kind": "import",
    "unchanged": False,
}


def test_unchanged_references_read_back() -> None:
    original = make_stage_proposal(references=[UNCHANGED_REFERENCE])

    assert read_change(_files(original)).references == original.references


# A line of `## Unchanged references` that the writer does not write: no kind and reason, and a
# reason that the model folds to no text (U+FEFF is a space for `openspec`, and none for Python).
BAD_REFERENCE_LINES = (
    "`src/devops_cli/old.py` holds the old path",
    "`src/devops_cli/old.py` (import): \ufeff",
)


@pytest.mark.parametrize("line", BAD_REFERENCE_LINES)
def test_a_reference_line_in_another_form_is_a_read_error(line: str) -> None:
    files = _files(make_stage_proposal())
    files[DESIGN] += f"\n## Unchanged references\n\n- {line}\n"

    with pytest.raises(PlanReadError) as found:
        read_change(files)

    assert (found.value.path, line.split(" ", 1)[0] in found.value.reason) == ("design.md", True)


def test_a_changed_reference_is_no_fact_of_the_files() -> None:
    from devops_cli.roadmap.plan_read import file_facts

    original = make_stage_proposal(references=[CHANGED_REFERENCE, UNCHANGED_REFERENCE])
    unchanged = original.references[1:]

    assert read_change(_files(original)).references == unchanged
    assert file_facts(original).references == unchanged


def test_the_fields_that_no_file_holds() -> None:
    from devops_cli.roadmap.plan_read import FIELDS_NOT_IN_FILES

    assert (
        frozenset(
            {"summary", "pull_request_body", "builds_own", "creates_lines", "weakened_checks"}
        )
        == FIELDS_NOT_IN_FILES
    )


def _golden_plans() -> list[str]:
    """The cases of the golden set whose `plan.json` is a valid `StageProposal`."""
    names: list[str] = []
    for plan in sorted(GOLDEN.glob("*/plan.json")):
        try:
            StageProposal.model_validate_json(plan.read_text(encoding="utf-8"))
        except ValidationError:
            continue
        names.append(plan.parent.name)
    return names


@pytest.mark.parametrize("case", _golden_plans())
def test_each_golden_plan_reads_back(case: str) -> None:
    from devops_cli.roadmap.plan_read import file_facts

    plan = json.loads((GOLDEN / case / "plan.json").read_text(encoding="utf-8"))
    original = StageProposal.model_validate(plan)

    assert read_change(_files(original, known=set())) == file_facts(original)


def _head_files(head: str) -> dict[str, str]:
    """The files of the change folder of a plan pull request head, by path from the root."""
    folder = PLAN_HEADS / head
    return {
        f"openspec/changes/{path.relative_to(folder).as_posix()}": path.read_text(encoding="utf-8")
        for path in folder.rglob("*")
        if path.is_file()
    }


# The change folders of three plan pull requests that the stage job wrote, at their heads: #4963
# and #5032 hold `manifest` groups that the job wrote with no `Kind:` line, and #5182 holds two
# `other` groups.
PLAN_HEAD_KINDS: dict[str, list[str]] = {
    "4963-9c4b2cf75c64": ["behavior", "behavior", "manifest", "other"],
    "5032-7fd165f69611": ["behavior", "behavior", "manifest", "manifest", "other"],
    "5182-5209df86045d": ["other", "other"],
}


@pytest.mark.parametrize("head", sorted(PLAN_HEAD_KINDS))
def test_a_plan_head_reads_with_its_kinds(head: str) -> None:
    read = read_change(_head_files(head))

    assert [group.kind.value for group in read.groups] == PLAN_HEAD_KINDS[head]


# ── The property: write, then read, keeps each fact that the files hold ───────────────────

WORDS = ("the", "job", "keeps", "each", "comment", "plan", "reader", "group", "Write", "Add")
PATHS = (
    "src/devops_cli/sample.py",
    "src/devops_cli/commands/sample.py",
    "tests/test_sample.py",
    "tests/roadmap/test_plan.py",
    "docs/TESTING.md",
    "SECURITY.md",
    "k8s/monitoring/prometheus-values.yaml",
    "tests/fixtures/prometheus_rules/stuck_tests.yaml",
)
TEST_COMMANDS = (
    "uv run devops ci test tests/test_sample.py",
    "uv run devops ci test tests/roadmap/test_plan.py",
)
CHECK_COMMANDS = (*TEST_COMMANDS, "uv run devops ci docs", "uv run devops openspec check")
# `plan` and `plan-check` sort in one order as names and in the other as paths of spec files.
CAPABILITIES = ("plan", "plan-check", "plan/reader", "comment-thread")
texts = st.lists(st.sampled_from(WORDS), min_size=1, max_size=4).map(" ".join)
# The line that the writer adds to `## What Changes`, which a model may also write.
FITS_ONE_PR = MESSAGES.roadmap.stage_fits_one_pr


@st.composite
def _group(draw: st.DrawFn) -> dict[str, Any]:
    kind = draw(st.sampled_from(list(GroupKind)))
    changes = draw(st.lists(st.sampled_from(PATHS), min_size=1, max_size=4, unique=True))
    if kind is GroupKind.BEHAVIOR and not any(path.startswith("src/") for path in changes):
        changes.insert(0, PATHS[0])
    creates = draw(st.lists(st.sampled_from(changes), unique=True))
    group: dict[str, Any] = {
        "title": draw(texts),
        "kind": kind,
        "reads": draw(st.lists(st.sampled_from(PATHS), max_size=3, unique=True)),
        "changes": changes,
        "creates": creates,
        "creates_lines": {path: draw(st.integers(1, 400)) for path in creates},
        "implementation": draw(texts),
        "documentation": draw(
            st.none() | texts | st.sampled_from(["SECURITY.md", "docs/TESTING.md"])
        ),
    }
    if kind is GroupKind.OTHER and draw(st.booleans()):
        return {**group, "process": draw(texts)}
    if kind is GroupKind.OTHER:
        return {**group, "verify": draw(st.sampled_from(CHECK_COMMANDS))}
    return {**group, "test": draw(texts), "verify": draw(st.sampled_from(TEST_COMMANDS))}


@st.composite
def _spec(draw: st.DrawFn, capability: str) -> dict[str, Any]:
    scenario = st.fixed_dictionaries({"name": texts, "when": texts, "then": texts})
    requirement = st.fixed_dictionaries(
        {"name": texts, "text": texts, "scenarios": st.lists(scenario, min_size=1, max_size=2)}
    )
    rename = st.fixed_dictionaries({"from_name": texts, "to_name": texts})
    removal = st.fixed_dictionaries(
        {"name": texts, "reason": texts, "migration": st.none() | texts}
    )
    return {
        "capability": capability,
        "purpose": draw(st.none() | texts),
        "added": draw(st.lists(requirement, max_size=2)),
        "modified": draw(st.lists(requirement, max_size=2)),
        "renamed": draw(st.lists(rename, max_size=2)),
        "removed": draw(st.lists(removal, max_size=2)),
    }


@st.composite
def _reference(draw: st.DrawFn) -> dict[str, Any]:
    unchanged = draw(st.booleans())
    return {
        "path": draw(st.sampled_from(PATHS)),
        "kind": draw(st.sampled_from(["", "import", "living spec"])),
        "unchanged": unchanged,
        "reason": draw(texts if unchanged else st.none() | texts),
    }


@st.composite
def _criterion(draw: st.DrawFn) -> dict[str, Any]:
    if draw(st.booleans()):
        return {"criterion": draw(texts), "group": PENDING_PERSON, "reason": draw(texts)}
    return {"criterion": draw(texts), "group": draw(st.integers(1, 5))}


@st.composite
def proposals(draw: st.DrawFn) -> StageProposal:
    """A valid `StageProposal` with groups of each kind, created paths, and unchanged and changed
    references. Its texts hold no mark of the reader, such as a `Verify that` phrase."""
    named = st.fixed_dictionaries({"decision": texts, "reason": texts})
    rejected = st.fixed_dictionaries({"alternative": texts, "evidence": texts})
    weakened = st.fixed_dictionaries({"check": texts, "stopped": texts, "safeguard": texts})
    capabilities = draw(st.lists(st.sampled_from(CAPABILITIES), max_size=3, unique=True))
    return StageProposal.model_validate(
        {
            "summary": "Keep the kind of each group",
            "pull_request_body": draw(texts),
            "why": draw(texts),
            "what_changes": draw(st.lists(texts | st.just(FITS_ONE_PR), min_size=1, max_size=3)),
            "skip_specs": draw(st.booleans()),
            "feasibility": draw(st.lists(texts, min_size=1, max_size=3)),
            "existing_tool": draw(texts),
            "builds_own": draw(st.booleans()),
            "decisions": draw(st.lists(named, max_size=2)),
            "rejected": draw(st.lists(rejected, max_size=2)),
            "specs": [draw(_spec(capability)) for capability in capabilities],
            "groups": draw(st.lists(_group(), min_size=1, max_size=3)),
            "criteria": draw(st.lists(_criterion(), max_size=3)),
            "dependencies": draw(st.lists(texts, max_size=2)),
            "references": draw(st.lists(_reference(), max_size=3)),
            "security": draw(st.just("") | texts),
            "weakened_checks": draw(st.lists(weakened, max_size=1)),
        }
    )


@given(proposals())
def test_no_fact_is_lost(proposal: StageProposal) -> None:
    from devops_cli.roadmap.plan_read import file_facts

    assert read_change(_files(proposal, known=set())) == file_facts(proposal)


@given(proposals())
def test_a_read_plan_is_a_fixed_point(proposal: StageProposal) -> None:
    read = read_change(_files(proposal, known=set()))

    assert read_change(_files(read, known=set())) == read
