"""Tests for prompt evaluation and mutation benchmarking CLI."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from devops_cli.ai.prompt_eval import evaluate_persona_prompts
from devops_cli.commands.ai import app as ai_app

runner = CliRunner()


def test_prompt_evaluation() -> None:
    """Verify prompt mutation benchmarking."""
    res = evaluate_persona_prompts("devsecops")
    assert res.persona == "devsecops"
    assert res.total_cases > 0
    assert res.accuracy_score >= 0.0


def test_prompt_eval_cli() -> None:
    """Verify devops ai prompt-eval CLI command."""
    res = runner.invoke(ai_app, ["prompt-eval", "--dry-run"])
    assert res.exit_code == 0
    assert "BENCHMARK_DRY_RUN" in res.output

    res_json = runner.invoke(ai_app, ["prompt-eval", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert "accuracy_score" in data
