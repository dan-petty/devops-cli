"""Domain models for polyglot AST symbols and whole-repository code graph."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SymbolKind(StrEnum):
    """Categorization of polyglot code symbols."""

    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    INTERFACE = "interface"
    STRUCT = "struct"
    TYPE = "type"
    CONSTANT = "constant"
    MODULE = "module"


class CodeSpan(BaseModel):
    """Source code range span with line and column positions."""

    model_config = ConfigDict(frozen=True)

    line_start: int
    line_end: int
    col_start: int = 0
    col_end: int = 0
    start_byte: int = 0
    end_byte: int = 0


class PolyglotSymbol(BaseModel):
    """Extracted code symbol across polyglot languages."""

    name: str
    kind: SymbolKind
    span: CodeSpan
    signature: str = ""
    docstring: str = ""
    language: str = ""
    parent_scope: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "line_start": self.span.line_start,
            "line_end": self.span.line_end,
            "signature": self.signature,
            "docstring": self.docstring,
            "language": self.language,
            "parent_scope": self.parent_scope,
        }


class PolyglotFileMap(BaseModel):
    """Parsed source file containing extracted polyglot symbols."""

    path: str
    language: str
    line_count: int
    symbols: list[PolyglotSymbol] = Field(default_factory=list)
    parse_engine: str = "fallback-ast"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "language": self.language,
            "line_count": self.line_count,
            "parse_engine": self.parse_engine,
            "symbols": [s.to_dict() for s in self.symbols],
        }


class CodeGraphEdge(BaseModel):
    """Relationship between two code symbols across the repository."""

    model_config = ConfigDict(frozen=True)

    source_symbol: str
    target_symbol: str
    relation: str = "calls"  # calls, implements, extends, imports
    file_path: str = ""
    line_number: int = 0


class CodeGraph(BaseModel):
    """Whole-repository code symbol and reference graph."""

    nodes: dict[str, PolyglotSymbol] = Field(default_factory=dict)
    edges: list[CodeGraphEdge] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "files": self.files,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [
                {
                    "source": e.source_symbol,
                    "target": e.target_symbol,
                    "relation": e.relation,
                    "file": e.file_path,
                    "line": e.line_number,
                }
                for e in self.edges
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        """Export code graph to JSON formatted string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_dot(self) -> str:
        """Export code graph to Graphviz DOT format."""
        lines = ["digraph CodeGraph {", '  rankdir="LR";', "  node [shape=box, style=rounded];"]
        for key, sym in self.nodes.items():
            safe_id = f'"{key}"'
            label = f"{sym.name}\\n({sym.kind.value})"
            lines.append(f'  {safe_id} [label="{label}"];')
        for edge in self.edges:
            src = f'"{edge.source_symbol}"'
            dst = f'"{edge.target_symbol}"'
            lines.append(f'  {src} -> {dst} [label="{edge.relation}"];')
        lines.append("}")
        return "\n".join(lines)
