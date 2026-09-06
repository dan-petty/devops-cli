"""AST-based Cyclomatic Complexity and Indentation Depth Scanner."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from devops_cli.ai.review_schema import Finding
from devops_cli.core.repo import find_top_level_repo_root


@dataclass
class FunctionComplexity:
    """Complexity metrics for a single function or method."""

    name: str
    line_number: int
    end_line_number: int
    cyclomatic_complexity: int
    max_nesting_depth: int
    is_method: bool = False


@dataclass
class FileComplexityReport:
    """Complexity report for a single Python file."""

    file_path: Path
    functions: list[FunctionComplexity] = field(default_factory=list)
    file_max_complexity: int = 1
    file_max_nesting: int = 0
    errors: list[str] = field(default_factory=list)


class _ComplexityVisitor(ast.NodeVisitor):
    """AST visitor calculating McCabe complexity and nesting depth."""

    def __init__(self) -> None:
        self.functions: list[FunctionComplexity] = []
        self._current_function: str | None = None
        self._func_start_line: int = 1
        self._func_end_line: int = 1
        self._func_complexity: int = 1
        self._func_max_depth: int = 0
        self._current_depth: int = 0
        self._class_depth: int = 0

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_depth += 1
        self.generic_visit(node)
        self._class_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._handle_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._handle_function(node, is_async=True)

    def _handle_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool
    ) -> None:
        old_func = self._current_function
        old_start = self._func_start_line
        old_end = self._func_end_line
        old_comp = self._func_complexity
        old_max_depth = self._func_max_depth
        old_depth = self._current_depth

        self._current_function = node.name
        self._func_start_line = node.lineno
        self._func_end_line = getattr(node, "end_lineno", node.lineno)
        self._func_complexity = 1
        self._func_max_depth = 0
        self._current_depth = 0
        is_method = self._class_depth > 0

        # Visit child nodes
        for item in node.body:
            self._visit_with_depth(item, depth=1)

        self.functions.append(
            FunctionComplexity(
                name=node.name,
                line_number=self._func_start_line,
                end_line_number=self._func_end_line,
                cyclomatic_complexity=self._func_complexity,
                max_nesting_depth=self._func_max_depth,
                is_method=is_method,
            )
        )

        self._current_function = old_func
        self._func_start_line = old_start
        self._func_end_line = old_end
        self._func_complexity = old_comp
        self._func_max_depth = old_max_depth
        self._current_depth = old_depth

    def _visit_with_depth(self, node: ast.AST, depth: int) -> None:
        if depth > self._func_max_depth:
            self._func_max_depth = depth

        # Track branching constructs that increase Cyclomatic Complexity
        if isinstance(
            node,
            (
                ast.If,
                ast.While,
                ast.For,
                ast.AsyncFor,
                ast.ExceptHandler,
                ast.With,
                ast.AsyncWith,
                ast.Assert,
            ),
        ):
            self._func_complexity += 1
            new_depth = depth + 1
        elif isinstance(node, ast.BoolOp):
            self._func_complexity += len(node.values) - 1
            new_depth = depth
        elif isinstance(node, ast.IfExp):
            self._func_complexity += 1
            new_depth = depth
        elif isinstance(node, ast.Match):
            self._func_complexity += len(node.cases)
            new_depth = depth + 1
        else:
            new_depth = depth

        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Do not recurse into nested function with current function's stats
                self.visit(child)
            else:
                self._visit_with_depth(child, new_depth)


def analyze_file_complexity(file_path: Path) -> FileComplexityReport:
    """Analyze cyclomatic complexity and indentation depth for a Python file."""
    report = FileComplexityReport(file_path=file_path)
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except Exception as exc:
        report.errors.append(f"Failed to parse {file_path}: {exc}")
        return report

    visitor = _ComplexityVisitor()
    visitor.visit(tree)
    report.functions = visitor.functions

    if visitor.functions:
        report.file_max_complexity = max(f.cyclomatic_complexity for f in visitor.functions)
        report.file_max_nesting = max(f.max_nesting_depth for f in visitor.functions)

    return report


def run_complexity_scan(
    target_path: Path,
    *,
    max_complexity: int = 10,
    max_nesting_depth: int = 5,
) -> list[Finding]:
    """Scan a target path (file or directory) for complexity and nesting violations."""
    findings: list[Finding] = []
    target = target_path.resolve()

    if target_path.is_symlink():
        return findings

    if target.is_file() and target.suffix == ".py":
        files = [target]
    elif target.is_dir():
        ignored_dirs = {".venv", ".data", ".git", "repos", "scratch"}
        files = [
            p
            for p in target.rglob("*.py")
            if not p.is_symlink() and not any(part in ignored_dirs for part in p.parts)
        ]
    else:
        return findings

    root = find_top_level_repo_root(Path.cwd())
    for py_file in files:
        rep = analyze_file_complexity(py_file)
        try:
            rel_path = str(py_file.resolve().relative_to(root))
        except ValueError:
            rel_path = py_file.name

        for fn in rep.functions:
            loc = f"{rel_path}:{fn.line_number}-{fn.end_line_number}"

            if fn.cyclomatic_complexity > max_complexity:
                findings.append(
                    Finding(
                        severity="HIGH"
                        if fn.cyclomatic_complexity > max_complexity * 1.5
                        else "MEDIUM",
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
                        severity="HIGH"
                        if fn.max_nesting_depth > max_nesting_depth + 2
                        else "MEDIUM",
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
