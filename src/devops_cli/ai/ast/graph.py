"""Whole-repository multilingual code graph builder and symbol dependency resolver."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from devops_cli.ai.ast.engine import EXT_TO_LANG, TreeSitterEngine
from devops_cli.ai.ast.models import CodeGraph, CodeGraphEdge, PolyglotFileMap, PolyglotSymbol
from devops_cli.core.repo import find_worktree_root, is_ignored_by_git

logger = logging.getLogger(__name__)


def _is_excluded(path: Path, repo_root: Path) -> bool:
    """Whether `path` is left out of the graph: a symlink, or ignored by `repo_root`'s rules."""
    return path.is_symlink() or is_ignored_by_git(repo_root, path)


def _list_folder(folder: Path, repo_root: Path) -> tuple[list[Path], list[Path]]:
    """Return the files of `folder` and its subfolders that git does not ignore, as listed."""
    files: list[Path] = []
    subfolders: list[Path] = []
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                path = folder / entry.name
                if not entry.is_dir(follow_symlinks=False):
                    files.append(path)
                elif not is_ignored_by_git(repo_root, path, is_dir=True):
                    subfolders.append(path)
    except OSError as exc:
        # `Path.rglob` also went past a folder that it could not list.
        logger.debug("Cannot list %s for the code graph: %s", folder, exc)
    return files, subfolders


def _walk_files(root_dir: Path, repo_root: Path) -> list[Path]:
    """List the files under `root_dir` once, and skip each folder that git ignores, whole.

    A walk per extension also went into `.venv` and the other ignored folders, which took
    most of a build. The order is the order of `Path.rglob`, so `max_files` keeps the same
    files: each subfolder of a folder gives its files in turn, then the walk goes into the
    last subfolder first.
    """
    files, subfolders = _list_folder(root_dir, repo_root)
    pending = [subfolders]
    while pending:
        for folder in pending.pop():
            folder_files, folder_subfolders = _list_folder(folder, repo_root)
            files.extend(folder_files)
            pending.append(folder_subfolders)
    return files


def _collect_target_files(root_dir: Path, max_files: int) -> list[Path]:
    repo_root = find_worktree_root(root_dir)
    walked = _walk_files(root_dir, repo_root)
    candidates = [path for ext in sorted(EXT_TO_LANG) for path in walked if path.name.endswith(ext)]
    candidates.extend(
        path
        for path in walked
        if path.name.startswith(("Dockerfile", "Containerfile"))
        and path.is_file()
        and path not in candidates
    )
    files: list[Path] = []
    for candidate in candidates:
        if not _is_excluded(candidate, repo_root):
            files.append(candidate)
            if len(files) >= max_files:
                break
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
    lines = file_lines[sym.span.line_start - 1 : sym.span.line_end]
    if len(lines) > 1:
        return "\n".join(lines[1:])
    return "\n".join(lines)


def _is_call_in_body(target_name: str, body: str) -> bool:
    # The call pattern holds the name as written, so a body without the name cannot match it.
    # The substring test skips the regex for almost every pair; one compile per pair missed
    # the `re` cache and took most of a build.
    return target_name in body and bool(re.search(rf"\b{re.escape(target_name)}\s*\(", body))


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
        self.root_dir = root_dir or find_worktree_root(Path.cwd())
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
