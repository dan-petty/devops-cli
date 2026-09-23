#!/usr/bin/env python3
"""Fail a commit whose changed files breach the project's AST invariants.

AGENTS.md caps cyclomatic complexity at 10 and nesting depth at 5. Those caps were checked
only by `tests/test_architectural_invariants.py`, which runs inside a test suite that takes
minutes -- so a breach was found after the work was finished rather than as it was written.

This is deliberately standalone. Importing `devops_cli` to reuse `run_complexity_scan`
costs about five seconds of interpreter startup before a single file is read, which is more
than a pre-commit hook has to spend; the same walk over the standard library's `ast` runs
in a fraction of that. The definitions here are the ones `security/complexity.py` applies,
and `tests/test_architectural_invariants.py` remains the authority over the whole tree.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

MAX_NESTING_DEPTH = 5
MAX_COMPLEXITY = 10

# These mirror `devops_cli/security/complexity.py` exactly, because a hook that applies a
# stricter definition than the project's own scanner rejects code the project accepts. The
# first version of this file counted `Try` rather than `ExceptHandler`, counted
# comprehensions, and recursed into nested functions; it reported 334 breaches where the
# scanner reports 240, and a nesting breach the scanner does not see at all.
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


def breaches(path: Path) -> tuple[list[str], int]:
    """Report nesting breaches, and count complexity breaches separately.

    Only nesting fails a commit. AGENTS.md caps complexity at 10, but 240 functions in
    `src/` breach it today and nothing enforces it -- `devops ci` has no complexity gate,
    Ruff's `C901` is not enabled, and the one architectural test passes
    `max_complexity=100`, so it catches nesting alone. Failing on complexity here would
    block work on any of those files rather than hold a line the codebase is on.
    """
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
        if depth > MAX_NESTING_DEPTH:
            found.append(f"{path}:{node.lineno}: {node.name} nesting {depth} > {MAX_NESTING_DEPTH}")
        over_complex += int(complexity > MAX_COMPLEXITY)
    return found, over_complex


def main(argv: list[str]) -> int:
    """Check the files pre-commit passed, reporting every breach before failing."""
    found: list[str] = []
    over_complex = 0
    for name in argv:
        path = Path(name)
        if path.suffix == ".py" and path.is_file():
            file_found, file_complex = breaches(path)
            found.extend(file_found)
            over_complex += file_complex

    for line in found:
        print(line, file=sys.stderr)
    if found:
        print(
            f"\n{len(found)} nesting breach(es). AGENTS.md caps nesting depth at "
            f"{MAX_NESTING_DEPTH}; decompose the block into a helper.",
            file=sys.stderr,
        )
    if over_complex:
        print(
            f"note: {over_complex} changed function(s) exceed complexity "
            f"{MAX_COMPLEXITY}. Not blocking -- see the roadmap entry on the existing debt.",
            file=sys.stderr,
        )
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
