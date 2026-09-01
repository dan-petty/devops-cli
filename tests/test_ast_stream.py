"""Tests for zero-allocation AST and token stream parser."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.ast_stream import (
    ASTSymbolType,
    stream_ast_symbols,
    stream_token_lines,
)


def test_stream_ast_symbols(tmp_path: Path) -> None:
    """Stream AST symbols including classes, functions, and imports."""
    sample_code = (
        "import os\n"
        "from typing import Any, Optional\n\n"
        "@decorator\n"
        "class Engine:\n"
        '    """Engine docstring."""\n'
        "    def start(self) -> None:\n"
        "        pass\n\n"
        "async def async_fetch(url: str) -> None:\n"
        "    pass\n"
    )
    sample_file = tmp_path / "sample.py"
    sample_file.write_text(sample_code, encoding="utf-8")

    symbols = list(stream_ast_symbols(sample_file))
    names = [s.name for s in symbols]
    types = [s.symbol_type for s in symbols]

    assert "os" in names
    assert "typing.Any" in names
    assert "Engine" in names
    assert "start" in names
    assert "async_fetch" in names

    assert ASTSymbolType.CLASS in types
    assert ASTSymbolType.FUNCTION in types
    assert ASTSymbolType.ASYNC_FUNCTION in types
    assert ASTSymbolType.IMPORT in types

    engine_sym = next(s for s in symbols if s.name == "Engine")
    assert engine_sym.docstring == "Engine docstring."
    assert "decorator" in engine_sym.decorators


def test_stream_token_lines() -> None:
    """Stream line-level tokenization properties."""
    code = 'def compute():\n    # Inside compute\n    msg = "hello world"\n    return msg\n'
    lines = list(stream_token_lines(code))
    assert len(lines) >= 3

    # Check comment line detection
    comment_line = next(line_info for line_info in lines if line_info.has_comment)
    assert comment_line.line_number == 2
    assert comment_line.indent_depth == 1


def test_stream_ast_syntax_error() -> None:
    """Gracefully handle syntax errors without exceptions."""
    bad_code = "def incomplete("
    symbols = list(stream_ast_symbols(bad_code))
    assert symbols == []
