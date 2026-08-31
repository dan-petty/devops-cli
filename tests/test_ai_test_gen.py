"""Tests for automated unit test synthesizer and devops ai test-gen CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from devops_cli.ai.test_gen import synthesize_unit_tests
from devops_cli.commands.ai import app as ai_app

runner = CliRunner()


def test_test_gen(tmp_path: Path) -> None:
    """Verify unit test synthesizer and CLI."""
    sample = tmp_path / "math_ops.py"
    sample.write_text("def multiply(x: int, y: int) -> int:\n    return x * y\n", encoding="utf-8")

    suite = synthesize_unit_tests(sample)
    assert suite.test_count >= 1
    assert "def test_multiply_isolated_behavior" in suite.test_code
    d = suite.to_dict()
    assert d["test_count"] >= 1

    # Function filter
    suite_filt = synthesize_unit_tests(sample, function_filter="multiply")
    assert suite_filt.test_count == 1

    # Missing/empty file
    empty_sample = tmp_path / "empty.py"
    empty_sample.write_text("", encoding="utf-8")
    suite_empty = synthesize_unit_tests(empty_sample)
    assert "def test_empty_import" in suite_empty.test_code

    # Syntax error fallback
    bad_sample = tmp_path / "bad.py"
    bad_sample.write_text("def (invalid python", encoding="utf-8")
    suite_bad = synthesize_unit_tests(bad_sample)
    assert suite_bad.test_count == 1

    res = runner.invoke(ai_app, ["test-gen", str(sample), "--dry-run"])
    assert res.exit_code == 0
    assert "SYNTHESIZED_DRY_RUN" in res.output


def test_prompt_eval_and_feedback_dataset(tmp_path: Path) -> None:
    """Verify prompt evaluation with real dataset and fallback cases."""
    from devops_cli.ai.prompt_eval import PromptEvalBenchmarkResult, evaluate_persona_prompts

    # 1. Fallback baseline
    res_base = evaluate_persona_prompts("devsecops", dataset_path=tmp_path / "nonexistent.jsonl")
    assert isinstance(res_base, PromptEvalBenchmarkResult)
    assert res_base.total_cases > 0
    d = res_base.to_dict()
    assert "accuracy_score" in d

    # 2. Existing JSONL dataset
    ds_file = tmp_path / "feedback.jsonl"
    ds_file.write_text(
        '{"id": "c1", "title": "Secret in code", "ground_truth": "VALID", "persona": "devsecops"}\n'
        '{"id": "c2", "title": "Doc comment", "ground_truth": "INVALID", "persona": "devsecops"}\n',
        encoding="utf-8",
    )
    res_ds = evaluate_persona_prompts("devsecops", dataset_path=ds_file)
    assert res_ds.total_cases == 2

    # 3. Malformed JSONL dataset
    bad_ds = tmp_path / "bad_feedback.jsonl"
    bad_ds.write_text("not json at all\n", encoding="utf-8")
    res_bad = evaluate_persona_prompts("devsecops", dataset_path=bad_ds)
    assert res_bad.total_cases > 0
