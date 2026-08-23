"""Unit tests for AI command terminology explainers and --explain CLI options."""

from __future__ import annotations

from typer.testing import CliRunner

from devops_cli.ai.explain import EXPLANATIONS, get_explanation_markdown, render_explanation
from devops_cli.commands.ai import app as ai_app

runner = CliRunner()


def test_explanation_definitions_coverage() -> None:
    """Verify explanation topics have required sections, formulas, and metadata."""
    assert "benchmark" in EXPLANATIONS
    assert "review" in EXPLANATIONS
    assert "analyze" in EXPLANATIONS
    assert "rag" in EXPLANATIONS

    for key, data in EXPLANATIONS.items():
        assert "title" in data
        assert "description" in data
        assert "sections" in data
        assert len(data["sections"]) > 0
        for section in data["sections"]:
            assert "name" in section
            assert "items" in section
            for term, definition, formula in section["items"]:
                assert len(term) > 0
                assert len(definition) > 0
                assert len(formula) > 0


def test_render_explanation_and_markdown() -> None:
    """Verify render_explanation and get_explanation_markdown work across topics."""
    # Test rendering to console
    render_explanation("benchmark")
    render_explanation("review")
    render_explanation("analyze")
    render_explanation("rag")
    render_explanation("unknown_topic")  # should fallback gracefully

    # Test markdown generation
    md = get_explanation_markdown("benchmark")
    assert "# ⚡ DevOps AI Benchmark Suite" in md
    assert "Recall@1" in md
    assert "NDCG@5" in md
    assert "Cosine Margin" in md


def test_cli_ai_explain_options() -> None:
    """Ensure --explain option works across all ai CLI command groups."""
    test_cases = [
        ["--explain"],
        ["benchmark", "--explain"],
        ["review", "--explain"],
        ["analyze", "--explain"],
        ["rag", "--explain"],
    ]
    for args in test_cases:
        result = runner.invoke(ai_app, args)
        assert result.exit_code == 0
        assert len(result.stdout) > 200
