"""Whole-repository multilingual code graph builder and symbol dependency resolver."""

from __future__ import annotations

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


def _link_call_edges(
    nodes: dict[str, PolyglotSymbol],
    file_map: PolyglotFileMap,
) -> list[CodeGraphEdge]:
    edges: list[CodeGraphEdge] = []
    symbol_names = {sym.name: k for k, sym in nodes.items()}

    for sym in file_map.symbols:
        # Check if symbol calls or references any other discovered symbol
        for target_name, target_key in symbol_names.items():
            if target_name != sym.name and target_name in sym.signature:
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
