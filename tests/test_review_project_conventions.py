"""Review rules that belong to one project come from that project's conventions (#515)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review import ReviewPipelineOrchestrator
from devops_cli.ai.review.review_environment import nearest_review_conventions
from devops_cli.ai.review.verification import _build_validation_prompt
from devops_cli.ai.review_schema import FileReviewPayload, Finding, SavedFinding

_SHARED_PROMPT = (
    Path(__file__).resolve().parents[1] / "src/devops_cli/ai/tasks/verify_finding_system.md"
)
_OWN_CONVENTIONS = Path(__file__).resolve().parents[1] / ".devops/review.md"


@pytest.fixture(autouse=True)
def _no_rag() -> object:
    with patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=None):
        yield


def _repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "AGENTS.md").write_text("# Project\nUse Go 1.23.\n", encoding="utf-8")
    (root / ".devops").mkdir()
    (root / ".devops" / "review.md").write_text(
        "# Review Conventions\nThe `metrics` exporter may reach private networks.\n",
        encoding="utf-8",
    )
    return root


@pytest.mark.parametrize(
    "phrase",
    [
        "mypy --strict",
        "DevOps CLI",
        "allow_private_network",
        "Valkey",
        "this repository",
        "RFC 1918",
    ],
)
def test_the_shared_verifier_prompt_holds_no_project_specific_rule(phrase: str) -> None:
    """Verify the verifier prompt applied to every project carries no devops-cli assumption."""
    assert phrase.lower() not in _SHARED_PROMPT.read_text(encoding="utf-8").lower()


_AI_DIR = Path(__file__).resolve().parents[1] / "src/devops_cli/ai"
_SHARED_REVIEW_PROMPTS = [
    *(_AI_DIR / "tasks").glob("*review*.md"),
    _AI_DIR / "tasks/verify_finding_system.md",
    *(_AI_DIR / "personas").glob("*/prompt.md"),
]


@pytest.mark.parametrize(
    "phrase",
    [
        "docs/ROADMAP.md",
        "this repository",
        "allow_private_network",
        "homelab",
        "RLock",
        "Valkey",
        "mypy --strict",
        "catalogued false alarm",
    ],
)
def test_no_shared_review_prompt_carries_a_project_rule(phrase: str) -> None:
    """Verify persona and review prompts hold only rules true of any project (#515)."""
    carriers = [
        p.relative_to(_AI_DIR).as_posix()
        for p in _SHARED_REVIEW_PROMPTS
        if phrase.lower() in p.read_text(encoding="utf-8").lower()
    ]

    assert carriers == []


def test_devops_cli_keeps_its_own_rules_in_its_review_conventions() -> None:
    """Verify the rules moved out of the shared prompt still apply to this repository."""
    own = _OWN_CONVENTIONS.read_text(encoding="utf-8")

    assert all(
        phrase in own
        for phrase in ("mypy --strict", "allow_private_network", "RFC 1918", "RLock", "is_symlink")
    )


def test_the_nearest_review_conventions_win(tmp_path: Path) -> None:
    """Verify a subproject's `.devops/review.md` overrides its repository's."""
    root = _repo(tmp_path)
    service = root / "services" / "api"
    (service / ".devops").mkdir(parents=True)
    (service / ".devops" / "review.md").write_text("API rules.\n", encoding="utf-8")
    (service / "src").mkdir()

    assert (
        nearest_review_conventions(service / "src"),
        nearest_review_conventions(root / "services"),
    ) == ("API rules.", "# Review Conventions\nThe `metrics` exporter may reach private networks.")


def test_the_verifier_is_given_the_projects_conventions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify verification receives the same project conventions the personas get."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    root = _repo(tmp_path / "project")
    (root / "app.go").write_text("package main\n", encoding="utf-8")
    orchestrator = ReviewPipelineOrchestrator(
        session_id="conventions", llm_client=MagicMock(), target_dir=root
    )
    finding = SavedFinding(location="app.go:1", title="SSRF in metrics exporter", description="d")
    payload = FileReviewPayload(file_path="app.go", findings=[finding])
    seen: dict[str, Any] = {}

    def verify(**kwargs: Any) -> Any:
        seen.update(kwargs)
        return kwargs["result"], None, None

    with patch("devops_cli.ai.review.pipeline._validate_segment_findings", side_effect=verify):
        orchestrator.execute_finding_verification([payload])

    conventions = seen.get("conventions", "")
    assert ("Use Go 1.23." in conventions, "may reach private networks" in conventions) == (
        True,
        True,
    )


def test_the_verifier_prompt_shows_conventions_only_when_there_are_some() -> None:
    """Verify the conventions section is added for a project that has conventions, and only then."""
    finding = Finding(location="a.go:1", title="t", description="d")

    with_conventions = _build_validation_prompt([finding], ["code"], conventions="Rule A.")
    without = _build_validation_prompt([finding], ["code"])

    assert (
        "<untrusted_project_conventions>\nRule A." in with_conventions,
        "untrusted_project_conventions" in without,
    ) == (True, False)


def test_a_mitigated_finding_is_reported_with_its_mitigation() -> None:
    """Verify a confirmed defect the verifier calls mitigated stays in the report, reason shown."""
    from devops_cli.ai.review.verification import _apply_single_finding_verification

    finding = Finding(
        severity="HIGH",
        location="paths.py:40",
        title="safe_resolve_subpath allows traversal outside base_dir",
        description="No containment check after resolve().",
    )
    verdict = {
        "title": finding.title,
        "mitigated": True,
        "reason": "Symlinks are rejected at line 31, which limits but does not stop `../`.",
    }

    result = _apply_single_finding_verification(finding, verdict, "t")
    saved = SavedFinding(**result.model_dump(), persona="devsecops")
    section = ReviewPipelineOrchestrator._build_detailed_findings_section([saved])

    assert (
        (result.status, result.reportable),
        any(line.startswith("- **Mitigation**: Symlinks are rejected") for line in section),
    ) == (("MITIGATED", True), True)
