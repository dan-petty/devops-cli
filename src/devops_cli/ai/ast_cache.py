"""In-memory thread-safe AST cache for high-performance syntax analysis."""

from __future__ import annotations

import ast
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


def _extract_assign_targets(node: ast.Assign) -> set[str]:
    """Extract identifier names from an Assign node."""
    return {target.id for target in node.targets if isinstance(target, ast.Name)}


def _extract_symbols_from_tree(tree: ast.AST) -> set[str]:
    """Extract declared top-level functions, classes, and assigned symbols from AST."""
    symbols: set[str] = set()
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.add(node.name)
        elif isinstance(node, ast.Assign):
            symbols.update(_extract_assign_targets(node))
    return symbols


class ASTCache:
    """Thread-safe AST cache indexed by file path and modification time."""

    def __init__(self) -> None:
        self._ast_store: dict[Path, tuple[float, ast.AST]] = {}
        self._symbols_store: dict[Path, tuple[float, set[str]]] = {}
        self._lock = threading.Lock()
        self.stats: dict[str, int] = {"hits": 0, "misses": 0}

    def clear(self) -> None:
        """Clear all cached AST and symbol entries and reset counters."""
        with self._lock:
            self._ast_store.clear()
            self._symbols_store.clear()
            self.stats["hits"] = 0
            self.stats["misses"] = 0

    def get_ast(self, file_path: Path) -> ast.AST | None:
        """Retrieve cached AST node or parse from disk if modified."""
        try:
            mtime = file_path.stat().st_mtime
        except OSError, RuntimeError:
            return None

        with self._lock:
            if file_path in self._ast_store:
                cached_mtime, tree = self._ast_store[file_path]
                if cached_mtime == mtime:
                    self.stats["hits"] += 1
                    return tree

        # Cache miss: parse AST outside lock
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(file_path))
        except (SyntaxError, OSError, UnicodeDecodeError) as exc:
            logger.debug("Failed parsing AST for '%s': %s", file_path, exc)
            return None

        with self._lock:
            self._ast_store[file_path] = (mtime, tree)
            self.stats["misses"] += 1
            return tree

    def get_exported_symbols(self, file_path: Path) -> set[str]:
        """Extract top-level symbol names defined in the target Python module."""
        try:
            mtime = file_path.stat().st_mtime
        except OSError, RuntimeError:
            return set()

        with self._lock:
            if file_path in self._symbols_store:
                cached_mtime, symbols = self._symbols_store[file_path]
                if cached_mtime == mtime:
                    return symbols

        tree = self.get_ast(file_path)
        if tree is None:
            return set()

        symbols = _extract_symbols_from_tree(tree)
        with self._lock:
            self._symbols_store[file_path] = (mtime, symbols)
            return symbols


global_ast_cache = ASTCache()
