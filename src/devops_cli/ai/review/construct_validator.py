"""Construct-aware finding location validator and AST relocation engine.

Verifies that a finding's cited line span actually contains the construct
(symbol, call, decorator, assignment, or literal) named by the finding.
On mismatch, attempts relocation by AST symbol search and records the correction;
invalidates the finding only when the construct is absent from the file entirely.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import re
from typing import TYPE_CHECKING

from devops_cli.ai.review_schema import (
    _extract_code_symbols,
    _parse_location,
)
from devops_cli.config.constants import REVIEW_GENERIC_SYMBOL_STOPWORDS

if TYPE_CHECKING:
    from devops_cli.ai.review_schema import Finding


@dataclass(frozen=True, slots=True)
class AstConstruct:
    """Indexed Python AST construct with line boundaries."""

    kind: str  # "function" | "class" | "call" | "decorator" | "assignment" | "literal" | "symbol" | "handler"
    name: str
    start_line: int
    end_line: int


def _get_dotted_name(node: ast.AST) -> str | None:
    """Extract full dotted name from an AST Attribute or Name node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _get_dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _extract_call_name(node: ast.Call) -> str | None:
    """Extract function or method call name from an ast.Call node."""
    return _get_dotted_name(node.func)


def _extract_decorator_name(node: ast.AST) -> str | None:
    """Extract decorator identifier or attribute name from decorator AST node."""
    if isinstance(node, ast.Call):
        return _get_dotted_name(node.func)
    return _get_dotted_name(node)


def _collect_decorator_constructs(decorators: list[ast.expr]) -> list[AstConstruct]:
    """Collect decorator constructs from a decorator list."""
    constructs: list[AstConstruct] = []
    for dec in decorators:
        d_name = _extract_decorator_name(dec)
        if d_name:
            constructs.append(
                AstConstruct(
                    kind="decorator",
                    name=d_name,
                    start_line=dec.lineno,
                    end_line=dec.end_lineno or dec.lineno,
                )
            )
    return constructs


def _collect_function_constructs(node: ast.AST) -> list[AstConstruct]:
    """Collect function definitions and their decorators."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []
    s_line = node.lineno
    e_line = node.end_lineno or node.lineno
    fn_construct = AstConstruct(
        kind="function", name=node.name, start_line=s_line, end_line=e_line
    )
    return [fn_construct, *_collect_decorator_constructs(node.decorator_list)]


def _collect_class_constructs(node: ast.AST) -> list[AstConstruct]:
    """Collect class definitions and their decorators."""
    if not isinstance(node, ast.ClassDef):
        return []
    s_line = node.lineno
    e_line = node.end_lineno or node.lineno
    cls_construct = AstConstruct(
        kind="class", name=node.name, start_line=s_line, end_line=e_line
    )
    return [cls_construct, *_collect_decorator_constructs(node.decorator_list)]


def _collect_call_constructs(node: ast.AST) -> list[AstConstruct]:
    """Collect call construct and optional terminal attribute from ast.Call."""
    if not isinstance(node, ast.Call):
        return []
    c_name = _extract_call_name(node)
    if not c_name:
        return []
    s_line = node.lineno
    e_line = node.end_lineno or node.lineno
    items = [AstConstruct(kind="call", name=c_name, start_line=s_line, end_line=e_line)]
    if "." in c_name:
        items.append(
            AstConstruct(
                kind="call",
                name=c_name.split(".")[-1],
                start_line=s_line,
                end_line=e_line,
            )
        )
    return items


def _collect_assign_constructs(node: ast.AST) -> list[AstConstruct]:
    """Collect assignment target identifiers from Assign or AnnAssign."""
    constructs: list[AstConstruct] = []
    if isinstance(node, ast.Assign):
        s_line = node.lineno
        e_line = node.end_lineno or node.lineno
        for target in node.targets:
            t_name = _get_dotted_name(target)
            if t_name:
                constructs.append(
                    AstConstruct(
                        kind="assignment",
                        name=t_name,
                        start_line=s_line,
                        end_line=e_line,
                    )
                )
    elif isinstance(node, ast.AnnAssign):
        t_name = _get_dotted_name(node.target)
        if t_name:
            s_line = node.lineno
            e_line = node.end_lineno or node.lineno
            constructs.append(
                AstConstruct(
                    kind="assignment", name=t_name, start_line=s_line, end_line=e_line
                )
            )
    return constructs


def _collect_literal_constructs(node: ast.AST) -> list[AstConstruct]:
    """Collect string literal constants within reasonable length bounds."""
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return []
    val = node.value.strip()
    if not (3 <= len(val) <= 120):
        return []
    return [
        AstConstruct(
            kind="literal",
            name=val,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
        )
    ]


def _collect_ast_name_constructs(node: ast.AST) -> list[AstConstruct]:
    """Collect identifier and exception handler constructs from AST."""
    if isinstance(node, ast.Name):
        s_line = node.lineno
        e_line = node.end_lineno or node.lineno
        return [
            AstConstruct(
                kind="symbol", name=node.id, start_line=s_line, end_line=e_line
            )
        ]
    if isinstance(node, ast.ExceptHandler):
        s_line = node.lineno
        e_line = node.end_lineno or node.lineno
        return [
            AstConstruct(
                kind="handler", name="except", start_line=s_line, end_line=e_line
            )
        ]
    return []


def collect_ast_constructs(tree: ast.AST) -> list[AstConstruct]:
    """Traverse an AST and index all functions, classes, calls, decorators, and literals."""
    constructs: list[AstConstruct] = []
    for node in ast.walk(tree):
        constructs.extend(_collect_function_constructs(node))
        constructs.extend(_collect_class_constructs(node))
        constructs.extend(_collect_call_constructs(node))
        constructs.extend(_collect_assign_constructs(node))
        constructs.extend(_collect_literal_constructs(node))
        constructs.extend(_collect_ast_name_constructs(node))
    return constructs


def _extract_backtick_candidates(text: str) -> list[str]:
    """Extract candidate names enclosed in backticks."""
    candidates: list[str] = []
    for raw in re.findall(r"`([^`\n]{2,80})`", text):
        clean = raw.strip().lstrip("@").rstrip("()")
        if (
            clean
            and len(clean) > 2
            and clean.lower() not in REVIEW_GENERIC_SYMBOL_STOPWORDS
        ):
            candidates.append(clean)
    return candidates


def _extract_syntax_candidates(text: str) -> list[str]:
    """Extract identifiers from def/class keywords, calls, and decorators."""
    candidates: list[str] = []
    for name in re.findall(
        r"\b(?:def|class|function|method)\s+([A-Za-z_][A-Za-z0-9_]*)", text
    ):
        if name.lower() not in REVIEW_GENERIC_SYMBOL_STOPWORDS:
            candidates.append(name)
    for call_match in re.findall(r"\b([A-Za-z_][A-Za-z0-9_.]*)\s*\(\)", text):
        if call_match.lower() not in REVIEW_GENERIC_SYMBOL_STOPWORDS:
            candidates.append(call_match)
    for dec_match in re.findall(r"@([A-Za-z_][A-Za-z0-9_.]*)", text):
        if dec_match.lower() not in REVIEW_GENERIC_SYMBOL_STOPWORDS:
            candidates.append(dec_match)
    return candidates


def _extract_quoted_candidates(text: str) -> list[str]:
    """Extract quoted string literals from finding text."""
    candidates: list[str] = []
    for lit in re.findall(r'["\']([A-Za-z0-9_\-./:]{3,60})["\']', text):
        if lit.lower() not in REVIEW_GENERIC_SYMBOL_STOPWORDS:
            candidates.append(lit)
    return candidates


def extract_finding_construct_candidates(finding: Finding) -> list[str]:
    """Extract distinctive construct names cited in a finding's title and description."""
    text = f"{finding.title} {finding.description or ''}"
    candidates = [
        *_extract_backtick_candidates(text),
        *_extract_syntax_candidates(text),
        *_extract_quoted_candidates(text),
        *(
            sym
            for sym in _extract_code_symbols(text)
            if sym.lower() not in REVIEW_GENERIC_SYMBOL_STOPWORDS
        ),
    ]
    unique_candidates = list(dict.fromkeys(candidates))
    unique_candidates.sort(key=lambda s: ("." in s, len(s)), reverse=True)
    return unique_candidates


def _construct_matches(construct: AstConstruct, candidate: str) -> bool:
    """Report whether an AST construct matches a candidate string."""
    c_name = construct.name.lower()
    cand = candidate.lower()
    if c_name == cand:
        return True
    if "." in c_name and c_name.endswith("." + cand):
        return True
    return False


def _construct_intersects_span(
    construct: AstConstruct, start_line: int, end_line: int
) -> bool:
    """Report whether an AST construct intersects or encloses the cited line span."""
    return construct.start_line <= end_line and construct.end_line >= start_line


def _line_contains_candidate(
    lines: list[str], candidate: str, s_line: int, end_line: int
) -> bool:
    """Check if the cited line span text literally contains candidate as an identifier or token."""
    pattern = rf"\b{re.escape(candidate)}\b"
    for line_idx in range(max(0, s_line - 1), min(len(lines), end_line)):
        if re.search(pattern, lines[line_idx], re.IGNORECASE):
            return True
    return False


def _find_text_relocation(lines: list[str], candidate: str) -> int | None:
    """Find line number (1-indexed) containing candidate identifier in file text."""
    pattern = rf"\b{re.escape(candidate)}\b"
    for idx, line in enumerate(lines, start=1):
        if re.search(pattern, line, re.IGNORECASE):
            return idx
    return None


def _is_candidate_present_in_text(content: str, candidate: str) -> bool:
    """Check if candidate appears as a word anywhere in the file text."""
    return bool(re.search(rf"\b{re.escape(candidate)}\b", content, re.IGNORECASE))


def _find_best_relocation(
    constructs: list[AstConstruct], candidates: list[str]
) -> AstConstruct | None:
    """Search for the best construct match elsewhere in the file."""
    kind_rank = {
        "call": 0,
        "function": 1,
        "class": 2,
        "decorator": 3,
        "assignment": 4,
        "symbol": 5,
        "handler": 6,
        "literal": 7,
    }
    for cand in candidates:
        matches = [c for c in constructs if _construct_matches(c, cand)]
        if matches:
            matches.sort(key=lambda c: (kind_rank.get(c.kind, 99), c.start_line))
            return matches[0]
    return None


def _check_span_containment(
    constructs: list[AstConstruct], candidates: list[str], s_line: int, end_line: int
) -> bool:
    """Check if any candidate construct is present within or enclosing the cited span."""
    return any(
        _construct_matches(c, cand) and _construct_intersects_span(c, s_line, end_line)
        for cand in candidates
        for c in constructs
    )


def _build_relocation_result(
    finding: Finding, file_part: str, reloc: AstConstruct
) -> Finding:
    """Build updated Finding model with relocated location coordinates."""
    new_loc = f"{file_part}:{reloc.start_line}"
    if reloc.end_line > reloc.start_line and reloc.kind in {"function", "class"}:
        new_loc = f"{file_part}:{reloc.start_line}-{reloc.end_line}"
    return finding.model_copy(
        update={
            "location": new_loc,
            "relocated_from": finding.location,
        }
    )


def _build_invalidation_result(
    finding: Finding, candidate: str, file_path: Path
) -> Finding:
    """Build invalidated Finding when cited construct is absent from file."""
    reason = f"Construct '{candidate}' cited in finding is absent from {file_path.name}"
    res = finding.model_copy(
        update={
            "verified": False,
            "mitigated": False,
            "reportable": False,
            "status": "INVALIDATED",
            "invalidation_reason": reason,
        }
    )
    try:
        from devops_cli.ai.review.common_hallucinations import (
            auto_record_invalidated_finding,
        )

        auto_record_invalidated_finding(res, file_path=file_path, reason=reason)
    except Exception:
        pass
    return res


def _is_inspectable_python_file(path: Path) -> bool:
    """Return True if path exists and has a Python source extension."""
    return path.is_file() and path.suffix.lower() in {".py", ".pyi"}


def _read_file_safely(file_path: Path) -> str | None:
    """Safely read target file contents returning None on I/O error."""
    try:
        return file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _parse_ast_safely(source: str, file_path: Path) -> ast.AST | None:
    """Read and parse Python source file AST, returning None on syntax error."""
    try:
        return ast.parse(source, filename=str(file_path))
    except Exception:
        return None


def _resolve_repaired_finding(
    finding: Finding,
    file_part: str,
    constructs: list[AstConstruct],
    candidates: list[str],
    file_lines: list[str],
    content: str,
    file_path: Path,
) -> Finding:
    """Attempt relocation in AST or text, or invalidate if construct is absent."""
    reloc = _find_best_relocation(constructs, candidates)
    if reloc is not None:
        return _build_relocation_result(finding, file_part, reloc)

    for cand in candidates:
        text_line = _find_text_relocation(file_lines, cand)
        if text_line is not None:
            text_reloc = AstConstruct(
                kind="symbol", name=cand, start_line=text_line, end_line=text_line
            )
            return _build_relocation_result(finding, file_part, text_reloc)

    if any(_is_candidate_present_in_text(content, cand) for cand in candidates):
        return finding

    return _build_invalidation_result(finding, candidates[0], file_path)


def validate_construct_location(finding: Finding, file_path: Path) -> Finding:
    """Verify that cited file span contains named construct; relocate on mismatch or invalidate if absent."""
    if not _is_inspectable_python_file(file_path):
        return finding

    file_part, s_line, e_line = _parse_location(finding.location)
    if s_line is None:
        return finding

    content = _read_file_safely(file_path)
    if content is None:
        return finding

    tree = _parse_ast_safely(content, file_path)
    if tree is None:
        return finding

    candidates = extract_finding_construct_candidates(finding)
    constructs = collect_ast_constructs(tree)
    if not (candidates and constructs):
        return finding

    end_line = e_line if e_line is not None else s_line
    file_lines = content.splitlines()

    if _check_span_containment(constructs, candidates, s_line, end_line):
        return finding
    if any(
        _line_contains_candidate(file_lines, cand, s_line, end_line)
        for cand in candidates
    ):
        return finding

    return _resolve_repaired_finding(
        finding, file_part, constructs, candidates, file_lines, content, file_path
    )
