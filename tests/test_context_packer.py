"""Unit tests for AI Context Packing & Symbol-Pruned Prompt Synthesizer."""

from __future__ import annotations

import ast
import json
import time
from pathlib import Path

from typer.testing import CliRunner

from devops_cli.ai.context_budget import count_tokens
from devops_cli.ai.context_packer import (
    ContextPacker,
    PackedContext,
    PackingConfig,
    _estimate_stmt_tokens,
    _find_truncation_index,
    _prune_tree_to_budget,
)
from devops_cli.main import app

runner = CliRunner()


SAMPLE_PYTHON_CODE = '''"""Sample module for testing context packing."""

import os
import sys
from typing import Optional, List, Dict, Any

GLOBAL_CONFIG = {"debug": True}
_INTERNAL_KEY = "secret_key_123"


def public_api_function(name: str, count: int = 1) -> bool:
    """Execute a public API action.

    This function does extensive operations that take up lots of lines.
    Line 1.
    Line 2.
    Line 3.
    """
    total = 0
    for i in range(count):
        total += i
    return total > 0


def _private_helper_calculation(value: int) -> int:
    """Calculate internal values that callers outside don't care about."""
    temp = value * 42
    return temp + 7


class UserService:
    """Service handling user accounts and operations."""

    def __init__(self, db_url: str) -> None:
        """Initialize user service."""
        self.db_url = db_url
        self._connected = False

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch user by identifier."""
        if not user_id:
            return None
        return {"id": user_id, "name": "Alice"}

    def _internal_db_ping(self) -> bool:
        """Ping database connection."""
        return True

    def delete_user(self, user_id: str) -> bool:
        """Delete user account."""
        self._internal_db_ping()
        return True
'''


def test_pack_code_skeletonizes_and_preserves_signatures() -> None:
    """Verify that skeletonization preserves function and class signatures while replacing bodies with ellipsis."""
    packer = ContextPacker()
    packed = packer.pack_code(SAMPLE_PYTHON_CODE)

    assert isinstance(packed, PackedContext)
    assert packed.packed_tokens < packed.original_tokens
    assert packed.reduction_ratio > 0.1

    # Public function signature preserved
    assert "def public_api_function(name: str, count: int=1) -> bool:" in packed.content
    assert "total = 0" not in packed.content
    assert "..." in packed.content

    # Public class and methods preserved
    assert "class UserService:" in packed.content
    assert "def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:" in packed.content
    assert "def delete_user(self, user_id: str) -> bool:" in packed.content


def test_pack_code_strips_unreferenced_private_symbols() -> None:
    """Verify that unreferenced private functions and methods are pruned."""
    packer = ContextPacker()
    packed = packer.pack_code(SAMPLE_PYTHON_CODE, referenced_symbols={"get_user"})

    # Private helper function stripped
    assert "_private_helper_calculation" not in packed.content
    assert "_private_helper_calculation" in packed.pruned_symbols

    # Private method stripped
    assert "_internal_db_ping" not in packed.content
    assert "_internal_db_ping" in packed.pruned_symbols

    # Unreferenced private global stripped
    assert "_INTERNAL_KEY" not in packed.content
    assert "_INTERNAL_KEY" in packed.pruned_symbols

    # Referenced method preserved
    assert "get_user" in packed.preserved_symbols
    assert "def get_user" in packed.content


def test_pack_code_retains_referenced_private_symbols() -> None:
    """Verify that private symbols are retained if explicitly referenced."""
    packer = ContextPacker()
    packed = packer.pack_code(
        SAMPLE_PYTHON_CODE,
        referenced_symbols={"_private_helper_calculation", "_internal_db_ping"},
    )

    assert "def _private_helper_calculation(value: int) -> int:" in packed.content
    assert "def _internal_db_ping(self) -> bool:" in packed.content
    assert "_private_helper_calculation" not in packed.pruned_symbols


def test_pack_code_strip_docstrings() -> None:
    """Verify that docstrings are stripped when strip_docstrings=True."""
    packer = ContextPacker()
    config = PackingConfig(strip_docstrings=True)
    packed = packer.pack_code(SAMPLE_PYTHON_CODE, config=config)

    assert "Execute a public API action." not in packed.content
    assert "Service handling user accounts and operations." not in packed.content


def test_pack_code_token_budget_enforcement() -> None:
    """Verify that packed content strictly obeys max_tokens budget."""
    packer = ContextPacker()
    packed = packer.pack_code(SAMPLE_PYTHON_CODE, config=PackingConfig(max_tokens=60))

    assert packed.packed_tokens <= 60
    assert packed.packed_tokens < packed.original_tokens


def test_pack_code_fallback_on_non_python() -> None:
    """Verify that non-Python or malformed code falls back gracefully without crashing."""
    malformed_code = """
    function greet(name: string): string {
        // Line comment to strip
        console.log("Hello " + name);
        return "Done";
    }
    """
    packer = ContextPacker()
    packed = packer.pack_code(malformed_code, config=PackingConfig(max_tokens=20))

    assert isinstance(packed, PackedContext)
    assert packed.packed_tokens <= 20
    assert "greet" in packed.content


def test_pack_snippets_distributes_budget() -> None:
    """Verify pack_snippets distributes token budget across multiple files."""
    packer = ContextPacker()
    snippets = [
        ("auth.py", SAMPLE_PYTHON_CODE),
        ("models.py", "class Role:\n    ADMIN = 'admin'\n    USER = 'user'\n"),
    ]
    results = packer.pack_snippets(snippets, total_budget=300)

    assert len(results) == 2
    total_tokens = sum(r.packed_tokens for r in results)
    assert total_tokens <= 300
    assert any("UserService" in r.content for r in results)


def test_pack_file(tmp_path: Path) -> None:
    """Verify pack_file reads a file from disk and packs it."""
    file_path = tmp_path / "sample.py"
    file_path.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")

    packer = ContextPacker()
    packed = packer.pack_file(file_path)

    assert "def public_api_function" in packed.content
    assert packed.original_tokens > 0


def test_cli_pack_context(tmp_path: Path) -> None:
    """Verify devops ai pack-context CLI subcommand."""
    test_file = tmp_path / "app.py"
    test_file.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")

    res = runner.invoke(
        app,
        ["ai", "pack-context", str(test_file), "--max-tokens", "100", "--json"],
    )
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert "content" in data
    assert "original_tokens" in data
    assert "packed_tokens" in data
    assert data["packed_tokens"] <= 100


def test_cli_pack_context_plain(tmp_path: Path) -> None:
    """Verify devops ai pack-context plain output with referenced symbols."""
    test_file = tmp_path / "app.py"
    test_file.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")

    res = runner.invoke(
        app,
        [
            "ai",
            "pack-context",
            str(test_file),
            "--referenced",
            "get_user,public_api_function",
        ],
    )
    assert res.exit_code == 0
    assert "def get_user" in res.stdout
    assert "public_api_function" in res.stdout


def test_pack_code_syntactically_valid_under_strict_budget() -> None:
    """Verify that AST statement pruning produces syntactically valid Python even with tight token limits."""
    packer = ContextPacker()
    packed = packer.pack_code(SAMPLE_PYTHON_CODE, config=PackingConfig(max_tokens=40))

    assert isinstance(packed, PackedContext)
    assert packed.packed_tokens <= 40
    # Must be 100% valid Python syntax without SyntaxError
    parsed = ast.parse(packed.content)
    assert parsed is not None


def test_pack_snippets_small_budget_never_exceeds_total() -> None:
    """Verify that pack_snippets never violates small total_budget contracts."""
    packer = ContextPacker()
    snippets = [
        ("a.py", SAMPLE_PYTHON_CODE),
        ("b.py", SAMPLE_PYTHON_CODE),
        ("c.py", SAMPLE_PYTHON_CODE),
    ]
    results = packer.pack_snippets(snippets, total_budget=60)
    assert len(results) == 3
    total_packed = sum(r.packed_tokens for r in results)
    assert total_packed <= 60


def test_prune_tree_linear_statement_scaling() -> None:
    """Verify that pruning many top-level statements scales linearly and obeys token budget."""
    code_lines = [f"def worker_fn_{i}() -> int:\n    return {i}\n" for i in range(120)]
    large_module_code = "\n".join(code_lines)

    packer = ContextPacker()
    packed = packer.pack_code(large_module_code, config=PackingConfig(max_tokens=80))

    assert isinstance(packed, PackedContext)
    assert packed.packed_tokens <= 80
    assert len(packed.pruned_symbols) > 50
    # Output must be syntactically valid Python
    ast.parse(packed.content)


def test_prune_tree_binary_search_under_10ms() -> None:
    """Verify that binary search truncation on 1,000-line AST trees runs under 10ms."""
    code_lines = [
        f"def worker_fn_{i}(arg: int) -> int:\n    y = arg + {i}\n    return y\n"
        for i in range(334)
    ]
    large_code = "\n".join(code_lines)
    tree = ast.parse(large_code)
    # Warm up tokenizer encoding
    count_tokens("def _warmup() -> None:\n    pass")

    pruned: list[str] = []
    start_time = time.perf_counter()
    unparsed, truncated = _prune_tree_to_budget(tree, 200, pruned)
    duration = time.perf_counter() - start_time

    assert count_tokens(unparsed) <= 200
    assert len(pruned) > 300
    assert truncated is True
    assert duration < 0.010, f"Execution exceeded benchmark threshold: {duration * 1000:.2f}ms"
    # Output must be syntactically valid Python without syntax errors
    parsed = ast.parse(unparsed)
    assert parsed is not None


def test_prune_tree_exact_boundary_integrity() -> None:
    """Verify boundary cases for statement truncation: tiny budgets and empty bodies."""
    packer = ContextPacker()

    # Zero/minimal budget fallback
    packed_tight = packer.pack_code(
        "def foo() -> None:\n    pass\ndef bar() -> None:\n    pass",
        config=PackingConfig(max_tokens=3),
    )
    assert isinstance(packed_tight, PackedContext)
    assert packed_tight.truncated is True

    # High budget retains all statements
    packed_full = packer.pack_code(
        "def a(): pass\ndef b(): pass",
        config=PackingConfig(max_tokens=500),
    )
    assert packed_full.truncated is False
    assert "def a" in packed_full.content
    assert "def b" in packed_full.content

    # Empty AST module body produces empty content without truncation
    empty_tree = ast.Module(body=[], type_ignores=[])
    pruned_empty: list[str] = []
    res_empty, trunc_empty = _prune_tree_to_budget(empty_tree, 100, pruned_empty)
    assert res_empty == ""
    assert trunc_empty is False
    assert pruned_empty == []

    # Non-empty tree with max_tokens <= 0 omits every statement and records pruned symbols
    zero_budget_tree = ast.parse("def a(): pass\ndef b(): pass")
    pruned_zero: list[str] = []
    res_zero, trunc_zero = _prune_tree_to_budget(zero_budget_tree, 0, pruned_zero)
    assert res_zero == "# [Code truncated due to token budget]"
    assert trunc_zero is True
    assert pruned_zero == ["a", "b"]
    assert zero_budget_tree.body == []


def test_find_truncation_index_short_statements_expands_to_full_body() -> None:
    """Verify that truncation index search explores full body for short statements."""
    code_lines = [f"x_{i} = {i}" for i in range(50)]
    tree = ast.parse("\n".join(code_lines))
    budget = count_tokens("\n".join(code_lines)) + 10
    pruned: list[str] = []
    unparsed, trunc = _prune_tree_to_budget(tree, budget, pruned)
    assert trunc is False
    assert len(pruned) == 0
    assert "x_49" in unparsed

    best_k, cand = _find_truncation_index(tree.body, budget)
    assert best_k == len(tree.body)

    # When budget is strictly constrained, truncation occurs and pruned symbols are recorded
    pruned_partial: list[str] = []
    tree_partial = ast.parse("\n".join(code_lines))
    unparsed_part, trunc_part = _prune_tree_to_budget(tree_partial, 50, pruned_partial)
    assert trunc_part is True
    assert len(pruned_partial) > 0
    assert count_tokens(unparsed_part) <= 50


def test_estimate_stmt_tokens_memoization() -> None:
    """Verify that statement token weights are estimated in O(1) and memoized on AST nodes."""
    tree = ast.parse("def sample_function(x: int, y: str) -> bool:\n    pass")
    fn_node = tree.body[0]
    est1 = _estimate_stmt_tokens(fn_node)
    assert est1 > 0
    assert getattr(fn_node, "_est_tokens", None) == est1

    # Mutate attribute to test memoization lookup
    fn_node._est_tokens = 999
    assert _estimate_stmt_tokens(fn_node) == 999
