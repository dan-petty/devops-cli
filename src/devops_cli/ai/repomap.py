"""AST-based repository symbol map generator for AI context compression."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.core.repo import find_top_level_repo_root


class SymbolNode(BaseModel):
    """Represents a class, function, or method declaration in the repository map."""

    name: str
    kind: str  # "class", "function", "method", "constant"
    line_number: int
    signature: str = ""
    docstring: str = ""
    children: list[SymbolNode] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "line_number": self.line_number,
            "signature": self.signature,
            "docstring": self.docstring,
            "children": [c.to_dict() for c in self.children],
        }


class FileMapNode(BaseModel):
    """Represents a source file and its exported symbols."""

    path: str
    line_count: int
    symbols: list[SymbolNode] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "line_count": self.line_count,
            "symbols": [s.to_dict() for s in self.symbols],
        }


def _extract_doc_summary(
    node: ast.AsyncFunctionDef | ast.FunctionDef | ast.ClassDef | ast.Module,
) -> str:
    doc = ast.get_docstring(node)
    if not doc:
        return ""
    first_line = doc.strip().splitlines()[0]
    return first_line[:80] + ("..." if len(first_line) > 80 else "")


def _format_function_signature(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args: list[str] = []
    for a in fn_node.args.args:
        if a.arg in ("self", "cls"):
            continue
        ann = ast.unparse(a.annotation) if a.annotation else ""
        args.append(f"{a.arg}: {ann}" if ann else a.arg)
    ret = ast.unparse(fn_node.returns) if fn_node.returns else "None"
    return f"({', '.join(args)}) -> {ret}"


def _extract_class_methods(class_node: ast.ClassDef) -> list[SymbolNode]:
    """Extract member method symbol nodes from an AST ClassDef."""
    return [
        SymbolNode(
            name=item.name,
            kind="method",
            line_number=item.lineno,
            signature=_format_function_signature(item),
            docstring=_extract_doc_summary(item),
        )
        for item in class_node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def parse_file_symbols(file_path: Path, relative_to: Path) -> FileMapNode | None:
    """Parse a Python source file using AST and extract class and function symbols."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    line_count = len(content.splitlines())
    try:
        tree = ast.parse(content, filename=str(file_path))
    except Exception:
        return None

    rel_path = str(file_path.relative_to(relative_to))
    symbols: list[SymbolNode] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append(
                SymbolNode(
                    name=node.name,
                    kind="class",
                    line_number=node.lineno,
                    docstring=_extract_doc_summary(node),
                    children=_extract_class_methods(node),
                )
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(
                SymbolNode(
                    name=node.name,
                    kind="function",
                    line_number=node.lineno,
                    signature=_format_function_signature(node),
                    docstring=_extract_doc_summary(node),
                )
            )

    return FileMapNode(path=rel_path, line_count=line_count, symbols=symbols)


def generate_repo_map(
    root_dir: Path | None = None,
    max_files: int = 100,
    include_tests: bool = False,
) -> list[FileMapNode]:
    """Traverse repository source files and generate symbol maps."""
    base_root = root_dir or find_top_level_repo_root(Path.cwd())
    src_dir = base_root / "src"
    target_dir = src_dir if src_dir.is_dir() else base_root

    py_files = sorted(
        [
            p
            for p in target_dir.rglob("*.py")
            if not any(
                part in p.parts
                for part in (".venv", ".git", "__pycache__", ".pytest_cache", "build", "dist")
            )
            and (include_tests or "test" not in p.name)
        ],
        key=lambda p: str(p),
    )

    results: list[FileMapNode] = []
    for p in py_files[:max_files]:
        node = parse_file_symbols(p, base_root)
        if node and node.symbols:
            results.append(node)

    return results


def render_repo_map_text(file_nodes: list[FileMapNode]) -> str:
    """Render repository symbol map as clean, indented ASCII text."""
    from devops_cli.output import format_repo_map_text

    return format_repo_map_text(file_nodes)
