"""The stage job writes and checks RENAMED and REMOVED spec deltas (#5340).

A plan that changes the meaning of a requirement renames it, and a plan that makes a requirement
false removes it. Plan #5182 could do neither: it kept the old name above a text that says the
opposite, and its delivery merged that name into the living spec. The real plan of #5182 is the
fixture of the rename here.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import isolated_openspec
from devops_cli.roadmap.plan_read import read_change
from devops_cli.roadmap.stage.stage_change import (
    StageProposal,
    StageRemoval,
    StageRename,
    StageSpec,
    check_proposal,
    render_change,
    spec_file,
    spec_file_path,
)
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_validate import restore_omitted_scenarios, validate_change
from tests.support.builders import make_stage_proposal
from tests.support.paths import REPO_ROOT

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

CREATED = date(2026, 11, 13)
TREE = StagedTree(["src/devops_cli/sample.py", "tests/test_sample.py"])
CAPABILITY = "comment-thread"
OLD = "The job keeps the last comment"
NEW = "The job keeps every comment of a thread"
OTHER = "The job reads each thread once"
# The change folder of plan pull request #5182 at its head 5209df86045d.
PLAN_5182 = REPO_ROOT / "tests" / "fixtures" / "roadmap" / "plan_heads" / "5182-5209df86045d"
# A name of the #5182 requirement that fits the text that the plan gives it.
FITTING_NAME = "The alloy-profiles pod runs on every node"


def _scenario(name: str = "The last comment") -> dict[str, str]:
    return {"name": name, "when": "a thread has two comments", "then": "both comments are kept"}


def _requirement(name: str, *scenarios: str) -> dict[str, Any]:
    return {
        "name": name,
        "text": "The job SHALL keep every comment of a thread.",
        "scenarios": [_scenario(s) for s in scenarios or ("The last comment",)],
    }


def _spec(**fields: Any) -> dict[str, Any]:
    return {"capability": CAPABILITY, "purpose": None, **fields}


def _problems(
    spec: dict[str, Any],
    *,
    known: Sequence[str] = (CAPABILITY,),
    requirements: Mapping[str, Sequence[str]] | None = None,
    requirement_texts: Mapping[str, Mapping[str, str]] | None = None,
) -> list[str]:
    return check_proposal(
        make_stage_proposal(specs=[spec]),
        known,
        TREE,
        requirements=requirements,
        requirement_texts=requirement_texts,
        registry=(),
    )


# ── The delta file ────────────────────────────────────────────────────────────


def test_a_rename_renders_a_renamed_block() -> None:
    spec = StageSpec.model_validate(
        _spec(renamed=[{"from_name": OLD, "to_name": NEW}], modified=[_requirement(NEW)])
    )

    text = spec_file(spec)

    assert text.endswith(
        "## RENAMED Requirements\n\n"
        f"- FROM: `### Requirement: {OLD}`\n"
        f"- TO: `### Requirement: {NEW}`\n"
    )
    assert text.index("## MODIFIED Requirements") < text.index("## RENAMED Requirements")


def test_a_removal_renders_a_removed_block_with_its_reason_and_migration() -> None:
    spec = StageSpec.model_validate(
        _spec(
            removed=[
                {"name": OLD, "reason": "The job keeps every comment now.", "migration": None},
                {"name": OTHER, "reason": "The job reads a thread again.", "migration": "Read X."},
            ]
        )
    )

    assert spec_file(spec) == (
        "## REMOVED Requirements\n\n"
        f"### Requirement: {OLD}\n**Reason**: The job keeps every comment now.\n\n"
        f"### Requirement: {OTHER}\n**Reason**: The job reads a thread again.\n"
        "**Migration**: Read X.\n"
    )


def test_a_plan_with_no_rename_and_no_removal_renders_neither_section() -> None:
    text = spec_file(make_stage_proposal().specs[0])

    assert "## RENAMED" not in text
    assert "## REMOVED" not in text


def test_the_capabilities_of_the_proposal_list_the_renamed_and_removed_names() -> None:
    spec = _spec(
        renamed=[{"from_name": OLD, "to_name": NEW}],
        modified=[_requirement(NEW)],
        removed=[{"name": OTHER, "reason": "The job reads a thread again."}],
    )

    files = render_change("1-x", make_stage_proposal(specs=[spec]), [CAPABILITY], created=CREATED)

    assert f"- `{CAPABILITY}`: {NEW}, {OTHER}" in files["openspec/changes/1-x/proposal.md"]


# ── The real OpenSpec validation ──────────────────────────────────────────────


def _plan_5182() -> tuple[str, dict[str, str]]:
    """The name and the files of the change folder of plan #5182, by path from the root."""
    files = {
        f"openspec/changes/{path.relative_to(PLAN_5182).as_posix()}": path.read_text("utf-8")
        for path in PLAN_5182.rglob("*")
        if path.is_file()
    }
    (change,) = {path.split("/")[2] for path in files}
    return change, files


def _write_base(source: Path, capability: str, requirements: str) -> None:
    """A checkout at `source` whose base spec of `capability` holds `requirements`."""
    (source / "openspec").mkdir(parents=True, exist_ok=True)
    (source / "openspec" / "config.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
    path = source / "openspec" / "specs" / capability / "spec.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {capability} Specification\n\n## Purpose\n"
        "The base spec of the capability, with a purpose long enough for the check.\n\n"
        f"## Requirements\n\n{requirements}",
        encoding="utf-8",
    )


def _renamed_5182(*, rename: bool) -> tuple[str, StageProposal, str, str]:
    """The change, the plan of #5182 with its modified requirement under a fitting name, the
    capability, and the requirement block of the plan as the base spec held it. `rename` adds the
    RENAMED entry from the old name."""
    change, files = _plan_5182()
    plan = read_change(files)
    (spec,) = plan.specs
    (requirement,) = spec.modified
    delta = files[spec_file_path(change, spec.capability)]
    base_block = delta.split("## MODIFIED Requirements", 1)[1].lstrip()
    renamed = spec.model_copy(
        update={
            "renamed": [StageRename(from_name=requirement.name, to_name=FITTING_NAME)]
            if rename
            else [],
            "modified": [requirement.model_copy(update={"name": FITTING_NAME})],
        }
    )
    return change, plan.model_copy(update={"specs": [renamed]}), spec.capability, base_block


@pytest.mark.live("openspec")
@pytest.mark.parametrize("rename", [True, False])
def test_the_plan_of_5182_with_a_rename_passes_the_pinned_openspec(
    tmp_path: Path, *, rename: bool
) -> None:
    change, plan, capability, base_block = _renamed_5182(rename=rename)
    _write_base(tmp_path, capability, base_block)
    files = render_change(change, plan, [capability], created=CREATED)

    with isolated_openspec() as tool:
        problem = validate_change(tool, tmp_path, change, files)

    delta = files[spec_file_path(change, capability)]
    assert ("## RENAMED Requirements" in delta, problem is None) == (rename, rename)


@pytest.mark.live("openspec")
def test_a_removal_passes_the_pinned_openspec(tmp_path: Path) -> None:
    _write_base(
        tmp_path,
        CAPABILITY,
        f"### Requirement: {OLD}\nThe job SHALL keep the last comment.\n\n"
        "#### Scenario: One\n- **WHEN** a\n- **THEN** b\n\n"
        f"### Requirement: {OTHER}\nThe job SHALL read each thread once.\n\n"
        "#### Scenario: Two\n- **WHEN** c\n- **THEN** d\n",
    )
    spec = _spec(
        removed=[{"name": OLD, "reason": "The job keeps every comment.", "migration": "Read Y."}]
    )
    files = render_change("1-x", make_stage_proposal(specs=[spec]), [CAPABILITY], created=CREATED)

    with isolated_openspec() as tool:
        problem = validate_change(tool, tmp_path, "1-x", files)

    assert problem is None


@pytest.mark.live("openspec")
def test_a_renamed_requirement_gets_the_base_scenario_that_it_omits(tmp_path: Path) -> None:
    _write_base(
        tmp_path,
        CAPABILITY,
        f"### Requirement: {OLD}\nThe job SHALL keep the last comment.\n\n"
        "#### Scenario: First\n- **WHEN** a\n- **THEN** b\n\n"
        "#### Scenario: Second\n- **WHEN** c\n- **THEN** d\n",
    )
    spec = _spec(
        renamed=[{"from_name": OLD, "to_name": NEW}], modified=[_requirement(NEW, "First")]
    )
    proposal = make_stage_proposal(specs=[spec])
    files = render_change("1-x", proposal, [CAPABILITY], created=CREATED)

    with isolated_openspec() as tool:
        restored = restore_omitted_scenarios(tool, tmp_path, "1-x", proposal, files)
        problem = validate_change(tool, tmp_path, "1-x", restored)

    assert (
        "#### Scenario: Second\n- **WHEN** c\n- **THEN** d"
        in restored[spec_file_path("1-x", CAPABILITY)]
    )
    assert problem is None


# ── The gate ──────────────────────────────────────────────────────────────────

BASE = {CAPABILITY: (OLD, OTHER)}


def test_a_valid_rename_and_removal_pass_the_gate() -> None:
    spec = _spec(
        renamed=[{"from_name": OLD, "to_name": NEW}],
        modified=[_requirement(NEW)],
        removed=[{"name": OTHER, "reason": "The job reads a thread again."}],
    )

    assert _problems(spec, requirements=BASE) == []


def test_a_rename_of_a_requirement_that_the_base_spec_lacks_is_refused() -> None:
    spec = _spec(renamed=[{"from_name": "The job stages two items", "to_name": NEW}])

    assert _problems(spec, requirements=BASE) == [
        MESSAGES.roadmap.stage_problem_rename_unknown.format(
            requirement="The job stages two items", capability=CAPABILITY
        )
    ]


def test_a_new_name_that_the_base_spec_has_is_refused() -> None:
    spec = _spec(renamed=[{"from_name": OLD, "to_name": OTHER}])

    assert _problems(spec, requirements=BASE) == [
        MESSAGES.roadmap.stage_problem_rename_taken.format(requirement=OTHER, capability=CAPABILITY)
    ]


def test_a_removal_of_a_requirement_that_the_base_spec_lacks_is_refused() -> None:
    spec = _spec(removed=[{"name": NEW, "reason": "The job keeps every comment."}])

    assert _problems(spec, requirements=BASE) == [
        MESSAGES.roadmap.stage_problem_remove_unknown.format(requirement=NEW, capability=CAPABILITY)
    ]


@pytest.mark.parametrize(
    "fields",
    [
        {"renamed": [{"from_name": OLD, "to_name": NEW}]},
        {"removed": [{"name": OLD, "reason": "The job keeps every comment."}]},
    ],
)
def test_a_rename_or_a_removal_on_a_new_capability_is_refused(fields: dict[str, Any]) -> None:
    purpose = "Defines how the job reads the comments of a thread, so none is lost."
    spec = {**_spec(**fields), "purpose": purpose}

    assert _problems(spec, known=()) == [
        MESSAGES.roadmap.stage_problem_modified.format(capability=CAPABILITY)
    ]


def test_a_caller_with_no_requirement_names_judges_no_base_name() -> None:
    spec = _spec(
        renamed=[{"from_name": "Any name", "to_name": NEW}],
        removed=[{"name": "Another name", "reason": "The job keeps every comment."}],
    )

    assert _problems(spec) == []


# ── A base requirement that names a removed command (#3287) ───────────────────

INTAKE_EVAL = "devops roadmap intake-eval"
STALE = "The intake-eval command runs each case"
STALE_TEXTS = {CAPABILITY: {STALE: f"`{INTAKE_EVAL}` SHALL run each case of the folder."}}
REMOVAL = {
    "name": "The old command is gone",
    "text": f"The `{INTAKE_EVAL}` command MUST NOT exist.",
    "scenarios": [_scenario()],
}
REWRITTEN = "The eval intake command runs each case"


@pytest.mark.parametrize(
    "fields",
    [
        {"removed": [{"name": STALE, "reason": "The command is gone."}]},
        {
            "renamed": [{"from_name": STALE, "to_name": REWRITTEN}],
            "modified": [
                {
                    "name": REWRITTEN,
                    "text": "The `devops roadmap eval intake` command SHALL run each case.",
                    "scenarios": [_scenario()],
                }
            ],
        },
    ],
    ids=["removed", "renamed-and-modified"],
)
def test_a_removed_or_rewritten_base_requirement_is_no_stale_command(
    fields: dict[str, Any],
) -> None:
    spec = _spec(added=[REMOVAL], **fields)

    assert _problems(spec, requirements={CAPABILITY: (STALE,)}, requirement_texts=STALE_TEXTS) == []


def test_a_renamed_base_requirement_with_its_old_text_names_the_stale_command() -> None:
    spec = _spec(added=[REMOVAL], renamed=[{"from_name": STALE, "to_name": REWRITTEN}])

    assert _problems(spec, requirements={CAPABILITY: (STALE,)}, requirement_texts=STALE_TEXTS) == [
        MESSAGES.roadmap.stage_problem_stale_command.format(
            requirement=STALE, capability=CAPABILITY, command=INTAKE_EVAL
        )
    ]


def test_the_models_refuse_an_empty_name_and_a_missing_reason() -> None:
    with pytest.raises(ValidationError, match="to_name"):
        StageRename.model_validate({"from_name": OLD, "to_name": " "})
    with pytest.raises(ValidationError, match="reason"):
        StageRemoval.model_validate({"name": OLD})
