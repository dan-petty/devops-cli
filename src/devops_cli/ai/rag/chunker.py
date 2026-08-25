"""Polyglot semantic chunking algorithms for source code, manifests, and technical docs."""

from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

from devops_cli.ai.analyze.scanner import detect_language
from devops_cli.ai.rag.metadata import extract_code_metadata, extract_doc_metadata
from devops_cli.ai.rag.models import CodeChunk

_DOC_EXTENSIONS = {".md", ".markdown", ".rst", ".adoc", ".asciidoc", ".org", ".txt"}
_IAC_EXTENSIONS = {".tf", ".hcl", ".tfvars"}
_CONFIG_EXTENSIONS = {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf", ".xml"}
MAX_CHUNK_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MiB safety cap


class SemanticChunker:
    """Chunks source code and documentation files into semantic search units."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_file(
        self,
        file_path: Path,
        relative_to: Path | None = None,
        project_name: str = "default",
    ) -> list[CodeChunk]:
        """Parse and chunk a given file based on its language and structural semantics."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        rel_path = str(file_path.relative_to(relative_to)) if relative_to else str(file_path)
        suffix = file_path.suffix.lower()
        language = detect_language(file_path, content)

        # Determine semantic category
        if suffix in _DOC_EXTENSIONS or "doc" in rel_path.lower():
            category = "docs"
        elif suffix in _IAC_EXTENSIONS or "k8s" in rel_path or "terraform" in rel_path:
            category = "iac"
        elif suffix in _CONFIG_EXTENSIONS:
            category = "config"
        else:
            category = "code"

        if suffix == ".py":
            chunks = self._chunk_python(content, rel_path, project_name=project_name)
        elif suffix in (".yaml", ".yml"):
            chunks = self._chunk_yaml(content, rel_path, project_name=project_name)
        elif suffix in _DOC_EXTENSIONS:
            chunks = self._chunk_tech_docs(
                content, rel_path, language=language, project_name=project_name
            )
        elif suffix == ".go":
            chunks = self._chunk_go(content, rel_path, project_name=project_name)
        elif suffix == ".rs":
            chunks = self._chunk_rust(content, rel_path, project_name=project_name)
        elif suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            chunks = self._chunk_js_ts(
                content, rel_path, language=language, project_name=project_name
            )
        elif suffix in (".java", ".kt", ".kts", ".cs", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp"):
            chunks = self._chunk_c_like(
                content, rel_path, language=language, project_name=project_name
            )
        elif suffix in (".tf", ".hcl"):
            chunks = self._chunk_terraform(content, rel_path, project_name=project_name)
        elif suffix == ".sql":
            chunks = self._chunk_sql(content, rel_path, project_name=project_name)
        else:
            chunks = self._chunk_line_window(
                content,
                rel_path,
                language=language,
                category=category,
                project_name=project_name,
            )

        if not chunks and content.strip():
            chunks = self._chunk_line_window(
                content,
                rel_path,
                language=language,
                category=category,
                project_name=project_name,
            )

        return chunks

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
            id=self._generate_id(file_path, start_line, end_line),
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
        if uncovered and len(uncovered) > 3:
            preamble_lines = lines[0 : min(uncovered[-1], 60)]
            preamble_content = "\n".join(preamble_lines).strip()
            if preamble_content:
                preamble_chunk = self._make_code_chunk(
                    file_path,
                    1,
                    len(preamble_lines),
                    preamble_content,
                    language="python",
                    category="code",
                    project_name=project_name,
                    symbols=["<module>"],
                )
                chunks.insert(0, preamble_chunk)

        return chunks

    def _chunk_language_symbols(
        self,
        content: str,
        file_path: str,
        language: str = "go",
        category: str = "code",
        project_name: str = "default",
    ) -> list[CodeChunk]:
        """Extract language-specific symbols and construct chunks using regex heuristics."""
        lang_lower = language.lower()
        if lang_lower == "go":
            pattern = re.compile(
                r"^(?:func\s+(?:\([^)]+\)\s+)?([A-Za-z0-9_]+)|type\s+([A-Za-z0-9_]+)\s+(?:struct|interface))",
                re.MULTILINE,
            )
            cat = "code"
        elif lang_lower == "rust":
            pattern = re.compile(
                r"^(?:pub\s+)?(?:async\s+)?(?:fn\s+([A-Za-z0-9_]+)|struct\s+([A-Za-z0-9_]+)|enum\s+([A-Za-z0-9_]+)|trait\s+([A-Za-z0-9_]+)|impl(?:<[^>]+>)?\s+([A-Za-z0-9_:]+))",
                re.MULTILINE,
            )
            cat = "code"
        elif lang_lower in ("typescript", "javascript", "js", "ts"):
            pattern = re.compile(
                r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\s+([A-Za-z0-9_$]+)|class\s+([A-Za-z0-9_$]+)|interface\s+([A-Za-z0-9_$]+)|type\s+([A-Za-z0-9_$]+)|const\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)",
                re.MULTILINE,
            )
            cat = "code"
        elif lang_lower in ("terraform", "tofu", "hcl"):
            pattern = re.compile(
                r'^(?:resource|data|module|variable|output)\s+"([^"]+)"(?:\s+"([^"]+)")?',
                re.MULTILINE,
            )
            cat = "iac"
        elif lang_lower == "sql":
            pattern = re.compile(
                r"^(?:CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW|PROCEDURE|FUNCTION|INDEX)\s+([A-Za-z0-9_.]+))",
                re.IGNORECASE | re.MULTILINE,
            )
            cat = "code"
        else:
            # C-like fallback: C/C++, Java, C#, Kotlin
            pattern = re.compile(
                r"^(?:(?:public|private|protected|static|final|abstract|override|inline|virtual)\s+)*(?:class\s+([A-Za-z0-9_]+)|interface\s+([A-Za-z0-9_]+)|struct\s+([A-Za-z0-9_]+)|enum\s+([A-Za-z0-9_]+)|fun\s+([A-Za-z0-9_]+))",
                re.MULTILINE,
            )
            cat = "code"

        return self._chunk_by_regex_symbols(
            content,
            file_path,
            pattern,
            language=language,
            category=category or cat,
            project_name=project_name,
        )

    def _chunk_go(
        self, content: str, file_path: str, project_name: str = "default"
    ) -> list[CodeChunk]:
        """Extract Go functions, methods, structs, and interfaces."""
        return self._chunk_language_symbols(
            content, file_path, language="go", project_name=project_name
        )

    def _chunk_rust(
        self, content: str, file_path: str, project_name: str = "default"
    ) -> list[CodeChunk]:
        """Extract Rust functions, structs, enums, traits, and impl blocks."""
        return self._chunk_language_symbols(
            content, file_path, language="rust", project_name=project_name
        )

    def _chunk_js_ts(
        self,
        content: str,
        file_path: str,
        language: str = "typescript",
        project_name: str = "default",
    ) -> list[CodeChunk]:
        """Extract JavaScript / TypeScript functions, classes, interfaces, and types."""
        return self._chunk_language_symbols(
            content, file_path, language=language, project_name=project_name
        )

    def _chunk_c_like(
        self,
        content: str,
        file_path: str,
        language: str = "cpp",
        project_name: str = "default",
    ) -> list[CodeChunk]:
        """Extract C/C++, Java, C#, Kotlin classes, structs, and methods."""
        return self._chunk_language_symbols(
            content, file_path, language=language, project_name=project_name
        )

    def _chunk_terraform(
        self, content: str, file_path: str, project_name: str = "default"
    ) -> list[CodeChunk]:
        """Extract Terraform/OpenTofu resources, modules, variables, and outputs."""
        return self._chunk_language_symbols(
            content, file_path, language="terraform", category="iac", project_name=project_name
        )

    def _chunk_sql(
        self, content: str, file_path: str, project_name: str = "default"
    ) -> list[CodeChunk]:
        """Extract SQL tables, procedures, views, and index definitions."""
        return self._chunk_language_symbols(
            content, file_path, language="sql", project_name=project_name
        )

    def _chunk_by_regex_symbols(
        self,
        content: str,
        file_path: str,
        pattern: re.Pattern[str],
        language: str,
        category: str,
        project_name: str = "default",
    ) -> list[CodeChunk]:
        """Generic symbol boundary chunker using regex match positions."""
        chunks: list[CodeChunk] = []
        lines = content.splitlines()
        if not lines:
            return []

        matches: list[tuple[int, str]] = []
        for idx, line in enumerate(lines):
            m = pattern.search(line)
            if m:
                # Find first non-None group as symbol name
                syms = [g for g in m.groups() if g]
                sym_name = " ".join(syms) if syms else line.strip()[:40]
                matches.append((idx, sym_name))

        if not matches:
            return self._chunk_line_window(
                content,
                file_path,
                language=language,
                category=category,
                project_name=project_name,
            )

        indices = [m[0] for m in matches] + [len(lines)]

        for i in range(len(matches)):
            start_idx = indices[i]
            end_idx = indices[i + 1]
            sym = matches[i][1]
            chunk_lines = lines[start_idx:end_idx]
            chunk_content = "\n".join(chunk_lines).strip()
            if not chunk_content:
                continue

            chunks.append(
                self._make_code_chunk(
                    file_path,
                    start_idx + 1,
                    end_idx,
                    chunk_content,
                    language=language,
                    category=category,
                    project_name=project_name,
                    symbols=[sym],
                )
            )

        return chunks

    def _chunk_yaml(
        self, content: str, file_path: str, project_name: str = "default"
    ) -> list[CodeChunk]:
        """Split multi-document YAML manifests and OpenAPI/Swagger specs."""
        chunks: list[CodeChunk] = []
        lines = content.splitlines()
        doc_starts = [0]

        for idx, line in enumerate(lines):
            if line.strip() == "---" and idx > 0:
                doc_starts.append(idx)

        doc_starts.append(len(lines))

        category = "iac" if any(k in file_path.lower() for k in ("k8s", "helm")) else "config"

        for i in range(len(doc_starts) - 1):
            start = doc_starts[i]
            end = doc_starts[i + 1]
            doc_lines = lines[start:end]
            doc_content = "\n".join(doc_lines).strip()
            if not doc_content:
                continue

            symbols: list[str] = []
            for line in doc_lines:
                if line.startswith("kind:"):
                    symbols.append(line.split(":", 1)[1].strip())
                elif line.strip().startswith("name:"):
                    symbols.append(line.strip().split(":", 1)[1].strip())

            chunks.append(
                self._make_code_chunk(
                    file_path,
                    start + 1,
                    end,
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

        # Match markdown headers (# Title, ## Sub), RST headers, or AsciiDoc (= Title, == Sub)
        md_regex = re.compile(r"^(#{1,4})\s+(.+)$")
        adoc_regex = re.compile(r"^(=+)\s+(.+)$")

        section_starts: list[tuple[int, int, str]] = []  # (line_idx, level, title)

        for idx, line in enumerate(lines):
            m_md = md_regex.match(line)
            if m_md:
                level = len(m_md.group(1))
                section_starts.append((idx, level, m_md.group(2).strip()))
                continue

            m_adoc = adoc_regex.match(line)
            if m_adoc:
                level = len(m_adoc.group(1))
                section_starts.append((idx, level, m_adoc.group(2).strip()))
                continue

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

            # Update breadcrumb stack for hierarchical section path
            while breadcrumb_stack and breadcrumb_stack[-1][0] >= level:
                breadcrumb_stack.pop()
            breadcrumb_stack.append((level, title))
            section_path = [b[1] for b in breadcrumb_stack]

            sec_lines = lines[start_idx:end_idx]
            sec_content = "\n".join(sec_lines).strip()
            if not sec_content:
                continue

            c_id = self._generate_id(file_path, start_idx + 1, end_idx)
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

            c_id = self._generate_id(file_path, start + 1, end)
            meta = (
                extract_doc_metadata(chunk_content, file_path=file_path)
                if category == "docs"
                else extract_code_metadata(chunk_content, language=language, file_path=file_path)
            )
            chunks.append(
                CodeChunk(
                    id=c_id,
                    file_path=file_path,
                    start_line=start + 1,
                    end_line=end,
                    content=chunk_content,
                    language=language or "text",
                    doc_type="doc" if category == "docs" else "code",
                    category=category,
                    project_name=project_name,
                    symbol_names=[],
                    metadata=meta,
                    content_hash=self._hash_content(chunk_content),
                )
            )

        return chunks

    @staticmethod
    def _generate_id(file_path: str, start_line: int, end_line: int) -> str:
        """Generate a deterministic UUID-compatible SHA256 hex ID."""
        raw = f"{file_path}:{start_line}:{end_line}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"

    @staticmethod
    def _hash_content(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
