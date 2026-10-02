"""AST symbol extraction and delta analysis between base and head source revisions."""

from __future__ import annotations

import ast
import logging
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath

from devops_cli.config.constants import (
    CONST_PYTHON_SOURCE_SUFFIXES,
    CONST_SYMBOL_DELTA_BASE_CHANGE_TYPES,
)
from devops_cli.models.ai import FileAnalysisMeta
from devops_cli.models.git import ChangedFile

logger = logging.getLogger(__name__)

SymbolDelta = tuple[list[str], list[str], list[str]]


@dataclass(frozen=True)
class BaseRevision:
    """The revision a reviewed diff starts from: the files the diff changed, and `read`, which
    returns a file's text there by its path at that revision, or None when it cannot.

    `read_head` does the same where the diff ends, when that is a commit rather than the files
    on disk: a branch that is not checked out, or one whose checkout has uncommitted edits the
    diff leaves out. Without it the reviewed files on disk are the head.
    """

    changes: tuple[ChangedFile, ...]
    read: Callable[[str], str | None]
    read_head: Callable[[str], str | None] | None = None


def extract_python_source_symbols(content: str | None) -> set[str]:
    """Extract top-level and class member symbols from Python source code."""
    if not content:
        return set()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
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
) -> SymbolDelta:
    """Compute (added, removed, retained) symbol lists from base and head source contents."""
    base_symbols = extract_python_source_symbols(base_content)
    head_symbols = extract_python_source_symbols(head_content)
    added = sorted(head_symbols - base_symbols)
    removed = sorted(base_symbols - head_symbols)
    retained = sorted(head_symbols & base_symbols)
    return added, removed, retained


def change_symbol_delta(
    change: ChangedFile,
    head_content: str | None,
    read_base: Callable[[str], str | None],
) -> SymbolDelta:
    """The (added, removed, retained) symbols of a changed Python file; empty when unknown.

    An added file's symbols are all added, and its base is never read. A modified, renamed or
    deleted file is compared with its base text, read at its old path. When that read fails the
    delta is unknown and stays empty: comparing with nothing would list every head symbol as
    added. Other changes, and files that are not Python, have none.
    """
    if PurePosixPath(change.path).suffix.lower() not in CONST_PYTHON_SOURCE_SUFFIXES:
        return [], [], []
    if change.change_type == "added":
        return compute_symbol_delta(None, head_content)
    if change.change_type not in CONST_SYMBOL_DELTA_BASE_CHANGE_TYPES:
        return [], [], []
    base_content = read_base(change.base_path)
    if base_content is None:
        logger.debug("No base text for %s; its symbol delta is unknown", change.base_path)
        return [], [], []
    return compute_symbol_delta(base_content, head_content)


def with_symbol_delta(meta: FileAnalysisMeta, delta: SymbolDelta) -> FileAnalysisMeta:
    """`meta` carrying exactly this delta, replacing any it had."""
    added, removed, retained = delta
    return meta.model_copy(
        update={"symbols_added": added, "symbols_removed": removed, "symbols_retained": retained}
    )
