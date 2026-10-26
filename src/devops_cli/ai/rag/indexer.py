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
from devops_cli.ai.kb import knowledge_base_digest
from devops_cli.config.constants import (
    CONST_EXIT_FAILURE,
    CONST_INDEX_CACHE_FILENAME,
    CONST_INDEX_COUNTS_FILENAME,
    CONST_RAG_INCOMPLETE_FILE_MARKER,
    CONST_RAG_KB_PROJECT,
    CONST_RAG_SKIPPED_LOCKFILES,
)
from devops_cli.config.defaults import (
    DEFAULT_DRY_RUN_EMBEDDING_DIMENSION,
    DEFAULT_MAX_AST_FILE_SIZE_BYTES,
    DEFAULT_RAG_CACHE_DIR,
    DEFAULT_RAG_CHUNK_OVERLAP,
    DEFAULT_RAG_CHUNK_SIZE,
    DEFAULT_RAG_COLLECTION,
    DEFAULT_RAG_DOCS_COLLECTION,
)
from devops_cli.core.repo import is_ignored_by_git
from devops_cli.exceptions import ConfigurationError, DevOpsCLIError
from devops_cli.lang.en.errors import ERRORS
from devops_cli.output.file_writer import write_json_file
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
    params = (
        info.get("config", {}).get("params", {}) if isinstance(info.get("config"), dict) else {}
    )
    vec_params = params.get("vectors", {}) if isinstance(params, dict) else {}
    v_size = info.get("vector_size") or (
        vec_params.get("size", 0) if isinstance(vec_params, dict) else 0
    )
    size = int(v_size or 0)
    return IndexStats(
        collection_name=coll,
        total_vectors=cnt,
        vector_size=size,
        indexed_files=cached_file_count,
        last_indexed_at=datetime.now(UTC).isoformat(),
    )


def _collect_deleted_keys_by_project(
    cache: dict[str, str],
    file_hashes: dict[str, str],
    scanned_projects: set[str],
) -> dict[str, list[str]]:
    """Group deleted cache keys by project name."""
    current_keys = set(file_hashes.keys())
    by_proj: dict[str, list[str]] = defaultdict(list)
    for k in cache:
        proj, _, rel_path = k.partition(":")
        if proj in scanned_projects and k not in current_keys and rel_path:
            by_proj[proj].append(rel_path)
    return by_proj


def _purge_deleted_batch(
    qdrant: QdrantClient,
    code_collection: str,
    docs_collection: str,
    proj: str,
    chunk: list[str],
    cache: dict[str, str],
    save_cache_fn: Callable[[dict[str, str]], None],
) -> None:
    """Purge a batch of deleted files and update local cache."""
    qdrant.delete_points_by_files(code_collection, chunk, project_name=proj, wait=True)
    qdrant.delete_points_by_files(docs_collection, chunk, project_name=proj, wait=True)
    for r in chunk:
        cache.pop(f"{proj}:{r}", None)
    save_cache_fn(cache)


def _purge_deleted_vectors(
    qdrant: QdrantClient,
    cache: dict[str, str],
    file_hashes: dict[str, str],
    code_collection: str,
    docs_collection: str,
    save_cache_fn: Callable[[dict[str, str]], None],
    *,
    project: str | None = None,
    projects: set[str] | Sequence[str] | None = None,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> int:
    """Purge obsolete points from Qdrant when files are deleted on disk."""
    if projects is not None:
        scanned_projects = set(projects)
    else:
        scanned_projects = {k.partition(":")[0] for k in file_hashes}
        if project:
            scanned_projects.add(project)

    by_proj = _collect_deleted_keys_by_project(cache, file_hashes, scanned_projects)
    total_deleted = sum(len(paths) for paths in by_proj.values())
    if total_deleted == 0:
        return 0

    if progress_callback:
        progress_callback("Purging deleted files", 0, total_deleted)

    processed = 0
    for proj, rel_paths in by_proj.items():
        for i in range(0, len(rel_paths), 100):
            chunk = rel_paths[i : i + 100]
            _purge_deleted_batch(
                qdrant, code_collection, docs_collection, proj, chunk, cache, save_cache_fn
            )
            processed += len(chunk)
            if progress_callback:
                progress_callback("Purging deleted files", processed, total_deleted)

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
            qdrant.delete_points_by_files(code_collection, chunk, project_name=fproj, wait=True)
            qdrant.delete_points_by_files(docs_collection, chunk, project_name=fproj, wait=True)
            processed += len(chunk)
            if progress_callback:
                progress_callback("Purging obsolete vectors", processed, total_files)


def _build_chunk_point(
    chunk: CodeChunk,
    vector: list[float],
    *,
    embedding_model: str | None = None,
    kb_digest: str | None = None,
) -> dict[str, Any]:
    """Construct Qdrant point dictionary with vector and chunk metadata payload."""
    payload: dict[str, Any] = {
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
        "indexed_at": datetime.now(UTC).isoformat(),
        "embedding_model": embedding_model or "",
    }
    if chunk.project_name == CONST_RAG_KB_PROJECT:
        payload["kb_digest"] = kb_digest or ""
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
        proj_name = CONST_RAG_KB_PROJECT
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
                getattr(ai_cfg, "ollama_server_urls", []),
            )
            urls = raw_urls if isinstance(raw_urls, list) else []
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
    url = base_url or settings.qdrant.url
    if not url:
        raise ConfigurationError(
            "No Qdrant vector store URL configured. Run: devops config set qdrant.url <url>",
            key="qdrant.url",
        )
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


def _extract_collection_vector_size(info: dict[str, Any]) -> int | None:
    """Extract vector dimension integer from Qdrant collection info dict."""
    size = info.get("vector_size")
    if isinstance(size, int):
        return size
    cfg = info.get("config")
    if isinstance(cfg, dict):
        params = cfg.get("params")
        if isinstance(params, dict):
            vectors = params.get("vectors")
            if isinstance(vectors, dict) and isinstance(vectors.get("size"), int):
                return int(vectors["size"])
    return None


def _extract_embedder_dimension(embedder: Any) -> int | None:
    """Extract or probe vector dimension integer from embedder object."""
    if hasattr(embedder, "dimension"):
        dim_attr = embedder.dimension
        try:
            dim = dim_attr() if callable(dim_attr) else dim_attr
            if isinstance(dim, int):
                return dim
        except (AttributeError, TypeError, ValueError, DevOpsCLIError) as exc:
            logger.debug("Failed probing embedder dimension: %s", exc)
    if hasattr(embedder, "_dimension") and isinstance(embedder._dimension, int):
        return embedder._dimension
    return None


def _check_collection_point_model(
    qdrant: Any,
    collection_name: str,
    configured_model: str,
) -> None:
    """Check that existing points in the collection were embedded by the configured model."""
    if not hasattr(qdrant, "scroll_points"):
        return
    sample = qdrant.scroll_points(collection_name, limit=1, with_payload=True)
    if not isinstance(sample, list) or not sample or not isinstance(sample[0], dict):
        return
    payload = sample[0].get("payload")
    if not isinstance(payload, dict):
        return
    point_model = payload.get("embedding_model") or "unknown"
    if configured_model and point_model != configured_model:
        raise EmbeddingsError(
            f"Qdrant collection '{collection_name}' embedding model mismatch "
            f"(collection: {point_model}, configured: {configured_model}). "
            "Fix: run `devops ai rag clear --force`, then `devops ai rag index --force`.",
            exit_code=CONST_EXIT_FAILURE,
            is_transient=False,
            details={
                "collection": collection_name[:256],
                "collection_model": point_model[:256],
                "configured_model": configured_model[:256],
                "fix": "devops ai rag clear --force && devops ai rag index --force",
            },
        )


def _check_collection_dimension(
    embedder: Any,
    collection_name: str,
    configured_model: str,
    info: dict[str, Any],
) -> None:
    """Check that collection vector dimension matches active embedder dimension."""
    coll_size = _extract_collection_vector_size(info)
    model_dim = _extract_embedder_dimension(embedder)
    if isinstance(coll_size, int) and isinstance(model_dim, int) and coll_size != model_dim:
        raise EmbeddingsError(
            f"Qdrant collection '{collection_name}' vector dimension mismatch "
            f"(collection: {coll_size}, model {configured_model}: {model_dim}). "
            "Fix: run `devops ai rag clear --force`, then `devops ai rag index --force`.",
            exit_code=CONST_EXIT_FAILURE,
            is_transient=False,
            details={
                "collection": collection_name[:256],
                "collection_dimension": coll_size,
                "model_dimension": model_dim,
                "configured_model": configured_model[:256],
                "fix": "devops ai rag clear --force && devops ai rag index --force",
            },
        )


def _verify_collection_compatibility_for_indexing(
    qdrant: Any,
    embedder: Any,
    collection_name: str,
) -> None:
    """Refuse indexing into a collection whose points or size mismatch the active embedding model."""
    if not hasattr(qdrant, "get_collection_info"):
        return
    try:
        info = qdrant.get_collection_info(collection_name)
    except (DevOpsCLIError, OSError) as exc:
        logger.debug("Failed getting collection info for %s: %s", collection_name, exc)
        return
    if not isinstance(info, dict):
        return
    points_count = (
        info.get("points_count")
        or info.get("vectors_count")
        or info.get("indexed_vectors_count")
        or 0
    )
    if not isinstance(points_count, (int, float)) or points_count <= 0:
        return
    raw_model = getattr(embedder, "model", getattr(embedder, "model_name", None))
    configured_model = raw_model if isinstance(raw_model, str) else ""
    if not configured_model:
        return
    _check_collection_point_model(qdrant, collection_name, configured_model)
    _check_collection_dimension(embedder, collection_name, configured_model, info)


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
        self.counts_file = cache_dir / CONST_INDEX_COUNTS_FILENAME
        self.chunker = SemanticChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def _load_cache(self) -> dict[str, str]:
        if self.cache_file.exists():
            try:
                return json.loads(self.cache_file.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
            except Exception as exc:
                logger.debug("Failed to read index cache file: %s", exc)
        return {}

    def _save_cache(self, cache: dict[str, str]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        write_json_file(self.cache_file, cache, indent=2, atomic=True)

    def _load_counts(self) -> dict[str, dict[str, int]]:
        if self.counts_file.exists():
            try:
                data = json.loads(self.counts_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception as exc:
                logger.debug("Failed to read index counts file: %s", exc)
        return {}

    def _save_counts(self, counts: dict[str, dict[str, int]]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        write_json_file(self.counts_file, counts, indent=2, atomic=True)

    def _check_project_points_intact(self, project: str) -> tuple[bool, str | None]:
        counts = self._load_counts()
        if project in counts:
            proj_counts = counts[project]
            for coll in (self.code_collection, self.docs_collection):
                prev_count = proj_counts.get(coll, 0)
                if prev_count > 0:
                    current = self.qdrant.count_points(coll, {"project_name": project})
                    if current == 0:
                        return False, coll
            return True, None

        cache = self._load_cache()
        if any(k.partition(":")[0] == project for k in cache):
            code_count = self.qdrant.count_points(self.code_collection, {"project_name": project})
            docs_count = self.qdrant.count_points(self.docs_collection, {"project_name": project})
            if code_count == 0 and docs_count == 0:
                return False, f"{self.code_collection}, {self.docs_collection}"

        return True, None

    def points_intact(self, project: str) -> bool:
        """Check whether the points for a project remain intact in Qdrant collections."""
        intact, _ = self._check_project_points_intact(project)
        return intact

    @staticmethod
    def collect_files(root_dir: Path) -> list[Path]:
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
            project=CONST_RAG_KB_PROJECT,
            force=force,
            include_kb=False,
            progress_callback=progress_callback,
        )

    def _ensure_collections(self) -> None:
        """Ensure collections exist and have payload schema indexes."""
        for coll_name in {self.code_collection, self.docs_collection}:
            _verify_collection_compatibility_for_indexing(self.qdrant, self.embedder, coll_name)

        model_dim = (
            _extract_embedder_dimension(self.embedder) or DEFAULT_DRY_RUN_EMBEDDING_DIMENSION
        )
        if hasattr(self.qdrant, "ensure_collection"):
            self.qdrant.ensure_collection(self.code_collection, vector_size=model_dim)
            self.qdrant.ensure_collection(self.docs_collection, vector_size=model_dim)

    def _resolve_scanned_projects(
        self,
        files: Sequence[Path],
        root_dir: Path,
        kb_dir: Path,
        project: str | None,
        include_kb: bool,
    ) -> set[str]:
        """Determine unique project names across collected files."""
        if project:
            scanned = {project}
        else:
            scanned = {
                _resolve_indexing_target_metadata(f, root_dir, kb_dir, None)[0] for f in files
            }
            if not scanned:
                scanned = {detect_project_name(root_dir, root_dir)}
        if include_kb:
            scanned.add(CONST_RAG_KB_PROJECT)
        return scanned

    def _prepare_force_projects(self, scanned_projects: set[str], *, force: bool) -> set[str]:
        """Detect and purge projects requiring full re-indexing."""
        force_projects: set[str] = set()
        if force:
            force_projects.update(scanned_projects)
        else:
            for proj in sorted(scanned_projects):
                intact, lost_coll = self._check_project_points_intact(proj)
                if not intact:
                    logger.info(
                        "Project '%s' lost points in collection '%s'; refilling index",
                        proj,
                        lost_coll,
                    )
                    force_projects.add(proj)

        for proj in sorted(force_projects):
            self.qdrant.delete_points_by_project(self.code_collection, proj, wait=True)
            self.qdrant.delete_points_by_project(self.docs_collection, proj, wait=True)

        return force_projects

    def _save_project_counts(self, scanned_projects: set[str]) -> None:
        """Record point counts per project and collection to counts file."""
        counts = self._load_counts()
        for p in sorted(scanned_projects):
            counts[p] = {
                self.code_collection: self.qdrant.count_points(
                    self.code_collection, {"project_name": p}
                ),
                self.docs_collection: self.qdrant.count_points(
                    self.docs_collection, {"project_name": p}
                ),
            }
        self._save_counts(counts)

    def _scan_workspace_files(
        self,
        files: Sequence[Path],
        root_dir: Path,
        kb_dir: Path,
        project: str | None,
        cache: dict[str, str],
        force_projects: set[str],
        *,
        force: bool,
        progress_callback: Callable[[str, int, int], None] | None,
    ) -> tuple[dict[str, str], list[CodeChunk], list[tuple[Path, str, str]]]:
        """Scan and chunk all indexable workspace files."""
        file_hashes: dict[str, str] = {}
        all_chunks: list[CodeChunk] = []
        files_to_reindex: list[tuple[Path, str, str]] = []

        for idx, file_path in enumerate(files, 1):
            if progress_callback:
                progress_callback("Scanning files", idx, len(files))

            proj_name, _, _ = _resolve_indexing_target_metadata(
                file_path, root_dir, kb_dir, project
            )
            file_forced = force or (proj_name in force_projects)
            scanned = _scan_single_file_for_indexing(
                file_path,
                root_dir,
                kb_dir,
                project,
                self.chunker,
                cache,
                file_hashes,
                file_forced,
            )
            if scanned is not None:
                file_info, file_chunks = scanned
                files_to_reindex.append(file_info)
                all_chunks.extend(file_chunks)

        return file_hashes, all_chunks, files_to_reindex

    def _upsert_partitioned_chunks(
        self,
        all_chunks: list[CodeChunk],
        cache: dict[str, str],
        file_hashes: dict[str, str],
        progress_callback: Callable[[str, int, int], None] | None,
    ) -> tuple[list[CodeChunk], list[CodeChunk]]:
        """Partition chunks into code and docs, then upsert to Qdrant."""
        code_chunks, doc_chunks = _partition_chunks(all_chunks)
        pending = Counter(f"{c.project_name}:{c.file_path}" for c in all_chunks)
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
        return code_chunks, doc_chunks

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
        self._ensure_collections()

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
            from devops_cli.ai.kb import get_knowledge_base_dir

            kb_dir = get_knowledge_base_dir().resolve()
            scanned_projects = self._resolve_scanned_projects(
                files, root_dir, kb_dir, project, include_kb
            )
            force_projects = self._prepare_force_projects(scanned_projects, force=force)

            cache = self._load_cache()
            if force_projects:
                cache = {
                    k: v for k, v in cache.items() if k.partition(":")[0] not in force_projects
                }

            file_hashes, all_chunks, files_to_reindex = self._scan_workspace_files(
                files,
                root_dir,
                kb_dir,
                project,
                cache,
                force_projects,
                force=force,
                progress_callback=progress_callback,
            )

            # Purge files deleted from disk since last index (scoped to scanned projects not forced)
            removed_files_count = 0
            projects_to_purge = scanned_projects - force_projects
            if projects_to_purge:
                removed_files_count = _purge_deleted_vectors(
                    self.qdrant,
                    cache,
                    file_hashes,
                    self.code_collection,
                    self.docs_collection,
                    self._save_cache,
                    projects=projects_to_purge,
                    progress_callback=progress_callback,
                )

            if not all_chunks:
                self._save_project_counts(scanned_projects)
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

            code_chunks, doc_chunks = self._upsert_partitioned_chunks(
                all_chunks, cache, file_hashes, progress_callback
            )
            self._save_cache(cache)
            self._save_project_counts(scanned_projects)

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

        has_kb = any(c.project_name == CONST_RAG_KB_PROJECT for c in chunks)
        kb_digest = knowledge_base_digest() if has_kb else ""
        embedding_model = getattr(self.embedder, "model", "")

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
                    _build_chunk_point(
                        chunk,
                        vec,
                        embedding_model=embedding_model,
                        kb_digest=kb_digest,
                    )
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
