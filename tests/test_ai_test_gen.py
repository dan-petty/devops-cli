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

    res = runner.invoke(ai_app, ["test-gen", str(sample), "--dry-run"])
    assert res.exit_code == 0
    assert "SYNTHESIZED_DRY_RUN" in res.output
