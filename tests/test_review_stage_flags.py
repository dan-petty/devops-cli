"""Unit tests for review pipeline stage feature flags and resolution logic."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.ai.review.flags import ReviewStageFlags, resolve_stage_flags
from devops_cli.commands.review import app as review_app

runner = CliRunner()


def test_review_stage_flags_defaults() -> None:
    """Verify default ReviewStageFlags has all stages enabled."""
    flags = ReviewStageFlags()
    assert flags.pre_analysis is True
    assert flags.static_scan is True
    assert flags.persona_review is True
    assert flags.verification is True
    assert flags.reranking is True
    assert flags.reporting is True
    assert flags.any_enabled() is True
    assert flags.to_dict() == {
        "pre_analysis": True,
        "static_scan": True,
        "persona_review": True,
        "verification": True,
        "reranking": True,
        "reporting": True,
    }


def test_resolve_stage_flags_no_options() -> None:
    """Verify default resolution enables all stages."""
    flags = resolve_stage_flags()
    assert flags == ReviewStageFlags()


def test_resolve_stage_flags_no_flags() -> None:
    """Verify --no-<stage> disables individual stages."""
    flags = resolve_stage_flags(
        no_pre_analysis=True,
        no_verification=True,
    )
    assert flags.pre_analysis is False
    assert flags.static_scan is True
    assert flags.persona_review is True
    assert flags.verification is False
    assert flags.reranking is True
    assert flags.reporting is True


def test_resolve_stage_flags_only_flags() -> None:
    """Verify --<stage>-only enables only that stage and disables all others."""
    flags = resolve_stage_flags(static_scan_only=True)
    assert flags.pre_analysis is False
    assert flags.static_scan is True
    assert flags.persona_review is False
    assert flags.verification is False
    assert flags.reranking is False
    assert flags.reporting is False


def test_resolve_stage_flags_multiple_only_flags() -> None:
    """Verify multiple --<stage>-only flags enable the specified union of stages."""
    flags = resolve_stage_flags(
        static_scan_only=True,
        persona_review_only=True,
    )
    assert flags.pre_analysis is False
    assert flags.static_scan is True
    assert flags.persona_review is True
    assert flags.verification is False
    assert flags.reranking is False
    assert flags.reporting is False


def test_resolve_stage_flags_conflicting_no_and_only() -> None:
    """Verify --no-<stage> takes precedence over --<stage>-only if both are passed for the same stage."""
    flags = resolve_stage_flags(
        static_scan_only=True,
        no_static_scan=True,
    )
    assert flags.static_scan is False
    assert flags.any_enabled() is False


def test_review_cli_stage_flags_propagation() -> None:
    """Verify CLI review commands pass resolved stage flags to workflow."""
    with (
        patch("devops_cli.commands.review.load_settings"),
        patch("devops_cli.commands.review._make_review_clients"),
        patch(
            "devops_cli.commands.review._prepare_path_content", return_value=(["diff"], "title", "")
        ),
        patch("devops_cli.commands.review._execute_review_workflow") as mock_exec,
    ):
        result = runner.invoke(
            review_app,
            ["path", "--no-verification", "--static-scan-only"],
        )
        assert result.exit_code == 0
        mock_exec.assert_called_once()
        call_kwargs = mock_exec.call_args[1]
        passed_flags: ReviewStageFlags = call_kwargs["stage_flags"]
        assert passed_flags.static_scan is True
        assert passed_flags.verification is False
        assert passed_flags.persona_review is False


def test_orchestrator_stage_bypasses(tmp_path) -> None:
    """Verify ReviewPipelineOrchestrator respects stage flags and skips execution."""
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator

    orchestrator = ReviewPipelineOrchestrator(
        session_id="test-flags-session",
        session_dir=tmp_path / "session",
        target_dir=tmp_path,
    )

    # 1. Skip pre-analysis
    flags_no_pre = ReviewStageFlags(pre_analysis=False)
    meta = orchestrator.run_pre_analysis_refresh(
        target_dir=tmp_path,
        stage_flags=flags_no_pre,
    )
    assert meta == {}

    # 2. Skip static scanning in init_per_file_payloads
    test_file = tmp_path / "main.py"
    test_file.write_text("print('hello')\n")
    flags_no_static = ReviewStageFlags(static_scan=False)
    payloads = orchestrator.init_per_file_payloads(
        [str(test_file)],
        {},
        target_dir=tmp_path,
        stage_flags=flags_no_static,
    )
    assert len(payloads) == 1
    assert payloads[0].findings == []

    # 3. Skip persona review
    flags_no_persona = ReviewStageFlags(persona_review=False)
    orchestrator.execute_multi_persona_review(
        payloads,
        {str(test_file): "diff"},
        stage_flags=flags_no_persona,
    )
    assert payloads[0].findings == []

    # 4. Skip verification
    flags_no_verify = ReviewStageFlags(verification=False)
    orchestrator.execute_finding_verification(
        payloads,
        stage_flags=flags_no_verify,
    )

    # 5. Skip reranking
    flags_no_rerank = ReviewStageFlags(reranking=False)
    orchestrator.execute_finding_reranking(
        payloads,
        stage_flags=flags_no_rerank,
    )

    # 6. Skip reporting
    flags_no_report = ReviewStageFlags(reporting=False)
    report_dict, report_md = orchestrator.generate_consolidated_report(
        payloads,
        stage_flags=flags_no_report,
    )
    assert report_dict == {}
    assert report_md == ""
