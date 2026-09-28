"""Review verification can use its own model, layered on the analysis task's settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review.runner import (
    ReviewClients,
    _make_review_clients,
    _validate_single_segment_findings,
)
from devops_cli.ai.review_schema import FileReviewPayload, Finding, ReviewResult, SavedFinding
from devops_cli.config.settings import AITaskOverride, Settings

GATEWAY_URL = "http://gateway.example.com:4000/v1"


def _settings(verification: AITaskOverride | None = None) -> Settings:
    settings = Settings()
    settings.ai.tasks.analysis = AITaskOverride(
        provider="gateway", model="devops-review", api_base_url=GATEWAY_URL, context_window=16384
    )
    if verification is not None:
        settings.ai.tasks.verification = verification
    return settings


def _finding() -> SavedFinding:
    return SavedFinding(
        severity="HIGH",
        location="src/app.py:3-4",
        title="Unchecked input",
        description="Input reaches a shell command.",
        fix="Quote it.",
        persona="devsecops",
        persona_title="Principal DevSecOps Engineer",
    )


def test_verification_uses_the_analysis_client_when_not_configured() -> None:
    """Verify reviews verify with the analysis client unless verification is configured."""
    clients = _make_review_clients(_settings())

    assert clients.verification is clients.analysis


def test_verification_override_layers_on_the_analysis_task() -> None:
    """Verify a verification model inherits the analysis task's provider, gateway and window."""
    clients = _make_review_clients(_settings(AITaskOverride(model="devops-reasoning")))
    cfg = clients.verification._config

    assert (
        clients.verification is clients.analysis,
        cfg.provider,
        cfg.model,
        cfg.gateway_url,
        cfg.context_window,
        clients.analysis._config.model,
    ) == (False, "gateway", "devops-reasoning", GATEWAY_URL, 16384, "devops-review")


def test_review_clients_default_verification_to_analysis() -> None:
    """Verify callers that build ReviewClients without a verifier get the analysis client."""
    analysis, compose = MagicMock(), MagicMock()

    assert ReviewClients(analysis=analysis, compose=compose).verification is analysis


def test_segment_verification_uses_the_verification_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify per-segment verification hands the verification client to the verifier."""
    used: list[Any] = []

    def fake_validate(result: ReviewResult, pages: list[str], client: Any, **kw: Any) -> Any:
        used.append(client)
        return result, 0.1, "backend"

    monkeypatch.setattr("devops_cli.ai.review.runner._validate_segment_findings", fake_validate)
    analysis, verifier = MagicMock(), MagicMock()
    parsed = ReviewResult(findings=[Finding(**_finding().model_dump())])

    _validate_single_segment_findings(
        1,
        "=== File: src/app.py ===\ncode",
        parsed,
        1,
        ["page"],
        ReviewClients(analysis=analysis, compose=MagicMock(), verification=verifier),
        {},
        None,
        "",
    )

    assert used == [verifier]


def test_pipeline_verification_uses_the_verification_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the pipeline's verification stage calls the verifier, not the analysis client."""
    used: list[Any] = []

    def fake_validate(result: ReviewResult, all_segments: list[str], client: Any, **kw: Any) -> Any:
        used.append(client)
        return result, 0.1, "backend"

    monkeypatch.setattr("devops_cli.ai.review.pipeline._validate_segment_findings", fake_validate)
    analysis, verifier = MagicMock(), MagicMock()
    orchestrator = ReviewPipelineOrchestrator(
        session_dir=tmp_path / "session",
        target_dir=tmp_path,
        llm_client=analysis,
        verification_client=verifier,
    )

    orchestrator._verify_single_file_payload(
        1, 1, FileReviewPayload(file_path="src/app.py", findings=[_finding()]), "server"
    )

    assert (used, orchestrator.llm_client) == ([verifier], analysis)


def test_verification_stage_reports_the_verification_model(tmp_path: Path) -> None:
    """Verify the verification stage names the model that verifies, not the analysis model."""
    analysis, verifier = MagicMock(), MagicMock()
    analysis.backend_info, verifier.backend_info = "gateway (gw)", "gateway (gw)"
    analysis._config.model, verifier._config.model = "devops-review", "devops-reasoning"
    orchestrator = ReviewPipelineOrchestrator(
        session_dir=tmp_path / "session",
        target_dir=tmp_path,
        llm_client=analysis,
        verification_client=verifier,
    )

    assert (
        orchestrator._get_server_info(),
        orchestrator._get_server_info(orchestrator.verification_client),
    ) == ("gateway (gw) [model: devops-review]", "gateway (gw) [model: devops-reasoning]")
