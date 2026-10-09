"""Nesting depth and McCabe complexity of Python functions, and the commit hook built on them.

The one copy of the metric. `devops scan complexity`, the inspection hotspots, the architecture
spec verifier, the whole-tree test and the structural-invariants pre-commit hook all read it.
Stdlib only and no `devops_cli` import, so the hook (`python -m devops_cli.core.code_metrics`)
loads no scanner: its cap arrives as `--max-depth`.

- **Nesting**: the function body is depth 1, and each If, While, For, AsyncFor, ExceptHandler,
  With, AsyncWith, Assert or Match opens one more level. A nested def is measured on its own.
- **Complexity**: Ruff's C901 count (standard McCabe), so the scanner flags what `ruff check`
  flags. `assert`, `with`, conditional expressions and boolean operands add nothing; a closure
  adds 1 plus its own count to the function that defines it and is reported on its own too.
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

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
# Only statements hold statements, so the walks never descend into an expression: a lambda or
# comprehension can hold no def and no nesting block.
_BLOCKS = (ast.stmt, ast.excepthandler, ast.match_case)


@dataclass
class FunctionComplexity:
    """Complexity metrics for a single function or method."""

    name: str
    line_number: int
    end_line_number: int
    cyclomatic_complexity: int
    max_nesting_depth: int
    is_method: bool = False


def nesting_depth(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Return one function's deepest nesting, its body being depth 1.

    A nesting block's own test, target or items sit one level in, so the block reaches one
    level deeper than itself. The walk keeps its own stack rather than recursing (#586).
    """
    deepest = 1
    pending: list[tuple[ast.AST, int]] = [(func, 1)]
    while pending:
        current, depth = pending.pop()
        inner = depth + isinstance(current, _NESTING)
        deepest = max(deepest, inner)
        pending.extend(
            (child, inner)
            for child in ast.iter_child_nodes(current)
            if isinstance(child, _BLOCKS) and not isinstance(child, _FUNCTIONS)
        )
    return deepest


def mccabe_complexity(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Return one function's McCabe complexity, as Ruff's C901 counts it."""
    return 1 + _block_complexity(func.body)


def _block_complexity(statements: Sequence[ast.stmt]) -> int:
    return sum(_statement_complexity(statement) for statement in statements)


def _statement_complexity(statement: ast.stmt) -> int:
    """Count one statement's decision points; Ruff walks statement lists, never expressions."""
    match statement:
        case ast.If() | ast.For() | ast.AsyncFor() | ast.While():
            # An `elif` is an If in `orelse`, so it adds its own 1, as Ruff's elif clause does.
            return 1 + _block_complexity(statement.body) + _block_complexity(statement.orelse)
        case ast.FunctionDef() | ast.AsyncFunctionDef():
            return mccabe_complexity(statement)
        case ast.With() | ast.AsyncWith() | ast.ClassDef():
            return _block_complexity(statement.body)
        case ast.Try() | ast.TryStar():
            return _try_complexity(statement)
        case ast.Match():
            return _match_complexity(statement)
    return 0


def _try_complexity(statement: ast.Try | ast.TryStar) -> int:
    handlers = sum(1 + _block_complexity(handler.body) for handler in statement.handlers)
    has_else = 1 if statement.orelse else 0
    return (
        _block_complexity(statement.body)
        + handlers
        + has_else
        + _block_complexity(statement.orelse)
        + _block_complexity(statement.finalbody)
    )


def _match_complexity(statement: ast.Match) -> int:
    cases = sum(1 + _block_complexity(case.body) for case in statement.cases)
    last = statement.cases[-1]
    # A trailing catch-all case is the match's `else`, which adds nothing.
    catch_all = 1 if last.guard is None and _is_irrefutable(last.pattern) else 0
    return cases - catch_all


def _is_irrefutable(pattern: ast.pattern) -> bool:
    if isinstance(pattern, ast.MatchAs):
        return pattern.pattern is None or _is_irrefutable(pattern.pattern)
    if isinstance(pattern, ast.MatchOr):
        return any(_is_irrefutable(alternative) for alternative in pattern.patterns)
    return False


def _functions(
    tree: ast.AST,
) -> Iterator[tuple[ast.FunctionDef | ast.AsyncFunctionDef, bool]]:
    """Yield every function in source order, with whether the nearest def or class is a class."""
    pending: list[tuple[ast.AST, bool]] = [(tree, False)]
    while pending:
        node, in_class = pending.pop()
        if isinstance(node, _FUNCTIONS):
            yield node, in_class
        if isinstance(node, (*_FUNCTIONS, ast.ClassDef)):
            in_class = isinstance(node, ast.ClassDef)
        blocks = [child for child in ast.iter_child_nodes(node) if isinstance(child, _BLOCKS)]
        pending.extend((child, in_class) for child in reversed(blocks))


def measure_tree(tree: ast.AST) -> list[FunctionComplexity]:
    """Measure every function in a parsed module, in source order.

    A function is a method when the nearest def or class around it is a class.
    """
    return [_measure_function(func, is_method=in_class) for func, in_class in _functions(tree)]


def _measure_function(
    func: ast.FunctionDef | ast.AsyncFunctionDef, *, is_method: bool
) -> FunctionComplexity:
    return FunctionComplexity(
        name=func.name,
        line_number=func.lineno,
        end_line_number=func.end_lineno or func.lineno,
        cyclomatic_complexity=mccabe_complexity(func),
        max_nesting_depth=nesting_depth(func),
        is_method=is_method,
    )


def breaches(path: Path, max_depth: int) -> list[str]:
    """Report every function in one file nested deeper than the cap."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, RecursionError, MemoryError) as exc:
        # The parser itself overflows on a deep enough expression: a RecursionError, or a
        # MemoryError ("Parser stack overflowed") for a long unary chain.
        return [f"{path}: could not parse ({exc})"]

    return [
        f"{path}:{func.lineno}: {func.name} nesting {depth} > {max_depth}"
        for func, _ in _functions(tree)
        if (depth := nesting_depth(func)) > max_depth
    ]


def main(argv: Sequence[str] | None = None) -> int:
    """Check the Python files pre-commit passes, reporting every breach before failing."""
    parser = argparse.ArgumentParser(
        prog="python -m devops_cli.core.code_metrics",
        description="Fail when a function in the given Python files nests deeper than the cap.",
    )
    parser.add_argument("--max-depth", type=int, required=True, help="deepest nesting allowed")
    parser.add_argument("files", nargs="*", type=Path, help="Python files to check")
    args = parser.parse_args(argv)

    found = [
        line
        for path in args.files
        if path.suffix == ".py" and path.is_file()
        for line in breaches(path, args.max_depth)
    ]
    for line in found:
        print(line, file=sys.stderr)
    if found:
        print(
            f"\n{len(found)} nesting breach(es). AGENTS.md caps nesting depth at "
            f"{args.max_depth}; decompose the block into a helper.",
            file=sys.stderr,
        )
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
