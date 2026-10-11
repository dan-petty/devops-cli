"""Autonomous Knowledge Base synchronisation and lazy rebuild on RAG use.

Ensures that the bundled DevOps CLI Knowledge Base is indexed in Qdrant before
first semantic retrieval in a process, and re-indexes whenever the collection is
empty or its recorded digest diverges from the installed knowledge base.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Sequence
from typing import Any

from devops_cli.ai.kb import knowledge_base_digest
from devops_cli.config.constants import CONST_RAG_KB_PROJECT
from devops_cli.config.defaults import DEFAULT_RAG_KB_SYNC_FAILURE_COOLDOWN_SECONDS
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.output.console import print_info, print_warning
from devops_cli.telemetry.instruments import RAG_POINTS, emit

logger = logging.getLogger(__name__)

_KB_SYNCED: bool = False
_KB_LAST_FAILURE_TIME: float | None = None
_KB_FAILURE_WARNED: bool = False
_KB_LOCK = threading.Lock()


def reset_kb_sync_state() -> None:
    """Reset process-local knowledge base synchronisation state (for testing)."""
    global _KB_SYNCED, _KB_LAST_FAILURE_TIME, _KB_FAILURE_WARNED
    with _KB_LOCK:
        _KB_SYNCED = False
        _KB_LAST_FAILURE_TIME = None
        _KB_FAILURE_WARNED = False


def _is_cooldown_active(now: float) -> bool:
    """Check whether the failure retry cooldown window is currently active."""
    if _KB_LAST_FAILURE_TIME is None:
        return False
    return (now - _KB_LAST_FAILURE_TIME) < DEFAULT_RAG_KB_SYNC_FAILURE_COOLDOWN_SECONDS


def _count_kb_points(qdrant: Any, coll: str) -> int | None:
    """Safely query count of KB points in the specified collection."""
    kb_filter = {"project_name": CONST_RAG_KB_PROJECT}
    if hasattr(qdrant, "count_points"):
        try:
            cnt = qdrant.count_points(coll, filter_payload=kb_filter)
            return cnt if isinstance(cnt, int) else None
        except (
            DevOpsCLIError,
            OSError,
            RuntimeError,
            ValueError,
            KeyError,
            AttributeError,
            TypeError,
        ) as exc:
            logger.debug("Failed counting KB points in %s: %s", coll, exc)
            return None
    if hasattr(qdrant, "get_collection_info"):
        try:
            info = qdrant.get_collection_info(coll)
            if isinstance(info, dict):
                pts = info.get("points_count", 0)
                return int(pts) if isinstance(pts, (int, float)) else None
        except (
            DevOpsCLIError,
            OSError,
            RuntimeError,
            ValueError,
            KeyError,
            AttributeError,
            TypeError,
        ) as exc:
            logger.debug("Failed getting collection info for %s: %s", coll, exc)
    return None


def _get_recorded_kb_digest(qdrant: Any, coll: str) -> str | None:
    """Safely fetch recorded KB digest from an existing KB point in Qdrant."""
    kb_filter = {"project_name": CONST_RAG_KB_PROJECT}
    if not hasattr(qdrant, "scroll_points"):
        return None
    try:
        records = qdrant.scroll_points(coll, filter_payload=kb_filter, limit=1)
        if isinstance(records, list) and records and isinstance(records[0], dict):
            payload = records[0].get("payload")
            if isinstance(payload, dict):
                d = payload.get("kb_digest")
                return str(d) if isinstance(d, str) else None
    except (
        DevOpsCLIError,
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        AttributeError,
        TypeError,
    ) as exc:
        logger.debug("Failed scrolling KB points in %s: %s", coll, exc)
    return None


def is_kb_rebuild_needed(qdrant: Any, docs_collection: str, installed_digest: str) -> bool:
    """Determine if Qdrant requires a knowledge base rebuild.

    Rebuild is required when the collection holds zero KB points, or when its
    recorded KB digest differs from the currently installed knowledge base digest.
    """
    points = _count_kb_points(qdrant, docs_collection)
    if points is not None and points == 0:
        return True
    if points is None:
        return False
    recorded = _get_recorded_kb_digest(qdrant, docs_collection)
    return recorded != installed_digest


def _execute_kb_rebuild(qdrant: Any, embedder: Any, docs_collection: str) -> None:
    """Print one progress line and execute knowledge base indexing into Qdrant."""
    print_info("Rebuilding knowledge base index...", prefix=False)
    from devops_cli.ai.rag.indexer import WorkspaceIndexer

    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        docs_collection=docs_collection,
    )
    indexer.index_knowledge_base(force=True)


def _fetch_coll_points(qdrant: Any, coll: str) -> int | None:
    """Fetch point count for a vector collection safely."""
    if hasattr(qdrant, "count_points"):
        try:
            val = qdrant.count_points(coll)
            if isinstance(val, int):
                return val
        except (
            DevOpsCLIError,
            OSError,
            RuntimeError,
            ValueError,
            KeyError,
            AttributeError,
            TypeError,
        ):
            return None
    if hasattr(qdrant, "get_collection_info"):
        try:
            info = qdrant.get_collection_info(coll)
            if isinstance(info, dict):
                raw = info.get("points_count", 0)
                return int(raw) if isinstance(raw, (int, float)) else None
        except (
            DevOpsCLIError,
            OSError,
            RuntimeError,
            ValueError,
            KeyError,
            AttributeError,
            TypeError,
        ):
            return None
    return None


def _emit_rag_points_gauge(qdrant: Any, collections: Sequence[str]) -> None:
    """Emit devops_cli_rag_points gauge for vector collections on RAG use (#974)."""
    for coll in collections:
        if not coll:
            continue
        pts = _fetch_coll_points(qdrant, coll)
        if pts is not None:
            emit(RAG_POINTS, float(pts), {"collection": coll})


def ensure_knowledge_base_ready(
    qdrant: Any,
    embedder: Any,
    docs_collection: str,
    code_collection: str | None = None,
    *,
    force_check: bool = False,
) -> bool:
    """Ensure the knowledge base is indexed in Qdrant on first RAG use in this process.

    Re-indexes before retrieval with a single progress line if the collection holds
    no KB points or if its digest differs from the installed KB digest. On failure,
    warns once and enters a 30-minute cooldown before retrying.
    """
    global _KB_SYNCED, _KB_LAST_FAILURE_TIME, _KB_FAILURE_WARNED

    with _KB_LOCK:
        if _KB_SYNCED and not force_check:
            return True

        now = time.monotonic()
        if _is_cooldown_active(now):
            return False

        if hasattr(qdrant, "is_alive"):
            alive = qdrant.is_alive()
            if not isinstance(alive, bool) or not alive:
                return False

        target_colls = [docs_collection]
        if code_collection:
            target_colls.append(code_collection)
        _emit_rag_points_gauge(qdrant, target_colls)

        installed_digest = knowledge_base_digest()
        if not installed_digest:
            _KB_SYNCED = True
            return True

        try:
            if is_kb_rebuild_needed(qdrant, docs_collection, installed_digest):
                _execute_kb_rebuild(qdrant, embedder, docs_collection)
            _KB_SYNCED = True
            _KB_LAST_FAILURE_TIME = None
            _KB_FAILURE_WARNED = False
            return True
        except (
            DevOpsCLIError,
            OSError,
            RuntimeError,
            ValueError,
            KeyError,
            AttributeError,
            TypeError,
        ) as exc:
            _KB_LAST_FAILURE_TIME = now
            if not _KB_FAILURE_WARNED:
                print_warning(f"Failed rebuilding knowledge base index: {exc}", prefix=False)
                _KB_FAILURE_WARNED = True
            return False


__all__ = [
    "ensure_knowledge_base_ready",
    "is_kb_rebuild_needed",
    "reset_kb_sync_state",
]
