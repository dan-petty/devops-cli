"""Zero-dependency, zero-crash fallback AST parser for polyglot languages."""

from __future__ import annotations

import ast
import re
import warnings
from typing import Any

from devops_cli.ai.ast.models import CodeSpan, PolyglotFileMap, PolyglotSymbol, SymbolKind


def _make_span(line_start: int, line_end: int) -> CodeSpan:
    return CodeSpan(line_start=line_start, line_end=line_end)


def _declared(
    name: str,
    kind: SymbolKind,
    line: str,
    idx: int,
    language: str,
    parent_scope: str | None = None,
) -> PolyglotSymbol:
    """A symbol declared on line `idx`, signed with that line as tree-sitter signs its symbols."""
    return PolyglotSymbol(
        name=name,
        kind=kind,
        span=_make_span(idx, idx),
        signature=line.strip(),
        language=language,
        parent_scope=parent_scope,
    )


# ---------------------------------------------------------------------------
# Python AST Parsing
# ---------------------------------------------------------------------------


def _extract_py_docstring(
    node: ast.AsyncFunctionDef | ast.FunctionDef | ast.ClassDef | ast.Module,
) -> str:
    doc = ast.get_docstring(node)
    if not doc:
        return ""
    lines = doc.strip().splitlines()
    return lines[0][:100] if lines else ""


def _py_declaration_line(
    node: ast.AsyncFunctionDef | ast.FunctionDef | ast.ClassDef, lines: list[str]
) -> str:
    """The line a definition starts on, after its decorators, as tree-sitter signs it."""
    return lines[node.lineno - 1].strip()


def _parse_py_class_members(cls_node: ast.ClassDef, lines: list[str]) -> list[PolyglotSymbol]:
    methods: list[PolyglotSymbol] = []
    for item in cls_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(
                PolyglotSymbol(
                    name=item.name,
                    kind=SymbolKind.METHOD,
                    span=_make_span(item.lineno, getattr(item, "end_lineno", item.lineno)),
                    signature=_py_declaration_line(item, lines),
                    docstring=_extract_py_docstring(item),
                    language="python",
                    parent_scope=cls_node.name,
                )
            )
    return methods


def _parse_python_symbols(code: str) -> list[PolyglotSymbol]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(code)
    except Exception:
        return []

    lines = code.splitlines()
    symbols: list[PolyglotSymbol] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append(
                PolyglotSymbol(
                    name=node.name,
                    kind=SymbolKind.CLASS,
                    span=_make_span(node.lineno, getattr(node, "end_lineno", node.lineno)),
                    signature=_py_declaration_line(node, lines),
                    docstring=_extract_py_docstring(node),
                    language="python",
                )
            )
            symbols.extend(_parse_py_class_members(node, lines))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(
                PolyglotSymbol(
                    name=node.name,
                    kind=SymbolKind.FUNCTION,
                    span=_make_span(node.lineno, getattr(node, "end_lineno", node.lineno)),
                    signature=_py_declaration_line(node, lines),
                    docstring=_extract_py_docstring(node),
                    language="python",
                )
            )
    return symbols


# ---------------------------------------------------------------------------
# TypeScript & JavaScript Regex Parsing
# ---------------------------------------------------------------------------

RE_TS_INTERFACE = re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z0-9_]+)", re.MULTILINE)
RE_TS_CLASS = re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z0-9_]+)", re.MULTILINE)
# `export default function main()`, and generics before the parameters: `function f<T>(x: T)`.
RE_TS_FUNC = re.compile(
    r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*(?:<.*?>)?\s*\(",
    re.MULTILINE,
)
RE_TS_METHOD = re.compile(
    r"^\s+(?:(?:public|private|protected|async)\s+)*([A-Za-z0-9_]+)\s*\((.*?)\)\s*[:{]",
    re.MULTILINE,
)


def _parse_typescript_symbols(code: str, lang: str = "typescript") -> list[PolyglotSymbol]:
    symbols: list[PolyglotSymbol] = []
    lines = code.splitlines()

    for idx, line in enumerate(lines, 1):
        m_iface = RE_TS_INTERFACE.match(line)
        if m_iface:
            symbols.append(_declared(m_iface.group(1), SymbolKind.INTERFACE, line, idx, lang))
            continue

        m_cls = RE_TS_CLASS.match(line)
        if m_cls:
            symbols.append(_declared(m_cls.group(1), SymbolKind.CLASS, line, idx, lang))
            continue

        m_fn = RE_TS_FUNC.match(line)
        if m_fn:
            symbols.append(_declared(m_fn.group(1), SymbolKind.FUNCTION, line, idx, lang))
            continue

        m_m = RE_TS_METHOD.match(line)
        if m_m and m_m.group(1) not in ("if", "for", "while", "switch", "catch"):
            symbols.append(_declared(m_m.group(1), SymbolKind.METHOD, line, idx, lang))
    return symbols


# ---------------------------------------------------------------------------
# Go Regex Parsing
# ---------------------------------------------------------------------------

RE_GO_STRUCT = re.compile(r"^\s*type\s+([A-Za-z0-9_]+)\s+struct\b")
RE_GO_IFACE = re.compile(r"^\s*type\s+([A-Za-z0-9_]+)\s+interface\b")
RE_GO_FUNC = re.compile(r"^\s*func\s+([A-Za-z0-9_]+)\s*\((.*?)\)")
RE_GO_METHOD = re.compile(
    r"^\s*func\s*\(\s*(?:[A-Za-z0-9_]+\s+)?\*?([A-Za-z0-9_]+)\s*\)\s*([A-Za-z0-9_]+)\s*\((.*?)\)"
)


def _match_go_line(line: str, idx: int) -> PolyglotSymbol | None:
    m_meth = RE_GO_METHOD.match(line)
    if m_meth:
        return _declared(
            m_meth.group(2), SymbolKind.METHOD, line, idx, "go", parent_scope=m_meth.group(1)
        )
    m_fn = RE_GO_FUNC.match(line)
    if m_fn:
        return _declared(m_fn.group(1), SymbolKind.FUNCTION, line, idx, "go")
    m_str = RE_GO_STRUCT.match(line)
    if m_str:
        return _declared(m_str.group(1), SymbolKind.STRUCT, line, idx, "go")
    m_if = RE_GO_IFACE.match(line)
    if m_if:
        return _declared(m_if.group(1), SymbolKind.INTERFACE, line, idx, "go")
    return None


def _parse_go_symbols(code: str) -> list[PolyglotSymbol]:
    symbols: list[PolyglotSymbol] = []
    for idx, line in enumerate(code.splitlines(), 1):
        sym = _match_go_line(line, idx)
        if sym:
            symbols.append(sym)
    return symbols


# ---------------------------------------------------------------------------
# Rust Regex Parsing
# ---------------------------------------------------------------------------

# Rust's function qualifiers, in the reference's grammar: `const`, `async`, `safe` or `unsafe`, and
# `extern` with an optional ABI; then generics before the parameters: `fn process<T: Clone>(x: T)`.
RE_RS_FN = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?"
    r'(?:(?:const|async|safe|unsafe|extern(?:\s+"[^"]*")?)\s+)*'
    r"fn\s+([A-Za-z0-9_]+)\s*(?:<.*?>)?\s*\("
)
RE_RS_STRUCT = re.compile(r"^\s*(?:pub(?:\(.*?\))?\s+)?struct\s+([A-Za-z0-9_]+)")
RE_RS_TRAIT = re.compile(r"^\s*(?:pub(?:\(.*?\))?\s+)?trait\s+([A-Za-z0-9_]+)")
RE_RS_IMPL = re.compile(r"^\s*impl(?:\s+.*?)?\s+([A-Za-z0-9_]+)\s*\{")


def _match_rust_line(line: str, idx: int) -> PolyglotSymbol | None:
    m_fn = RE_RS_FN.match(line)
    if m_fn:
        return _declared(m_fn.group(1), SymbolKind.FUNCTION, line, idx, "rust")
    m_str = RE_RS_STRUCT.match(line)
    if m_str:
        return _declared(m_str.group(1), SymbolKind.STRUCT, line, idx, "rust")
    m_tr = RE_RS_TRAIT.match(line)
    if m_tr:
        return _declared(m_tr.group(1), SymbolKind.INTERFACE, line, idx, "rust")
    return None


def _parse_rust_symbols(code: str) -> list[PolyglotSymbol]:
    symbols: list[PolyglotSymbol] = []
    for idx, line in enumerate(code.splitlines(), 1):
        sym = _match_rust_line(line, idx)
        if sym:
            symbols.append(sym)
    return symbols


# ---------------------------------------------------------------------------
# Java Regex Parsing
# ---------------------------------------------------------------------------

RE_JAVA_CLASS = re.compile(
    r"^\s*(?:public|protected|private)?\s*(?:static\s+)?class\s+([A-Za-z0-9_]+)"
)
RE_JAVA_IFACE = re.compile(r"^\s*(?:public|protected|private)?\s*interface\s+([A-Za-z0-9_]+)")
RE_JAVA_METHOD = re.compile(
    r"^\s*(?:public|protected|private)?\s*(?:static\s+)?(?:final\s+)?(?:[\w<>\[\],\s]+)\s+([A-Za-z0-9_]+)\s*\((.*?)\)\s*\{?"
)


def _match_java_line(line: str, idx: int) -> PolyglotSymbol | None:
    m_cls = RE_JAVA_CLASS.match(line)
    if m_cls:
        return _declared(m_cls.group(1), SymbolKind.CLASS, line, idx, "java")
    m_if = RE_JAVA_IFACE.match(line)
    if m_if:
        return _declared(m_if.group(1), SymbolKind.INTERFACE, line, idx, "java")
    m_meth = RE_JAVA_METHOD.match(line)
    if m_meth and m_meth.group(1) not in ("if", "for", "while", "switch", "catch", "new"):
        return _declared(m_meth.group(1), SymbolKind.METHOD, line, idx, "java")
    return None


def _parse_java_symbols(code: str) -> list[PolyglotSymbol]:
    symbols: list[PolyglotSymbol] = []
    for idx, line in enumerate(code.splitlines(), 1):
        sym = _match_java_line(line, idx)
        if sym:
            symbols.append(sym)
    return symbols


# ---------------------------------------------------------------------------
# HCL / Terraform Regex Parsing
# ---------------------------------------------------------------------------

RE_HCL_RESOURCE = re.compile(r'^\s*resource\s+"([^"]+)"\s+"([^"]+)"')
RE_HCL_DATA = re.compile(r'^\s*data\s+"([^"]+)"\s+"([^"]+)"')
RE_HCL_VAR = re.compile(r'^\s*variable\s+"([^"]+)"')
RE_HCL_OUT = re.compile(r'^\s*output\s+"([^"]+)"')


def _match_hcl_line(line: str, idx: int) -> PolyglotSymbol | None:
    m_res = RE_HCL_RESOURCE.match(line)
    if m_res:
        name = f'resource "{m_res.group(1)}" "{m_res.group(2)}"'
        return _declared(name, SymbolKind.STRUCT, line, idx, "hcl")
    m_data = RE_HCL_DATA.match(line)
    if m_data:
        name = f'data "{m_data.group(1)}" "{m_data.group(2)}"'
        return _declared(name, SymbolKind.STRUCT, line, idx, "hcl")
    m_var = RE_HCL_VAR.match(line)
    if m_var:
        return _declared(f'variable "{m_var.group(1)}"', SymbolKind.CONSTANT, line, idx, "hcl")
    m_out = RE_HCL_OUT.match(line)
    if m_out:
        return _declared(f'output "{m_out.group(1)}"', SymbolKind.CONSTANT, line, idx, "hcl")
    return None


def _parse_hcl_symbols(code: str) -> list[PolyglotSymbol]:
    symbols: list[PolyglotSymbol] = []
    for idx, line in enumerate(code.splitlines(), 1):
        sym = _match_hcl_line(line, idx)
        if sym:
            symbols.append(sym)
    return symbols


# ---------------------------------------------------------------------------
# C#, C, C++ and Shell Regex Parsing
# ---------------------------------------------------------------------------

# Words a declaration pattern can mistake for a name: `if (x)`, `while (...)`.
_CONTROL_WORDS = frozenset(
    {"if", "for", "foreach", "while", "switch", "catch", "return", "sizeof", "using", "lock"}
)
_CS_MODIFIERS = (
    r"(?:(?:public|private|protected|internal|static|sealed|abstract|partial|readonly|unsafe"
    r"|virtual|override|async|extern|new)\s+)*"
)
# A statement that calls rather than declares: `return Foo(`, `await Bar(`.
_NOT_A_DECLARATION = r"(?!(?:return|await|throw|yield|else|new)\b)"

# Each language's line patterns, tried in order: the first that matches names the symbol.
_LINE_PATTERNS: dict[str, tuple[tuple[re.Pattern[str], SymbolKind], ...]] = {
    "csharp": (
        (re.compile(r"^\s*namespace\s+([\w.]+)"), SymbolKind.MODULE),
        (re.compile(rf"^\s*{_CS_MODIFIERS}(?:record\s+)?class\s+(\w+)"), SymbolKind.CLASS),
        (re.compile(rf"^\s*{_CS_MODIFIERS}interface\s+(\w+)"), SymbolKind.INTERFACE),
        (re.compile(rf"^\s*{_CS_MODIFIERS}(?:record\s+)?struct\s+(\w+)"), SymbolKind.STRUCT),
        (re.compile(rf"^\s*{_CS_MODIFIERS}record\s+(\w+)"), SymbolKind.CLASS),
        (re.compile(rf"^\s*{_CS_MODIFIERS}enum\s+(\w+)"), SymbolKind.TYPE),
        (
            re.compile(
                rf"^\s*{_NOT_A_DECLARATION}{_CS_MODIFIERS}[\w<>\[\],.?]+\s+(\w+)\s*(?:<[^>]*>)?"
                # A body on later lines, or an expression body: `Foo() => ...;`.
                r"\s*\((?:[^;]*$|[^)]*\)\s*=>)"
            ),
            SymbolKind.METHOD,
        ),
    ),
    "c": (
        (re.compile(r"^\s*#\s*define\s+(\w+)\("), SymbolKind.FUNCTION),
        (re.compile(r"^(?:typedef\s+)?(?:struct|union)\s+(\w+)\s*\{"), SymbolKind.STRUCT),
        (re.compile(r"^(?:typedef\s+)?enum\s+(\w+)\s*\{"), SymbolKind.TYPE),
        # A definition starts at column 0, as C code is written.
        (
            re.compile(
                # An export macro may wrap the return type: `CJSON_PUBLIC(void) cJSON_Delete(...)`.
                rf"^{_NOT_A_DECLARATION}(?:\w+\([^()]*\)\s*)?(?:[A-Za-z_][\w\s*]*?[\s*])?"
                # The body may open on the line, or be written on it: `int f() { return 0; }`.
                r"(\w+)\s*\([^;]*?\)\s*(?:\{.*)?$"
            ),
            SymbolKind.FUNCTION,
        ),
    ),
    "cpp": (
        (re.compile(r"^\s*namespace\s+([\w:]+)\s*\{"), SymbolKind.MODULE),
        (re.compile(r"^\s*(?:template\s*<.*>\s*)?class\s+(\w+)[^;]*$"), SymbolKind.CLASS),
        (re.compile(r"^\s*(?:template\s*<.*>\s*)?struct\s+(\w+)[^;]*$"), SymbolKind.STRUCT),
        (re.compile(r"^\s*enum\s+(?:class\s+)?(\w+)"), SymbolKind.TYPE),
        (re.compile(r"^\s*#\s*define\s+(\w+)\("), SymbolKind.FUNCTION),
        (
            re.compile(
                rf"^{_NOT_A_DECLARATION}[A-Za-z_][\w\s*&:<>,]*?\b([\w:~]+)\s*\([^;]*?\)\s*(?:const\s*)?(?:\{{.*)?$"
            ),
            SymbolKind.FUNCTION,
        ),
    ),
    "bash": (
        (re.compile(r"^\s*function\s+([\w.:-]+)"), SymbolKind.FUNCTION),
        (re.compile(r"^\s*([\w.:-]+)\s*\(\)\s*\{?"), SymbolKind.FUNCTION),
    ),
}


def _match_line_patterns(language: str, line: str, idx: int) -> PolyglotSymbol | None:
    for pattern, kind in _LINE_PATTERNS[language]:
        match = pattern.match(line)
        if match and match.group(1) not in _CONTROL_WORDS:
            return _declared(match.group(1), kind, line, idx, language)
    return None


def _parse_line_symbols(code: str, language: str) -> list[PolyglotSymbol]:
    symbols: list[PolyglotSymbol] = []
    for idx, line in enumerate(code.splitlines(), 1):
        sym = _match_line_patterns(language, line, idx)
        if sym:
            symbols.append(sym)
    return symbols


# ---------------------------------------------------------------------------
# Markdown Heading Parsing
# ---------------------------------------------------------------------------

RE_MD_HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$")


def _front_matter_end(lines: list[str]) -> int:
    """The index of the first line after YAML front matter, or 0 without any."""
    if not lines or lines[0].strip() != "---":
        return 0
    for idx, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return idx + 1
    return 0


def _parse_markdown_symbols(code: str) -> list[PolyglotSymbol]:
    """ATX headings, skipping front matter and fenced code, where `#` starts comments."""
    lines = code.splitlines()
    start = _front_matter_end(lines)
    symbols: list[PolyglotSymbol] = []
    fence = ""
    for idx, line in enumerate(lines[start:], start + 1):
        marker = line.lstrip()[:3]
        if marker in ("```", "~~~"):
            fence = "" if fence == marker else fence or marker
            continue
        match = None if fence else RE_MD_HEADING.match(line)
        if match:
            symbols.append(_declared(match.group(1), SymbolKind.HEADING, line, idx, "markdown"))
    return symbols


# ---------------------------------------------------------------------------
# Fallback Dispatcher
# ---------------------------------------------------------------------------

_PARSERS: dict[str, Any] = {
    "python": _parse_python_symbols,
    "typescript": lambda c: _parse_typescript_symbols(c, "typescript"),
    "tsx": lambda c: _parse_typescript_symbols(c, "tsx"),
    "javascript": lambda c: _parse_typescript_symbols(c, "javascript"),
    "go": _parse_go_symbols,
    "rust": _parse_rust_symbols,
    "java": _parse_java_symbols,
    "hcl": _parse_hcl_symbols,
    "csharp": lambda c: _parse_line_symbols(c, "csharp"),
    "c": lambda c: _parse_line_symbols(c, "c"),
    "cpp": lambda c: _parse_line_symbols(c, "cpp"),
    "bash": lambda c: _parse_line_symbols(c, "bash"),
    "markdown": _parse_markdown_symbols,
}


class FallbackASTParser:
    """Zero-dependency polyglot symbol extractor utilizing standard AST and pattern scans."""

    def parse(self, path: str, code: str, language: str) -> PolyglotFileMap:
        """Parse source code into PolyglotFileMap using appropriate language extractor."""
        parser_fn = _PARSERS.get(language)
        symbols = parser_fn(code) if parser_fn else []
        return PolyglotFileMap(
            path=path,
            language=language,
            line_count=len(code.splitlines()),
            symbols=symbols,
            parse_engine="fallback-ast",
        )
