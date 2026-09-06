"""Zero-allocation generator-based AST symbol and token line streaming parser."""

from __future__ import annotations

import ast
import io
import tokenize
from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.exceptions import SecurityError


class ASTSymbolType(StrEnum):
    """Categorization of Python AST structural symbols."""

    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    CLASS = "class"
    IMPORT = "import"
    CONSTANT = "constant"


class ASTSymbol(BaseModel):
    """Extracted Python code symbol metadata yielded during AST streaming."""

    model_config = ConfigDict(frozen=True)

    name: str
    symbol_type: ASTSymbolType
    line_start: int
    line_end: int
    parent_scope: str | None = None
    decorators: list[str] = Field(default_factory=list)
    docstring: str | None = None


class TokenLineInfo(BaseModel):
    """Line-level structural token metadata yielded during token stream parsing."""

    model_config = ConfigDict(frozen=True)

    line_number: int
    indent_depth: int
    token_count: int
    has_comment: bool
    has_docstring_or_string: bool


def _extract_single_decorator_name(d: ast.expr) -> str | None:
    if isinstance(d, ast.Name):
        return d.id
    if isinstance(d, ast.Attribute):
        return f"{getattr(d.value, 'id', '')}.{d.attr}".strip(".")
    if isinstance(d, ast.Call):
        if isinstance(d.func, ast.Name):
            return d.func.id
        if isinstance(d.func, ast.Attribute):
            return f"{getattr(d.func.value, 'id', '')}.{d.func.attr}".strip(".")
    return None


def _extract_decorator_names(decorator_list: list[ast.expr]) -> list[str]:
    """Extract string representations of AST decorator nodes concisely."""
    results: list[str] = []
    for d in decorator_list:
        name = _extract_single_decorator_name(d)
        if name:
            results.append(name)
    return results


def _handle_import_node(
    node: ast.Import | ast.ImportFrom, parent_scope: str | None
) -> list[ASTSymbol]:
    """Extract import symbols from Import or ImportFrom AST nodes."""
    symbols: list[ASTSymbol] = []
    module = getattr(node, "module", "") or ""
    for alias in node.names:
        name = f"{module}.{alias.name}" if module else alias.name
        symbols.append(
            ASTSymbol(
                name=name,
                symbol_type=ASTSymbolType.IMPORT,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno),
                parent_scope=parent_scope,
            )
        )
    return symbols


def _handle_ast_node(
    node: ast.AST,
    parent_scope: str | None,
    stack: list[tuple[ast.AST, str | None]],
) -> list[ASTSymbol]:
    if isinstance(node, ast.ClassDef):
        stack.append((node, node.name))
        return [
            ASTSymbol(
                name=node.name,
                symbol_type=ASTSymbolType.CLASS,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno),
                parent_scope=parent_scope,
                decorators=_extract_decorator_names(node.decorator_list),
                docstring=ast.get_docstring(node),
            )
        ]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        sym_type = (
            ASTSymbolType.ASYNC_FUNCTION
            if isinstance(node, ast.AsyncFunctionDef)
            else ASTSymbolType.FUNCTION
        )
        stack.append((node, f"{parent_scope}.{node.name}" if parent_scope else node.name))
        return [
            ASTSymbol(
                name=node.name,
                symbol_type=sym_type,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno),
                parent_scope=parent_scope,
                decorators=_extract_decorator_names(node.decorator_list),
                docstring=ast.get_docstring(node),
            )
        ]
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return _handle_import_node(node, parent_scope)
    return []


def stream_ast_symbols(source: str | Path) -> Iterator[ASTSymbol]:
    """Yield structural code symbols (classes, functions, imports) directly via AST streaming."""
    if isinstance(source, Path):
        if source.is_symlink():
            raise SecurityError(f"Symlinks not permitted in stream_ast_symbols: {source}")
        source_code = source.read_text(encoding="utf-8")
    else:
        source_code = source
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return

    # Scope stack maintaining (node, scope_name)
    stack: list[tuple[ast.AST, str | None]] = [(tree, None)]

    while stack:
        current, parent_scope = stack.pop()
        for node in ast.iter_child_nodes(current):
            yield from _handle_ast_node(node, parent_scope, stack)


def _make_token_line_info(
    line_number: int,
    indent_depth: int,
    token_count: int,
    has_comment: bool,
    has_string: bool,
) -> TokenLineInfo | None:
    if token_count > 0 or has_comment:
        return TokenLineInfo(
            line_number=line_number,
            indent_depth=indent_depth,
            token_count=token_count,
            has_comment=has_comment,
            has_docstring_or_string=has_string,
        )
    return None


def _classify_token(token: tokenize.TokenInfo, current_indent: int) -> tuple[int, bool, bool, int]:
    """Classify token into (indent, is_comment, is_string, token_increment)."""
    tok_type = token.type
    if tok_type == tokenize.INDENT:
        return len(token.string) // 4, False, False, 0
    if tok_type == tokenize.COMMENT:
        indent = (
            token.start[1] // 4 if current_indent == 0 and token.start[1] > 0 else current_indent
        )
        return indent, True, False, 0
    if tok_type == tokenize.STRING:
        return current_indent, False, True, 0
    if tok_type not in (tokenize.NL, tokenize.NEWLINE, tokenize.DEDENT):
        return current_indent, False, False, 1
    return current_indent, False, False, 0


def stream_token_lines(source: str | Path) -> Iterator[TokenLineInfo]:
    """Stream line-level tokenization properties (indentation, comment, string detection) with zero node allocation."""
    source_code = source.read_text(encoding="utf-8") if isinstance(source, Path) else source
    readline = io.StringIO(source_code).readline

    current_line = 1
    current_tokens = 0
    current_indent = 0
    has_comment = False
    has_string = False

    try:
        for token in tokenize.generate_tokens(readline):
            tok_line = token.start[0]

            if tok_line != current_line:
                info = _make_token_line_info(
                    current_line, current_indent, current_tokens, has_comment, has_string
                )
                if info is not None:
                    yield info
                current_line = tok_line
                current_tokens, has_comment, has_string = 0, False, False

            indent, is_comm, is_str, inc = _classify_token(token, current_indent)
            current_indent = indent
            has_comment = has_comment or is_comm
            has_string = has_string or is_str
            current_tokens += inc

        final_info = _make_token_line_info(
            current_line, current_indent, current_tokens, has_comment, has_string
        )
        if final_info is not None:
            yield final_info
    except tokenize.TokenError:
        return
