"""Whole-repository multilingual code graph builder and symbol dependency resolver."""

from __future__ import annotations

import re
from pathlib import Path

from devops_cli.ai.ast.engine import EXT_TO_LANG, TreeSitterEngine
from devops_cli.ai.ast.models import CodeGraph, CodeGraphEdge, PolyglotFileMap, PolyglotSymbol
from devops_cli.core.repo import find_top_level_repo_root

EXCLUDE_DIRS = {
    ".venv",
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "build",
    "dist",
    ".data",
}


def _is_excluded(path: Path) -> bool:
    return any(part in path.parts for part in EXCLUDE_DIRS) or path.is_symlink()


def _collect_target_files(root_dir: Path, max_files: int) -> list[Path]:
    files: list[Path] = []
    for ext in sorted(EXT_TO_LANG.keys()):
        for candidate in root_dir.rglob(f"*{ext}"):
            if not _is_excluded(candidate):
                files.append(candidate)
            if len(files) >= max_files:
                return files
    return files


def _read_file_lines(path_str: str) -> list[str]:
    try:
        p = Path(path_str)
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        pass
    return []


def _extract_symbol_body(sym: PolyglotSymbol, file_lines: list[str]) -> str:
    """Extract symbol body text excluding signature declaration line."""
    if not file_lines:
        return sym.docstring
    lines = file_lines[sym.span.line_start - 1 : sym.span.line_end]
    if len(lines) > 1:
        return "\n".join(lines[1:])
    return "\n".join(lines)


def _is_call_in_body(target_name: str, body: str) -> bool:
    return bool(re.search(rf"\b{re.escape(target_name)}\s*\(", body))


def _link_call_edges(
    nodes: dict[str, PolyglotSymbol],
    file_map: PolyglotFileMap,
) -> list[CodeGraphEdge]:
    edges: list[CodeGraphEdge] = []
    symbol_names = {sym.name: k for k, sym in nodes.items()}
    file_lines = _read_file_lines(file_map.path)

    for sym in file_map.symbols:
        body = _extract_symbol_body(sym, file_lines)
        if not body:
            continue
        for target_name, target_key in symbol_names.items():
            if target_name != sym.name and _is_call_in_body(target_name, body):
                edges.append(
                    CodeGraphEdge(
                        source_symbol=f"{file_map.path}::{sym.name}",
                        target_symbol=target_key,
                        relation="calls",
                        file_path=file_map.path,
                        line_number=sym.span.line_start,
                    )
                )
    return edges


class CodeGraphBuilder:
    """Traverses repository files and synthesizes multi-file code dependency graphs."""

    def __init__(
        self,
        root_dir: Path | None = None,
        max_files: int = 100,
        engine: TreeSitterEngine | None = None,
    ) -> None:
        self.root_dir = root_dir or find_top_level_repo_root(Path.cwd())
        self.max_files = max_files
        self.engine = engine or TreeSitterEngine()

    def build(self) -> CodeGraph:
        """Scan repository files and build whole-project symbol and reference graph."""
        target_files = _collect_target_files(self.root_dir, self.max_files)
        nodes: dict[str, PolyglotSymbol] = {}
        file_maps: list[PolyglotFileMap] = []
        indexed_files: list[str] = []

        for file_path in target_files:
            file_map = self.engine.parse_file(file_path)
            if not file_map:
                continue
            file_maps.append(file_map)
            indexed_files.append(file_map.path)
            for sym in file_map.symbols:
                qual_key = f"{file_map.path}::{sym.name}"
                nodes[qual_key] = sym

        all_edges: list[CodeGraphEdge] = []
        for fm in file_maps:
            all_edges.extend(_link_call_edges(nodes, fm))

        return CodeGraph(
            nodes=nodes,
            edges=all_edges,
            files=indexed_files,
        )
