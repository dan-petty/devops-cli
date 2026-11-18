"""Unit tests for delivery pull request title and Conventional Commit type derivation (#4127)."""

from __future__ import annotations

from pathlib import Path

from devops_cli.roadmap.implement.implement_run import (
    plan_commit_type,
    proposal_summary,
)
from devops_cli.roadmap.stage.stage_change import delivery_title

DECLARED = {
    "scope/roadmap",
    "scope/k8s",
    "type/test",
    "type/infra",
    "type/bug",
    "type/docs",
    "type/ci",
    "type/feat",
}


def test_plan_commit_type_test_only() -> None:
    """A plan that changes only paths under tests/ uses test."""
    paths = [
        "tests/roadmap/stage/test_roadmap_stage_eval_gates.py",
        "openspec/changes/archive/2026-11-08-4057-cache-registry-table-in-stage-eval/proposal.md",
        "openspec/changes/archive/2026-11-08-4057-cache-registry-table-in-stage-eval/tasks.md",
    ]
    assert plan_commit_type(paths, "perf") == "test"


def test_plan_commit_type_docs_only() -> None:
    """A plan that changes only docs/, openspec/ or markdown files uses docs."""
    paths = [
        "docs/roadmap/guide.md",
        "openspec/specs/roadmap/spec.md",
        "README.md",
    ]
    assert plan_commit_type(paths, "feat") == "docs"


def test_plan_commit_type_ci_only() -> None:
    """A plan that changes only .github/workflows/ or .github/actions/ uses ci."""
    paths = [
        ".github/workflows/ci.yml",
        ".github/actions/setup-python/action.yml",
    ]
    assert plan_commit_type(paths, "fix") == "ci"


def test_plan_commit_type_mixed_paths_keeps_issue_type() -> None:
    """Any other set of paths keeps the issue title type."""
    paths = [
        "src/devops_cli/roadmap/stage/stage_change.py",
        "tests/roadmap/stage/test_roadmap_stage_title.py",
    ]
    assert plan_commit_type(paths, "perf") == "perf"


def test_plan_commit_type_empty_paths() -> None:
    """Empty paths keep the issue type."""
    assert plan_commit_type([], "feat") == "feat"
    assert plan_commit_type(["openspec/changes/foo/tasks.md"], "fix") == "fix"


def test_plan_commit_type_none_issue_type() -> None:
    """None issue type returns None."""
    assert plan_commit_type(["tests/roadmap/test_job.py"], None) is None


def test_proposal_summary_from_summary_section(tmp_path: Path) -> None:
    """The summary comes from the first non-empty line of the ## Summary section."""
    proposal = tmp_path / "proposal.md"
    proposal.write_text(
        "# Proposal\n\n## Summary\n\npin a single registry read\n\n## What Changes\n\n- Add two regression tests\n",
        encoding="utf-8",
    )
    assert proposal_summary(proposal) == "pin a single registry read"
    assert proposal_summary(proposal, section="changes") == "Add two regression tests"


def test_proposal_summary_nonexistent_file() -> None:
    """Non-existent file returns None."""
    assert proposal_summary(Path("nonexistent_proposal.md")) is None


def test_proposal_summary_fallback_to_what_changes(tmp_path: Path) -> None:
    """The summary falls back to the first bullet of ## What Changes when ## Summary is missing."""
    proposal = tmp_path / "proposal.md"
    proposal.write_text(
        "# Proposal\n\n## Why\n\nSome reason\n\n## What Changes\n\n- Add two regression tests\n- Second change\n",
        encoding="utf-8",
    )
    assert proposal_summary(proposal) == "Add two regression tests"


def test_proposal_summary_none_when_both_missing(tmp_path: Path) -> None:
    """None is returned when neither ## Summary nor ## What Changes has usable text."""
    proposal = tmp_path / "proposal.md"
    proposal.write_text("# Proposal\n\n## Why\n\nSome reason\n", encoding="utf-8")
    assert proposal_summary(proposal) is None


def test_delivery_title_with_derived_type_and_summary() -> None:
    """delivery_title combines the derived Conventional Commit type, declared scope, and summary."""
    title = delivery_title(
        "perf(roadmap): cache registry_table in stage eval replay",
        DECLARED,
        summary="pin a single registry read",
        commit_type="test",
    )
    assert title == "test(roadmap): pin a single registry read"


def test_delivery_title_without_summary_uses_issue_summary() -> None:
    """delivery_title preserves the issue summary when summary is None."""
    title = delivery_title(
        "perf(roadmap): cache registry_table in stage eval replay",
        DECLARED,
        commit_type="test",
    )
    assert title == "test(roadmap): cache registry_table in stage eval replay"


def test_delivery_title_drops_undeclared_scope() -> None:
    """delivery_title drops a scope that is not in declared labels."""
    title = delivery_title(
        "perf(floor): cache registry_table in stage eval replay",
        DECLARED,
        summary="pin a single registry read",
        commit_type="test",
    )
    assert title == "test: pin a single registry read"


def test_delivery_title_keeps_unlisted_issue_type_when_commit_type_is_none() -> None:
    """delivery_title keeps unlisted issue type when commit_type is None."""
    title = delivery_title(
        "wip(cli): add a flag",
        DECLARED,
        summary="add a flag",
        commit_type=None,
    )
    assert title == "wip(cli): add a flag"


def test_delivery_title_strips_exclamation() -> None:
    """delivery_title strips exclamation from breaking change."""
    title = delivery_title(
        "feat(roadmap)!: breaking change",
        DECLARED,
        summary="breaking change",
        commit_type="feat",
    )
    assert title == "feat(roadmap): breaking change"
