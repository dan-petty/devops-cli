"""Incremental polyglot workspace indexer with content hash caching."""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from devops_cli.ai.rag.chunker import SemanticChunker
from devops_cli.ai.rag.embeddings import EmbeddingsEngine, EmbeddingsError
from devops_cli.ai.rag.models import CodeChunk, IndexStats

if TYPE_CHECKING:
    from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.config.constants import (
    CONST_EXIT_FAILURE,
    CONST_INDEX_CACHE_FILENAME,
    CONST_RAG_INCOMPLETE_FILE_MARKER,
    CONST_RAG_SKIPPED_LOCKFILES,
)
from devops_cli.config.defaults import (
    DEFAULT_MAX_AST_FILE_SIZE_BYTES,
    DEFAULT_RAG_CACHE_DIR,
    DEFAULT_RAG_CHUNK_OVERLAP,
    DEFAULT_RAG_CHUNK_SIZE,
    DEFAULT_RAG_COLLECTION,
    DEFAULT_RAG_DOCS_COLLECTION,
)
from devops_cli.core.repo import is_ignored_by_git
from devops_cli.lang.en.errors import ERRORS
from devops_cli.telemetry import record_metric, trace_span

logger = logging.getLogger(__name__)


def is_text_file(p: Path) -> bool:
    """Determine if a file contains textual content by checking for null bytes in initial chunk."""
    try:
        with open(p, "rb") as f:
            chunk = f.read(1024)
            return b"\x00" not in chunk
    except OSError:
        return False


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
        if not patterns:
            return None
        try:
            return pathspec.PathSpec.from_lines("gitignore", patterns)
        except Exception:
            return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    except Exception:
        return None


def _is_hidden_file_path(p: Path, root: Path) -> bool:
    """Return True if path is a hidden file or inside a hidden directory."""
    rel_parts = p.relative_to(root).parts if p.is_relative_to(root) else p.parts
    if any(part.startswith(".") for part in rel_parts[:-1]):
        return True
    return p.name.startswith(".") and not p.name.endswith((".yaml", ".yml", ".json", ".toml"))


def _is_lockfile(p: Path) -> bool:
    """Determine if a file is a package manager lockfile or dependency checksum."""
    return p.name.endswith(".lock") or p.name in CONST_RAG_SKIPPED_LOCKFILES


def _is_indexable_file(p: Path, root: Path, *, gitignore_spec: Any = None) -> bool:
    """Determine if a path is an indexable code/doc file under root."""
    if not p.is_file() or p.is_symlink():
        return False
    try:
        resolved = p.resolve()
        if not resolved.is_relative_to(root.resolve()):
            return False
    except OSError:
        return False
    if _is_lockfile(p) or _is_hidden_file_path(p, root):
        return False
    if gitignore_spec is not None:
        rel = str(p.relative_to(root)) if p.is_relative_to(root) else p.name
        if gitignore_spec.match_file(rel):
            return False
    if is_ignored_by_git(root, p, is_dir=False):
        return False
    try:
        if p.stat().st_size > DEFAULT_MAX_AST_FILE_SIZE_BYTES:
            return False
    except OSError:
        return False

    return is_text_file(p)


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
    pending: Counter[str],
) -> None:
    """Record each file of an embedded batch in the cache, then persist.

    A file is cached under its content hash once its last pending chunk is stored. Until then it
    is cached as incomplete, a value no content hash matches: a resume without `--force` embeds
    it again (its deterministic chunk ids overwrite the stored points), and the purges still
    find its stored points if it is edited or deleted first (#1296).
    """
    if cache is None or file_hashes is None:
        return
    for c in batch:
        ckey = f"{c.project_name}:{c.file_path}"
        pending[ckey] -= 1
        if ckey in file_hashes:
            done = pending[ckey] == 0
            cache[ckey] = file_hashes[ckey] if done else CONST_RAG_INCOMPLETE_FILE_MARKER
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


def _safe_delete_points_by_files(
    qdrant: Any,
    collection_name: str,
    file_paths: Sequence[str],
    *,
    project_name: str | None = None,
) -> bool:
    """Delete points for file paths in batches if supported, falling back to per-file deletion."""
    if not file_paths:
        return True
    if hasattr(qdrant, "delete_points_by_files"):
        return bool(
            qdrant.delete_points_by_files(
                collection_name, file_paths, project_name=project_name, wait=False
            )
        )
    if hasattr(qdrant, "delete_points_by_file"):
        for f in file_paths:
            qdrant.delete_points_by_file(collection_name, f, project_name=project_name)
        return True
    return False


def _purge_deleted_vectors(
    qdrant: QdrantClient,
    cache: dict[str, str],
    file_hashes: dict[str, str],
    code_collection: str,
    docs_collection: str,
    save_cache_fn: Callable[[dict[str, str]], None],
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> int:
    """Purge obsolete points from Qdrant when files are deleted on disk."""
    scanned_projects = {k.partition(":")[0] for k in file_hashes.keys()}
    current_keys = set(file_hashes.keys())
    deleted_keys = [
        k for k in cache if k.partition(":")[0] in scanned_projects and k not in current_keys
    ]
    if not deleted_keys:
        return 0

    total_deleted = len(deleted_keys)
    if progress_callback:
        progress_callback("Purging deleted files", 0, total_deleted)

    by_proj: dict[str, list[str]] = defaultdict(list)
    for dkey in deleted_keys:
        dproj, _, d_rel_path = dkey.partition(":")
        if d_rel_path:
            by_proj[dproj].append(d_rel_path)
        del cache[dkey]

    processed = 0
    for proj, rel_paths in by_proj.items():
        _safe_delete_points_by_files(qdrant, code_collection, rel_paths, project_name=proj)
        _safe_delete_points_by_files(qdrant, docs_collection, rel_paths, project_name=proj)
        processed += len(rel_paths)
        if progress_callback:
            progress_callback("Purging deleted files", processed, total_deleted)

    save_cache_fn(cache)
    return total_deleted


def _purge_obsolete_points(
    qdrant: QdrantClient,
    files_to_reindex: list[tuple[Path, str, str]],
    code_collection: str,
    docs_collection: str,
    cache: dict[str, str] | None = None,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> None:
    """Purge existing vectors for files that are about to be re-indexed."""
    if not files_to_reindex:
        return

    # If cache has existing entries, only purge files that were previously indexed
    targets = [f for f in files_to_reindex if not cache or f"{f[2]}:{f[1]}" in cache]
    if not targets:
        return

    by_proj: dict[str, list[str]] = defaultdict(list)
    for _, rel_fpath, fproj in targets:
        by_proj[fproj].append(rel_fpath)

    total_files = len(targets)
    processed = 0
    if progress_callback:
        progress_callback("Purging obsolete vectors", 0, total_files)

    for fproj, rel_paths in by_proj.items():
        batch_size = 100
        for i in range(0, len(rel_paths), batch_size):
            chunk = rel_paths[i : i + batch_size]
            _safe_delete_points_by_files(qdrant, code_collection, chunk, project_name=fproj)
            _safe_delete_points_by_files(qdrant, docs_collection, chunk, project_name=fproj)
            processed += len(chunk)
            if progress_callback:
                progress_callback("Purging obsolete vectors", processed, total_files)


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


def _resolve_indexing_target_metadata(
    file_path: Path, root_dir: Path, kb_dir: Path, project: str | None
) -> tuple[str, Path, str]:
    """Determine project name, relative base directory, and relative path for indexing target."""
    f_resolved = file_path.resolve()
    is_kb = False
    try:
        is_kb = kb_dir.is_dir() and f_resolved.is_relative_to(kb_dir)
    except Exception:
        pass

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

    return proj_name, rel_base, rel_path


def _scan_single_file_for_indexing(
    file_path: Path,
    root_dir: Path,
    kb_dir: Path,
    project: str | None,
    chunker: SemanticChunker,
    cache: dict[str, str],
    file_hashes: dict[str, str],
    force: bool,
) -> tuple[tuple[Path, str, str], list[CodeChunk]] | None:
    """Read and chunk a single file if content has changed or force is True."""
    proj_name, rel_base, rel_path = _resolve_indexing_target_metadata(
        file_path, root_dir, kb_dir, project
    )
    cache_key = f"{proj_name}:{rel_path}"

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        content_hash = SemanticChunker._hash_content(content)
        file_hashes[cache_key] = content_hash
    except Exception as exc:
        logger.warning("Failed to read file %s for indexing: %s", file_path, exc)
        return None

    if not force and cache.get(cache_key) == content_hash:
        return None

    file_chunks = chunker.chunk_file(file_path, relative_to=rel_base, project_name=proj_name)
    return (file_path, rel_path, proj_name), file_chunks


def _partition_chunks(all_chunks: list[CodeChunk]) -> tuple[list[CodeChunk], list[CodeChunk]]:
    """Split chunks into code and documentation sets."""
    code_chunks: list[CodeChunk] = []
    doc_chunks: list[CodeChunk] = []
    for chunk in all_chunks:
        if chunk.category == "docs" or chunk.doc_type == "doc":
            doc_chunks.append(chunk)
        else:
            code_chunks.append(chunk)
    return code_chunks, doc_chunks


def _calc_effective_batch_size(embedder: Any, default_batch: int) -> int:
    """Calculate batch size from embedder config, Ollama nodes, or gateway concurrency."""
    ai_cfg = getattr(embedder, "ai_config", getattr(embedder, "config", None))
    if ai_cfg is None:
        return default_batch
    try:
        prov = str(getattr(ai_cfg, "provider", "")).lower()
        if prov in ("gateway", "litellm", "portkey") or getattr(ai_cfg, "gateway_enabled", False):
            gw_conc = getattr(ai_cfg, "gateway_concurrency", {})
            concurrency = int(gw_conc.get("embedding", 4) if isinstance(gw_conc, dict) else 4)
            calc_batch = max(1, concurrency) * 32
        else:
            raw_urls = getattr(
                ai_cfg,
                "ollama_urls",
                getattr(ai_cfg, "ollama_server_urls", ["http://localhost:11434"]),
            )
            urls = raw_urls if isinstance(raw_urls, list) else ["http://localhost:11434"]
            raw_par = getattr(ai_cfg, "ollama_max_parallel", 2)
            is_numeric = isinstance(raw_par, (int, float, str)) and not isinstance(raw_par, bool)
            max_par = int(raw_par) if is_numeric else 2
            calc_batch = len(urls) * max_par * 32
        return max(int(default_batch), min(256, calc_batch))
    except TypeError, ValueError:
        return int(default_batch)


def resolve_qdrant_client(
    base_url: str | None = None,
    api_key: str | None = None,
    *,
    allow_private_network: bool | None = None,
) -> QdrantClient:
    """Resolve authenticated QdrantClient using OS Keyring when api_key is not explicitly provided.

    Indexing's upserts and deletes go through this client, so each waits `qdrant.timeout` per
    attempt, as a RAG search does.
    """
    from devops_cli.config.settings import get_qdrant_api_key, load_settings

    settings = load_settings()
    url = base_url or settings.qdrant.url or "http://localhost:6333"
    resolved_api_key = api_key or get_qdrant_api_key(settings)
    private_net = (
        allow_private_network
        if allow_private_network is not None
        else settings.ai.allow_private_network
    )
    from devops_cli.ai.rag.qdrant import QdrantClient

    return QdrantClient(
        base_url=url,
        api_key=resolved_api_key,
        allow_private_network=private_net,
        timeout=settings.qdrant.timeout,
    )


class WorkspaceIndexer:
    """Discovers, chunks, embeds, and indexes workspace source code and docs into Qdrant."""

    def __init__(
        self,
        qdrant: QdrantClient | None = None,
        embedder: EmbeddingsEngine | None = None,
        *,
        code_collection: str = DEFAULT_RAG_COLLECTION,
        docs_collection: str = DEFAULT_RAG_DOCS_COLLECTION,
        cache_dir: Path = DEFAULT_RAG_CACHE_DIR,
        chunk_size: int = DEFAULT_RAG_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_RAG_CHUNK_OVERLAP,
    ) -> None:
        if qdrant is None:
            self.qdrant = resolve_qdrant_client()
        else:
            self.qdrant = qdrant
            if not self.qdrant.api_key:
                from devops_cli.config.settings import get_qdrant_api_key, load_settings

                try:
                    self.qdrant.api_key = get_qdrant_api_key(load_settings())
                except Exception as err:
                    logger.debug(
                        "Failed to resolve Qdrant API key from keyring: %s", type(err).__name__
                    )

        if embedder is None:
            from devops_cli.config.settings import get_ai_api_key, load_settings

            settings = load_settings()
            self.embedder = EmbeddingsEngine(
                ai_config=settings.ai,
                api_key=get_ai_api_key(settings),
            )
        else:
            self.embedder = embedder

        self.code_collection = code_collection
        self.docs_collection = docs_collection
        self.cache_dir = cache_dir
        self.cache_file = cache_dir / CONST_INDEX_CACHE_FILENAME
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
        """Collect all indexable files under root_dir, respecting .gitignore rules."""
        import os

        root = root_dir.resolve()
        if root.is_file():
            return [root] if _is_indexable_file(root, root.parent) else []

        gitignore_spec = _load_gitignore_spec(root)
        indexable_files: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dp = Path(dirpath)
            dirnames[:] = [
                d for d in dirnames if not d.startswith(".") and not is_ignored_by_git(root, dp / d)
            ]
            for fname in filenames:
                p = dp / fname
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

            for idx, file_path in enumerate(files, 1):
                if progress_callback:
                    progress_callback("Scanning files", idx, len(files))

                scanned = _scan_single_file_for_indexing(
                    file_path, root_dir, kb_dir, project, self.chunker, cache, file_hashes, force
                )
                if scanned is not None:
                    file_info, file_chunks = scanned
                    files_to_reindex.append(file_info)
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
                    progress_callback=progress_callback,
                )

            if not all_chunks:
                root_span.set_attribute("rag.indexed_files", 0)
                root_span.set_attribute("rag.total_chunks", 0)
                return {
                    "indexed_files": 0,
                    "files_indexed": 0,
                    "total_chunks": 0,
                    "chunks_indexed": 0,
                    "code_chunks": 0,
                    "doc_chunks": 0,
                    "removed_files": removed_files_count,
                    "pruned_chunks": removed_files_count,
                    "skipped_files": len(files),
                    "collections": [self.code_collection, self.docs_collection],
                }

            # Purge obsolete vectors for files that are being re-indexed (scoped to project)
            _purge_obsolete_points(
                self.qdrant,
                files_to_reindex,
                self.code_collection,
                self.docs_collection,
                cache=cache,
                progress_callback=progress_callback,
            )

            code_chunks, doc_chunks = _partition_chunks(all_chunks)
            pending = Counter(f"{c.project_name}:{c.file_path}" for c in all_chunks)

            # Upsert chunks to their respective collections with batch embeddings
            if code_chunks:
                self._upsert_chunks(
                    self.code_collection,
                    code_chunks,
                    cache,
                    file_hashes,
                    pending=pending,
                    progress_callback=progress_callback,
                    progress_title="Embedding code",
                )
            if doc_chunks:
                self._upsert_chunks(
                    self.docs_collection,
                    doc_chunks,
                    cache,
                    file_hashes,
                    pending=pending,
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
                "files_indexed": len(files_to_reindex),
                "total_chunks": len(all_chunks),
                "chunks_indexed": len(all_chunks),
                "code_chunks": len(code_chunks),
                "doc_chunks": len(doc_chunks),
                "removed_files": removed_files_count,
                "pruned_chunks": removed_files_count,
                "skipped_files": len(files) - len(files_to_reindex),
                "collections": [self.code_collection, self.docs_collection],
            }

    def _upsert_chunks(
        self,
        collection_name: str,
        chunks: list[CodeChunk],
        cache: dict[str, str],
        file_hashes: dict[str, str],
        *,
        pending: Counter[str],
        progress_callback: Callable[[str, int, int], None] | None = None,
        progress_title: str = "Embedding",
    ) -> None:
        """Embed and upsert a list of chunks in batches.

        `pending` counts each file's chunks not yet stored, across both collections.
        """
        if not chunks:
            return

        total = len(chunks)
        if progress_callback:
            progress_callback(progress_title, 0, total)
        base_batch = getattr(self.embedder, "batch_size", 32)
        effective_batch_size = _calc_effective_batch_size(self.embedder, base_batch)

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
                try:
                    embeddings = self.embedder.embed_texts(texts)
                except Exception as exc:
                    first_file = batch[0].file_path
                    last_file = batch[-1].file_path
                    det = dict(getattr(exc, "details", {}) or {})
                    det.setdefault("model", getattr(self.embedder, "model", ""))
                    det["first_file"] = first_file
                    det["last_file"] = last_file
                    raise EmbeddingsError(
                        ERRORS.rag.batch_failed.format(
                            first_file=first_file,
                            last_file=last_file,
                            error=str(exc),
                        ),
                        exit_code=CONST_EXIT_FAILURE,
                        details=det,
                    ) from exc
                points = [
                    _build_chunk_point(chunk, vec)
                    for chunk, vec in zip(batch, embeddings, strict=False)
                ]
                self.qdrant.upsert_points(collection_name, points)

                # Persist incremental progress to cache
                _update_incremental_cache(cache, file_hashes, batch, self._save_cache, pending)

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


def __getattr__(name: str) -> Any:
    if name == "QdrantClient":
        from devops_cli.ai.rag.qdrant import QdrantClient

        globals()["QdrantClient"] = QdrantClient
        return QdrantClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
