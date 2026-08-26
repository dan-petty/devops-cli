"""Incremental polyglot workspace indexer with content hash caching."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devops_cli.ai.rag.chunker import SemanticChunker
from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.ai.rag.models import CodeChunk, IndexStats
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.config.defaults import (
    DEFAULT_RAG_CACHE_DIR,
    DEFAULT_RAG_CHUNK_OVERLAP,
    DEFAULT_RAG_CHUNK_SIZE,
    DEFAULT_RAG_COLLECTION,
    DEFAULT_RAG_DOCS_COLLECTION,
)
from devops_cli.telemetry import record_metric, trace_span

logger = logging.getLogger(__name__)

_INDEXABLE_EXTENSIONS = {
    # Python & dynamic languages
    ".py",
    ".pyi",
    ".rb",
    ".php",
    ".lua",
    ".r",
    ".dart",
    # Systems & Compiled
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".kts",
    ".scala",
    ".cs",
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hpp",
    ".swift",
    # Web & Frontend
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".html",
    ".css",
    ".scss",
    # Shell & Scripts
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".ps1",
    # Infrastructure & Data
    ".tf",
    ".hcl",
    ".tfvars",
    ".sql",
    ".proto",
    ".graphql",
    ".gql",
    # Config & Manifests
    ".yaml",
    ".yml",
    ".json",
    ".json5",
    ".jsonc",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".xml",
    # Technical Documentation & Specs
    ".md",
    ".markdown",
    ".rst",
    ".adoc",
    ".asciidoc",
    ".org",
    ".txt",
    ".tex",
    ".mmd",
    ".mermaid",
    ".puml",
}

_EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".data",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    ".coverage",
    ".tox",
    ".next",
    ".turbo",
}


def detect_project_name(file_path: Path, root_dir: Path) -> str:
    """Determine the project or repository name for a given file."""
    current = file_path.parent
    root_resolved = root_dir.resolve()
    while current != current.parent:
        if (
            (current / ".git").exists()
            or (current / "pyproject.toml").exists()
            or (current / "package.json").exists()
            or (current / "Cargo.toml").exists()
            or (current / "go.mod").exists()
        ):
            return current.name
        if current.resolve() == root_resolved:
            break
        current = current.parent
    return root_dir.name or "default"


def _load_gitignore_spec(root: Path) -> Any:
    """Load .gitignore patterns from root as a compiled pathspec matcher."""
    gitignore_file = root / ".gitignore"
    if not gitignore_file.is_file():
        return None
    try:
        import pathspec

        patterns = [
            line.strip()
            for line in gitignore_file.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns) if patterns else None
    except Exception:
        return None


def _is_indexable_file(p: Path, root: Path, *, gitignore_spec: Any = None) -> bool:
    """Determine if a path is an indexable code/doc file under root."""
    if not p.is_file():
        return False
    rel_parts = p.relative_to(root).parts
    if any(part in _EXCLUDED_PARTS or part.startswith(".") for part in rel_parts[:-1]):
        return False
    if p.name.startswith(".") and not p.name.endswith((".yaml", ".yml", ".json", ".toml")):
        return False
    if gitignore_spec is not None and gitignore_spec.match_file(str(p.relative_to(root))):
        return False
    named_match = p.name in {
        "Dockerfile",
        "Containerfile",
        "Makefile",
        "Vagrantfile",
        "Jenkinsfile",
    }
    if not (p.suffix.lower() in _INDEXABLE_EXTENSIONS or named_match):
        return False
    try:
        return p.stat().st_size <= 2 * 1024 * 1024
    except OSError:
        return False


def _collect_all_indexing_files(
    collector: Callable[[Path], list[Path]], root_dir: Path, include_kb: bool
) -> list[Path]:
    """Collect workspace and optional knowledge base files."""
    files = collector(root_dir)
    if not include_kb:
        return files
    from devops_cli.ai.kb import get_knowledge_base_dir

    kb_dir = get_knowledge_base_dir()
    if kb_dir.is_dir() and kb_dir.resolve() != root_dir.resolve():
        existing_set = {f.resolve() for f in files}
        for kbf in collector(kb_dir):
            if kbf.resolve() not in existing_set:
                files.append(kbf)
    return files


def _update_incremental_cache(
    cache: dict[str, str] | None,
    file_hashes: dict[str, str] | None,
    batch: list[CodeChunk],
    save_fn: Callable[[dict[str, str]], None],
) -> None:
    """Update and persist incremental cache entries for an embedded batch."""
    if cache is None or file_hashes is None:
        return
    for c in batch:
        ckey = f"{c.project_name}:{c.file_path}"
        if ckey in file_hashes:
            cache[ckey] = file_hashes[ckey]
    save_fn(cache)


def _get_single_collection_stat(
    qdrant: Any, coll: str, cached_file_count: int
) -> IndexStats | None:
    """Query single Qdrant collection info and construct IndexStats."""
    info = qdrant.get_collection_info(coll)
    if not info:
        return None
    cnt = int(info.get("points_count", 0))
    size = int(info.get("config", {}).get("params", {}).get("vectors", {}).get("size", 0))
    return IndexStats(
        collection_name=coll,
        total_vectors=cnt,
        vector_size=size,
        indexed_files=cached_file_count,
        last_indexed_at=datetime.now(UTC).isoformat(),
    )


def _purge_deleted_vectors(
    qdrant: QdrantClient,
    cache: dict[str, str],
    file_hashes: dict[str, str],
    code_collection: str,
    docs_collection: str,
    save_cache_fn: Callable[[dict[str, str]], None],
) -> int:
    """Purge obsolete points from Qdrant when files are deleted on disk."""
    scanned_projects = {k.partition(":")[0] for k in file_hashes.keys()}
    current_keys = set(file_hashes.keys())
    deleted_keys = [
        k for k in cache if k.partition(":")[0] in scanned_projects and k not in current_keys
    ]
    removed_count = 0
    for dkey in deleted_keys:
        dproj, _, d_rel_path = dkey.partition(":")
        if d_rel_path:
            qdrant.delete_points_by_file(code_collection, d_rel_path, project_name=dproj)
            qdrant.delete_points_by_file(docs_collection, d_rel_path, project_name=dproj)
            removed_count += 1
        del cache[dkey]
    if deleted_keys:
        save_cache_fn(cache)
    return removed_count


def _purge_obsolete_points(
    qdrant: QdrantClient,
    files_to_reindex: list[tuple[Path, str, str]],
    code_collection: str,
    docs_collection: str,
) -> None:
    """Purge existing vectors for files that are about to be re-indexed."""
    for _, rel_fpath, fproj in files_to_reindex:
        try:
            qdrant.delete_points_by_file(code_collection, rel_fpath, project_name=fproj)
            qdrant.delete_points_by_file(docs_collection, rel_fpath, project_name=fproj)
        except Exception as exc:
            logger.debug(
                "Failed to delete obsolete points for %s (%s): %s",
                rel_fpath,
                fproj,
                exc,
            )


def _build_chunk_point(chunk: CodeChunk, vector: list[float]) -> dict[str, Any]:
    """Construct Qdrant point dictionary with vector and chunk metadata payload."""
    payload = {
        "file_path": chunk.file_path,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "content": chunk.content,
        "language": chunk.language,
        "doc_type": chunk.doc_type,
        "category": chunk.category,
        "project_name": chunk.project_name,
        "section_path": chunk.section_path,
        "symbol_names": chunk.symbol_names,
        "metadata": chunk.metadata,
        "content_hash": chunk.content_hash,
    }
    return {"id": chunk.id, "vector": vector, "payload": payload}


class WorkspaceIndexer:
    """Discovers, chunks, embeds, and indexes workspace source code and docs into Qdrant."""

    def __init__(
        self,
        qdrant: QdrantClient,
        embedder: EmbeddingsEngine,
        *,
        code_collection: str = DEFAULT_RAG_COLLECTION,
        docs_collection: str = DEFAULT_RAG_DOCS_COLLECTION,
        cache_dir: Path = DEFAULT_RAG_CACHE_DIR,
        chunk_size: int = DEFAULT_RAG_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_RAG_CHUNK_OVERLAP,
    ) -> None:
        self.qdrant = qdrant
        self.embedder = embedder
        self.code_collection = code_collection
        self.docs_collection = docs_collection
        self.cache_dir = cache_dir
        self.cache_file = cache_dir / "index_cache.json"
        self.chunker = SemanticChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def _load_cache(self) -> dict[str, str]:
        if self.cache_file.exists():
            try:
                return json.loads(self.cache_file.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
            except Exception as exc:
                logger.debug("Failed to read index cache file: %s", exc)
        return {}

    def _save_cache(self, cache: dict[str, str]) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.debug("Failed to write index cache: %s", exc)

    def collect_files(self, root_dir: Path) -> list[Path]:
        """Collect all indexable files under root_dir, respecting .gitignore and exclusion rules."""
        import os

        root = root_dir.resolve()
        if root.is_file():
            return [root]

        gitignore_spec = _load_gitignore_spec(root)
        indexable_files: list[Path] = []

        def _is_dir_excluded(d: str, rel_dir: str) -> bool:
            if d in _EXCLUDED_PARTS or d.startswith("."):
                return True
            if gitignore_spec is None:
                return False
            path_suffix = os.path.join(rel_dir, d, "") if rel_dir != "." else f"{d}/"
            return bool(gitignore_spec.match_file(path_suffix))

        for dirpath, dirnames, filenames in os.walk(root):
            rel_dir = os.path.relpath(dirpath, root)
            dirnames[:] = [d for d in dirnames if not _is_dir_excluded(d, rel_dir)]
            for fname in filenames:
                p = Path(dirpath) / fname
                if _is_indexable_file(p, root, gitignore_spec=gitignore_spec):
                    indexable_files.append(p)

        return sorted(indexable_files)

    def index_knowledge_base(
        self,
        *,
        force: bool = False,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> dict[str, Any]:
        """Index the bundled DevOps CLI Knowledge Base markdown files into the docs collection."""
        from devops_cli.ai.kb import get_knowledge_base_dir

        kb_dir = get_knowledge_base_dir()
        if not kb_dir.is_dir():
            logger.warning("Knowledge base directory not found at %s", kb_dir)
            return {
                "indexed_files": 0,
                "total_chunks": 0,
                "code_chunks": 0,
                "doc_chunks": 0,
                "removed_files": 0,
                "skipped_files": 0,
                "collections": [self.docs_collection],
            }

        return self.index_workspace(
            kb_dir,
            project="devops-cli-kb",
            force=force,
            include_kb=False,
            progress_callback=progress_callback,
        )

    def index_workspace(
        self,
        root_dir: Path,
        *,
        project: str | None = None,
        force: bool = False,
        include_kb: bool = False,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> dict[str, Any]:
        """Incrementally index workspace files into Qdrant."""
        with trace_span(
            "ai.rag.index_workspace",
            attributes={
                "rag.root_dir": str(root_dir),
                "rag.project": project or "auto",
                "rag.force": force,
                "rag.include_kb": include_kb,
            },
        ) as root_span:
            files = _collect_all_indexing_files(self.collect_files, root_dir, include_kb)
            cache = {} if force else self._load_cache()
            file_hashes: dict[str, str] = {}

            all_chunks: list[CodeChunk] = []
            files_to_reindex: list[tuple[Path, str, str]] = []

            from devops_cli.ai.kb import get_knowledge_base_dir

            kb_dir = get_knowledge_base_dir().resolve()

            def _is_kb_file(f_path: Path) -> bool:
                try:
                    return kb_dir.is_dir() and f_path.is_relative_to(kb_dir)
                except Exception:
                    return False

            for idx, file_path in enumerate(files, 1):
                if progress_callback:
                    progress_callback("Scanning files", idx, len(files))

                f_resolved = file_path.resolve()
                is_kb = _is_kb_file(f_resolved)

                if is_kb:
                    proj_name = "devops-cli-kb"
                    rel_base = kb_dir
                else:
                    proj_name = project or detect_project_name(file_path, root_dir)
                    rel_base = root_dir.resolve()

                try:
                    rel_path = str(f_resolved.relative_to(rel_base))
                except ValueError:
                    rel_path = file_path.name

                cache_key = f"{proj_name}:{rel_path}"

                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    content_hash = SemanticChunker._hash_content(content)
                    file_hashes[cache_key] = content_hash
                except Exception:
                    continue

                if not force and cache.get(cache_key) == content_hash:
                    continue

                files_to_reindex.append((file_path, rel_path, proj_name))
                file_chunks = self.chunker.chunk_file(
                    file_path, relative_to=rel_base, project_name=proj_name
                )
                all_chunks.extend(file_chunks)

            # Purge files deleted from disk since last index (scoped to scanned projects)
            removed_files_count = 0
            if not force:
                removed_files_count = _purge_deleted_vectors(
                    self.qdrant,
                    cache,
                    file_hashes,
                    self.code_collection,
                    self.docs_collection,
                    self._save_cache,
                )

            if not all_chunks:
                root_span.set_attribute("rag.indexed_files", 0)
                root_span.set_attribute("rag.total_chunks", 0)
                return {
                    "indexed_files": 0,
                    "total_chunks": 0,
                    "code_chunks": 0,
                    "doc_chunks": 0,
                    "removed_files": removed_files_count,
                    "skipped_files": len(files),
                    "collections": [self.code_collection, self.docs_collection],
                }

            # Purge obsolete vectors for files that are being re-indexed (scoped to project)
            _purge_obsolete_points(
                self.qdrant,
                files_to_reindex,
                self.code_collection,
                self.docs_collection,
            )

            # Separate code vs doc chunks
            code_chunks: list[CodeChunk] = []
            doc_chunks: list[CodeChunk] = []

            for chunk in all_chunks:
                if chunk.category == "docs" or chunk.doc_type == "doc":
                    doc_chunks.append(chunk)
                else:
                    code_chunks.append(chunk)

            # Upsert chunks to their respective collections with batch embeddings
            if code_chunks:
                self._upsert_chunks(
                    self.code_collection,
                    code_chunks,
                    cache,
                    file_hashes,
                    progress_callback=progress_callback,
                    progress_title="Embedding code",
                )
            if doc_chunks:
                self._upsert_chunks(
                    self.docs_collection,
                    doc_chunks,
                    cache,
                    file_hashes,
                    progress_callback=progress_callback,
                    progress_title="Embedding docs",
                )

            self._save_cache(cache)

            record_metric("rag.indexed_files", len(files) - len(files_to_reindex))
            record_metric("rag.total_chunks", len(all_chunks))

            root_span.set_attribute("rag.indexed_files", len(files_to_reindex))
            root_span.set_attribute("rag.total_chunks", len(all_chunks))
            root_span.set_attribute("rag.code_chunks", len(code_chunks))
            root_span.set_attribute("rag.doc_chunks", len(doc_chunks))

            return {
                "indexed_files": len(files_to_reindex),
                "total_chunks": len(all_chunks),
                "code_chunks": len(code_chunks),
                "doc_chunks": len(doc_chunks),
                "removed_files": removed_files_count,
                "skipped_files": len(files) - len(files_to_reindex),
                "collections": [self.code_collection, self.docs_collection],
            }

    def _upsert_chunks(
        self,
        collection_name: str,
        chunks: list[CodeChunk],
        cache: dict[str, str],
        file_hashes: dict[str, str],
        progress_callback: Callable[[str, int, int], None] | None = None,
        progress_title: str = "Embedding",
    ) -> None:
        """Embed and upsert a list of chunks in batches."""
        if not chunks:
            return

        total = len(chunks)
        batch_size = getattr(self.embedder, "batch_size", 32)
        try:
            ai_cfg = getattr(self.embedder, "config", None)
            raw_urls = getattr(ai_cfg, "ollama_server_urls", ["http://localhost:11434"])
            urls = raw_urls if isinstance(raw_urls, list) else ["http://localhost:11434"]
            raw_par = getattr(ai_cfg, "ollama_max_parallel", 2)
            is_numeric = isinstance(raw_par, (int, float, str)) and not isinstance(raw_par, bool)
            max_par = int(raw_par) if is_numeric else 2
            calc_batch = len(urls) * max_par * 32
            effective_batch_size = max(int(batch_size), min(256, calc_batch))
        except TypeError, ValueError:
            effective_batch_size = int(batch_size)

        for i in range(0, total, effective_batch_size):
            batch = chunks[i : i + effective_batch_size]
            with trace_span(
                "ai.rag.upsert_chunk_batch",
                attributes={
                    "rag.collection_name": collection_name,
                    "rag.batch_chunks_count": len(batch),
                    "rag.batch_index": i // effective_batch_size,
                    "rag.total_chunks": total,
                },
            ):
                texts = [c.content for c in batch]
                embeddings = self.embedder.embed_texts(texts)
                points = [
                    _build_chunk_point(chunk, vec)
                    for chunk, vec in zip(batch, embeddings, strict=False)
                ]
                self.qdrant.upsert_points(collection_name, points)

                # Persist incremental progress to cache
                _update_incremental_cache(cache, file_hashes, batch, self._save_cache)

            if progress_callback:
                progress_callback(progress_title, min(i + len(batch), total), total)

    def get_stats(self) -> list[IndexStats]:
        """Fetch index stats from Qdrant and local cache."""
        stats: list[IndexStats] = []
        cache = self._load_cache()

        for coll in (self.code_collection, self.docs_collection):
            stat = _get_single_collection_stat(self.qdrant, coll, len(cache))
            if stat:
                stats.append(stat)
        return stats
