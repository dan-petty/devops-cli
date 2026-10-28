"""Polyglot semantic chunking algorithms for source code, manifests, and technical docs."""

from __future__ import annotations

import ast
import hashlib
import logging
import mimetypes
import uuid
import warnings
from pathlib import Path

from devops_cli.ai.analyze.scanner import detect_language
from devops_cli.ai.ast.engine import TreeSitterEngine
from devops_cli.ai.context_budget import get_tiktoken_encoding
from devops_cli.ai.rag.metadata import extract_code_metadata, extract_doc_metadata
from devops_cli.ai.rag.models import CodeChunk
from devops_cli.config.constants import (
    CONST_CHUNK_MODULE_PREAMBLE_SYMBOL,
    CONST_RAG_MAX_CHUNK_TOKENS,
)

logger = logging.getLogger(__name__)

MAX_CHUNK_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MiB safety cap


def count_chunk_tokens(text: str, model: str | None = None) -> int:
    """Count tokens for chunk boundary enforcement.

    Uses tiktoken matching the configured embedding model when available.
    Falls back to cl100k_base or a documented safe bound (1 token per character)
    for dense punctuation and worst-case sequences.
    """
    if not text:
        return 0
    clean_model = model.split(":", 1)[1] if model and ":" in model else (model or "cl100k_base")
    enc = get_tiktoken_encoding(clean_model)
    if enc is not None:
        try:
            return len(enc.encode(text, disallowed_special=()))
        except (ValueError, TypeError, KeyError) as exc:
            logger.debug("Failed to count tokens with %s: %s", clean_model, exc)
    return len(text)


def parse_markdown_headings(content: str) -> list[tuple[int, int, str]]:
    """Extract heading line numbers (0-indexed), levels (1-6), and titles using CommonMark parser.

    Headings inside fenced code blocks are excluded by the AST parser.
    """
    from markdown_it import MarkdownIt

    md = MarkdownIt("commonmark")
    tokens = md.parse(content)
    headings: list[tuple[int, int, str]] = []

    for idx, token in enumerate(tokens):
        if token.type == "heading_open" and token.map:
            level = int(token.tag[1:]) if len(token.tag) > 1 and token.tag[1:].isdigit() else 1
            inline = (
                tokens[idx + 1]
                if idx + 1 < len(tokens) and tokens[idx + 1].type == "inline"
                else None
            )
            title = inline.content.strip() if inline else ""
            headings.append((token.map[0], level, title))

    return headings


def _append_sub_window(
    sub_windows: list[tuple[int, int, str]],
    start_line: int,
    end_line: int,
    content: str,
    max_tokens: int,
    model: str | None = None,
) -> None:
    """Append bounded sub-window(s) to sub_windows list capped at max_tokens."""
    if not content:
        return
    if count_chunk_tokens(content, model=model) <= max_tokens:
        sub_windows.append((start_line, end_line, content))
        return

    clean_model = model.split(":", 1)[1] if model and ":" in model else (model or "cl100k_base")
    enc = get_tiktoken_encoding(clean_model)
    if enc is not None:
        try:
            tokens = enc.encode(content, disallowed_special=())
            for i in range(0, len(tokens), max_tokens):
                piece = enc.decode(tokens[i : i + max_tokens])
                if piece:
                    sub_windows.append((start_line, end_line, piece))
            return
        except (ValueError, TypeError, KeyError) as exc:
            logger.debug("Failed to decode token chunks with %s: %s", clean_model, exc)

    for i in range(0, len(content), max_tokens):
        sub_windows.append((start_line, end_line, content[i : i + max_tokens]))


def _split_window_by_token_limit(
    lines: list[str],
    window_start_line: int,
    max_tokens: int = CONST_RAG_MAX_CHUNK_TOKENS,
    model: str | None = None,
) -> list[tuple[int, int, str]]:
    """Split a window of lines into (start_line, end_line, content) tuples capped at max_tokens."""
    sub_windows: list[tuple[int, int, str]] = []
    current_lines: list[str] = []
    current_start = window_start_line

    for offset, line in enumerate(lines):
        cand_lines = current_lines + [line]
        cand_content = "\n".join(cand_lines).strip()
        if current_lines and count_chunk_tokens(cand_content, model=model) > max_tokens:
            content = "\n".join(current_lines).strip()
            end_line = current_start + len(current_lines) - 1
            _append_sub_window(
                sub_windows, current_start, end_line, content, max_tokens, model=model
            )
            current_start = window_start_line + offset
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        content = "\n".join(current_lines).strip()
        end_line = current_start + len(current_lines) - 1
        _append_sub_window(sub_windows, current_start, end_line, content, max_tokens, model=model)

    return sub_windows


def _resolve_file_category(suffix: str, rel_path: str, language: str = "") -> str:
    """Categorize file into docs, iac, config, or code based on language, mimetypes, and path."""
    rel_lower = rel_path.lower()
    if not language:
        language = detect_language(rel_path)

    if language in ("hcl", "terraform") or any(
        k in rel_lower for k in ("k8s", "terraform", "helm")
    ):
        return "iac"
    if language in ("yaml", "json", "toml", "ini", "xml"):
        return "config"
    mime, _ = mimetypes.guess_type(rel_path)
    if mime and any(c in mime for c in ("json", "yaml", "xml", "toml", "config")):
        return "config"
    if language in ("markdown", "rst", "asciidoc", "org") or "doc" in rel_lower:
        return "docs"
    if mime and any(d in mime for d in ("markdown", "rst", "asciidoc", "msword", "pdf")):
        return "docs"
    if mime == "text/plain" and language in ("text", "plain", "unknown", ""):
        return "docs"
    return "code"


def _extract_yaml_metadata_name(metadata_node: object) -> str | None:
    """Extract name attribute from a YAML metadata MappingNode."""
    import yaml

    if not isinstance(metadata_node, yaml.MappingNode):
        return None
    for mk, mv in metadata_node.value:
        if getattr(mk, "value", None) == "name" and isinstance(getattr(mv, "value", None), str):
            return str(mv.value)
    return None


def _extract_yaml_symbols(doc: object) -> list[str]:
    """Extract top-level kind and metadata.name symbols from a YAML MappingNode."""
    import yaml

    if not isinstance(doc, yaml.MappingNode):
        return []
    kind_val: str | None = None
    name_val: str | None = None
    for k_node, v_node in doc.value:
        k_val = getattr(k_node, "value", None)
        v_val = getattr(v_node, "value", None)
        if k_val == "kind" and isinstance(v_val, str):
            kind_val = str(v_val)
        elif k_val == "metadata":
            name_val = _extract_yaml_metadata_name(v_node)
    symbols: list[str] = []
    if kind_val:
        symbols.append(kind_val)
    if name_val:
        symbols.append(name_val)
    return symbols


class SemanticChunker:
    """Chunks source code and documentation files into semantic search units."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        embedding_model: str | None = None,
        max_tokens: int = CONST_RAG_MAX_CHUNK_TOKENS,
    ) -> None:
        """A size or overlap that is not given is `ai.rag.chunk_size` or `ai.rag.chunk_overlap` of
        the loaded settings, so every chunker splits files as the configuration says (#2447)."""
        if chunk_size is None or chunk_overlap is None:
            from devops_cli.config.settings import load_settings

            rag = load_settings().ai.rag
            chunk_size = rag.chunk_size if chunk_size is None else chunk_size
            chunk_overlap = rag.chunk_overlap if chunk_overlap is None else chunk_overlap
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_model = embedding_model
        self.max_tokens = max_tokens
        self._ts_engine = TreeSitterEngine()

    def _dispatch_language_chunker(
        self,
        suffix: str,
        content: str,
        rel_path: str,
        language: str,
        category: str,
        project_name: str,
    ) -> list[CodeChunk]:
        """Dispatch file content to language-specific structural chunker."""
        if language == "python":
            return self._chunk_python(content, rel_path, project_name=project_name)
        if language == "yaml":
            return self._chunk_yaml(content, rel_path, project_name=project_name)
        if category == "docs" or language in ("markdown", "rst", "asciidoc", "org"):
            return self._chunk_tech_docs(
                content, rel_path, language=language, project_name=project_name
            )
        if self._ts_engine.is_language_supported(language) or self._ts_engine.is_language_supported(
            suffix
        ):
            return self._chunk_tree_sitter_symbols(
                content,
                rel_path,
                language=language,
                category=category,
                project_name=project_name,
            )
        return self._chunk_line_window(
            content,
            rel_path,
            language=language,
            category=category,
            project_name=project_name,
        )

    def chunk_file(
        self,
        file_path: Path,
        relative_to: Path | None = None,
        project_name: str = "default",
    ) -> list[CodeChunk]:
        if relative_to is not None:
            try:
                resolved_rel = relative_to.resolve()
                resolved_fpath = file_path.resolve()
                if file_path.is_symlink() or not resolved_fpath.is_relative_to(resolved_rel):
                    return []
            except OSError, RuntimeError:
                return []

        try:
            if (
                file_path.is_symlink()
                or not file_path.is_file()
                or file_path.stat().st_size > MAX_CHUNK_FILE_SIZE_BYTES
            ):
                return []
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError) as exc:
            logger.debug("Failed to read %s for chunking: %s", file_path, exc)
            return []

        rel_path = str(file_path.relative_to(relative_to)) if relative_to else str(file_path)
        suffix = file_path.suffix.lower()
        language = detect_language(file_path, content)
        category = _resolve_file_category(suffix, rel_path, language=language)

        chunks = self._dispatch_language_chunker(
            suffix, content, rel_path, language, category, project_name
        )

        if not chunks and content.strip():
            chunks = self._chunk_line_window(
                content,
                rel_path,
                language=language,
                category=category,
                project_name=project_name,
            )

        bounded_chunks: list[CodeChunk] = []
        for chk in chunks:
            bounded_chunks.extend(self._split_large_chunk(chk))
        return bounded_chunks

    def _make_code_chunk(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        content: str,
        language: str = "python",
        category: str = "code",
        project_name: str = "default",
        symbols: list[str] | None = None,
    ) -> CodeChunk:
        """Construct a standardized CodeChunk with metadata and content hash."""
        sym_list = symbols or []
        doc_type = "code" if category != "docs" else "doc"
        if category == "iac" and language == "yaml":
            doc_type = "manifest"
        meta = extract_code_metadata(
            content, language=language, symbols=sym_list, file_path=file_path
        )
        return CodeChunk(
            id=self._generate_id(file_path, start_line, end_line, project_name=project_name),
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            content=content,
            language=language,
            doc_type=doc_type,
            category=category,
            project_name=project_name,
            symbol_names=sym_list,
            metadata=meta,
            content_hash=self._hash_content(content),
        )

    def _build_python_node_chunk(
        self, node: ast.AST, lines: list[str], file_path: str, project_name: str
    ) -> tuple[CodeChunk, range] | None:
        """Extract a single function or class AST node into a CodeChunk."""
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)
        chunk_content = "\n".join(lines[start_line - 1 : end_line])

        if isinstance(node, ast.ClassDef):
            symbols = [node.name] + [
                f"{node.name}.{sub.name}"
                for sub in node.body
                if isinstance(sub, ast.FunctionDef | ast.AsyncFunctionDef)
            ]
            chunk = self._make_code_chunk(
                file_path,
                start_line,
                end_line,
                chunk_content,
                language="python",
                category="code",
                project_name=project_name,
                symbols=symbols,
            )
            return chunk, range(start_line, end_line + 1)

        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            chunk = self._make_code_chunk(
                file_path,
                start_line,
                end_line,
                chunk_content,
                language="python",
                category="code",
                project_name=project_name,
                symbols=[node.name],
            )
            return chunk, range(start_line, end_line + 1)

        return None

    def _chunk_python(
        self, content: str, file_path: str, project_name: str = "default"
    ) -> list[CodeChunk]:
        """Extract top-level functions, classes, and module headers using AST."""
        chunks: list[CodeChunk] = []
        lines = content.splitlines()
        if not lines:
            return []

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                tree = ast.parse(content)
        except SyntaxError:
            return self._chunk_line_window(
                content, file_path, language="python", project_name=project_name
            )

        covered_lines: set[int] = set()

        for node in tree.body:
            res = self._build_python_node_chunk(node, lines, file_path, project_name)
            if res:
                chunk, line_range = res
                chunks.append(chunk)
                covered_lines.update(line_range)

        uncovered = [i + 1 for i in range(len(lines)) if (i + 1) not in covered_lines]
        if uncovered and uncovered[0] == 1 and len(uncovered) > 3:
            first_covered = min(covered_lines) if covered_lines else len(lines) + 1
            preamble_end = min(first_covered - 1, 60)
            if preamble_end >= 1:
                preamble_lines = lines[0:preamble_end]
                preamble_content = "\n".join(preamble_lines).strip()
                if preamble_content:
                    preamble_chunk = self._make_code_chunk(
                        file_path,
                        1,
                        preamble_end,
                        preamble_content,
                        language="python",
                        category="code",
                        project_name=project_name,
                        symbols=[CONST_CHUNK_MODULE_PREAMBLE_SYMBOL],
                    )
                    chunks.insert(0, preamble_chunk)

        return chunks

    def _chunk_tree_sitter_symbols(
        self,
        content: str,
        file_path: str,
        language: str,
        category: str,
        project_name: str = "default",
    ) -> list[CodeChunk]:
        """Extract code chunks based on TreeSitterEngine symbol spans."""
        file_map = self._ts_engine.parse_code(content, language, path=file_path)
        if not file_map.symbols:
            return self._chunk_line_window(
                content,
                file_path,
                language=language,
                category=category,
                project_name=project_name,
            )

        lines = content.splitlines()
        if not lines:
            return []

        chunks: list[CodeChunk] = []
        covered_lines: set[int] = set()

        for sym in file_map.symbols:
            start_line = sym.span.line_start
            end_line = min(len(lines), sym.span.line_end)
            if start_line > len(lines) or end_line < start_line:
                continue
            chunk_lines = lines[start_line - 1 : end_line]
            chunk_content = "\n".join(chunk_lines).strip()
            if not chunk_content:
                continue

            symbols = [sym.name]
            if sym.parent_scope:
                symbols.insert(0, f"{sym.parent_scope}.{sym.name}")

            chunks.append(
                self._make_code_chunk(
                    file_path,
                    start_line,
                    end_line,
                    chunk_content,
                    language=language,
                    category=category,
                    project_name=project_name,
                    symbols=symbols,
                )
            )
            covered_lines.update(range(start_line, end_line + 1))

        # Check preamble before first symbol
        uncovered = [i + 1 for i in range(len(lines)) if (i + 1) not in covered_lines]
        if uncovered and uncovered[0] == 1 and len(uncovered) > 3:
            first_covered = min(covered_lines) if covered_lines else len(lines) + 1
            preamble_end = min(first_covered - 1, 60)
            if preamble_end >= 1:
                preamble_lines = lines[0:preamble_end]
                preamble_content = "\n".join(preamble_lines).strip()
                if preamble_content:
                    preamble_chunk = self._make_code_chunk(
                        file_path,
                        1,
                        preamble_end,
                        preamble_content,
                        language=language,
                        category=category,
                        project_name=project_name,
                        symbols=[CONST_CHUNK_MODULE_PREAMBLE_SYMBOL],
                    )
                    chunks.insert(0, preamble_chunk)

        return chunks

    def _chunk_yaml(
        self, content: str, file_path: str, project_name: str = "default"
    ) -> list[CodeChunk]:
        """Split multi-document YAML manifests using PyYAML compose_all and SafeLoader."""
        import yaml

        lines = content.splitlines()
        if not lines:
            return []

        category = "iac" if any(k in file_path.lower() for k in ("k8s", "helm")) else "config"
        try:
            docs = list(yaml.compose_all(content, Loader=yaml.SafeLoader))
        except yaml.YAMLError:
            return self._chunk_line_window(
                content, file_path, language="yaml", category=category, project_name=project_name
            )

        chunks: list[CodeChunk] = []
        for doc in docs:
            if doc is None:
                continue
            start_line = doc.start_mark.line + 1
            end_line = max(start_line, doc.end_mark.line)
            doc_content = "\n".join(lines[start_line - 1 : end_line]).strip()
            if not doc_content:
                continue

            symbols = _extract_yaml_symbols(doc)
            chunks.append(
                self._make_code_chunk(
                    file_path,
                    start_line,
                    end_line,
                    doc_content,
                    language="yaml",
                    category=category,
                    project_name=project_name,
                    symbols=symbols,
                )
            )

        return chunks

    def _chunk_tech_docs(
        self,
        content: str,
        file_path: str,
        language: str = "markdown",
        project_name: str = "default",
    ) -> list[CodeChunk]:
        """Hierarchical technical documentation parser with breadcrumbs and title tracking."""
        chunks: list[CodeChunk] = []
        lines = content.splitlines()
        if not lines:
            return []

        if language != "markdown":
            return self._chunk_line_window(
                content,
                file_path,
                language=language,
                category="docs",
                project_name=project_name,
            )

        section_starts = parse_markdown_headings(content)
        if not section_starts:
            return self._chunk_line_window(
                content,
                file_path,
                language=language,
                category="docs",
                project_name=project_name,
            )

        section_indices = [s[0] for s in section_starts] + [len(lines)]
        breadcrumb_stack: list[tuple[int, str]] = []

        for i in range(len(section_starts)):
            start_idx = section_indices[i]
            end_idx = section_indices[i + 1]
            level, title = section_starts[i][1], section_starts[i][2]

            while breadcrumb_stack and breadcrumb_stack[-1][0] >= level:
                breadcrumb_stack.pop()
            breadcrumb_stack.append((level, title))
            section_path = [b[1] for b in breadcrumb_stack]

            sec_lines = lines[start_idx:end_idx]
            sec_content = "\n".join(sec_lines).strip()
            if not sec_content:
                continue

            c_id = self._generate_id(file_path, start_idx + 1, end_idx, project_name=project_name)
            chunks.append(
                CodeChunk(
                    id=c_id,
                    file_path=file_path,
                    start_line=start_idx + 1,
                    end_line=end_idx,
                    content=sec_content,
                    language=language,
                    doc_type="doc",
                    category="docs",
                    project_name=project_name,
                    section_path=section_path,
                    symbol_names=[title],
                    metadata=extract_doc_metadata(sec_content, section_path=section_path),
                    content_hash=self._hash_content(sec_content),
                )
            )

        return chunks

    def _create_window_chunk(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        content: str,
        language: str,
        category: str,
        project_name: str,
    ) -> CodeChunk:
        """Create a CodeChunk from a line-window or sub-window slice."""
        c_id = self._generate_id(file_path, start_line, end_line, project_name=project_name)
        meta = (
            extract_doc_metadata(content, file_path=file_path)
            if category == "docs"
            else extract_code_metadata(content, language=language, file_path=file_path)
        )
        return CodeChunk(
            id=c_id,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            content=content,
            language=language or "text",
            doc_type="doc" if category == "docs" else "code",
            category=category,
            project_name=project_name,
            symbol_names=[],
            metadata=meta,
            content_hash=self._hash_content(content),
        )

    def _split_large_chunk(self, chunk: CodeChunk) -> list[CodeChunk]:
        """Split a CodeChunk that exceeds the maximum token limit into sub-chunks."""
        if count_chunk_tokens(chunk.content, model=self.embedding_model) <= self.max_tokens:
            return [chunk]
        lines = chunk.content.splitlines()
        sub_windows = _split_window_by_token_limit(
            lines, chunk.start_line, self.max_tokens, model=self.embedding_model
        )
        return [
            CodeChunk(
                id=self._generate_id(chunk.file_path, s, e, project_name=chunk.project_name),
                file_path=chunk.file_path,
                start_line=s,
                end_line=e,
                content=cnt,
                language=chunk.language,
                doc_type=chunk.doc_type,
                category=chunk.category,
                project_name=chunk.project_name,
                symbol_names=chunk.symbol_names,
                metadata=chunk.metadata,
                content_hash=self._hash_content(cnt),
            )
            for s, e, cnt in sub_windows
        ]

    def _chunk_line_window(
        self,
        content: str,
        file_path: str,
        language: str = "text",
        category: str = "code",
        project_name: str = "default",
    ) -> list[CodeChunk]:
        """Sliding line-window chunker with overlap."""
        chunks: list[CodeChunk] = []
        lines = content.splitlines()
        if not lines:
            return []

        step = max(1, self.chunk_size - self.chunk_overlap)
        total_lines = len(lines)

        for start in range(0, total_lines, step):
            end = min(total_lines, start + self.chunk_size)
            chunk_lines = lines[start:end]
            chunk_content = "\n".join(chunk_lines).strip()
            if not chunk_content:
                continue

            if count_chunk_tokens(chunk_content, model=self.embedding_model) > self.max_tokens:
                for sub_start, sub_end, sub_content in _split_window_by_token_limit(
                    chunk_lines, start + 1, self.max_tokens, model=self.embedding_model
                ):
                    chunks.append(
                        self._create_window_chunk(
                            file_path,
                            sub_start,
                            sub_end,
                            sub_content,
                            language,
                            category,
                            project_name,
                        )
                    )
            else:
                chunks.append(
                    self._create_window_chunk(
                        file_path, start + 1, end, chunk_content, language, category, project_name
                    )
                )

        return chunks

    @staticmethod
    def _generate_id(
        file_path: str,
        start_line: int,
        end_line: int,
        project_name: str = "default",
    ) -> str:
        """Generate a deterministic UUID-5 ID based on project, relative path, and line range."""
        raw = f"{project_name}:{file_path}:{start_line}:{end_line}"
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, raw))

    @staticmethod
    def _hash_content(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
