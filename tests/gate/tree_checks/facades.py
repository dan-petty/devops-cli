"""The package facades of ai and github (#2164)."""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from pathlib import Path

from tests.support.paths import REPO_ROOT
from tests.support.trees import (
    parse_python_file,
)


def _find_package_submodules(pkg_dir: Path) -> set[str]:
    """Return all valid Python submodule names inside a package directory."""
    if not pkg_dir.is_dir():
        return set()
    return {
        child.stem if child.is_file() else child.name
        for child in pkg_dir.iterdir()
        if (child.is_file() and child.name.endswith(".py") and child.name != "__init__.py")
        or (child.is_dir() and (child / "__init__.py").exists())
    }


def _collect_facade_import_violations(
    tree: ast.AST,
    allowed_submodules: Mapping[str, set[str]],
    origin: str,
) -> list[str]:
    """Find any ImportFrom node on facade packages importing a non-submodule name."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module not in allowed_submodules:
            continue
        allowed = allowed_submodules[node.module]
        for alias in node.names:
            if alias.name not in allowed:
                violations.append(f"{origin}:{node.lineno}: from {node.module} import {alias.name}")
    return violations


def check_ai_and_github_package_inits_hold_only_docstrings(
    parsed_source_trees: dict[Path, ast.Module],
) -> None:
    """The six __init__.py files parse to a single docstring expression and nothing else (#1002, #776)."""
    init_paths = [
        REPO_ROOT / "src" / "devops_cli" / "ai" / "__init__.py",
        REPO_ROOT / "src" / "devops_cli" / "ai" / "agents" / "__init__.py",
        REPO_ROOT / "src" / "devops_cli" / "ai" / "mcp" / "__init__.py",
        REPO_ROOT / "src" / "devops_cli" / "config" / "__init__.py",
        REPO_ROOT / "src" / "devops_cli" / "core" / "__init__.py",
        REPO_ROOT / "src" / "devops_cli" / "github" / "__init__.py",
    ]
    failures = []
    for path in init_paths:
        tree = parsed_source_trees.get(path) or parse_python_file(path)
        is_only_docstring = (
            len(tree.body) == 1
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        )
        if not is_only_docstring:
            failures.append(str(path.relative_to(REPO_ROOT)))
    assert failures == []


def check_no_non_submodule_imports_from_ai_and_github_facades(
    parsed_repo_trees: dict[Path, ast.Module],
) -> None:
    """No import from facade packages names anything but a submodule (#1002, #776)."""
    facade_packages = {
        "devops_cli.ai": REPO_ROOT / "src" / "devops_cli" / "ai",
        "devops_cli.ai.agents": REPO_ROOT / "src" / "devops_cli" / "ai" / "agents",
        "devops_cli.ai.mcp": REPO_ROOT / "src" / "devops_cli" / "ai" / "mcp",
        "devops_cli.config": REPO_ROOT / "src" / "devops_cli" / "config",
        "devops_cli.core": REPO_ROOT / "src" / "devops_cli" / "core",
        "devops_cli.github": REPO_ROOT / "src" / "devops_cli" / "github",
    }
    allowed_submodules = {
        pkg_name: _find_package_submodules(pkg_dir) for pkg_name, pkg_dir in facade_packages.items()
    }
    violations: list[str] = []

    for py_file, tree in parsed_repo_trees.items():
        violations.extend(
            _collect_facade_import_violations(
                tree, allowed_submodules, str(py_file.relative_to(REPO_ROOT))
            )
        )

    fenced_re = re.compile(r"```python\n(.*?)```", re.DOTALL)
    kb_dir = REPO_ROOT / "src" / "devops_cli" / "ai" / "knowledge_base"
    if kb_dir.is_dir():
        for md_file in kb_dir.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            for idx, match in enumerate(fenced_re.finditer(content)):
                try:
                    tree = ast.parse(match.group(1))
                    violations.extend(
                        _collect_facade_import_violations(
                            tree,
                            allowed_submodules,
                            f"{md_file.relative_to(REPO_ROOT)} (block {idx + 1})",
                        )
                    )
                except SyntaxError:
                    continue

    assert violations == []
