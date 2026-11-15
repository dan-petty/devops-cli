"""`devops roadmap step scaffold`: doc invariants for scaffold resume rules (#5499)."""

from __future__ import annotations

from devops_cli.roadmap.steps.scaffold import ScaffoldResult
from devops_cli.roadmap.stores.store import ScaffoldRecordKey
from tests.support.paths import REPO_ROOT

STAGE_DOC = REPO_ROOT / "docs" / "roadmap" / "stage.md"
WORKFLOW_DOC = REPO_ROOT / "docs" / "ROADMAP_WORKFLOW.md"

REQUIRED_RESULTS = tuple(result.value for result in ScaffoldResult)


def test_stage_doc_states_scaffold_resume_rules() -> None:
    """`docs/roadmap/stage.md` states the scaffold resume rules and results."""
    text = STAGE_DOC.read_text(encoding="utf-8")
    assert "scaffold" in text
    for result in REQUIRED_RESULTS:
        assert f"`{result}`" in text or result in text


def test_workflow_doc_states_scaffold_branch_and_resume_rules() -> None:
    """`docs/ROADMAP_WORKFLOW.md` states `scaffold.branch` and the resume rules."""
    text = WORKFLOW_DOC.read_text(encoding="utf-8")
    assert f"`{ScaffoldRecordKey.BRANCH.value}`" in text
    for result in REQUIRED_RESULTS:
        assert f"`{result}`" in text or result in text
