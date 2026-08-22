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
    DEFAULT_RAG_COLLECTION,
    DEFAULT_RAG_DOCS_COLLECTION,
)

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
        chunk_size: int = 500,
        chunk_overlap: int = 50,
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
            except Exception:
                pass
        return {}

    def _save_cache(self, cache: dict[str, str]) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.debug("Failed to write index cache: %s", exc)

    def collect_files(self, root_dir: Path) -> list[Path]:
        """Collect all indexable files under root_dir, respecting exclusion rules."""
        root = root_dir.resolve()
        indexable_files: list[Path] = []

        if root.is_file():
            return [root]

        for p in root.rglob("*"):
            if not p.is_file():
                continue
            rel_parts = p.relative_to(root).parts
            if any(part in _EXCLUDED_PARTS or part.startswith(".") for part in rel_parts[:-1]):
                continue
            if p.name.startswith(".") and not p.name.endswith((".yaml", ".yml", ".json", ".toml")):
                continue
            if p.suffix.lower() in _INDEXABLE_EXTENSIONS or p.name in (
                "Dockerfile",
                "Containerfile",
                "Makefile",
                "Vagrantfile",
                "Jenkinsfile",
            ):
                try:
                    if p.stat().st_size <= 2 * 1024 * 1024:  # Up to 2MB per file
                        indexable_files.append(p)
                except OSError:
                    continue

        return sorted(indexable_files)

    def index_workspace(
        self,
        root_dir: Path,
        *,
        project: str | None = None,
        force: bool = False,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> dict[str, Any]:
        """Incrementally index workspace files into Qdrant."""
        files = self.collect_files(root_dir)
        cache = {} if force else self._load_cache()
        file_hashes: dict[str, str] = {}

        all_chunks: list[CodeChunk] = []
        files_to_embed: list[Path] = []

        for idx, file_path in enumerate(files, 1):
            if progress_callback:
                progress_callback("Scanning files", idx, len(files))

            proj_name = project or detect_project_name(file_path, root_dir)

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                content_hash = SemanticChunker._hash_content(content)
                rel_path = str(file_path.relative_to(root_dir))
                cache_key = f"{proj_name}:{rel_path}"
                file_hashes[cache_key] = content_hash
            except Exception:
                continue

            if not force and cache.get(cache_key) == content_hash:
                continue

            files_to_embed.append(file_path)
            file_chunks = self.chunker.chunk_file(
                file_path, relative_to=root_dir, project_name=proj_name
            )
            all_chunks.extend(file_chunks)

        # Identify and purge files that were deleted from disk since last index
        removed_files_count = 0
        if not force:
            current_keys = set(file_hashes.keys())
            deleted_keys = [k for k in cache if k not in current_keys]
            for dkey in deleted_keys:
                _, _, d_rel_path = dkey.partition(":")
                if d_rel_path:
                    self.qdrant.delete_points_by_file(self.code_collection, d_rel_path)
                    self.qdrant.delete_points_by_file(self.docs_collection, d_rel_path)
                    removed_files_count += 1
                del cache[dkey]
            if deleted_keys:
                self._save_cache(cache)

        if not all_chunks:
            return {
                "indexed_files": 0,
                "total_chunks": 0,
                "removed_files": removed_files_count,
                "skipped_files": len(files),
                "collections": [self.code_collection, self.docs_collection],
            }

        # Purge obsolete vectors for files that are being re-indexed
        for fpath in files_to_embed:
            try:
                rel_fpath = str(fpath.relative_to(root_dir))
                self.qdrant.delete_points_by_file(self.code_collection, rel_fpath)
                self.qdrant.delete_points_by_file(self.docs_collection, rel_fpath)
            except Exception:
                pass

        # Separate code vs doc chunks
        code_chunks: list[CodeChunk] = []
        doc_chunks: list[CodeChunk] = []

        for chunk in all_chunks:
            if chunk.category == "docs" or chunk.doc_type == "doc":
                doc_chunks.append(chunk)
            else:
                code_chunks.append(chunk)

        # Ensure collections exist in Qdrant with appropriate vector size
        sample_emb = self.embedder.embed_query("test dimension probe")
        dim = len(sample_emb)

        if code_chunks:
            self.qdrant.ensure_collection(self.code_collection, vector_size=dim)
            self._upsert_chunk_batch(
                self.code_collection,
                code_chunks,
                progress_title="Indexing code chunks",
                progress_callback=progress_callback,
                cache=cache,
                file_hashes=file_hashes,
            )

        if doc_chunks:
            self.qdrant.ensure_collection(self.docs_collection, vector_size=dim)
            self._upsert_chunk_batch(
                self.docs_collection,
                doc_chunks,
                progress_title="Indexing doc chunks",
                progress_callback=progress_callback,
                cache=cache,
                file_hashes=file_hashes,
            )

        self._save_cache(cache)

        return {
            "indexed_files": len(files_to_embed),
            "total_chunks": len(all_chunks),
            "code_chunks": len(code_chunks),
            "doc_chunks": len(doc_chunks),
            "removed_files": removed_files_count,
            "skipped_files": len(files) - len(files_to_embed),
            "collections": [self.code_collection, self.docs_collection],
        }

    def _upsert_chunk_batch(
        self,
        collection_name: str,
        chunks: list[CodeChunk],
        *,
        batch_size: int = 32,
        progress_title: str = "Indexing",
        progress_callback: Callable[[str, int, int], None] | None = None,
        cache: dict[str, str] | None = None,
        file_hashes: dict[str, str] | None = None,
    ) -> None:
        """Embed text and upsert points in batches into Qdrant, saving incremental cache."""
        total = len(chunks)
        ai_cfg = getattr(self.embedder, "ai_config", None)
        urls = (
            getattr(ai_cfg, "get_ollama_urls", ["http://localhost:11434"])
            if ai_cfg
            else ["http://localhost:11434"]
        )
        max_par = getattr(ai_cfg, "ollama_max_parallel", 2) if ai_cfg else 2
        effective_batch_size = max(batch_size, min(256, len(urls) * max_par * 32))

        for i in range(0, total, effective_batch_size):
            batch = chunks[i : i + effective_batch_size]
            texts = [c.content for c in batch]
            embeddings = self.embedder.embed_texts(texts)

            points: list[dict[str, Any]] = []
            for chunk, vec in zip(batch, embeddings, strict=False):
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
                points.append({"id": chunk.id, "vector": vec, "payload": payload})

            self.qdrant.upsert_points(collection_name, points)

            # Persist incremental progress to cache
            if cache is not None and file_hashes is not None:
                for c in batch:
                    ckey = f"{c.project_name}:{c.file_path}"
                    if ckey in file_hashes:
                        cache[ckey] = file_hashes[ckey]
                self._save_cache(cache)

            if progress_callback:
                progress_callback(progress_title, min(i + len(batch), total), total)

    def get_stats(self) -> list[IndexStats]:
        """Fetch index stats from Qdrant and local cache."""
        stats: list[IndexStats] = []
        cache = self._load_cache()

        for coll in (self.code_collection, self.docs_collection):
            info = self.qdrant.get_collection_info(coll)
            if info:
                cnt = int(info.get("points_count", 0))
                size = int(
                    info.get("config", {}).get("params", {}).get("vectors", {}).get("size", 0)
                )
                stats.append(
                    IndexStats(
                        collection_name=coll,
                        total_vectors=cnt,
                        vector_size=size,
                        indexed_files=len(cache),
                        last_indexed_at=datetime.now(UTC).isoformat(),
                    )
                )
        return stats
