"""Findings for functions over the complexity or nesting cap, from `core.code_metrics`."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.constants import CONST_COMPLEXITY_SOURCE
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


def measure_python_text_complexity(
    source_code: str, filename: str = "<source>"
) -> dict[str, FunctionComplexity]:
    """Measure McCabe complexity of all functions in Python source string."""
    try:
        tree = ast.parse(source_code, filename=filename)
        return {fn.name: fn for fn in measure_tree(tree)}
    except SyntaxError, ValueError, RecursionError, MemoryError:
        return {}


def _evaluate_single_function_delta(
    rel_path: str,
    name: str,
    base_fn: FunctionComplexity | None,
    head_fn: FunctionComplexity | None,
    cap: int,
    max_increase: int | None,
) -> tuple[dict[str, Any] | None, Finding | None]:
    """Evaluate complexity delta and possible finding for one function across base and head."""
    if base_fn is not None and head_fn is not None:
        before = base_fn.cyclomatic_complexity
        after = head_fn.cyclomatic_complexity
        if before == after:
            return None, None
        delta = {
            "file": rel_path,
            "function": name,
            "before": before,
            "after": after,
            "source": CONST_COMPLEXITY_SOURCE,
        }
        crossed = after > cap
        increase_hit = max_increase is not None and (after - before) >= max_increase
        if crossed or increase_hit:
            loc = f"{rel_path}:{head_fn.line_number}"
            finding = Finding(
                severity="HIGH" if after > cap * 1.5 else "MEDIUM",
                location=loc,
                title=f"High Cyclomatic Complexity in `{name}` ({after} > {cap})",
                description=(
                    f"Function `{name}` complexity rose to {after} (was {before}), "
                    f"exceeding the project cap of {cap}."
                ),
                fix="Decompose function into smaller helper functions or functional pipelines.",
            )
            return delta, finding
        return delta, None

    if head_fn is not None and base_fn is None:
        after = head_fn.cyclomatic_complexity
        delta = {
            "file": rel_path,
            "function": name,
            "before": None,
            "after": after,
            "source": CONST_COMPLEXITY_SOURCE,
        }
        if after > cap:
            loc = f"{rel_path}:{head_fn.line_number}"
            finding = Finding(
                severity="HIGH" if after > cap * 1.5 else "MEDIUM",
                location=loc,
                title=f"High Cyclomatic Complexity in `{name}` ({after} > {cap})",
                description=(
                    f"Added function `{name}` has a Cyclomatic Complexity of {after}, "
                    f"exceeding the project cap of {cap}."
                ),
                fix="Decompose function into smaller helper functions or functional pipelines.",
            )
            return delta, finding
        return delta, None

    if base_fn is not None and head_fn is None:
        delta = {
            "file": rel_path,
            "function": name,
            "before": base_fn.cyclomatic_complexity,
            "after": None,
            "source": CONST_COMPLEXITY_SOURCE,
        }
        return delta, None

    return None, None


def compute_complexity_deltas(
    base_files: dict[str, str],
    head_files: dict[str, str],
    *,
    cap: int = DEFAULT_MAX_COMPLEXITY,
    max_increase: int | None = None,
) -> tuple[list[dict[str, Any]], list[Finding]]:
    """Compute per-function complexity deltas before/after for changed functions (#873)."""
    deltas: list[dict[str, Any]] = []
    findings: list[Finding] = []

    all_files = sorted(set(base_files.keys()) | set(head_files.keys()))
    for rel_path in all_files:
        base_src = base_files.get(rel_path)
        head_src = head_files.get(rel_path)

        base_funcs = measure_python_text_complexity(base_src, rel_path) if base_src else {}
        head_funcs = measure_python_text_complexity(head_src, rel_path) if head_src else {}

        all_names = sorted(set(base_funcs.keys()) | set(head_funcs.keys()))
        for name in all_names:
            delta, finding = _evaluate_single_function_delta(
                rel_path,
                name,
                base_funcs.get(name),
                head_funcs.get(name),
                cap,
                max_increase,
            )
            if delta is not None:
                deltas.append(delta)
            if finding is not None:
                findings.append(finding)

    return deltas, findings
