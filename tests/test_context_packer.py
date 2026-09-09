"""Unit tests for AI Context Packing & Symbol-Pruned Prompt Synthesizer."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from devops_cli.ai.context_packer import (
    ContextPacker,
    PackedContext,
    PackingConfig,
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
