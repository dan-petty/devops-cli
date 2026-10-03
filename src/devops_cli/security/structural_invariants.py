"""AST-based nesting-depth sentinel for the structural-invariants pre-commit hook."""

from __future__ import annotations

import ast
import sys
from collections.abc import Sequence
from pathlib import Path

from devops_cli.config.defaults import DEFAULT_MAX_NESTING_DEPTH

MAX_NESTING_DEPTH: int = DEFAULT_MAX_NESTING_DEPTH

_NESTING = (
    ast.If,
    ast.While,
    ast.For,
    ast.AsyncFor,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.Assert,
    ast.Match,
)
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


def measure(node: ast.AST) -> int:
    """Return one function's deepest nesting.

    An explicit stack, not recursion: `1 + 1 + ... + 1` parses into one node per term, so a
    long expression that `ast.parse` accepts would exceed Python's recursion limit (#586).
    """
    deepest = 0
    pending: list[tuple[ast.AST, int]] = [(node, 0)]
    while pending:
        current, depth = pending.pop()
        deepest = max(deepest, depth)
        inner = depth + isinstance(current, _NESTING)
        # A nested function carries its own budget, as the scanner treats it.
        pending.extend(
            (child, inner)
            for child in ast.iter_child_nodes(current)
            if not isinstance(child, _FUNCTIONS)
        )
    return deepest


def breaches(path: Path, max_depth: int = DEFAULT_MAX_NESTING_DEPTH) -> list[str]:
    """Report every function in one file nested deeper than the cap."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, RecursionError) as exc:
        # The parser itself overflows the stack on a long enough expression.
        return [f"{path}: could not parse ({exc})"]

    return [
        f"{path}:{node.lineno}: {node.name} nesting {depth} > {max_depth}"
        for node in ast.walk(tree)
        if isinstance(node, _FUNCTIONS) and (depth := measure(node)) > max_depth
    ]


def check_structural_invariants(
    paths: Sequence[Path | str],
    max_depth: int = DEFAULT_MAX_NESTING_DEPTH,
) -> list[str]:
    """Audit paths for nesting breaches."""
    found: list[str] = []
    for name in paths:
        path = Path(name)
        if path.suffix == ".py" and path.is_file():
            found.extend(breaches(path, max_depth=max_depth))
    return found


def main(argv: list[str] | None = None) -> int:
    """Check Python files passed via argv, reporting every breach before failing."""
    args = sys.argv[1:] if argv is None else argv
    found = check_structural_invariants(args)

    for line in found:
        print(line, file=sys.stderr)
    if found:
        print(
            f"\n{len(found)} nesting breach(es). AGENTS.md caps nesting depth at "
            f"{DEFAULT_MAX_NESTING_DEPTH}; decompose the block into a helper.",
            file=sys.stderr,
        )
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
