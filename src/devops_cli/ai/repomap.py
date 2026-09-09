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
            "children": [child.to_dict() for child in self.children],
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
            "symbols": [symbol.to_dict() for symbol in self.symbols],
        }


def _extract_doc_summary(
    node: ast.AsyncFunctionDef | ast.FunctionDef | ast.ClassDef | ast.Module,
) -> str:
    docstring = ast.get_docstring(node)
    if not docstring:
        return ""
    first_line = docstring.strip().splitlines()[0]
    return first_line[:80] + ("..." if len(first_line) > 80 else "")


def _format_function_signature(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args: list[str] = []
    for arg_node in fn_node.args.args:
        if arg_node.arg in ("self", "cls"):
            continue
        annotation = ast.unparse(arg_node.annotation) if arg_node.annotation else ""
        args.append(f"{arg_node.arg}: {annotation}" if annotation else arg_node.arg)
    returns = ast.unparse(fn_node.returns) if fn_node.returns else "None"
    return f"({', '.join(args)}) -> {returns}"


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


MAX_REPOMAP_FILE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MiB


def parse_file_symbols(file_path: Path, relative_to: Path) -> FileMapNode | None:
    """Parse a Python source file using AST and extract class and function symbols."""
    try:
        if file_path.stat().st_size > MAX_REPOMAP_FILE_SIZE_BYTES:
            return None
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


def _is_file_excluded(source_file: Path, include_tests: bool) -> bool:
    if source_file.is_symlink():
        return True
    if any(
        part in source_file.parts
        for part in (
            ".venv",
            ".git",
            "__pycache__",
            ".pytest_cache",
            "build",
            "dist",
            ".data",
            "node_modules",
        )
    ):
        return True
    return not include_tests and "test" in source_file.name


def _discover_repo_files(
    target_dir: Path,
    include_tests: bool,
    multilingual: bool,
) -> list[Path]:
    from devops_cli.ai.ast.engine import EXT_TO_LANG

    extensions = list(EXT_TO_LANG.keys()) if multilingual else [".py"]
    found: list[Path] = []
    for ext in extensions:
        for p in target_dir.rglob(f"*{ext}"):
            if not _is_file_excluded(p, include_tests):
                found.append(p)
    return sorted(found, key=lambda f: str(f))


def _polyglot_to_file_node(source_file: Path, base_root: Path) -> FileMapNode | None:
    from devops_cli.ai.ast.engine import TreeSitterEngine

    engine = TreeSitterEngine()
    poly_map = engine.parse_file(source_file)
    if not poly_map or not poly_map.symbols:
        return None

    try:
        rel_path = str(source_file.relative_to(base_root))
    except ValueError:
        rel_path = str(source_file)

    symbols = [
        SymbolNode(
            name=s.name,
            kind=s.kind.value,
            line_number=s.span.line_start,
            signature=s.signature,
            docstring=s.docstring,
        )
        for s in poly_map.symbols
    ]
    return FileMapNode(path=rel_path, line_count=poly_map.line_count, symbols=symbols)


def generate_repo_map(
    root_dir: Path | None = None,
    max_files: int = 100,
    include_tests: bool = False,
    multilingual: bool = False,
) -> list[FileMapNode]:
    """Traverse repository source files and generate symbol maps."""
    base_root = root_dir or find_top_level_repo_root(Path.cwd())
    src_dir = base_root / "src"
    target_dir = src_dir if src_dir.is_dir() else base_root

    files = _discover_repo_files(target_dir, include_tests, multilingual)
    results: list[FileMapNode] = []
    base_resolved = base_root.resolve()

    for source_file in files[:max_files]:
        try:
            if not source_file.resolve().is_relative_to(base_resolved):
                continue
        except ValueError, OSError:
            continue

        if source_file.suffix.lower() == ".py" and not multilingual:
            node = parse_file_symbols(source_file, base_root)
        else:
            node = _polyglot_to_file_node(source_file, base_root)

        if node and node.symbols:
            results.append(node)

    return results


def render_repo_map_text(file_nodes: list[FileMapNode]) -> str:
    """Render repository symbol map as clean, indented ASCII text."""
    from devops_cli.output import format_repo_map_text

    return format_repo_map_text(file_nodes)
