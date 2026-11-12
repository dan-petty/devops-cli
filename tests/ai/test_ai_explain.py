"""Unit tests for AI command terminology explainers and --explain CLI options."""

from __future__ import annotations

from rich.console import Console
from typer.testing import CliRunner

from devops_cli.ai.explain import EXPLANATIONS, render_explanation
from devops_cli.commands.ai import app as ai_app

runner = CliRunner()


def test_explanation_definitions_coverage() -> None:
    """Verify explanation topics have required sections, formulas, and metadata."""
    assert "benchmark" in EXPLANATIONS
    assert "review" in EXPLANATIONS
    assert "analyze" in EXPLANATIONS
    assert "rag" in EXPLANATIONS

    for data in EXPLANATIONS.values():
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


def test_render_explanation_falls_back_to_the_benchmark_topic() -> None:
    """Verify render_explanation renders each topic, and an unknown topic as the benchmark one."""
    rendered = {}
    for topic in ("benchmark", "review", "analyze", "rag", "unknown_topic"):
        console = Console(record=True, width=200)
        render_explanation(topic, console_instance=console)
        rendered[topic] = console.export_text()

    assert (
        all(EXPLANATIONS[topic]["title"] in rendered[topic] for topic in EXPLANATIONS),
        rendered["unknown_topic"] == rendered["benchmark"],
    ) == (True, True)


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
