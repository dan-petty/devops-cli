"""Test suite for the commit-time structural invariant sentinel."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from devops_cli.security.structural_invariants import breaches, measure


def _run(*paths: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the structural invariants sentinel exactly as pre-commit does."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "devops_cli.security.structural_invariants",
            *(str(p) for p in paths),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_deep_nesting_fails_the_commit(tmp_path: Path) -> None:
    """AGENTS.md caps nesting at 5, and the tree satisfies it, so the hook holds the line."""
    module = tmp_path / "deep.py"
    body = "def f(x):\n"
    for level in range(7):
        body += "    " * (level + 1) + f"if x > {level}:\n"
    body += "    " * 8 + "return x\n"
    module.write_text(body, encoding="utf-8")

    result = _run(module)
    assert (result.returncode, "nesting" in result.stderr) == (1, True)


def test_shallow_nesting_passes(tmp_path: Path) -> None:
    """A gate that rejected ordinary code would be turned off within a day."""
    module = tmp_path / "shallow.py"
    module.write_text("def f(x):\n    if x:\n        return 1\n    return 0\n", encoding="utf-8")
    assert _run(module).returncode == 0


def test_the_metric_matches_the_projects_own_scanner() -> None:
    """A hook stricter than the scanner rejects code the project accepts.

    The first version counted `Try` rather than `ExceptHandler`, counted comprehensions,
    and recursed into nested functions -- reporting a nesting breach the scanner does not
    see at all.
    """
    from devops_cli.security.complexity import run_complexity_scan

    src = Path("src/devops_cli")
    authority = run_complexity_scan(src, max_complexity=10, max_nesting_depth=5)
    scanner_nesting = len([f for f in authority if "Nesting" in f.title])

    result = _run(*src.rglob("*.py"))
    hook_nesting = len([line for line in result.stderr.splitlines() if "nesting" in line])
    assert hook_nesting == scanner_nesting


def test_an_unparseable_file_is_reported_rather_than_skipped(tmp_path: Path) -> None:
    """Silently passing a file it could not read would make the gate meaningless."""
    module = tmp_path / "broken.py"
    module.write_text("def f(:\n", encoding="utf-8")
    assert _run(module).returncode == 1


def test_a_long_expression_is_measured_rather_than_overflowing(tmp_path: Path) -> None:
    """`1 + 1 + ... + 1` parses one node deeper per term.

    A recursive walk spending two frames per node raised RecursionError from 600 terms on, a
    traceback where the hook before it passed; the walk now keeps its own stack (#586).
    """
    module = tmp_path / "long.py"
    expression = " + ".join(["1"] * 3000)
    module.write_text(f"def f(x):\n    if x:\n        return {expression}\n", encoding="utf-8")
    function = ast.parse(module.read_text(encoding="utf-8")).body[0]

    assert (measure(function), breaches(module)) == (1, [])


def test_a_parser_overflow_is_reported_rather_than_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`ast.parse` raises RecursionError on an expression too deep for its own stack."""

    def overflow(source: str) -> ast.Module:
        raise RecursionError("Stack overflow during compilation")

    module = tmp_path / "deep.py"
    module.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(ast, "parse", overflow)

    assert breaches(module) == [f"{module}: could not parse (Stack overflow during compilation)"]
