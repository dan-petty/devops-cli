"""Tree-Sitter Multilingual AST Engine: the symbols and queries of source files."""

from __future__ import annotations

import importlib
import logging
import re
import threading
from pathlib import Path
from typing import Any

from devops_cli.ai.ast.models import CodeSpan, PolyglotFileMap, PolyglotSymbol, SymbolKind
from devops_cli.config.defaults import DEFAULT_MAX_AST_FILE_SIZE_BYTES

logger = logging.getLogger(__name__)

EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".tf": "hcl",
    ".hcl": "hcl",
    ".cs": "csharp",
    # A .h header is C unless its content is C++ (see _header_language).
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".c++": "cpp",
    ".hh": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".sh": "bash",
    ".bash": "bash",
    # Scripts the official nginx image's entrypoint sources.
    ".envsh": "bash",
    ".md": "markdown",
    ".markdown": "markdown",
}

# Each language's grammar package and the function returning its language. The TypeScript
# package holds two grammars, one without JSX and one with it.
LANG_TO_GRAMMAR: dict[str, tuple[str, str]] = {
    "python": ("tree_sitter_python", "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "tsx": ("tree_sitter_typescript", "language_tsx"),
    "javascript": ("tree_sitter_javascript", "language"),
    "go": ("tree_sitter_go", "language"),
    "rust": ("tree_sitter_rust", "language"),
    "java": ("tree_sitter_java", "language"),
    "hcl": ("tree_sitter_hcl", "language"),
    "csharp": ("tree_sitter_c_sharp", "language"),
    "c": ("tree_sitter_c", "language"),
    "cpp": ("tree_sitter_cpp", "language"),
    "bash": ("tree_sitter_bash", "language"),
    # The block grammar: headings and sections, without inline markup.
    "markdown": ("tree_sitter_markdown", "language"),
}

# Other names for a language, as the analysis scanner and users write them.
LANG_ALIASES: dict[str, str] = {
    "shell": "bash",
    "sh": "bash",
    "c#": "csharp",
    "cs": "csharp",
    "c++": "cpp",
    "md": "markdown",
}

# C++ in a .h header: a namespace, a template, a class with a body, or a scope operator, none of
# which C has.
_CPP_HEADER = re.compile(
    r"^\s*(?:namespace\s+\w|template\s*<|class\s+\w+[^;(]*\{)|\w::\w", re.MULTILINE
)


def _header_language(code: str) -> str:
    """The language of a .h header: C++ when its content uses C++, otherwise C."""
    return "cpp" if _CPP_HEADER.search(code) else "c"


def detect_language(path: Path | str, content: str | None = None) -> str | None:
    """The file's language from its extension, or None for an unknown one. Given the content, a
    .h header is C++ when that content uses C++ (see _header_language), otherwise C."""
    suffix = Path(path).suffix.lower()
    if suffix == ".h" and content is not None:
        return _header_language(content)
    return EXT_TO_LANG.get(suffix)


def _read_source(file_path: Path) -> tuple[str, str] | None:
    """The file's text and language, a header's read from its content, or None when the file
    cannot be read or its language is unknown."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lang = detect_language(file_path, content)
    return None if lang is None else (content, lang)


NATIVE_KIND_MAP: dict[str, SymbolKind] = {
    "function_declaration": SymbolKind.FUNCTION,
    "function_item": SymbolKind.FUNCTION,
    "class_definition": SymbolKind.CLASS,
    "class_declaration": SymbolKind.CLASS,
    "struct_item": SymbolKind.STRUCT,
    "trait_item": SymbolKind.INTERFACE,
    "interface_declaration": SymbolKind.INTERFACE,
    "method_definition": SymbolKind.METHOD,
    "method_declaration": SymbolKind.METHOD,
    "abstract_class_declaration": SymbolKind.CLASS,
    "generator_function_declaration": SymbolKind.FUNCTION,
    "type_alias_declaration": SymbolKind.TYPE,
    "enum_declaration": SymbolKind.TYPE,
    "record_declaration": SymbolKind.CLASS,
    "constructor_declaration": SymbolKind.METHOD,
    "enum_item": SymbolKind.TYPE,
    "type_item": SymbolKind.TYPE,
    "union_item": SymbolKind.STRUCT,
    "mod_item": SymbolKind.MODULE,
    "const_item": SymbolKind.CONSTANT,
    "static_item": SymbolKind.CONSTANT,
    "macro_definition": SymbolKind.FUNCTION,
    "annotation_type_declaration": SymbolKind.INTERFACE,
    "annotation_type_element_declaration": SymbolKind.METHOD,
    # C#
    "struct_declaration": SymbolKind.STRUCT,
    "namespace_declaration": SymbolKind.MODULE,
    "file_scoped_namespace_declaration": SymbolKind.MODULE,
    "delegate_declaration": SymbolKind.TYPE,
    # C and C++
    "namespace_definition": SymbolKind.MODULE,
    "alias_declaration": SymbolKind.TYPE,
    "preproc_function_def": SymbolKind.FUNCTION,
}
# A declarator holding a function, as `const handle = () => {}` declares one.
_FUNCTION_VALUES = frozenset({"arrow_function", "function_expression", "function"})
# Top-level HCL blocks, named by their type and labels: resource "aws_vpc" "this".
_HCL_BLOCK_KINDS: dict[str, SymbolKind] = {
    "resource": SymbolKind.STRUCT,
    "data": SymbolKind.STRUCT,
    "variable": SymbolKind.CONSTANT,
    "output": SymbolKind.CONSTANT,
    "locals": SymbolKind.CONSTANT,
    "module": SymbolKind.MODULE,
}


def _text(node: Any) -> str:
    return str(node.text.decode("utf-8")) if node is not None and hasattr(node, "text") else ""


def _declared_function(node: Any) -> tuple[SymbolKind, str] | None:
    value = node.child_by_field_name("value")
    if value is None or value.type not in _FUNCTION_VALUES:
        return None
    name = _text(node.child_by_field_name("name"))
    return (SymbolKind.FUNCTION, name) if name else None


def _go_type_spec(node: Any) -> tuple[SymbolKind, str] | None:
    body = node.child_by_field_name("type")
    kind = {"struct_type": SymbolKind.STRUCT, "interface_type": SymbolKind.INTERFACE}.get(
        getattr(body, "type", ""), SymbolKind.TYPE
    )
    name = _text(node.child_by_field_name("name"))
    return (kind, name) if name else None


# What wraps the type a Go receiver names: `*List[T]` and `(*List[T])` name List.
_GO_RECEIVER_WRAPPERS = frozenset({"pointer_type", "generic_type", "parenthesized_type"})


def _go_receiver_type(node: Any) -> str | None:
    """The type a Go method's receiver names, which owns the method:
    `func (w *WorkerPool) Start()` is WorkerPool's. None for a node with no receiver."""
    receiver = node.child_by_field_name("receiver")
    params = [
        c for c in getattr(receiver, "named_children", []) if c.type == "parameter_declaration"
    ]
    type_node = params[0].child_by_field_name("type") if params else None
    while type_node is not None and type_node.type in _GO_RECEIVER_WRAPPERS:
        type_node = type_node.named_children[0] if type_node.named_children else None
    return _text(type_node) or None


def _hcl_block(node: Any) -> tuple[SymbolKind, str] | None:
    parent = node.parent
    if (
        parent is None
        or parent.type != "body"
        or getattr(parent.parent, "type", "") != "config_file"
    ):
        return None
    parts = [c for c in node.children if c.type in ("identifier", "string_lit")]
    if not parts or parts[0].type != "identifier":
        return None
    block_type = _text(parts[0])
    labels = " ".join(f'"{_text(c).strip(chr(34))}"' for c in parts[1:])
    return _HCL_BLOCK_KINDS.get(block_type, SymbolKind.MODULE), f"{block_type} {labels}".strip()


# Where a C or C++ declarator chain ends in the declared name.
_C_NAMES = frozenset(
    {
        "identifier",
        "field_identifier",
        "type_identifier",
        "qualified_identifier",
        "operator_name",
        "destructor_name",
    }
)


def _c_declarator_name(declarator: Any) -> str:
    """The name at the end of a C declarator chain: `*name`, `name(args)`, `Class::name`."""
    node = declarator
    while node is not None and node.type not in _C_NAMES:
        node = node.child_by_field_name("declarator")
    return _text(node)


def _declares_function(declarator: Any) -> bool:
    node = declarator
    while node is not None:
        if node.type == "function_declarator":
            return True
        node = node.child_by_field_name("declarator")
    return False


def _function_definition(node: Any) -> tuple[SymbolKind, str] | None:
    """A function: named by its `name` (Python, shell) or its declarator (C, C++)."""
    declarator = node.child_by_field_name("declarator")
    if declarator is None:
        name = _extract_node_name(node)
        return (SymbolKind.FUNCTION, name) if name else None
    name = _c_declarator_name(declarator)
    if not name:
        return None
    in_class = getattr(node.parent, "type", "") == "field_declaration_list"
    return (SymbolKind.METHOD if in_class or "::" in name else SymbolKind.FUNCTION), name


# What may enclose a file-scope declaration: include guards and other conditionals, `extern "C"`
# blocks, namespaces and templates.
_FILE_SCOPE_WRAPPERS = frozenset(
    {
        "preproc_ifdef",
        "preproc_if",
        "preproc_else",
        "preproc_elif",
        "preproc_elifdef",
        "linkage_specification",
        "declaration_list",
        "namespace_definition",
        "template_declaration",
    }
)


def _at_file_scope(node: Any) -> bool:
    parent = node.parent
    while parent is not None and parent.type in _FILE_SCOPE_WRAPPERS:
        parent = parent.parent
    return getattr(parent, "type", "") == "translation_unit"


def _c_prototype(node: Any) -> tuple[SymbolKind, str] | None:
    """A function declared at file scope, as a header declares its API."""
    if not _at_file_scope(node):
        return None
    declarator = node.child_by_field_name("declarator")
    if declarator is None or not _declares_function(declarator):
        return None
    name = _c_declarator_name(declarator)
    return (SymbolKind.FUNCTION, name) if name else None


def _c_typedef(node: Any) -> tuple[SymbolKind, str] | None:
    name = _c_declarator_name(node.child_by_field_name("declarator"))
    return (SymbolKind.TYPE, name) if name else None


def _c_type_with_body(kind: SymbolKind) -> Any:
    """A struct, class, union or enum that is defined here, not merely named."""

    def extract(node: Any) -> tuple[SymbolKind, str] | None:
        if node.child_by_field_name("body") is None:
            return None
        name = _text(node.child_by_field_name("name"))
        return (kind, name) if name else None

    return extract


# An ATX heading's optional closing sequence: `## Install ##`.
_CLOSING_HASHES = re.compile(r"\s+#+$")


def _markdown_heading(node: Any) -> tuple[SymbolKind, str] | None:
    text = " ".join(_text(node.child_by_field_name("heading_content")).split())
    name = _CLOSING_HASHES.sub("", text)
    return (SymbolKind.HEADING, name) if name else None


_SPECIAL_NODES: dict[str, Any] = {
    "variable_declarator": _declared_function,
    "type_spec": _go_type_spec,
    "block": _hcl_block,
    "function_definition": _function_definition,
    "declaration": _c_prototype,
    "type_definition": _c_typedef,
    "struct_specifier": _c_type_with_body(SymbolKind.STRUCT),
    "union_specifier": _c_type_with_body(SymbolKind.STRUCT),
    "class_specifier": _c_type_with_body(SymbolKind.CLASS),
    "enum_specifier": _c_type_with_body(SymbolKind.TYPE),
    "atx_heading": _markdown_heading,
    "setext_heading": _markdown_heading,
}


def _native_symbol(node: Any) -> tuple[SymbolKind, str] | None:
    """The kind and name a syntax node declares, or None when it declares no symbol."""
    node_type = getattr(node, "type", "")
    special = _SPECIAL_NODES.get(node_type)
    if special:
        result: tuple[SymbolKind, str] | None = special(node)
        return result
    if node_type in NATIVE_KIND_MAP:
        name = _extract_node_name(node)
        return (NATIVE_KIND_MAP[node_type], name) if name else None
    return None


def _extract_node_name(node: Any) -> str:
    name_node = getattr(node, "child_by_field_name", lambda _: None)("name")
    if name_node and hasattr(name_node, "text"):
        return str(name_node.text.decode("utf-8"))
    for ch in getattr(node, "children", []):
        if getattr(ch, "type", "") == "identifier" and hasattr(ch, "text"):
            return str(ch.text.decode("utf-8"))
    return ""


class TreeSitterEngine:
    """Multilingual syntax tree parser over the Tree-Sitter grammars the project pins."""

    def __init__(self, max_file_size_bytes: int = DEFAULT_MAX_AST_FILE_SIZE_BYTES) -> None:
        self.max_file_size_bytes = max_file_size_bytes
        self._parsers: dict[str, Any] = {}
        self._languages: dict[str, Any] = {}
        self._file_cache: dict[Path, tuple[float, PolyglotFileMap]] = {}
        self._lock = threading.Lock()

    def is_language_supported(self, lang_or_ext: str) -> bool:
        """Check if a language identifier or file extension is supported."""
        if lang_or_ext.startswith("."):
            return lang_or_ext.lower() in EXT_TO_LANG
        lang = LANG_ALIASES.get(lang_or_ext.lower(), lang_or_ext.lower())
        return lang in LANG_TO_GRAMMAR or lang in EXT_TO_LANG.values()

    def _resolve_lang(self, lang_or_ext: str) -> str:
        if lang_or_ext.startswith("."):
            return EXT_TO_LANG.get(lang_or_ext.lower(), "python")
        return LANG_ALIASES.get(lang_or_ext.lower(), lang_or_ext.lower())

    def _load_native_parser(self, lang: str) -> tuple[Any, Any] | None:
        with self._lock:
            if lang in self._parsers:
                return self._parsers[lang], self._languages[lang]
            pkg_name, entry = LANG_TO_GRAMMAR.get(lang, ("", ""))
            if not pkg_name:
                return None
            try:
                ts_mod = importlib.import_module("tree_sitter")
                grammar_mod = importlib.import_module(pkg_name)
                ts_lang = ts_mod.Language(getattr(grammar_mod, entry)())
                parser = ts_mod.Parser(ts_lang)
                self._parsers[lang] = parser
                self._languages[lang] = ts_lang
                return parser, ts_lang
            except Exception as exc:
                logger.debug("Native tree-sitter load error for %s: %s", lang, exc)
                return None

    def _extract_native_symbols(self, tree: Any, code: str, lang: str) -> list[PolyglotSymbol]:
        """Extract polyglot symbols from a native Tree-Sitter tree."""
        symbols: list[PolyglotSymbol] = []
        lines = code.splitlines()

        stack: list[tuple[Any, str | None]] = [(tree.root_node, None)]
        while stack:
            curr, scope = stack.pop()
            next_scope = scope
            declared = _native_symbol(curr)
            if declared:
                kind, name = declared
                if name:
                    start_pt = getattr(curr, "start_point", (0, 0))
                    end_pt = getattr(curr, "end_point", (0, 0))
                    # Signed with the line holding its name, so an annotation, attribute or
                    # decorator above it (`@Override`, `[HttpGet]`) is not taken for it.
                    name_node = curr.child_by_field_name("name")
                    sig_row = name_node.start_point[0] if name_node is not None else start_pt[0]
                    sig = lines[sig_row].strip() if sig_row < len(lines) else ""
                    symbols.append(
                        PolyglotSymbol(
                            name=name,
                            kind=kind,
                            span=CodeSpan(line_start=start_pt[0] + 1, line_end=end_pt[0] + 1),
                            signature=sig,
                            language=lang,
                            parent_scope=_go_receiver_type(curr) or scope,
                        )
                    )
                    if kind in (SymbolKind.CLASS, SymbolKind.INTERFACE, SymbolKind.STRUCT):
                        next_scope = name

            for child in reversed(getattr(curr, "children", [])):
                stack.append((child, next_scope))

        return symbols

    def parse_code(
        self,
        code: str,
        language_or_ext: str,
        path: str = "snippet",
    ) -> PolyglotFileMap:
        """Parse source code string into PolyglotFileMap.

        A language without a grammar, or a grammar that fails to load or parse, has no symbols.
        """
        lang = self._resolve_lang(language_or_ext)
        return PolyglotFileMap(
            path=path,
            language=lang,
            symbols=self._parse_native_symbols(code, lang),
            line_count=len(code.splitlines()),
        )

    def _parse_native_symbols(self, code: str, lang: str) -> list[PolyglotSymbol]:
        """The symbols tree-sitter finds in the code, none without a grammar for the language."""
        pair = self._load_native_parser(lang)
        if pair is None:
            return []
        parser, _ = pair
        try:
            tree = parser.parse(bytes(code, "utf-8"))
        except Exception as exc:
            logger.debug("Native parse failed for %s: %s", lang, exc)
            return []
        return self._extract_native_symbols(tree, code, lang)

    def _mtime_within_cap(self, file_path: Path) -> float | None:
        """The file's mtime, or None when it cannot be stat'ed or exceeds the size cap.

        Checked before the file is read, so an oversized file never reaches memory or a parser.
        """
        try:
            stat = file_path.stat()
        except OSError:
            return None
        return None if stat.st_size > self.max_file_size_bytes else stat.st_mtime

    def parse_file(self, file_path: Path) -> PolyglotFileMap | None:
        """Parse source file with mtime-indexed in-memory caching."""
        mtime = self._mtime_within_cap(file_path) if detect_language(file_path) else None
        if mtime is None:
            return None

        with self._lock:
            cached = self._file_cache.get(file_path)
            if cached and cached[0] == mtime:
                return cached[1]

        source = _read_source(file_path)
        if source is None:
            return None
        file_map = self.parse_code(source[0], source[1], path=str(file_path))

        with self._lock:
            self._file_cache[file_path] = (mtime, file_map)
        return file_map

    def query_file(self, file_path: Path, query_sexpr: str) -> list[dict[str, Any]] | None:
        """Query a source file, or None when its language is unknown, it cannot be read, or it
        exceeds the size cap, which parse_file shares."""
        if detect_language(file_path) is None or self._mtime_within_cap(file_path) is None:
            return None
        source = _read_source(file_path)
        return None if source is None else self.query_code(source[0], source[1], query_sexpr)

    def query_code(
        self,
        code: str,
        language_or_ext: str,
        query_sexpr: str,
    ) -> list[dict[str, Any]]:
        """The nodes a tree-sitter S-expression query captures, in source order, each named by
        its capture. A language without a grammar has none; a query the grammar cannot compile
        raises tree_sitter.QueryError."""
        from tree_sitter import Query, QueryCursor

        pair = self._load_native_parser(self._resolve_lang(language_or_ext))
        if pair is None:
            return []
        parser, ts_lang = pair
        root = parser.parse(bytes(code, "utf-8")).root_node
        captures = QueryCursor(Query(ts_lang, query_sexpr)).captures(root)
        captured = sorted(
            ((name, node) for name, nodes in captures.items() for node in nodes),
            key=lambda capture: capture[1].start_byte,
        )
        return [
            {
                "symbol": _text(node),
                "kind": name,
                "line": node.start_point[0] + 1,
                "signature": _text(node),
                "query": query_sexpr,
            }
            for name, node in captured
        ]
