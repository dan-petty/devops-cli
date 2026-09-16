"""AI Context Packing & Symbol-Pruned Prompt Synthesizer.

Optimizes LLM prompt token efficiency by ranking imported symbols by usage density,
stripping unreferenced private methods/docstrings, and compressing code representations
while preserving strict interface fidelity and type annotations.
"""

from __future__ import annotations

import ast
import bisect
import logging
from collections.abc import Collection, Sequence
from pathlib import Path

from pydantic import BaseModel, Field

from devops_cli.ai.context_budget import (
    _get_tiktoken_encoding,
    count_tokens,
    truncate_to_token_limit,
)
from devops_cli.config.defaults import (
    DEFAULT_CONTEXT_PACKING_MAX_TOKENS,
    DEFAULT_CONTEXT_PACKING_TOTAL_BUDGET,
)

logger = logging.getLogger(__name__)


class PackedContext(BaseModel):
    """Packed and symbol-pruned code or context artifact."""

    content: str
    original_tokens: int
    packed_tokens: int
    reduction_ratio: float = 0.0
    pruned_symbols: list[str] = Field(default_factory=list)
    preserved_symbols: list[str] = Field(default_factory=list)
    truncated: bool = False


class PackingConfig(BaseModel):
    """Configuration options for context packing and symbol pruning."""

    max_tokens: int = DEFAULT_CONTEXT_PACKING_MAX_TOKENS
    strip_private: bool = True
    strip_docstrings: bool = False
    skeletonize: bool = True
    preserve_magic_methods: bool = True


def _is_private_symbol(name: str, preserve_magic: bool = True) -> bool:
    """Check if a symbol identifier is considered private."""
    if not name.startswith("_"):
        return False
    if preserve_magic and name.startswith("__") and name.endswith("__"):
        return False
    return True


def _make_ellipsis_expr() -> ast.Expr:
    """Create an AST Expr node representing '...'."""
    return ast.Expr(value=ast.Constant(value=...))


def _transform_docstring(docstring_node: ast.AST | None, strip_docstrings: bool) -> list[ast.stmt]:
    """Return transformed docstring statements."""
    if strip_docstrings or docstring_node is None:
        return []
    return [docstring_node]  # type: ignore[list-item]


def _skeletonize_function_body(
    fn_node: ast.FunctionDef | ast.AsyncFunctionDef,
    strip_docstrings: bool,
) -> list[ast.stmt]:
    """Produce a skeletonized function body containing optional docstring and ellipsis."""
    doc_stmt: ast.AST | None = None
    if fn_node.body and isinstance(fn_node.body[0], ast.Expr):
        first_val = fn_node.body[0].value
        if isinstance(first_val, ast.Constant) and isinstance(first_val.value, str):
            doc_stmt = fn_node.body[0]

    body: list[ast.stmt] = _transform_docstring(doc_stmt, strip_docstrings)
    body.append(_make_ellipsis_expr())
    return body


def _extract_assign_target_name(stmt: ast.Assign | ast.AnnAssign) -> str:
    """Extract identifier name from Assign or AnnAssign statement."""
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        return stmt.target.id
    if isinstance(stmt, ast.Assign) and stmt.targets and isinstance(stmt.targets[0], ast.Name):
        return stmt.targets[0].id
    return ""


def _prune_method_stmt(
    stmt: ast.FunctionDef | ast.AsyncFunctionDef,
    referenced: set[str],
    config: PackingConfig,
    pruned: list[str],
    preserved: list[str],
) -> ast.stmt | None:
    """Prune or skeletonize a function or method definition."""
    if config.strip_private and _is_private_symbol(stmt.name, config.preserve_magic_methods):
        if stmt.name not in referenced:
            pruned.append(stmt.name)
            return None
    preserved.append(stmt.name)
    if config.skeletonize:
        stmt.body = _skeletonize_function_body(stmt, config.strip_docstrings)
    return stmt


def _prune_assign_stmt(
    stmt: ast.Assign | ast.AnnAssign,
    referenced: set[str],
    config: PackingConfig,
    pruned: list[str],
    preserved: list[str],
) -> ast.stmt | None:
    """Prune or retain an assignment statement."""
    target_name = _extract_assign_target_name(stmt)
    if target_name and config.strip_private and _is_private_symbol(target_name):
        if target_name not in referenced:
            pruned.append(target_name)
            return None
    if target_name:
        preserved.append(target_name)
    return stmt


def _prune_class_stmt(
    stmt: ast.stmt,
    referenced: set[str],
    config: PackingConfig,
    pruned: list[str],
    preserved: list[str],
) -> ast.stmt | None:
    """Prune or skeletonize a statement within a class body."""
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return _prune_method_stmt(stmt, referenced, config, pruned, preserved)
    if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
        return _prune_assign_stmt(stmt, referenced, config, pruned, preserved)
    return stmt


def _prune_class_def(
    node: ast.ClassDef,
    referenced: set[str],
    config: PackingConfig,
    pruned: list[str],
    preserved: list[str],
) -> ast.ClassDef:
    """Prune methods and attributes inside a class definition."""
    preserved.append(node.name)
    new_body: list[ast.stmt] = []

    has_doc = bool(
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    )
    start_idx = 1 if has_doc else 0
    if has_doc and not config.strip_docstrings:
        new_body.append(node.body[0])

    for stmt in node.body[start_idx:]:
        pruned_stmt = _prune_class_stmt(stmt, referenced, config, pruned, preserved)
        if pruned_stmt is not None:
            new_body.append(pruned_stmt)

    node.body = new_body or [_make_ellipsis_expr()]
    return node


def _prune_top_level_stmt(
    stmt: ast.stmt,
    referenced: set[str],
    config: PackingConfig,
    pruned: list[str],
    preserved: list[str],
) -> ast.stmt | None:
    """Prune or skeletonize a top-level statement in a module."""
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return _prune_method_stmt(stmt, referenced, config, pruned, preserved)
    if isinstance(stmt, ast.ClassDef):
        return _prune_class_def(stmt, referenced, config, pruned, preserved)
    if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
        return _prune_assign_stmt(stmt, referenced, config, pruned, preserved)
    if (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
        and config.strip_docstrings
    ):
        return None
    return stmt


def _fallback_prune_code(code: str, max_tokens: int) -> str:
    """Line-oriented zero-crash fallback pruner for non-Python or unparseable code."""
    lines: list[str] = []
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("#"):
            continue
        if not stripped and lines and not lines[-1].strip():
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    return truncate_to_token_limit(cleaned, max_tokens)


def _build_pruned_ast_body(
    tree: ast.Module,
    ref_set: set[str],
    cfg: PackingConfig,
    pruned: list[str],
    preserved: list[str],
) -> list[ast.stmt]:
    """Construct pruned module body from AST tree."""
    has_mod_doc = bool(
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    )
    start_idx = 1 if has_mod_doc else 0
    new_body: list[ast.stmt] = []
    if has_mod_doc and not cfg.strip_docstrings:
        new_body.append(tree.body[0])

    for stmt in tree.body[start_idx:]:
        pruned_stmt = _prune_top_level_stmt(stmt, ref_set, cfg, pruned, preserved)
        if pruned_stmt is not None:
            new_body.append(pruned_stmt)
    return new_body


def _handle_syntax_fallback(code: str, orig_tokens: int, cfg: PackingConfig) -> PackedContext:
    """Handle fallback packing on syntax error."""
    fallback_text = _fallback_prune_code(code, cfg.max_tokens)
    fallback_tokens = count_tokens(fallback_text)
    ratio = max(0.0, (orig_tokens - fallback_tokens) / max(1, orig_tokens))
    return PackedContext(
        content=fallback_text,
        original_tokens=orig_tokens,
        packed_tokens=fallback_tokens,
        reduction_ratio=round(ratio, 3),
        truncated=fallback_tokens < orig_tokens,
    )


def _strip_docstrings_from_node(node: ast.AST) -> None:
    """Remove docstring expressions from functions, classes, and module."""
    for child in ast.walk(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if child.body and isinstance(child.body[0], ast.Expr):
                val = getattr(child.body[0], "value", None)
                if isinstance(val, ast.Constant) and isinstance(val.value, str):
                    child.body = child.body[1:] if len(child.body) > 1 else [_make_ellipsis_expr()]


def _estimate_stmt_tokens(stmt: ast.stmt) -> int:
    """Estimate token weight of an AST statement node with memoization."""
    cached: int | None = getattr(stmt, "_est_tokens", None)
    if cached is not None:
        return cached

    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        arg_len = sum(len(arg.arg) + 8 for arg in stmt.args.args)
        ret_len = 10 if stmt.returns else 0
        char_est = 10 + len(stmt.name) + arg_len + ret_len + 10
    elif isinstance(stmt, ast.ClassDef):
        char_est = 15 + len(stmt.name)
    elif isinstance(stmt, (ast.Assign, ast.AnnAssign)):
        char_est = 30
    elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
        char_est = 25
    else:
        char_est = 20

    est = max(3, char_est // 4)
    stmt._est_tokens = est  # type: ignore[attr-defined]
    return est


def _find_truncation_index(body: list[ast.stmt], max_tokens: int) -> tuple[int, str]:
    """Find maximum statement prefix index and unparsed text fitting within max_tokens."""
    if not body or max_tokens <= 0:
        return 0, ""

    weights = [_estimate_stmt_tokens(s) for s in body]
    prefix_sums = [0]
    for weight in weights:
        prefix_sums.append(prefix_sums[-1] + weight)

    est_k = min(len(body), max(0, bisect.bisect_right(prefix_sums, max_tokens) - 1))
    cand_est = ast.unparse(ast.Module(body=body[:est_k], type_ignores=[])) if est_k > 0 else ""
    tok_est = count_tokens(cand_est)

    if tok_est <= max_tokens:
        best_k = est_k
        best_unparsed = cand_est
        low = est_k + 1
        high = len(body)
    else:
        best_k = 0
        best_unparsed = ""
        low = 0
        high = est_k - 1

    while low <= high:
        mid = (low + high) // 2
        cand = ast.unparse(ast.Module(body=body[:mid], type_ignores=[])) if mid > 0 else ""
        if count_tokens(cand) <= max_tokens:
            best_k = mid
            best_unparsed = cand
            low = mid + 1
        else:
            high = mid - 1

    return best_k, best_unparsed


def _prune_tree_to_budget(tree: ast.Module, max_tokens: int, pruned: list[str]) -> tuple[str, bool]:
    """Prune AST body nodes from the end until unparsed code fits within max_tokens."""
    if not tree.body:
        return "", False

    if max_tokens <= 0:
        for removed in tree.body:
            rem_name = getattr(removed, "name", type(removed).__name__)
            pruned.append(rem_name)
        tree.body = []
        return "# [Code truncated due to token budget]", True

    # Fast estimation check: if upper bound fits within max_tokens, verify with single unparse
    weights = [_estimate_stmt_tokens(stmt) for stmt in tree.body]
    total_est = sum(weights)
    docstrings_stripped = False

    if total_est <= max_tokens:
        unparsed = ast.unparse(tree)
        if count_tokens(unparsed) <= max_tokens:
            return unparsed, False
        _strip_docstrings_from_node(tree)
        docstrings_stripped = True
        unparsed = ast.unparse(tree)
        if count_tokens(unparsed) <= max_tokens:
            return unparsed, True

    orig_count = len(tree.body)
    # Binary-search truncation index discovery
    best_k, best_unparsed = _find_truncation_index(tree.body, max_tokens)

    for removed in tree.body[best_k:]:
        rem_name = getattr(removed, "name", type(removed).__name__)
        pruned.append(rem_name)

    tree.body = tree.body[:best_k]

    if not best_unparsed:
        best_unparsed = "# [Code truncated due to token budget]"

    return best_unparsed, (best_k < orig_count or docstrings_stripped)


def _finalize_packed_ast(
    tree: ast.Module,
    orig_tokens: int,
    cfg: PackingConfig,
    pruned: list[str],
    preserved: list[str],
) -> PackedContext:
    """Finalize AST into PackedContext by pruning statements to fit token budget."""
    unparsed, truncated = _prune_tree_to_budget(tree, cfg.max_tokens, pruned)
    packed_tokens = count_tokens(unparsed)
    ratio = max(0.0, (orig_tokens - packed_tokens) / max(1, orig_tokens))
    return PackedContext(
        content=unparsed,
        original_tokens=orig_tokens,
        packed_tokens=packed_tokens,
        reduction_ratio=round(ratio, 3),
        pruned_symbols=pruned,
        preserved_symbols=preserved,
        truncated=truncated,
    )


class ContextPacker:
    """Synthesizes token-compact, symbol-pruned code contexts for AI prompts."""

    def __init__(self, default_config: PackingConfig | None = None) -> None:
        self.config = default_config or PackingConfig()
        _get_tiktoken_encoding()  # Pre-warm BPE tokenizer encoding

    def pack_code(
        self,
        code: str,
        referenced_symbols: Collection[str] | None = None,
        config: PackingConfig | None = None,
    ) -> PackedContext:
        """Pack source code by pruning unreferenced private symbols and skeletonizing bodies."""
        cfg = config or self.config
        orig_tokens = count_tokens(code)
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return _handle_syntax_fallback(code, orig_tokens, cfg)

        pruned: list[str] = []
        preserved: list[str] = []
        ref_set = set(referenced_symbols or ())
        tree.body = _build_pruned_ast_body(tree, ref_set, cfg, pruned, preserved)
        return _finalize_packed_ast(tree, orig_tokens, cfg, pruned, preserved)

    def pack_file(
        self,
        file_path: Path | str,
        referenced_symbols: Collection[str] | None = None,
        config: PackingConfig | None = None,
    ) -> PackedContext:
        """Read and pack a source file from disk."""
        path = Path(file_path)
        content = path.read_text(encoding="utf-8", errors="replace")
        return self.pack_code(content, referenced_symbols=referenced_symbols, config=config)

    def pack_snippets(
        self,
        snippets: Sequence[tuple[str, str]],
        referenced_symbols: Collection[str] | None = None,
        total_budget: int = DEFAULT_CONTEXT_PACKING_TOTAL_BUDGET,
        config: PackingConfig | None = None,
    ) -> list[PackedContext]:
        """Pack multiple code snippets, distributing token budget across items."""
        if not snippets:
            return []

        per_item_budget = max(1, total_budget // len(snippets))
        base_cfg = config or self.config
        results: list[PackedContext] = []

        for _name, code in snippets:
            item_cfg = base_cfg.model_copy(update={"max_tokens": per_item_budget})
            packed = self.pack_code(code, referenced_symbols=referenced_symbols, config=item_cfg)
            results.append(packed)

        return results
