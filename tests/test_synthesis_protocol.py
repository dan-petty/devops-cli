"""Tests for Big Decides, Small Types, Big Checks synthesis protocol."""

from __future__ import annotations

from devops_cli.ai.agents.synthesis_protocol import SynthesisPipelineOrchestrator


def test_synthesis_pipeline_orchestrator() -> None:
    """Execute 3-stage synthesis protocol and verify plan, drafts, and verification report."""
    orchestrator = SynthesisPipelineOrchestrator(
        planner_model="claude-3-7-sonnet",
        drafter_model="qwen2.5-coder",
        auditor_model="claude-3-7-sonnet",
    )

    result = orchestrator.execute(
        goal="Implement secure token authentication broker",
        max_subtasks=3,
    )

    assert result.plan.goal == "Implement secure token authentication broker"
    assert len(result.plan.sub_tasks) == 3
    assert len(result.drafts) == 3
    assert result.verification.passed is True
    assert result.verification.score >= 0.8
    assert "handle_subtask_1_schema" in result.final_output
    assert result.latency_ms >= 0.0
