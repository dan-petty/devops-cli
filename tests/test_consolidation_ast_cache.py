"""Test suite for high-performance in-memory ASTCache."""

from __future__ import annotations

import time
from pathlib import Path

from devops_cli.ai.ast_cache import ASTCache, global_ast_cache


def test_ast_cache_parses_and_caches_ast(tmp_path: Path) -> None:
    """ASTCache parses Python files and caches the AST node object across subsequent calls."""
    cache = ASTCache()
    sample = tmp_path / "sample.py"
    sample.write_text("def hello() -> str:\n    return 'world'\n", encoding="utf-8")

    tree1 = cache.get_ast(sample)
    assert tree1 is not None
    assert cache.stats["hits"] == 0
    assert cache.stats["misses"] == 1

    tree2 = cache.get_ast(sample)
    assert tree2 is tree1
    assert cache.stats["hits"] == 1


def test_ast_cache_invalidates_on_mtime_change(tmp_path: Path) -> None:
    """When file mtime advances, ASTCache invalidates and reparses the updated content."""
    cache = ASTCache()
    sample = tmp_path / "sample2.py"
    sample.write_text("X = 1\n", encoding="utf-8")

    tree1 = cache.get_ast(sample)
    assert tree1 is not None

    # Update file content and advance mtime
    time.sleep(0.05)
    sample.write_text("X = 2\nY = 3\n", encoding="utf-8")

    tree2 = cache.get_ast(sample)
    assert tree2 is not tree1
    assert cache.stats["misses"] == 2


def test_ast_cache_extracts_exported_symbols(tmp_path: Path) -> None:
    """ASTCache extracts defined top-level functions, classes, and __all__ variables."""
    cache = ASTCache()
    sample = tmp_path / "module.py"
    sample.write_text(
        "__all__ = ['alpha']\nalpha = 10\nbeta = 20\ndef compute(): pass\nclass Worker: pass\n",
        encoding="utf-8",
    )

    symbols = cache.get_exported_symbols(sample)
    assert "alpha" in symbols
    assert "beta" in symbols
    assert "compute" in symbols
    assert "Worker" in symbols


def test_ast_cache_handles_syntax_errors(tmp_path: Path) -> None:
    """When target file contains invalid Python syntax, returns None safely without crashing."""
    cache = ASTCache()
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def invalid syntax :::\n", encoding="utf-8")

    tree = cache.get_ast(bad_file)
    assert tree is None
    symbols = cache.get_exported_symbols(bad_file)
    assert symbols == set()


def test_global_ast_cache_singleton() -> None:
    """Global AST cache instance exists and can be cleared."""
    global_ast_cache.clear()
    assert global_ast_cache.stats["hits"] == 0
    assert global_ast_cache.stats["misses"] == 0
