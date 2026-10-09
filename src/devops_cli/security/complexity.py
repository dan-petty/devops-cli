"""Findings for functions over the complexity or nesting cap, from `core.code_metrics`."""

from __future__ import annotations

import ast
from pathlib import Path

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import DEFAULT_MAX_COMPLEXITY, DEFAULT_MAX_NESTING_DEPTH
from devops_cli.core.code_metrics import FunctionComplexity, measure_tree
from devops_cli.core.repo import find_worktree_root, list_repo_files


def _evaluate_function_findings(
    fn: FunctionComplexity,
    rel_path: str,
    max_complexity: int,
    max_nesting_depth: int,
) -> list[Finding]:
    """Generate Finding objects for functions violating complexity or nesting limits."""
    findings: list[Finding] = []
    loc = f"{rel_path}:{fn.line_number}-{fn.end_line_number}"

    if fn.cyclomatic_complexity > max_complexity:
        findings.append(
            Finding(
                severity="HIGH" if fn.cyclomatic_complexity > max_complexity * 1.5 else "MEDIUM",
                location=loc,
                title=f"High Cyclomatic Complexity in `{fn.name}` ({fn.cyclomatic_complexity} > {max_complexity})",
                description=(
                    f"Function `{fn.name}` has a Cyclomatic Complexity of {fn.cyclomatic_complexity}, "
                    f"which exceeds the configured threshold of {max_complexity}."
                ),
                fix="Decompose function into smaller helper functions or functional pipelines.",
            )
        )

    if fn.max_nesting_depth > max_nesting_depth:
        findings.append(
            Finding(
                severity="HIGH" if fn.max_nesting_depth > max_nesting_depth + 2 else "MEDIUM",
                location=loc,
                title=f"Excessive Nesting Depth in `{fn.name}` ({fn.max_nesting_depth} > {max_nesting_depth})",
                description=(
                    f"Function `{fn.name}` reaches a nesting depth of {fn.max_nesting_depth}, "
                    f"exceeding the strict limit of {max_nesting_depth} levels."
                ),
                fix="Flatten nested loops and branches using guard clauses or early returns.",
            )
        )
    return findings


def run_complexity_scan(
    target_path: Path,
    *,
    max_complexity: int = DEFAULT_MAX_COMPLEXITY,
    max_nesting_depth: int = DEFAULT_MAX_NESTING_DEPTH,
) -> list[Finding]:
    """Scan a target path (file or directory) for complexity and nesting violations."""
    findings: list[Finding] = []
    target = target_path.resolve()

    if target_path.is_symlink():
        return findings

    if target.is_file() and target.suffix == ".py":
        files = [target]
        root = find_worktree_root(target)
    elif target.is_dir():
        root = find_worktree_root(target)
        files = [p for p in list_repo_files(target) if p.suffix == ".py" and not p.is_symlink()]
    else:
        return findings
    for py_file in files:
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except OSError, SyntaxError, ValueError, RecursionError, MemoryError:
            # An unreadable or unparseable file has no functions to measure; the scan reports
            # the rest. ValueError covers a file that is not UTF-8.
            continue
        try:
            rel_path = str(py_file.resolve().relative_to(root))
        except ValueError:
            rel_path = py_file.name

        for fn in measure_tree(tree):
            findings.extend(
                _evaluate_function_findings(fn, rel_path, max_complexity, max_nesting_depth)
            )

    return findings
