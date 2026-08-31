"""Tests for AST code complexity and nesting scanner."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from devops_cli.commands.scan import app as scan_app
from devops_cli.security.complexity import (
    analyze_file_complexity,
    run_complexity_scan,
)

runner = CliRunner()


def test_analyze_simple_function(tmp_path: Path) -> None:
    """Analyze simple low-complexity Python function."""
    sample = tmp_path / "simple.py"
    sample.write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )
    rep = analyze_file_complexity(sample)
    assert len(rep.functions) == 1
    assert rep.functions[0].name == "add"
    assert rep.functions[0].cyclomatic_complexity == 1
    assert rep.functions[0].max_nesting_depth == 1


def test_analyze_complex_function(tmp_path: Path) -> None:
    """Analyze function with multiple branches and nested loops."""
    sample = tmp_path / "complex.py"
    sample.write_text(
        "async def process(items: list[int]) -> list[int]:\n"
        "    res = []\n"
        "    for x in items:\n"
        "        if x > 0:\n"
        "            if x % 2 == 0:\n"
        "                while x > 10:\n"
        "                    x -= 1\n"
        "                    res.append(x)\n"
        "        elif x < -5:\n"
        "            res.append(-x)\n"
        "    return res\n",
        encoding="utf-8",
    )
    rep = analyze_file_complexity(sample)
    assert len(rep.functions) == 1
    fn = rep.functions[0]
    assert fn.name == "process"
    assert fn.cyclomatic_complexity >= 5
    assert fn.max_nesting_depth >= 4


def test_run_complexity_scan_thresholds(tmp_path: Path) -> None:
    """Verify findings generation when complexity exceeds limits."""
    sample = tmp_path / "deep.py"
    sample.write_text(
        "def deep_nesting(val: int) -> None:\n"
        "    if val > 0:\n"
        "        if val > 1:\n"
        "            if val > 2:\n"
        "                if val > 3:\n"
        "                    if val > 4:\n"
        "                        if val > 5:\n"
        "                            print(val)\n",
        encoding="utf-8",
    )
    findings = run_complexity_scan(sample, max_complexity=2, max_nesting_depth=3)
    assert len(findings) >= 1
    assert any("Excessive Nesting Depth" in f.title for f in findings)
    assert any("High Cyclomatic Complexity" in f.title for f in findings)


def test_scan_complexity_cli(tmp_path: Path) -> None:
    """Test CLI execution of devops scan complexity."""
    sample = tmp_path / "code.py"
    sample.write_text(
        "def calculate(n: int) -> int:\n    return n * 2 if n > 0 else 0\n",
        encoding="utf-8",
    )
    # Test JSON output
    res = runner.invoke(scan_app, ["complexity", str(sample), "--json", "--max-complexity", "20"])
    assert res.exit_code == 0
    assert "[]" in res.output or "location" in res.output

    # Test clean pass table output
    res_clean = runner.invoke(scan_app, ["complexity", str(sample), "--max-complexity", "20"])
    assert res_clean.exit_code == 0
    assert "Code complexity and indentation depth within standard limits" in res_clean.output

    # Test dry run
    res_dry = runner.invoke(scan_app, ["complexity", str(sample), "--dry-run"])
    assert res_dry.exit_code == 0
