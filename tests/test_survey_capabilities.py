"""Tests for comparable tools capability comparison, citation rules, and gap detection."""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from devops_cli.roadmap.intake_model import ModelProposal, ProposalRequest
from devops_cli.survey.capabilities import (
    compare_capabilities,
    find_capability_gaps,
    load_survey_config,
)
from devops_cli.survey.models import CapabilityComparison, CapabilityGap, CapabilityStatus
from tests.support.paths import REPO_ROOT


def test_load_survey_config_and_compare_capabilities() -> None:
    """Configured capabilities are compared across devops-cli and comparable tools."""
    config_toml = """
    [[tools]]
    name = "gh"
    description = "GitHub CLI"
    url = "https://cli.github.com"

    [[capabilities]]
    name = "pr-review"
    description = "Interactive code review for pull requests"
    devops_cli = "present"
    citation = "devops review pr"

    [[capabilities.comparable]]
    tool = "gh"
    status = "present"
    citation = "https://cli.github.com/manual/gh_pr_review"

    [[capabilities]]
    name = "issue-pinning"
    description = "Pin an issue in a repository"
    devops_cli = "absent"
    citation = "N/A"

    [[capabilities.comparable]]
    tool = "gh"
    status = "present"
    citation = "https://cli.github.com/manual/gh_issue_pin"
    """
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
        f.write(config_toml)
        config_path = Path(f.name)

    try:
        config = load_survey_config(config_path)
        comparisons = compare_capabilities(config)

        assert len(comparisons) == 2
        for comp in comparisons:
            assert isinstance(comp, CapabilityComparison)
            assert comp.citation != ""
            assert comp.devops_cli_status in (
                CapabilityStatus.PRESENT,
                CapabilityStatus.ABSENT,
                CapabilityStatus.UNKNOWN,
            )
            assert comp.tool_status in (
                CapabilityStatus.PRESENT,
                CapabilityStatus.ABSENT,
                CapabilityStatus.UNKNOWN,
            )

        pinning = next(c for c in comparisons if c.capability == "issue-pinning")
        assert pinning.devops_cli_status == CapabilityStatus.ABSENT
        assert pinning.tool_status == CapabilityStatus.PRESENT
        assert pinning.is_gap is True
    finally:
        config_path.unlink(missing_ok=True)


def test_unassessed_capability_records_as_unknown_never_absent() -> None:
    """A capability unassessed for a comparable tool reports unknown status, never absent."""
    config_toml = """
    [[tools]]
    name = "k9s"
    description = "Kubernetes CLI UI"
    url = "https://k9scli.io"

    [[capabilities]]
    name = "arbitrary-benchmark"
    description = "LLM gateway benchmarking"
    devops_cli = "present"
    citation = "devops ai benchmark"
    # Note: no k9s assessment provided under capabilities.comparable
    """
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
        f.write(config_toml)
        config_path = Path(f.name)

    try:
        config = load_survey_config(config_path)
        comparisons = compare_capabilities(config)

        assert len(comparisons) == 1
        k9s_row = comparisons[0]
        assert k9s_row.tool == "k9s"
        assert k9s_row.tool_status == CapabilityStatus.UNKNOWN
        assert k9s_row.citation != ""
    finally:
        config_path.unlink(missing_ok=True)


def test_every_comparable_tool_row_carries_citation() -> None:
    """Every capability row for a comparable tool carries a citation field."""
    config_toml = """
    [[tools]]
    name = "glab"
    description = "GitLab CLI"
    url = "https://gitlab.com/gitlab-org/cli"

    [[capabilities]]
    name = "mr-view"
    description = "View merge requests"
    devops_cli = "absent"
    citation = "N/A"

    [[capabilities.comparable]]
    tool = "glab"
    status = "present"
    citation = "https://docs.gitlab.com/ee/editor_extensions/gitlab_cli/"
    """
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
        f.write(config_toml)
        config_path = Path(f.name)

    try:
        config = load_survey_config(config_path)
        comparisons = compare_capabilities(config)
        assert all(bool(row.citation) for row in comparisons)
    finally:
        config_path.unlink(missing_ok=True)


def test_find_capability_gaps_identifies_missing_features() -> None:
    """Capability gaps are features present in a comparable tool and absent in devops-cli."""
    rows = [
        CapabilityComparison(
            capability="feature-a",
            tool="tool-1",
            devops_cli_status=CapabilityStatus.ABSENT,
            tool_status=CapabilityStatus.PRESENT,
            citation="https://example.com/a",
            is_gap=True,
            description="Feature A",
        ),
        CapabilityComparison(
            capability="feature-b",
            tool="tool-1",
            devops_cli_status=CapabilityStatus.PRESENT,
            tool_status=CapabilityStatus.PRESENT,
            citation="https://example.com/b",
            is_gap=False,
            description="Feature B",
        ),
        CapabilityComparison(
            capability="feature-c",
            tool="tool-1",
            devops_cli_status=CapabilityStatus.ABSENT,
            tool_status=CapabilityStatus.UNKNOWN,
            citation="https://example.com/c",
            is_gap=False,
            description="Feature C",
        ),
    ]
    gaps = find_capability_gaps(rows)
    assert len(gaps) == 1
    assert gaps[0].capability == "feature-a"
    assert gaps[0].citation == "https://example.com/a"


class _FakeIntakeModel:
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    def propose(self, request: ProposalRequest) -> ModelProposal:
        return ModelProposal.model_validate(
            {
                "type": "type/feature",
                "type_reason": "adds a capability",
                "priority": "P2-Medium",
                "priority_reason": "standard priority",
                "value": "Medium",
                "value_reason": "improves parity",
                "effort": "Low",
                "effort_reason": "manageable",
            }
        )


def test_emit_gap_to_intake_creates_candidate(roadmap_store: Any) -> None:
    """Emitting a capability gap generates a NewCandidate for roadmap intake."""
    from devops_cli.survey.intake import emit_gap_to_intake

    labels_content = (REPO_ROOT / ".github" / "labels.yml").read_text(encoding="utf-8")
    roadmap_store.seed_file(".github/labels.yml", labels_content)

    gap = CapabilityGap(
        capability="issue-pinning",
        tool="gh",
        citation="https://cli.github.com/manual/gh_issue_pin",
        description="Pin an issue in a repository",
    )
    outcome = emit_gap_to_intake(
        gap,
        roadmap_store,
        repo="dan-petty/devops-cli",
        model=_FakeIntakeModel(),
        confirm=False,
    )
    assert outcome.plan is not None
    assert "issue-pinning" in outcome.decision.subject.name
    assert outcome.decision.subject.new is not None
    assert outcome.decision.subject.new.source == "https://cli.github.com/manual/gh_issue_pin"
