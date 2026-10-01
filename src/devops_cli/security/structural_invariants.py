"""AST-based structural invariants sentinel and verification module."""

from __future__ import annotations

import ast
import sys
from collections.abc import Sequence
from pathlib import Path

from devops_cli.config.defaults import DEFAULT_MAX_COMPLEXITY, DEFAULT_MAX_NESTING_DEPTH

MAX_NESTING_DEPTH: int = DEFAULT_MAX_NESTING_DEPTH
MAX_COMPLEXITY: int = DEFAULT_MAX_COMPLEXITY

_DEPTH_AND_BRANCH = (
    ast.If,
    ast.While,
    ast.For,
    ast.AsyncFor,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.Assert,
)


def _measure(node: ast.AST, depth: int, state: dict[str, int]) -> None:
    """Accumulate complexity and deepest nesting for one function."""
    state["depth"] = max(state["depth"], depth)

    if isinstance(node, _DEPTH_AND_BRANCH):
        state["complexity"] += 1
        depth += 1
    elif isinstance(node, ast.BoolOp):
        state["complexity"] += len(node.values) - 1
    elif isinstance(node, ast.IfExp):
        state["complexity"] += 1
    elif isinstance(node, ast.Match):
        state["complexity"] += len(node.cases)
        depth += 1

    for child in ast.iter_child_nodes(node):
        # A nested function carries its own budget, as the scanner treats it.
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _measure(child, depth, state)


def measure(node: ast.AST) -> tuple[int, int]:
    """Return one function's cyclomatic complexity and deepest nesting."""
    state = {"complexity": 1, "depth": 0}
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _measure(child, 0, state)
    return state["complexity"], state["depth"]


def breaches(
    path: Path,
    max_depth: int = DEFAULT_MAX_NESTING_DEPTH,
    max_complexity: int = DEFAULT_MAX_COMPLEXITY,
) -> tuple[list[str], int]:
    """Report nesting breaches, and count complexity breaches separately."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        return [f"{path}: could not parse ({exc})"], 0

    found: list[str] = []
    over_complex = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        complexity, depth = measure(node)
        if depth > max_depth:
            found.append(f"{path}:{node.lineno}: {node.name} nesting {depth} > {max_depth}")
        over_complex += int(complexity > max_complexity)
    return found, over_complex


def check_structural_invariants(
    paths: Sequence[Path | str],
    max_depth: int = DEFAULT_MAX_NESTING_DEPTH,
    max_complexity: int = DEFAULT_MAX_COMPLEXITY,
) -> tuple[list[str], int]:
    """Audit paths for structural invariant violations, returning breaches and complexity count."""
    found: list[str] = []
    over_complex = 0
    for name in paths:
        path = Path(name)
        if path.suffix == ".py" and path.is_file():
            file_found, file_complex = breaches(
                path, max_depth=max_depth, max_complexity=max_complexity
            )
            found.extend(file_found)
            over_complex += file_complex
    return found, over_complex


def main(argv: list[str] | None = None) -> int:
    """Check Python files passed via argv, reporting every breach before failing."""
    args = sys.argv[1:] if argv is None else argv
    found, over_complex = check_structural_invariants(args)

    for line in found:
        print(line, file=sys.stderr)
    if found:
        print(
            f"\n{len(found)} nesting breach(es). AGENTS.md caps nesting depth at "
            f"{DEFAULT_MAX_NESTING_DEPTH}; decompose the block into a helper.",
            file=sys.stderr,
        )
    if over_complex:
        print(
            f"note: {over_complex} changed function(s) exceed complexity "
            f"{DEFAULT_MAX_COMPLEXITY}. Not blocking -- see the roadmap entry on the existing debt.",
            file=sys.stderr,
        )
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
