"""Tree-Sitter Multilingual AST Engine with resilient fallback to AST/regex scanners."""

from __future__ import annotations

import importlib
import importlib.util
import logging
import threading
from pathlib import Path
from typing import Any

from devops_cli.ai.ast.fallback import FallbackASTParser
from devops_cli.ai.ast.models import CodeSpan, PolyglotFileMap, PolyglotSymbol, SymbolKind

logger = logging.getLogger(__name__)

EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".tf": "hcl",
    ".hcl": "hcl",
}

LANG_TO_GRAMMAR_PKG: dict[str, str] = {
    "python": "tree_sitter_python",
    "typescript": "tree_sitter_typescript",
    "javascript": "tree_sitter_javascript",
    "go": "tree_sitter_go",
    "rust": "tree_sitter_rust",
    "java": "tree_sitter_java",
    "hcl": "tree_sitter_hcl",
}


def detect_language(path: Path | str) -> str | None:
    """Infer canonical programming language identifier from file extension."""
    suffix = Path(path).suffix.lower()
    return EXT_TO_LANG.get(suffix)


NATIVE_KIND_MAP: dict[str, SymbolKind] = {
    "function_definition": SymbolKind.FUNCTION,
    "function_declaration": SymbolKind.FUNCTION,
    "function_item": SymbolKind.FUNCTION,
    "class_definition": SymbolKind.CLASS,
    "class_declaration": SymbolKind.CLASS,
    "struct_item": SymbolKind.STRUCT,
    "trait_item": SymbolKind.INTERFACE,
    "interface_declaration": SymbolKind.INTERFACE,
    "method_definition": SymbolKind.METHOD,
    "method_declaration": SymbolKind.METHOD,
}


def _matches_sexpr_filter(sym: PolyglotSymbol, query_sexpr: str) -> bool:
    """Filter polyglot symbols based on S-expression query intent."""
    q = query_sexpr.lower()
    targets: set[str] = set()
    if "function" in q or "func" in q:
        targets.update(["function", "method"])
    if "class" in q:
        targets.add("class")
    if "interface" in q:
        targets.add("interface")
    if "struct" in q:
        targets.add("struct")
    if "method" in q:
        targets.add("method")
    if "type" in q:
        targets.add("type")
    if "constant" in q or "const" in q:
        targets.add("constant")

    return sym.kind.value in targets if targets else True


def _extract_node_name(node: Any) -> str:
    name_node = getattr(node, "child_by_field_name", lambda _: None)("name")
    if name_node and hasattr(name_node, "text"):
        return str(name_node.text.decode("utf-8"))
    for ch in getattr(node, "children", []):
        if getattr(ch, "type", "") == "identifier" and hasattr(ch, "text"):
            return str(ch.text.decode("utf-8"))
    return ""


class TreeSitterEngine:
    """Multilingual syntax tree parser supporting Tree-Sitter grammars and AST fallback."""

    def __init__(self, max_file_size_bytes: int = 5 * 1024 * 1024) -> None:
        self.max_file_size_bytes = max_file_size_bytes
        self._fallback = FallbackASTParser()
        self._parsers: dict[str, Any] = {}
        self._languages: dict[str, Any] = {}
        self._file_cache: dict[Path, tuple[float, PolyglotFileMap]] = {}
        self._lock = threading.Lock()
        self._has_native_ts: bool | None = None

    def _check_native_tree_sitter(self) -> bool:
        if self._has_native_ts is None:
            self._has_native_ts = importlib.util.find_spec("tree_sitter") is not None
        return self._has_native_ts

    def is_language_supported(self, lang_or_ext: str) -> bool:
        """Check if a language identifier or file extension is supported."""
        if lang_or_ext.startswith("."):
            return lang_or_ext.lower() in EXT_TO_LANG
        return (
            lang_or_ext.lower() in LANG_TO_GRAMMAR_PKG
            or lang_or_ext.lower() in EXT_TO_LANG.values()
        )

    def _resolve_lang(self, lang_or_ext: str) -> str:
        if lang_or_ext.startswith("."):
            return EXT_TO_LANG.get(lang_or_ext.lower(), "python")
        return lang_or_ext.lower()

    def _load_native_parser(self, lang: str) -> tuple[Any, Any] | None:
        if not self._check_native_tree_sitter():
            return None
        with self._lock:
            if lang in self._parsers:
                return self._parsers[lang], self._languages[lang]
            pkg_name = LANG_TO_GRAMMAR_PKG.get(lang)
            if not pkg_name or not importlib.util.find_spec(pkg_name):
                return None
            try:
                ts_mod = importlib.import_module("tree_sitter")
                grammar_mod = importlib.import_module(pkg_name)
                ts_lang = ts_mod.Language(grammar_mod.language())
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
            node_type = getattr(curr, "type", "")
            next_scope = scope
            if node_type in NATIVE_KIND_MAP:
                name = _extract_node_name(curr)
                if name:
                    start_pt = getattr(curr, "start_point", (0, 0))
                    end_pt = getattr(curr, "end_point", (0, 0))
                    sig = lines[start_pt[0]].strip() if start_pt[0] < len(lines) else ""
                    kind = NATIVE_KIND_MAP[node_type]
                    symbols.append(
                        PolyglotSymbol(
                            name=name,
                            kind=kind,
                            span=CodeSpan(line_start=start_pt[0] + 1, line_end=end_pt[0] + 1),
                            signature=sig,
                            language=lang,
                            parent_scope=scope,
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
        """Parse source code string into PolyglotFileMap."""
        lang = self._resolve_lang(language_or_ext)
        pair = self._load_native_parser(lang)
        if pair is not None:
            parser, _ = pair
            try:
                tree = parser.parse(bytes(code, "utf-8"))
                symbols = self._extract_native_symbols(tree, code, lang)
                if symbols:
                    return PolyglotFileMap(
                        path=path,
                        language=lang,
                        symbols=symbols,
                        line_count=len(code.splitlines()) if code else 0,
                        parse_engine="tree-sitter",
                    )
            except Exception as exc:
                logger.debug("Native parse failed for %s, falling back: %s", lang, exc)
        return self._fallback.parse(path, code, lang)

    def parse_file(self, file_path: Path) -> PolyglotFileMap | None:
        """Parse source file with mtime-indexed in-memory caching."""
        lang = detect_language(file_path)
        if not lang:
            return None

        try:
            stat = file_path.stat()
            if stat.st_size > self.max_file_size_bytes:
                return None
            mtime = stat.st_mtime
        except OSError:
            return None

        with self._lock:
            cached = self._file_cache.get(file_path)
            if cached and cached[0] == mtime:
                return cached[1]

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

        file_map = self.parse_code(content, lang, path=str(file_path))

        with self._lock:
            self._file_cache[file_path] = (mtime, file_map)
        return file_map

    def query_code(
        self,
        code: str,
        language_or_ext: str,
        query_sexpr: str,
    ) -> list[dict[str, Any]]:
        """Execute S-expression or structural query across code symbols."""
        lang = self._resolve_lang(language_or_ext)
        pair = self._load_native_parser(lang)
        if pair is not None:
            _, ts_lang = pair
            try:
                query = ts_lang.query(query_sexpr)
                # Parse raw CST for captures
                parser, _ = pair
                cst = parser.parse(bytes(code, "utf-8"))
                captures = query.captures(cst.root_node)
                matches: list[dict[str, Any]] = []
                for node, capture_name in captures:
                    text = node.text.decode("utf-8") if hasattr(node, "text") else str(node)
                    line = node.start_point[0] + 1 if hasattr(node, "start_point") else 1
                    matches.append(
                        {
                            "symbol": text,
                            "kind": capture_name,
                            "line": line,
                            "signature": text,
                            "query": query_sexpr,
                        }
                    )
                return matches
            except Exception as exc:
                logger.debug("Native query failed for %s, falling back: %s", lang, exc)

        file_map = self.parse_code(code, lang)
        matches = []
        for sym in file_map.symbols:
            if _matches_sexpr_filter(sym, query_sexpr):
                matches.append(
                    {
                        "symbol": sym.name,
                        "kind": sym.kind.value,
                        "line": sym.span.line_start,
                        "signature": sym.signature,
                        "query": query_sexpr,
                    }
                )
        return matches
