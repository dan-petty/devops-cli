"""`devops ai ast` reads a source file only once it is within the engine's size cap (#959)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from devops_cli.config.defaults import DEFAULT_MAX_AST_FILE_SIZE_BYTES

FUNCTION_QUERY = "(function_definition name: (identifier) @n)"


def test_ast_parse_query_respects_size_cap(cli: Callable[..., Any], tmp_path: Path) -> None:
    """Verify `ai ast parse --query` refuses a file over the size cap, as a plain parse does, and
    still queries one within it; it read and parsed the whole file whatever its size."""
    big, small = tmp_path / "big.py", tmp_path / "small.py"
    with open(big, "wb") as f:
        f.seek(DEFAULT_MAX_AST_FILE_SIZE_BYTES + 10)
        f.write(b"\n")
    small.write_text("def f(x): ...\n", encoding="utf-8")

    capped = cli("ai", "ast", "parse", str(big), "--query", FUNCTION_QUERY)
    within = cli("ai", "ast", "parse", str(small), "--query", FUNCTION_QUERY)

    assert (
        capped.exit_code,
        '"symbol"' in capped.output,
        "file size exceeded" in capped.output,
        within.exit_code,
        '"symbol": "f"' in within.output,
    ) == (1, False, True, 0, True)


def test_ast_parse_rejects_a_malformed_query(cli: Callable[..., Any], tmp_path: Path) -> None:
    """Verify `ai ast parse --query` exits 1 naming the query's error when tree-sitter cannot
    compile it; it exited 0 and printed every symbol of the file."""
    source = tmp_path / "small.py"
    source.write_text("def f(x): ...\n", encoding="utf-8")

    result = cli("ai", "ast", "parse", str(source), "--query", "(((")

    assert (
        result.exit_code,
        "Invalid tree-sitter query" in result.output,
        '"symbol"' in result.output,
    ) == (
        1,
        True,
        False,
    )
