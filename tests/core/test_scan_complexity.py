"""Tests for the AST code complexity scanner. Ruff's PLR1702 caps nesting (#1876)."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.core.code_metrics import FunctionComplexity, measure_tree
from devops_cli.security.complexity import run_complexity_scan


def _measure(path: Path) -> list[FunctionComplexity]:
    return measure_tree(ast.parse(path.read_text(encoding="utf-8")))


def test_analyze_simple_function(tmp_path: Path) -> None:
    """Analyze simple low-complexity Python function."""
    sample = tmp_path / "simple.py"
    sample.write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )
    functions = _measure(sample)
    assert len(functions) == 1
    assert functions[0].name == "add"
    assert functions[0].cyclomatic_complexity == 1


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
    functions = _measure(sample)
    assert len(functions) == 1
    fn = functions[0]
    assert fn.name == "process"
    assert fn.cyclomatic_complexity >= 5


def test_run_complexity_scan_thresholds(tmp_path: Path) -> None:
    """A function over the complexity cap gets one finding; its depth of six blocks gets none."""
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
    findings = run_complexity_scan(sample, max_complexity=2)

    assert [f.title for f in findings] == ["High Cyclomatic Complexity in `deep_nesting` (7 > 2)"]


def test_scan_complexity_cli(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """Test CLI execution of devops scan complexity."""
    sample = tmp_path / "code.py"
    sample.write_text(
        "def calculate(n: int) -> int:\n    return n * 2 if n > 0 else 0\n",
        encoding="utf-8",
    )
    # Test JSON output
    res = cli(["scan", "complexity", str(sample), "--json", "--max-complexity", "20"])
    assert res.exit_code == 0
    assert "[]" in res.output or "location" in res.output

    # Test clean pass table output
    res_clean = cli(["scan", "complexity", str(sample), "--max-complexity", "20"])
    assert res_clean.exit_code == 0
    assert "Code complexity within standard limits" in res_clean.output

    # Nesting is Ruff's PLR1702, so the scanner has no nesting option
    res_indent = cli(["scan", "complexity", str(sample), "--max-indent", "5"])
    assert res_indent.exit_code == 2

    # Test dry run
    res_dry = cli(["--dry-run", "scan", "complexity", str(sample)])
    assert res_dry.exit_code == 0


def test_analyze_class_method_distinction(tmp_path: Path) -> None:
    """Verify is_method flag is True for methods and False for top-level functions."""
    sample = tmp_path / "classes.py"
    sample.write_text(
        "def standalone() -> None:\n"
        "    pass\n\n"
        "class MyService:\n"
        "    def method(self) -> None:\n"
        "        pass\n",
        encoding="utf-8",
    )
    functions = _measure(sample)
    assert len(functions) == 2
    standalone = next(f for f in functions if f.name == "standalone")
    method = next(f for f in functions if f.name == "method")
    assert standalone.is_method is False
    assert method.is_method is True


def test_a_closure_counts_toward_the_enclosing_function_and_is_reported_on_its_own(
    tmp_path: Path,
) -> None:
    """As in Ruff's C901, a closure adds 1 plus its own count to the function defining it and
    is reported on its own too."""
    sample = tmp_path / "closure.py"
    sample.write_text(
        "def outer(x):\n"
        "    def inner(y):\n"
        "        if y:\n"
        "            return 1\n"
        "        if y > 2:\n"
        "            return 2\n"
        "    return inner\n",
        encoding="utf-8",
    )
    assert sorted((f.name, f.cyclomatic_complexity) for f in _measure(sample)) == [
        ("inner", 3),
        ("outer", 4),
    ]


def test_a_class_directly_in_a_function_body_has_methods(tmp_path: Path) -> None:
    """A class defined in a function gives methods; a def nested in a method is not one."""
    sample = tmp_path / "local_class.py"
    sample.write_text(
        "def factory():\n"
        "    class C:\n"
        "        def m(self):\n"
        "            def helper():\n"
        "                return 1\n"
        "            return helper()\n"
        "    return C\n",
        encoding="utf-8",
    )
    assert sorted((f.name, f.is_method) for f in _measure(sample)) == [
        ("factory", False),
        ("helper", False),
        ("m", True),
    ]


def test_complexity_boolops_match_and_syntax_error(tmp_path: Path) -> None:
    """Verify boolops, match/case statements, nested functions, and unparseable syntax."""
    # 1. BoolOp, Match, and Nested function
    code_f = tmp_path / "advanced.py"
    code_f.write_text(
        "def evaluate_cmd(a: bool, b: bool, c: bool, val: int) -> int:\n"
        "    if a and b and c:\n"
        "        def nested_helper(x: int) -> int:\n"
        "            return x * 2\n"
        "        return nested_helper(val)\n"
        "    match val:\n"
        "        case 1:\n"
        "            return 10\n"
        "        case 2:\n"
        "            return 20\n"
        "        case _:\n"
        "            return 0\n",
        encoding="utf-8",
    )
    assert sorted((f.name, f.cyclomatic_complexity) for f in _measure(code_f)) == [
        ("evaluate_cmd", 5),
        ("nested_helper", 1),
    ]

    # 2. An unparseable file is skipped
    bad_f = tmp_path / "broken.py"
    bad_f.write_text("def broken( :::", encoding="utf-8")
    assert run_complexity_scan(bad_f) == []

    # 3. Directory scanning with ignored subdirs and non-python file
    sub_dir = tmp_path / "src"
    sub_dir.mkdir()
    (sub_dir / "valid.py").write_text("def ok() -> None: pass\n", encoding="utf-8")
    (sub_dir / "doc.txt").write_text("text doc", encoding="utf-8")
    ignored_venv = tmp_path / ".venv" / "lib"
    ignored_venv.mkdir(parents=True)
    (ignored_venv / "lib.py").write_text("def bad() -> None: pass\n", encoding="utf-8")

    findings = run_complexity_scan(tmp_path)
    assert isinstance(findings, list)

    # Scan non-python file
    non_py = tmp_path / "readme.md"
    non_py.write_text("# Readme", encoding="utf-8")
    assert run_complexity_scan(non_py) == []


def test_complexity_findings_are_located_relative_to_a_nested_worktree(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify findings from a worktree under `.claude/worktrees/` name paths inside that
    worktree, not paths through the checkout around it (#582)."""
    _, nested = nested_worktree
    (nested / "src").mkdir()
    (nested / "src" / "deep.py").write_text(
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
    monkeypatch.chdir(nested)

    findings = run_complexity_scan(nested / "src", max_complexity=2)

    locations = [finding.location for finding in findings]
    assert (
        bool(locations),
        all(loc.startswith("src/") and ".claude" not in loc for loc in locations),
    ) == (True, True)
