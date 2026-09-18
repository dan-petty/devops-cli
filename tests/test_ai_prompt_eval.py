"""Tests for prompt evaluation and mutation benchmarking CLI."""

from __future__ import annotations

import json
from pathlib import Path

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


def test_prompt_evaluation_security_boundaries(tmp_path: Path) -> None:
    """Verify that symlinks and path traversal attempts raise SecurityError."""
    import pytest

    from devops_cli.exceptions import SecurityError

    # 1. Traversal outside repo root and cwd
    outside_path = Path("/etc/passwd")
    with pytest.raises(SecurityError):
        evaluate_persona_prompts("devsecops", dataset_path=outside_path)

    # 2. Symlink
    real_file = tmp_path / "dataset.jsonl"
    real_file.write_text('{"id": "1"}\n', encoding="utf-8")
    symlink_file = tmp_path / "symlink_dataset.jsonl"
    symlink_file.symlink_to(real_file)

    with pytest.raises(SecurityError):
        evaluate_persona_prompts("devsecops", dataset_path=symlink_file)
