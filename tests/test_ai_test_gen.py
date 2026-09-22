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
