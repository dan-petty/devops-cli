"""AST import extractor for source code and unified git diffs."""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence

_IMPORT_LINE_REGEX = re.compile(
    r"^\s*(?:from\s+([a-zA-Z0-9_.]+)\s+import\s+([^#\n]+)|import\s+([^#\n]+))"
)


def _parse_regex_import_line(line: str) -> list[tuple[str, str | None]]:
    """Fallback regex extraction of module and symbol from a single import line."""
    m = _IMPORT_LINE_REGEX.match(line)
    if not m:
        return []

    from_mod, from_names, direct_imports = m.groups()
    if from_mod and from_names:
        # from mod import sym1, sym2 as alias
        names = [n.strip().split()[0] for n in from_names.split(",") if n.strip()]
        return [(from_mod, name) for name in names if name != "*"]

    if direct_imports:
        # import mod1, mod2 as alias
        modules = [mod.strip().split()[0] for mod in direct_imports.split(",") if mod.strip()]
        return [(mod, None) for mod in modules]

    return []


def _extract_from_ast_node(node: ast.AST) -> list[tuple[str, str | None]]:
    """Extract (module, symbol) tuples from an AST import node."""
    if isinstance(node, ast.Import):
        return [(alias.name, None) for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        return [(node.module, alias.name) for alias in node.names if alias.name != "*"]
    return []


def extract_imports_from_source(code: str) -> list[tuple[str, str | None]]:
    """Extract imported modules and symbols from Python source code via AST with regex fallback."""
    if not code or not code.strip():
        return []

    try:
        tree = ast.parse(code)
        imports: list[tuple[str, str | None]] = []
        for node in ast.walk(tree):
            imports.extend(_extract_from_ast_node(node))
        return imports
    except SyntaxError, ValueError:
        # Fallback to line-by-line regex extraction on partial or unparseable source
        results: list[tuple[str, str | None]] = []
        for line in code.splitlines():
            results.extend(_parse_regex_import_line(line))
        return results


def extract_imports_from_diff(diff_text: str) -> list[tuple[str, str | None]]:
    """Extract imported modules and symbols added or modified in a unified git diff."""
    if not diff_text or not diff_text.strip():
        return []

    added_lines: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            stripped = line[1:].strip()
            if stripped.startswith(("import ", "from ")):
                added_lines.append(stripped)

    results: list[tuple[str, str | None]] = []
    for line in added_lines:
        results.extend(_parse_regex_import_line(line))

    # De-duplicate while preserving insertion order
    seen: set[tuple[str, str | None]] = set()
    deduped: list[tuple[str, str | None]] = []
    for item in results:
        if item not in seen:
            seen.add(item)
            deduped.append(item)

    return deduped


def group_imports_by_package(
    imports: Sequence[tuple[str, str | None]],
) -> dict[str, set[str]]:
    """Group extracted imports by top-level package name mapped to set of imported symbol names."""
    grouped: dict[str, set[str]] = {}
    for mod, sym in imports:
        top_pkg = mod.split(".", 1)[0]
        grouped.setdefault(top_pkg, set())
        if sym:
            grouped[top_pkg].add(sym)
            # Also record qualified symbol if sub-module import
            if "." in mod:
                grouped[top_pkg].add(f"{mod}.{sym}")
        else:
            grouped[top_pkg].add(mod)
    return grouped
