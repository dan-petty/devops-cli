"""Mechanical rewrite of refused stage proposals (#4853)."""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

import devops_cli.roadmap.stage.stage as stage_module
import devops_cli.roadmap.stage.stage_rewrite as stage_rewrite_module
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage.stage import StagedChange
from devops_cli.roadmap.stage.stage_findings import StageFinding, stage_finding
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_request import StageRequest
from devops_cli.roadmap.stage.stage_rewrite import apply_mechanical_rewrites
from devops_cli.telemetry.instruments import ROADMAP_FIX_CHECKS_TOTAL
from tests.support.builders import make_stage_proposal
from tests.support.paths import FIXTURES


def _tree(files: list[str]) -> StagedTree:
    return StagedTree(files)


# ── Dependencies finding ──────────────────────────────────────────────────────


def test_dependencies_finding_adds_item_to_dependencies() -> None:
    proposal = make_stage_proposal(dependencies=[])
    text = MESSAGES.roadmap.stage_problem_dependencies.format(
        pull=42, path="src/devops_cli/sample.py"
    )
    finding = stage_finding("dependencies", text)
    tree = _tree(["src/devops_cli/sample.py"])

    with patch.object(stage_rewrite_module, "emit") as mock_emit:
        rewritten, count = apply_mechanical_rewrites(proposal, [finding], tree)

    assert count == 1
    assert any("#42" in d and "src/devops_cli/sample.py" in d for d in rewritten.dependencies)
    mock_emit.assert_called_once_with(
        ROADMAP_FIX_CHECKS_TOTAL, 1, {"site": "stage.gate", "path": "mechanical"}
    )


def test_dependencies_finding_idempotent() -> None:
    proposal = make_stage_proposal(dependencies=["#42: changes `src/devops_cli/sample.py`."])
    text = MESSAGES.roadmap.stage_problem_dependencies.format(
        pull=42, path="src/devops_cli/sample.py"
    )
    finding = stage_finding("dependencies", text)
    tree = _tree(["src/devops_cli/sample.py"])

    with patch.object(stage_rewrite_module, "emit") as mock_emit:
        rewritten, count = apply_mechanical_rewrites(proposal, [finding], tree)

    assert count == 0
    assert rewritten == proposal
    mock_emit.assert_not_called()


# ── Perimeter test finding ───────────────────────────────────────────────────


def test_missing_perimeter_test_adds_test_to_manifest_group_changes() -> None:
    proposal = make_stage_proposal(
        groups=[
            {
                "title": "Change manifest",
                "kind": "manifest",
                "reads": [],
                "changes": ["k8s/values.yaml"],
                "creates": [],
                "creates_lines": {},
                "test": "Check case",
                "implementation": "Update manifest",
                "documentation": None,
                "verify": "uv run devops ci test tests/k8s/test_values.py",
            }
        ]
    )
    manifest = "k8s/values.yaml"
    test_path = "tests/k8s/test_values.py"
    text = MESSAGES.roadmap.stage_problem_missing_perimeter_test.format(
        path=manifest, test=test_path
    )
    finding = stage_finding("paths", text)
    tree = _tree([manifest, test_path])

    with patch.object(stage_rewrite_module, "emit") as mock_emit:
        rewritten, count = apply_mechanical_rewrites(proposal, [finding], tree)

    assert count == 1
    assert test_path in rewritten.groups[0].changes
    mock_emit.assert_called_once_with(
        ROADMAP_FIX_CHECKS_TOTAL, 1, {"site": "stage.gate", "path": "mechanical"}
    )


def test_missing_perimeter_test_skips_when_test_file_absent() -> None:
    proposal = make_stage_proposal(
        groups=[
            {
                "title": "Change manifest",
                "kind": "manifest",
                "reads": [],
                "changes": ["k8s/values.yaml"],
                "creates": [],
                "creates_lines": {},
                "test": "Check case",
                "implementation": "Update manifest",
                "documentation": None,
                "verify": "uv run devops ci test tests/k8s/test_values.py",
            }
        ]
    )
    manifest = "k8s/values.yaml"
    test_path = "tests/k8s/test_values.py"
    text = MESSAGES.roadmap.stage_problem_missing_perimeter_test.format(
        path=manifest, test=test_path
    )
    finding = stage_finding("paths", text)
    tree = _tree([manifest])

    with patch.object(stage_rewrite_module, "emit") as mock_emit:
        rewritten, count = apply_mechanical_rewrites(proposal, [finding], tree)

    assert count == 0
    assert rewritten == proposal
    mock_emit.assert_not_called()


# ── Module test finding ───────────────────────────────────────────────────────


def test_missing_module_test_adds_test_to_group_reads() -> None:
    proposal = make_stage_proposal()
    text = MESSAGES.roadmap.stage_problem_missing_module_test.format(
        group=1, path="src/devops_cli/sample.py", test="tests/test_existing_sample.py"
    )
    finding = stage_finding("paths", text)
    tree = _tree(["src/devops_cli/sample.py", "tests/test_existing_sample.py"])

    with patch.object(stage_rewrite_module, "emit") as mock_emit:
        rewritten, count = apply_mechanical_rewrites(proposal, [finding], tree)

    assert count == 1
    assert "tests/test_existing_sample.py" in rewritten.groups[0].reads
    mock_emit.assert_called_once_with(
        ROADMAP_FIX_CHECKS_TOTAL, 1, {"site": "stage.gate", "path": "mechanical"}
    )


def test_missing_module_test_skips_when_test_file_absent() -> None:
    proposal = make_stage_proposal()
    text = MESSAGES.roadmap.stage_problem_missing_module_test.format(
        group=1, path="src/devops_cli/sample.py", test="tests/test_nonexistent.py"
    )
    finding = stage_finding("paths", text)
    tree = _tree(["src/devops_cli/sample.py"])

    with patch.object(stage_rewrite_module, "emit") as mock_emit:
        rewritten, count = apply_mechanical_rewrites(proposal, [finding], tree)

    assert count == 0
    assert rewritten == proposal
    mock_emit.assert_not_called()


# ── Registry finding ──────────────────────────────────────────────────────────


def test_registry_finding_adds_task_for_declared_path() -> None:
    proposal = make_stage_proposal()
    doc_path = "docs/CLI_REFERENCE.md"
    declaring = "src/devops_cli/sample.py:10"
    text = MESSAGES.roadmap.stage_problem_registry.format(
        token="SAMPLE_TOKEN", path=doc_path, location=declaring
    )
    finding = stage_finding("registry", text)
    tree = _tree(["src/devops_cli/sample.py", doc_path])

    with patch.object(stage_rewrite_module, "emit") as mock_emit:
        rewritten, count = apply_mechanical_rewrites(proposal, [finding], tree)

    assert count == 1
    assert doc_path in (rewritten.groups[0].documentation or "")
    mock_emit.assert_called_once_with(
        ROADMAP_FIX_CHECKS_TOTAL, 1, {"site": "stage.gate", "path": "mechanical"}
    )


def test_registry_finding_skips_when_declared_path_absent() -> None:
    proposal = make_stage_proposal()
    doc_path = "docs/NONEXISTENT.md"
    declaring = "src/devops_cli/sample.py:10"
    text = MESSAGES.roadmap.stage_problem_registry.format(
        token="SAMPLE_TOKEN", path=doc_path, location=declaring
    )
    finding = stage_finding("registry", text)
    tree = _tree(["src/devops_cli/sample.py"])

    with patch.object(stage_rewrite_module, "emit") as mock_emit:
        rewritten, count = apply_mechanical_rewrites(proposal, [finding], tree)

    assert count == 0
    assert rewritten == proposal
    mock_emit.assert_not_called()


# ── No edit outside finding ───────────────────────────────────────────────────


def test_diff_touches_only_lines_of_the_finding() -> None:
    proposal = make_stage_proposal(dependencies=[])
    text = MESSAGES.roadmap.stage_problem_dependencies.format(
        pull=99, path="src/devops_cli/sample.py"
    )
    finding = stage_finding("dependencies", text)
    tree = _tree(["src/devops_cli/sample.py"])

    rewritten, count = apply_mechanical_rewrites(proposal, [finding], tree)
    assert count == 1
    dump_before = proposal.model_dump()
    dump_after = rewritten.model_dump()
    for key in dump_before:
        if key == "dependencies":
            continue
        assert dump_before[key] == dump_after[key]


# ── Logging ───────────────────────────────────────────────────────────────────


def test_log_names_code_and_edited_path(caplog: pytest.LogCaptureFixture) -> None:
    proposal = make_stage_proposal(dependencies=[])
    text = MESSAGES.roadmap.stage_problem_dependencies.format(
        pull=99, path="src/devops_cli/sample.py"
    )
    finding = stage_finding("dependencies", text)
    tree = _tree(["src/devops_cli/sample.py"])

    with caplog.at_level(logging.INFO):
        apply_mechanical_rewrites(proposal, [finding], tree)

    assert any(
        "stage_problem_dependencies" in record.message
        and "src/devops_cli/sample.py" in record.message
        for record in caplog.records
    )


# ── Stage Planner Rewrite Loop ────────────────────────────────────────────────


def test_planner_rewrite_mechanical_rewrites_and_passes_with_no_model_return() -> None:
    planner = stage_module._Planner.__new__(stage_module._Planner)
    target = MagicMock()
    proposal = make_stage_proposal(dependencies=[])
    request = MagicMock(spec=StageRequest)

    text = MESSAGES.roadmap.stage_problem_dependencies.format(
        pull=42, path="src/devops_cli/sample.py"
    )
    finding = stage_finding("dependencies", text)
    problem_key = "some_refusal_problem"
    initial_outcome = stage_module._Refused(problem=problem_key, reply=proposal)

    staged_success = MagicMock(spec=StagedChange)

    planner._findings = {problem_key: (finding,)}
    planner._tree_of = MagicMock(return_value=_tree(["src/devops_cli/sample.py"]))
    planner._trace_facts = MagicMock(return_value=())
    planner._settle = MagicMock(return_value=staged_success)

    final_proposal, final_outcome = planner._rewrite_mechanical(
        target, proposal, request, initial_outcome
    )

    assert final_outcome is staged_success
    assert any("#42" in d for d in final_proposal.dependencies)
    assert planner._settle.call_count == 1


def test_planner_rewrite_mechanical_bounds_passes_to_two() -> None:
    planner = stage_module._Planner.__new__(stage_module._Planner)
    target = MagicMock()
    proposal = make_stage_proposal(dependencies=[])
    request = MagicMock(spec=StageRequest)

    text = MESSAGES.roadmap.stage_problem_dependencies.format(
        pull=42, path="src/devops_cli/sample.py"
    )
    finding = stage_finding("dependencies", text)
    problem_key = "persisting_problem"
    outcome = stage_module._Refused(problem=problem_key, reply=proposal)

    planner._findings = {problem_key: (finding,)}
    planner._tree_of = MagicMock(return_value=_tree(["src/devops_cli/sample.py"]))
    planner._trace_facts = MagicMock(return_value=())
    # Settle always returns _Refused with persisting_problem
    planner._settle = MagicMock(return_value=outcome)

    _final_proposal, final_outcome = planner._rewrite_mechanical(target, proposal, request, outcome)

    assert isinstance(final_outcome, stage_module._Refused)
    # At most 2 settle calls
    assert planner._settle.call_count <= 2


def test_planner_rewrite_mechanical_skips_when_no_mechanical_findings() -> None:
    planner = stage_module._Planner.__new__(stage_module._Planner)
    target = MagicMock()
    proposal = make_stage_proposal()
    request = MagicMock(spec=StageRequest)

    # Finding with non-mechanical code
    finding = stage_finding("paths", "Unknown untracked problem.")
    problem_key = "model_problem"
    outcome = stage_module._Refused(problem=problem_key, reply=proposal)

    planner._findings = {problem_key: (finding,)}
    planner._tree_of = MagicMock(return_value=_tree([]))
    planner._trace_facts = MagicMock(return_value=())
    planner._settle = MagicMock()

    _final_proposal, final_outcome = planner._rewrite_mechanical(target, proposal, request, outcome)

    assert final_outcome is outcome
    assert planner._settle.call_count == 0


def test_saved_refused_records_mechanical_findings() -> None:
    saved = json.loads(
        (FIXTURES / "roadmap" / "stage_refused_findings.json").read_text(encoding="utf-8")
    )
    registry_findings = []
    module_test_findings = []
    for plan in saved["plans"]:
        for reply in plan["replies"]:
            for gate, text in reply:
                f = stage_finding(gate, text)
                if f.code == "stage_problem_registry":
                    registry_findings.append(f)
                elif f.code == "stage_problem_missing_module_test":
                    module_test_findings.append(f)

    assert len(registry_findings) == 4
    assert len(module_test_findings) > 0

    tree = StagedTree(["tests/roadmap/test_roadmap_limit_classes.py"])
    for f in registry_findings:
        proposal = make_stage_proposal()
        rewritten, count = apply_mechanical_rewrites(proposal, [f], tree)
        assert count == 1
        assert "tests/roadmap/test_roadmap_limit_classes.py" in (
            rewritten.groups[0].documentation or ""
        )


def test_mechanical_rewrite_edge_cases_and_idempotency() -> None:
    proposal = make_stage_proposal()
    tree = _tree(["src/devops_cli/sample.py", "docs/CLI_REFERENCE.md", "tests/test_sample.py"])

    # 1. Non-mechanical finding code
    non_mech = StageFinding(
        gate="groups", code="stage_problem_criterion", text="Criterion not mapped."
    )
    assert apply_mechanical_rewrites(proposal, [non_mech], tree)[1] == 0

    # 2. Dependencies unmatching text
    dep_unmatched = StageFinding(
        gate="dependencies", code="stage_problem_dependencies", text="malformed"
    )
    assert apply_mechanical_rewrites(proposal, [dep_unmatched], tree)[1] == 0

    # 3. Perimeter test unmatching text
    perim_unmatched = StageFinding(
        gate="paths", code="stage_problem_missing_perimeter_test", text="malformed"
    )
    assert apply_mechanical_rewrites(proposal, [perim_unmatched], tree)[1] == 0

    # 4. Perimeter test path not changed in any group
    text_perim_no_group = MESSAGES.roadmap.stage_problem_missing_perimeter_test.format(
        path="k8s/other.yaml", test="tests/test_sample.py"
    )
    finding_perim_no_group = stage_finding("paths", text_perim_no_group)
    assert (
        apply_mechanical_rewrites(
            proposal, [finding_perim_no_group], _tree(["k8s/other.yaml", "tests/test_sample.py"])
        )[1]
        == 0
    )

    # 5. Module test unmatching text
    mod_unmatched = StageFinding(
        gate="paths", code="stage_problem_missing_module_test", text="malformed"
    )
    assert apply_mechanical_rewrites(proposal, [mod_unmatched], tree)[1] == 0

    # 6. Module test already in group.reads
    proposal_with_reads = make_stage_proposal()
    proposal_with_reads.groups[0].reads.append("tests/test_sample.py")
    text_mod_read = MESSAGES.roadmap.stage_problem_missing_module_test.format(
        group=1, path="src/devops_cli/sample.py", test="tests/test_sample.py"
    )
    finding_mod_read = stage_finding("paths", text_mod_read)
    assert apply_mechanical_rewrites(proposal_with_reads, [finding_mod_read], tree)[1] == 0

    # 7. Registry finding without path
    finding_no_path = StageFinding(
        gate="registry",
        code="stage_problem_registry",
        path=None,
        text=MESSAGES.roadmap.stage_problem_registry.format(
            token="SAMPLE_TOKEN",
            path="docs/CLI_REFERENCE.md",
            location="src/devops_cli/sample.py:10",
        ),
    )
    rewritten, count = apply_mechanical_rewrites(proposal, [finding_no_path], tree)
    assert count == 1
    assert "docs/CLI_REFERENCE.md" in (rewritten.groups[0].documentation or "")

    # 8. Registry path already mentioned in task documentation
    proposal_with_doc = make_stage_proposal()
    proposal_with_doc.groups[0].documentation = "Already mentions docs/CLI_REFERENCE.md."
    assert apply_mechanical_rewrites(proposal_with_doc, [finding_no_path], tree)[1] == 0

    # 9. Registry target group has existing documentation (not None)
    proposal_doc_append = make_stage_proposal()
    proposal_doc_append.groups[0].documentation = "Existing documentation text."
    rewritten_doc, count = apply_mechanical_rewrites(proposal_doc_append, [finding_no_path], tree)
    assert count == 1
    assert (
        rewritten_doc.groups[0].documentation
        == "Existing documentation text. Update `docs/CLI_REFERENCE.md`"
    )
