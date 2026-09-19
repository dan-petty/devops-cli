"""Multi-Scale Semantic Outline & Inspectional Scanner.

Provides 3 discrete focal zoom levels for source code inspection:
- Level 0 (Topology): Class/method hierarchies, exported symbols, docstrings, cyclomatic hotspots (< 200 tokens).
- Level 1 (Structural Outline): Signatures, return contracts, and control-flow sketches (> 85% token reduction).
- Level 2 (Deep Focal Window): Line-bounded code slices with surrounding breadcrumb context.
"""

from __future__ import annotations

import ast
import logging
import time
from collections.abc import Callable
from enum import IntEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.ai.ast.engine import EXT_TO_LANG
from devops_cli.ai.ast.fallback import FallbackASTParser
from devops_cli.ai.ast.models import SymbolKind
from devops_cli.config.constants import (
    CONST_DEFAULT_FOCAL_WINDOW_SIZE,
    CONST_HOTSPOT_COMPLEXITY_THRESHOLD,
    CONST_MAX_INSPECT_FILE_SIZE_BYTES,
)
from devops_cli.core.paths import is_forbidden_system_path, validate_no_path_traversal
from devops_cli.exceptions import DevOpsCLIError, ValidationError
from devops_cli.security.complexity import _ComplexityVisitor

logger = logging.getLogger(__name__)


class FocalLevel(IntEnum):
    """Discrete focal zoom levels for inspectional reading."""

    TOPOLOGY = 0
    STRUCTURAL = 1
    DEEP_FOCAL = 2


class ClassTopology(BaseModel):
    """Summary of a class in the topological overview."""

    name: str
    bases: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    docstring: str = ""
    line_start: int = 1
    line_end: int = 1


class FunctionTopology(BaseModel):
    """Summary of a function or method in the topological overview."""

    name: str
    docstring: str = ""
    cyclomatic_complexity: int = 1
    is_hotspot: bool = False
    line_number: int = 1
    end_line_number: int = 1
    is_method: bool = False
    parent_class: str | None = None


class TopologyOutline(BaseModel):
    """Level 0: Topological outline of symbols, hierarchy, and complexity hotspots."""

    classes: list[ClassTopology] = Field(default_factory=list)
    functions: list[FunctionTopology] = Field(default_factory=list)
    exported_symbols: list[str] = Field(default_factory=list)
    cyclomatic_hotspots: list[FunctionTopology] = Field(default_factory=list)
    total_symbols: int = 0
    estimated_tokens: int = 0


class FunctionStructural(BaseModel):
    """Structural outline of a function with signature and control-flow sketch."""

    name: str
    signature: str
    docstring: str = ""
    control_flow: list[str] = Field(default_factory=list)
    line_start: int = 1
    line_end: int = 1
    parent_class: str | None = None


class ClassStructural(BaseModel):
    """Structural outline of a class with methods and signature contracts."""

    name: str
    bases: list[str] = Field(default_factory=list)
    docstring: str = ""
    methods: list[FunctionStructural] = Field(default_factory=list)
    line_start: int = 1
    line_end: int = 1


class StructuralOutline(BaseModel):
    """Level 1: Structural outline of function signatures and control-flow sketches."""

    classes: list[ClassStructural] = Field(default_factory=list)
    functions: list[FunctionStructural] = Field(default_factory=list)
    raw_skeleton: str = ""
    estimated_tokens: int = 0


class FocalWindow(BaseModel):
    """Level 2: Targeted line slice with surrounding breadcrumb context."""

    line_start: int
    line_end: int
    total_file_lines: int
    scope_breadcrumbs: str = ""
    content: str
    symbol_name: str | None = None
    estimated_tokens: int = 0


class SemanticOutline(BaseModel):
    """Comprehensive multi-scale semantic outline container."""

    path: str
    language: str
    level: FocalLevel
    raw_lines: int
    raw_tokens: int
    outline_tokens: int
    token_reduction_pct: float
    generation_time_ms: float
    topology: TopologyOutline | None = None
    structural: StructuralOutline | None = None
    focal_window: FocalWindow | None = None

    def to_display_text(self) -> str:
        """Render multi-scale outline into formatted markdown for terminals and agents."""
        return _render_semantic_outline_text(self)


def estimate_tokens(text: str) -> int:
    """Estimate token count for a string (~4 characters per token)."""
    return max(1, len(text) // 4) if text else 0


def _calculate_token_reduction(raw_tokens: int, outline_tokens: int) -> float:
    """Calculate token reduction percentage relative to full file."""
    if raw_tokens <= 0:
        return 0.0
    reduction = (1.0 - (outline_tokens / raw_tokens)) * 100.0
    return max(0.0, min(100.0, round(reduction, 2)))


def _validate_inspect_path(target_path: Path, repo_root: Path | None = None) -> tuple[Path, Path]:
    """Validate path safety, directory traversal, and workspace containment."""
    validate_no_path_traversal(target_path, label="Target file")
    base_root = (repo_root or Path.cwd()).resolve()
    resolved = target_path.resolve()

    if is_forbidden_system_path(resolved):
        raise ValidationError(
            f"Target path points to forbidden system location: {resolved}",
            details={"path": str(resolved)[:256]},
        )
    if repo_root is not None:
        base_root = repo_root.resolve()
        if not (resolved == base_root or resolved.is_relative_to(base_root)):
            raise ValidationError(
                f"Target path escapes repository root: {resolved}",
                details={"path": str(resolved)[:256], "root": str(base_root)[:256]},
            )
    else:
        cwd = Path.cwd().resolve()
        base_root = cwd if (resolved == cwd or resolved.is_relative_to(cwd)) else resolved.parent
    if not resolved.is_file():
        raise DevOpsCLIError(
            f"Target file not found: {target_path}",
            details={"path": str(target_path)[:256]},
        )
    if resolved.stat().st_size > CONST_MAX_INSPECT_FILE_SIZE_BYTES:
        raise DevOpsCLIError(
            f"File exceeds maximum inspection size limit ({CONST_MAX_INSPECT_FILE_SIZE_BYTES} bytes): {target_path}",
            details={"path": str(target_path)[:256], "size": resolved.stat().st_size},
        )
    return resolved, base_root


def _extract_py_docstring(
    node: ast.AsyncFunctionDef | ast.FunctionDef | ast.ClassDef | ast.Module,
) -> str:
    """Extract first line of docstring from a Python AST node."""
    doc = ast.get_docstring(node)
    if not doc:
        return ""
    first_line = doc.strip().splitlines()[0].strip()
    return first_line[:120]


def _extract_py_all_exports(tree: ast.AST) -> list[str]:
    """Extract __all__ exported symbol list from AST if defined."""
    for stmt in getattr(tree, "body", []):
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    return _extract_list_or_tuple_names(stmt.value)
    return []


def _extract_list_or_tuple_names(node: ast.AST) -> list[str]:
    """Extract constant string names from AST list or tuple."""
    if isinstance(node, (ast.List, ast.Tuple)):
        return [
            elt.value
            for elt in node.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        ]
    return []


def _format_pos_args(args: list[ast.arg]) -> list[str]:
    """Format positional function arguments with type annotations."""
    formatted: list[str] = []
    for a in args:
        ann = f": {ast.unparse(a.annotation)}" if a.annotation else ""
        formatted.append(f"{a.arg}{ann}")
    return formatted


def _format_kwonly_args(kwonlyargs: list[ast.arg]) -> list[str]:
    """Format keyword-only arguments with type annotations."""
    return [
        f"{kw.arg}: {ast.unparse(kw.annotation)}" if kw.annotation else kw.arg for kw in kwonlyargs
    ]


def _format_special_args(vararg: ast.arg | None, kwarg: ast.arg | None) -> list[str]:
    """Format *args and **kwargs parameter declarations."""
    res: list[str] = []
    if vararg:
        v_ann = f": {ast.unparse(vararg.annotation)}" if vararg.annotation else ""
        res.append(f"*{vararg.arg}{v_ann}")
    if kwarg:
        k_ann = f": {ast.unparse(kwarg.annotation)}" if kwarg.annotation else ""
        res.append(f"**{kwarg.arg}{k_ann}")
    return res


def _extract_py_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Extract full function signature with type hints."""
    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
    all_args = _format_pos_args(node.args.args)
    all_args.extend(_format_kwonly_args(node.args.kwonlyargs))
    all_args.extend(_format_special_args(node.args.vararg, node.args.kwarg))

    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{prefix}{node.name}({', '.join(all_args)}){ret}:"


_SKETCHABLE_STMTS = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.Return,
    ast.Raise,
)


def _extract_control_flow_sketch(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Extract structural control-flow skeleton from function AST."""
    sketches: list[str] = []
    for item in node.body:
        if isinstance(item, _SKETCHABLE_STMTS):
            try:
                line = ast.unparse(item).splitlines()[0]
                sketches.append(line[:80])
            except Exception:
                pass
        if len(sketches) >= 6:
            sketches.append("...")
            break
    return sketches


def _build_python_topology(tree: ast.AST, content: str) -> TopologyOutline:
    """Construct Level 0 Topology outline from Python AST."""
    visitor = _ComplexityVisitor()
    visitor.visit(tree)
    complexity_map = {f.name: f.cyclomatic_complexity for f in visitor.functions}

    classes: list[ClassTopology] = []
    functions: list[FunctionTopology] = []
    public_symbols: list[str] = []

    for stmt in getattr(tree, "body", []):
        if isinstance(stmt, ast.ClassDef):
            bases = [ast.unparse(b) for b in stmt.bases]
            methods = [
                m.name for m in stmt.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            classes.append(
                ClassTopology(
                    name=stmt.name,
                    bases=bases,
                    methods=methods,
                    docstring=_extract_py_docstring(stmt),
                    line_start=stmt.lineno,
                    line_end=getattr(stmt, "end_lineno", stmt.lineno),
                )
            )
            public_symbols.append(stmt.name)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            comp = complexity_map.get(stmt.name, 1)
            is_hot = comp >= CONST_HOTSPOT_COMPLEXITY_THRESHOLD
            functions.append(
                FunctionTopology(
                    name=stmt.name,
                    docstring=_extract_py_docstring(stmt),
                    cyclomatic_complexity=comp,
                    is_hotspot=is_hot,
                    line_number=stmt.lineno,
                    end_line_number=getattr(stmt, "end_lineno", stmt.lineno),
                    is_method=False,
                )
            )
            public_symbols.append(stmt.name)

    exports = _extract_py_all_exports(tree) or [s for s in public_symbols if not s.startswith("_")]
    all_hotspots = [
        FunctionTopology(
            name=f.name,
            docstring="",
            cyclomatic_complexity=f.cyclomatic_complexity,
            is_hotspot=True,
            line_number=f.line_number,
            end_line_number=f.end_line_number,
            is_method=f.is_method,
        )
        for f in sorted(visitor.functions, key=lambda x: x.cyclomatic_complexity, reverse=True)
        if f.cyclomatic_complexity >= CONST_HOTSPOT_COMPLEXITY_THRESHOLD
    ]

    total_syms = len(classes) + len(functions)
    text_repr = f"classes: {len(classes)}, functions: {len(functions)}, exports: {len(exports)}"
    est_tokens = estimate_tokens(text_repr) + (total_syms * 6)

    return TopologyOutline(
        classes=classes,
        functions=functions,
        exported_symbols=exports[:20],
        cyclomatic_hotspots=all_hotspots[:5],
        total_symbols=total_syms,
        estimated_tokens=est_tokens,
    )


def _build_single_func_structural(
    item: ast.FunctionDef | ast.AsyncFunctionDef,
    parent_class: str | None = None,
    indent: str = "",
) -> tuple[FunctionStructural, list[str]]:
    """Build single function structural item and rendered skeleton lines."""
    sig = _extract_py_signature(item)
    doc = _extract_py_docstring(item)
    sketches = _extract_control_flow_sketch(item)
    lines: list[str] = [f"{indent}{sig}"]
    if doc:
        lines.append(f'{indent}    """{doc}"""')
    for sk in sketches[:4]:
        lines.append(f"{indent}    {sk}")
    if not sketches:
        lines.append(f"{indent}    ...")

    func_obj = FunctionStructural(
        name=item.name,
        signature=sig,
        docstring=doc,
        control_flow=sketches,
        line_start=item.lineno,
        line_end=getattr(item, "end_lineno", item.lineno),
        parent_class=parent_class,
    )
    return func_obj, lines


def _build_single_class_structural(
    stmt: ast.ClassDef,
) -> tuple[ClassStructural, list[str]]:
    """Build single class structural item and member method skeletons."""
    cls_bases = [ast.unparse(b) for b in stmt.bases]
    bases_suffix = f"({', '.join(cls_bases)})" if cls_bases else ""
    lines: list[str] = [f"class {stmt.name}{bases_suffix}:"]
    doc = _extract_py_docstring(stmt)
    if doc:
        lines.append(f'    """{doc}"""')

    methods: list[FunctionStructural] = []
    for item in stmt.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            m_obj, m_lines = _build_single_func_structural(
                item, parent_class=stmt.name, indent="    "
            )
            methods.append(m_obj)
            lines.extend(m_lines)

    class_obj = ClassStructural(
        name=stmt.name,
        bases=cls_bases,
        docstring=doc,
        methods=methods,
        line_start=stmt.lineno,
        line_end=getattr(stmt, "end_lineno", stmt.lineno),
    )
    return class_obj, lines


def _build_python_structural(tree: ast.AST, content: str) -> StructuralOutline:
    """Construct Level 1 Structural outline from Python AST."""
    classes: list[ClassStructural] = []
    functions: list[FunctionStructural] = []
    skeleton_lines: list[str] = []

    for stmt in getattr(tree, "body", []):
        if isinstance(stmt, ast.ClassDef):
            c_obj, c_lines = _build_single_class_structural(stmt)
            classes.append(c_obj)
            skeleton_lines.extend(c_lines)
            skeleton_lines.append("")
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            f_obj, f_lines = _build_single_func_structural(stmt)
            functions.append(f_obj)
            skeleton_lines.extend(f_lines)
            skeleton_lines.append("")

    raw_skel = "\n".join(skeleton_lines).strip()
    return StructuralOutline(
        classes=classes,
        functions=functions,
        raw_skeleton=raw_skel,
        estimated_tokens=estimate_tokens(raw_skel),
    )


def _find_symbol_in_class(cls_node: ast.ClassDef, target: str) -> tuple[int, int, str] | None:
    """Search for target method inside an AST class definition."""
    for item in cls_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == target:
            end_line = getattr(item, "end_lineno", item.lineno)
            return item.lineno, end_line, f"{cls_node.name} > {item.name}"
    return None


def _find_symbol_line_range(tree: ast.AST, symbol_name: str) -> tuple[int, int, str] | None:
    """Find line span and breadcrumb path for a targeted symbol name."""
    target = symbol_name.strip()
    for stmt in getattr(tree, "body", []):
        if isinstance(stmt, ast.ClassDef):
            if stmt.name == target:
                return stmt.lineno, getattr(stmt, "end_lineno", stmt.lineno), stmt.name
            match = _find_symbol_in_class(stmt, target)
            if match:
                return match
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == target:
            return stmt.lineno, getattr(stmt, "end_lineno", stmt.lineno), stmt.name
    return None


def _find_polyglot_symbol_range(
    symbols: list[Any], symbol_name: str
) -> tuple[int, int, str] | None:
    """Find line span for symbol across polyglot AST symbols."""
    clean = symbol_name.strip().lower()
    for s in symbols:
        if s.name.lower() == clean:
            parent = f"{s.parent_scope} > " if s.parent_scope else ""
            return s.span.line_start, s.span.line_end, f"{parent}{s.name}"
    return None


def _parse_line_range_arg(lines_arg: str, total_lines: int) -> tuple[int, int]:
    """Parse a line range string like '40:80', '40-80', or '40' into (start, end)."""
    clean = lines_arg.strip()
    if not clean:
        return 1, min(total_lines, CONST_DEFAULT_FOCAL_WINDOW_SIZE)

    parts = clean.replace("-", ":").split(":")
    if len(parts) == 1:
        try:
            target = int(parts[0])
            half = CONST_DEFAULT_FOCAL_WINDOW_SIZE // 2
            start = max(1, target - half)
            end = min(total_lines, target + half)
            return start, end
        except ValueError:
            return 1, min(total_lines, CONST_DEFAULT_FOCAL_WINDOW_SIZE)

    try:
        start = max(1, int(parts[0]))
        end = min(total_lines, max(start, int(parts[1])))
        return start, end
    except ValueError:
        return 1, min(total_lines, CONST_DEFAULT_FOCAL_WINDOW_SIZE)


def _build_focal_window(
    content: str,
    line_start: int,
    line_end: int,
    breadcrumbs: str = "",
    symbol_name: str | None = None,
) -> FocalWindow:
    """Slice content into line-numbered focal window with breadcrumbs."""
    all_lines = content.splitlines()
    total_lines = len(all_lines)
    start_idx = max(0, line_start - 1)
    end_idx = min(total_lines, line_end)

    sliced = all_lines[start_idx:end_idx]
    formatted_lines: list[str] = []
    width = len(str(end_idx))
    for idx, line in enumerate(sliced, start=start_idx + 1):
        formatted_lines.append(f"{idx:>{width}} | {line}")

    focal_text = "\n".join(formatted_lines)
    return FocalWindow(
        line_start=start_idx + 1,
        line_end=end_idx,
        total_file_lines=total_lines,
        scope_breadcrumbs=breadcrumbs,
        content=focal_text,
        symbol_name=symbol_name,
        estimated_tokens=estimate_tokens(focal_text),
    )


def _build_polyglot_topology(path: Path, content: str, lang: str) -> TopologyOutline:
    """Construct Level 0 Topology outline for polyglot files via FallbackASTParser."""
    parser = FallbackASTParser()
    file_map = parser.parse(path=str(path), code=content, language=lang)
    classes: list[ClassTopology] = []
    functions: list[FunctionTopology] = []

    class_methods: dict[str, list[str]] = {}
    for sym in file_map.symbols:
        if sym.kind == SymbolKind.METHOD and sym.parent_scope:
            class_methods.setdefault(sym.parent_scope, []).append(sym.name)

    for sym in file_map.symbols:
        if sym.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE, SymbolKind.STRUCT):
            classes.append(
                ClassTopology(
                    name=sym.name,
                    methods=class_methods.get(sym.name, []),
                    docstring=sym.docstring,
                    line_start=sym.span.line_start,
                    line_end=sym.span.line_end,
                )
            )
        elif sym.kind == SymbolKind.FUNCTION:
            functions.append(
                FunctionTopology(
                    name=sym.name,
                    docstring=sym.docstring,
                    line_number=sym.span.line_start,
                    end_line_number=sym.span.line_end,
                )
            )

    exports = [
        s.name for s in file_map.symbols if s.kind in (SymbolKind.FUNCTION, SymbolKind.CLASS)
    ]
    total_syms = len(file_map.symbols)
    est_tokens = max(1, total_syms * 6)

    return TopologyOutline(
        classes=classes,
        functions=functions,
        exported_symbols=exports[:20],
        cyclomatic_hotspots=[],
        total_symbols=total_syms,
        estimated_tokens=est_tokens,
    )


def _build_polyglot_structural(path: Path, content: str, lang: str) -> StructuralOutline:
    """Construct Level 1 Structural outline for polyglot files."""
    parser = FallbackASTParser()
    file_map = parser.parse(path=str(path), code=content, language=lang)
    classes: list[ClassStructural] = []
    functions: list[FunctionStructural] = []
    skeleton_lines: list[str] = []

    for sym in file_map.symbols:
        if sym.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE, SymbolKind.STRUCT):
            sig = f"{sym.kind.value} {sym.name}"
            skeleton_lines.append(sig)
            classes.append(
                ClassStructural(
                    name=sym.name,
                    docstring=sym.docstring,
                    line_start=sym.span.line_start,
                    line_end=sym.span.line_end,
                )
            )
        elif sym.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD):
            sig = sym.signature or f"fn {sym.name}()"
            skeleton_lines.append(f"  {sig}")
            functions.append(
                FunctionStructural(
                    name=sym.name,
                    signature=sig,
                    docstring=sym.docstring,
                    line_start=sym.span.line_start,
                    line_end=sym.span.line_end,
                    parent_class=sym.parent_scope,
                )
            )

    raw_skel = "\n".join(skeleton_lines)
    return StructuralOutline(
        classes=classes,
        functions=functions,
        raw_skeleton=raw_skel,
        estimated_tokens=estimate_tokens(raw_skel),
    )


def _resolve_topology_level(
    is_py: bool, py_tree: ast.AST | None, resolved_path: Path, content: str
) -> TopologyOutline:
    """Resolve Level 0 Topology outline based on language."""
    if is_py and py_tree:
        return _build_python_topology(py_tree, content)
    lang = EXT_TO_LANG.get(resolved_path.suffix.lower(), "text")
    return _build_polyglot_topology(resolved_path, content, lang)


def _resolve_structural_level(
    is_py: bool, py_tree: ast.AST | None, resolved_path: Path, content: str
) -> StructuralOutline:
    """Resolve Level 1 Structural outline based on language."""
    if is_py and py_tree:
        return _build_python_structural(py_tree, content)
    lang = EXT_TO_LANG.get(resolved_path.suffix.lower(), "text")
    return _build_polyglot_structural(resolved_path, content, lang)


def _find_symbol_or_lines_range(
    is_py: bool,
    py_tree: ast.AST | None,
    resolved_path: Path,
    content: str,
    raw_lines: int,
    lines: str,
    target_sym: str,
) -> tuple[int, int, str]:
    """Find line range targeting a specific symbol or line range fallback."""
    found: tuple[int, int, str] | None = None
    if is_py and py_tree:
        found = _find_symbol_line_range(py_tree, target_sym)
    else:
        lang = EXT_TO_LANG.get(resolved_path.suffix.lower(), "text")
        parser = FallbackASTParser()
        file_map = parser.parse(path=str(resolved_path), code=content, language=lang)
        found = _find_polyglot_symbol_range(file_map.symbols, target_sym)

    if found:
        return found
    start, end = _parse_line_range_arg(lines, raw_lines)
    return start, end, str(resolved_path.name)


def _find_default_hotspot_range(
    is_py: bool,
    py_tree: ast.AST | None,
    content: str,
    raw_lines: int,
    rel_path: str,
) -> tuple[int, int, str, str | None]:
    """Find default focal range based on primary cyclomatic hotspot or head of file."""
    if is_py and py_tree:
        top = _build_python_topology(py_tree, content)
        if top.cyclomatic_hotspots:
            hot = top.cyclomatic_hotspots[0]
            crumbs = f"{rel_path} > {hot.name} (hotspot M={hot.cyclomatic_complexity})"
            return hot.line_number, hot.end_line_number, crumbs, hot.name

    return 1, min(raw_lines, CONST_DEFAULT_FOCAL_WINDOW_SIZE), rel_path, None


def _resolve_focal_bounds(
    is_py: bool,
    py_tree: ast.AST | None,
    resolved_path: Path,
    content: str,
    raw_lines: int,
    lines: str,
    symbol: str,
    rel_path: str,
) -> tuple[int, int, str, str | None]:
    """Determine line boundaries, breadcrumb path, and symbol name for focal window."""
    target_sym = symbol.strip() if symbol else ""
    if target_sym:
        start, end, crumbs = _find_symbol_or_lines_range(
            is_py, py_tree, resolved_path, content, raw_lines, lines, target_sym
        )
        return start, end, crumbs, target_sym

    if lines:
        start, end = _parse_line_range_arg(lines, raw_lines)
        return start, end, rel_path, None

    return _find_default_hotspot_range(is_py, py_tree, content, raw_lines, rel_path)


def generate_semantic_outline(
    target_path: Path,
    level: FocalLevel = FocalLevel.TOPOLOGY,
    lines: str = "",
    symbol: str = "",
    repo_root: Path | None = None,
) -> SemanticOutline:
    """Generate multi-scale semantic outline across Level 0, Level 1, or Level 2."""
    t0 = time.perf_counter()
    resolved_path, base_root = _validate_inspect_path(target_path, repo_root=repo_root)

    try:
        content = resolved_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise DevOpsCLIError(
            f"Failed to read target file: {target_path}",
            details={"path": str(target_path)[:256], "error": str(exc)[:256]},
        ) from exc

    rel_path = str(resolved_path.relative_to(base_root))
    raw_lines = len(content.splitlines())
    raw_tokens = estimate_tokens(content)

    is_py, py_tree = _parse_optional_python_ast(resolved_path, content)
    topology: TopologyOutline | None = None
    structural: StructuralOutline | None = None
    focal_window: FocalWindow | None = None
    outline_tokens = 0

    if level == FocalLevel.TOPOLOGY:
        topology = _resolve_topology_level(is_py, py_tree, resolved_path, content)
        outline_tokens = topology.estimated_tokens
    elif level == FocalLevel.STRUCTURAL:
        structural = _resolve_structural_level(is_py, py_tree, resolved_path, content)
        outline_tokens = structural.estimated_tokens
    elif level == FocalLevel.DEEP_FOCAL:
        l_start, l_end, crumbs, sym_name = _resolve_focal_bounds(
            is_py, py_tree, resolved_path, content, raw_lines, lines, symbol, rel_path
        )
        focal_window = _build_focal_window(
            content, l_start, l_end, breadcrumbs=crumbs, symbol_name=sym_name
        )
        outline_tokens = focal_window.estimated_tokens

    reduction_pct = _calculate_token_reduction(raw_tokens, outline_tokens)
    t_elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    return SemanticOutline(
        path=rel_path,
        language=(
            "python"
            if is_py
            else EXT_TO_LANG.get(resolved_path.suffix.lower(), resolved_path.suffix.lstrip("."))
        ),
        level=level,
        raw_lines=raw_lines,
        raw_tokens=raw_tokens,
        outline_tokens=outline_tokens,
        token_reduction_pct=reduction_pct,
        generation_time_ms=t_elapsed_ms,
        topology=topology,
        structural=structural,
        focal_window=focal_window,
    )


def _parse_optional_python_ast(path: Path, content: str) -> tuple[bool, ast.AST | None]:
    """Safely parse Python AST if file suffix indicates Python."""
    if path.suffix != ".py":
        return False, None
    try:
        return True, ast.parse(content, filename=str(path))
    except SyntaxError:
        return False, None


def _render_classes_section(classes: list[ClassTopology]) -> list[str]:
    """Render classes subsection for topology markdown."""
    if not classes:
        return []
    res = ["**Classes**:"]
    for c in classes:
        bases = f"({', '.join(c.bases)})" if c.bases else ""
        doc = f" — {c.docstring}" if c.docstring else ""
        methods = f" [methods: {', '.join(c.methods[:5])}]" if c.methods else ""
        res.append(f"  - `class {c.name}{bases}`{methods}{doc}")
    res.append("")
    return res


def _render_functions_section(functions: list[FunctionTopology]) -> list[str]:
    """Render functions subsection for topology markdown."""
    if not functions:
        return []
    res = ["**Functions**:"]
    for fn in functions:
        doc = f" — {fn.docstring}" if fn.docstring else ""
        res.append(f"  - `{fn.name}()` (M={fn.cyclomatic_complexity}){doc}")
    res.append("")
    return res


def _render_hotspots_section(hotspots: list[FunctionTopology]) -> list[str]:
    """Render cyclomatic hotspots subsection for topology markdown."""
    if not hotspots:
        return []
    res = ["**Cyclomatic Hotspots**:"]
    for h in hotspots:
        res.append(
            f"  - `{h.name}` (lines {h.line_number}-{h.end_line_number}, McCabe M={h.cyclomatic_complexity})"
        )
    res.append("")
    return res


def _render_topology_markdown(outline: SemanticOutline) -> str:
    """Render Level 0 Topology outline as structured markdown."""
    top = outline.topology
    if not top:
        return ""
    parts = []
    if top.exported_symbols:
        parts.append(f"**Exported Symbols**: {', '.join(top.exported_symbols)}\n")
    parts.extend(_render_classes_section(top.classes))
    parts.extend(_render_functions_section(top.functions))
    parts.extend(_render_hotspots_section(top.cyclomatic_hotspots))
    return "\n".join(parts).strip()


def _render_structural_markdown(outline: SemanticOutline) -> str:
    """Render Level 1 Structural outline as code skeleton."""
    st = outline.structural
    if not st:
        return ""
    return f"```{outline.language}\n{st.raw_skeleton}\n```"


def _render_focal_markdown(outline: SemanticOutline) -> str:
    """Render Level 2 Deep Focal window with breadcrumbs."""
    fw = outline.focal_window
    if not fw:
        return ""
    crumb = f"# Breadcrumb: {fw.scope_breadcrumbs} (lines {fw.line_start}-{fw.line_end} of {fw.total_file_lines})\n"
    return f"{crumb}```{outline.language}\n{fw.content}\n```"


_RENDERERS: dict[FocalLevel, Callable[[SemanticOutline], str]] = {
    FocalLevel.TOPOLOGY: _render_topology_markdown,
    FocalLevel.STRUCTURAL: _render_structural_markdown,
    FocalLevel.DEEP_FOCAL: _render_focal_markdown,
}


def _render_semantic_outline_text(outline: SemanticOutline) -> str:
    """Format SemanticOutline into readable Markdown display."""
    level_names = {
        0: "Level 0: Topology",
        1: "Level 1: Structural Outline",
        2: "Level 2: Deep Focal Window",
    }
    header = (
        f"### {level_names.get(int(outline.level), 'Outline')}: `{outline.path}` "
        f"({outline.language}, {outline.raw_lines} lines | "
        f"~{outline.outline_tokens} tokens, {outline.token_reduction_pct}% reduction, "
        f"{outline.generation_time_ms}ms)\n"
    )
    renderer = _RENDERERS.get(outline.level)
    body = renderer(outline) if renderer else ""
    return f"{header}\n{body}".strip()
