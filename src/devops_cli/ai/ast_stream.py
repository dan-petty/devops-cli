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


def _extract_decorator_names(decorator_list: list[ast.expr]) -> list[str]:
    """Extract string representations of AST decorator nodes concisely."""
    results: list[str] = []
    for d in decorator_list:
        if isinstance(d, ast.Name):
            results.append(d.id)
        elif isinstance(d, ast.Attribute):
            results.append(f"{getattr(d.value, 'id', '')}.{d.attr}".strip("."))
        elif isinstance(d, ast.Call):
            if isinstance(d.func, ast.Name):
                results.append(d.func.id)
            elif isinstance(d.func, ast.Attribute):
                results.append(f"{getattr(d.func.value, 'id', '')}.{d.func.attr}".strip("."))
    return results


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
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                decorators = _extract_decorator_names(node.decorator_list)
                yield ASTSymbol(
                    name=node.name,
                    symbol_type=ASTSymbolType.CLASS,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    parent_scope=parent_scope,
                    decorators=decorators,
                    docstring=doc,
                )
                stack.append((node, node.name))

            elif isinstance(node, ast.FunctionDef):
                doc = ast.get_docstring(node)
                decorators = _extract_decorator_names(node.decorator_list)
                yield ASTSymbol(
                    name=node.name,
                    symbol_type=ASTSymbolType.FUNCTION,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    parent_scope=parent_scope,
                    decorators=decorators,
                    docstring=doc,
                )
                stack.append((node, f"{parent_scope}.{node.name}" if parent_scope else node.name))

            elif isinstance(node, ast.AsyncFunctionDef):
                doc = ast.get_docstring(node)
                decorators = _extract_decorator_names(node.decorator_list)
                yield ASTSymbol(
                    name=node.name,
                    symbol_type=ASTSymbolType.ASYNC_FUNCTION,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    parent_scope=parent_scope,
                    decorators=decorators,
                    docstring=doc,
                )
                stack.append((node, f"{parent_scope}.{node.name}" if parent_scope else node.name))

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    yield ASTSymbol(
                        name=alias.name,
                        symbol_type=ASTSymbolType.IMPORT,
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                        parent_scope=parent_scope,
                    )

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    yield ASTSymbol(
                        name=f"{module}.{alias.name}" if module else alias.name,
                        symbol_type=ASTSymbolType.IMPORT,
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                        parent_scope=parent_scope,
                    )


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
                if current_tokens > 0 or has_comment:
                    yield TokenLineInfo(
                        line_number=current_line,
                        indent_depth=current_indent,
                        token_count=current_tokens,
                        has_comment=has_comment,
                        has_docstring_or_string=has_string,
                    )
                current_line = tok_line
                current_tokens = 0
                has_comment = False
                has_string = False

            tok_type = token.type
            if tok_type == tokenize.INDENT:
                current_indent = len(token.string) // 4
            elif tok_type == tokenize.COMMENT:
                has_comment = True
                if current_indent == 0 and token.start[1] > 0:
                    current_indent = token.start[1] // 4
            elif tok_type == tokenize.STRING:
                has_string = True
            elif tok_type not in (tokenize.NL, tokenize.NEWLINE, tokenize.DEDENT):
                current_tokens += 1

        if current_tokens > 0 or has_comment:
            yield TokenLineInfo(
                line_number=current_line,
                indent_depth=current_indent,
                token_count=current_tokens,
                has_comment=has_comment,
                has_docstring_or_string=has_string,
            )
    except tokenize.TokenError:
        return
