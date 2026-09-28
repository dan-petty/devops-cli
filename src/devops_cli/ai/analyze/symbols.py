"""AST symbol extraction and delta analysis between base and head source revisions."""

from __future__ import annotations

import ast


def extract_python_source_symbols(content: str | None) -> set[str]:
    """Extract top-level and class member symbols from Python source code."""
    if not content:
        return set()
    try:
        tree = ast.parse(content)
    except SyntaxError, ValueError, RecursionError:
        return set()

    from devops_cli.ai.ast_cache import _extract_symbols_from_tree
    from devops_cli.ai.repomap import _extract_class_methods

    symbols = set(_extract_symbols_from_tree(tree))
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef):
            for method in _extract_class_methods(node):
                symbols.add(method.name)
                symbols.add(f"{node.name}.{method.name}")
    return symbols


def compute_symbol_delta(
    base_content: str | None,
    head_content: str | None,
) -> tuple[list[str], list[str], list[str]]:
    """Compute (added, removed, retained) symbol lists from base and head source contents."""
    base_symbols = extract_python_source_symbols(base_content)
    head_symbols = extract_python_source_symbols(head_content)
    added = sorted(head_symbols - base_symbols)
    removed = sorted(base_symbols - head_symbols)
    retained = sorted(head_symbols & base_symbols)
    return added, removed, retained
