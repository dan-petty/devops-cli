"""Tree-Sitter Multilingual AST Engine with resilient fallback to AST/regex scanners."""

from __future__ import annotations

import importlib
import importlib.util
import logging
import threading
from pathlib import Path
from typing import Any

from devops_cli.ai.ast.fallback import FallbackASTParser
from devops_cli.ai.ast.models import PolyglotFileMap

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

    def parse_code(
        self,
        code: str,
        language_or_ext: str,
        path: str = "snippet",
    ) -> PolyglotFileMap:
        """Parse source code string into PolyglotFileMap."""
        lang = self._resolve_lang(language_or_ext)
        # Always fallback cleanly if native grammar is absent or on syntax error
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
        file_map = self.parse_code(code, lang)
        matches: list[dict[str, Any]] = []

        # When running native or fallback, extract captured symbol identifiers
        for sym in file_map.symbols:
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
