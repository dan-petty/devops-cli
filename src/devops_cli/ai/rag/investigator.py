"""Safe, non-blocking RAG investigation step for grounding AI tasks and generation workflows."""

from __future__ import annotations

import functools
import logging
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from pybreaker import (
    STATE_CLOSED,
    STATE_OPEN,
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerListener,
    CircuitBreakerState,
    CircuitMemoryStorage,
)

from devops_cli.ai.rag.embeddings import EmbeddingsEngine, EmbeddingsError
from devops_cli.ai.rag.models import RAGContext
from devops_cli.ai.rag.qdrant import QdrantClient, qdrant_server_label
from devops_cli.ai.rag.retriever import SemanticRetriever
from devops_cli.config import settings as settings_mod
from devops_cli.config.constants import (
    CONST_RAG_CIRCUIT_BREAKER_FAILURES,
    CONST_RAG_CIRCUIT_BREAKER_PAUSE_SECONDS,
)
from devops_cli.config.defaults import (
    DEFAULT_RAG_COLLECTION,
    DEFAULT_RAG_DOCS_COLLECTION,
    DEFAULT_RAG_INVESTIGATION_MAX_CHARS,
    DEFAULT_RAG_INVESTIGATION_MAX_QUERY_CHARS,
)
from devops_cli.config.settings import Settings
from devops_cli.lang import MESSAGES
from devops_cli.security.sanitizer import redact_text
from devops_cli.telemetry import trace_span
from devops_cli.telemetry.instruments import RAG_INVESTIGATIONS_TOTAL, RAG_STOPS_TOTAL, emit

logger = logging.getLogger(__name__)

_INVESTIGATION_CACHE: dict[str, tuple[float, RAGContext | None]] = {}
_RETRIEVER_CACHE: tuple[float, SemanticRetriever] | None = None
_CACHE_TTL_SECONDS = 60.0

# Set by the first permanent error (unserved/unknown model).
_RAG_STOPPED = threading.Event()
_STOP_LOCK = threading.Lock()
_RETRIEVER_LOCK = threading.Lock()
# Set by the first lookup the embedding model answers.
_RAG_SERVED = threading.Event()
# Set by the first lookup that fails for any non-embedding reason.
_FAILURE_REPORTED = threading.Event()


def _is_permanent_embeddings_error(exc: BaseException) -> bool:
    """Whether `exc` turns RAG off for the run, so that it does not count toward a pause."""
    return isinstance(exc, EmbeddingsError) and not exc.is_transient


class _PauseWarning(CircuitBreakerListener):
    """Warns when the breaker opens, with the failure that opened it.

    pybreaker opens the breaker while it handles the failure, so `sys.exception()` is that failure.
    """

    def state_change(
        self,
        cb: CircuitBreaker,
        old_state: CircuitBreakerState | None,
        new_state: CircuitBreakerState,
    ) -> None:
        if new_state.name != STATE_OPEN:
            return
        failure = sys.exception()
        logger.warning(
            MESSAGES.rag.paused.format(
                seconds=int(cb.reset_timeout),
                failures=cb.fail_max,
                error=getattr(failure, "message", str(failure)),
            )
        )


# The pause of RAG lookups: pybreaker's circuit breaker counts the transient failures in a row.
# The lookups keep the storage, so they can check a pause without a call that changes the state.
_LOOKUP_STATE = CircuitMemoryStorage(STATE_CLOSED)
_LOOKUP_BREAKER = CircuitBreaker(
    fail_max=CONST_RAG_CIRCUIT_BREAKER_FAILURES,
    reset_timeout=CONST_RAG_CIRCUIT_BREAKER_PAUSE_SECONDS,
    exclude=[_is_permanent_embeddings_error],
    listeners=[_PauseWarning()],
    state_storage=_LOOKUP_STATE,
)


class _ProbeCoordinator:
    """Coordinates a single probe lookup while concurrent lookups wait for its outcome."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._event: threading.Event | None = None
        self._succeeded: bool = False

    def clear(self) -> None:
        with self._lock:
            if self._event is not None:
                self._event.set()
            self._event = None
            self._succeeded = False

    def coordinate(self, search_fn: Callable[[], RAGContext | None]) -> RAGContext | None:
        with self._lock:
            if self._event is not None:
                event = self._event
                is_prober = False
            else:
                self._event = threading.Event()
                self._succeeded = False
                event = self._event
                is_prober = True

        if not is_prober:
            event.wait()
            return search_fn() if self._succeeded else None

        success = False
        try:
            ctx = search_fn()
            success = (
                _RAG_SERVED.is_set()
                and _LOOKUP_BREAKER.current_state == STATE_CLOSED
                and _LOOKUP_BREAKER.fail_counter == 0
            )
            return ctx
        finally:
            with self._lock:
                self._succeeded = success
                self._event = None
                event.set()


_PROBE_COORDINATOR = _ProbeCoordinator()


def _lookups_paused() -> bool:
    """Whether the breaker is open and its cooldown runs, so that a lookup sends no request.

    pybreaker moves an open breaker to half-open only at the first call after the cooldown, so the
    check reads the time at which the breaker opened.
    """
    opened_at = _LOOKUP_STATE.opened_at
    return (
        _LOOKUP_STATE.state == STATE_OPEN
        and opened_at is not None
        and datetime.now(UTC) < opened_at + timedelta(seconds=_LOOKUP_BREAKER.reset_timeout)
    )


def _probe_required() -> bool:
    """Whether one lookup probes while the others wait: before the first lookup that the
    embedding model answers, and while the breaker is not closed."""
    return not _RAG_SERVED.is_set() or _LOOKUP_BREAKER.current_state != STATE_CLOSED


def clear_investigation_cache() -> None:
    """Clear in-memory RAG investigation and retriever caches, and lift a run-wide RAG stop."""
    global _RETRIEVER_CACHE
    _RETRIEVER_CACHE = None
    _INVESTIGATION_CACHE.clear()
    _RAG_STOPPED.clear()
    _RAG_SERVED.clear()
    _FAILURE_REPORTED.clear()
    _LOOKUP_BREAKER.close()
    _PROBE_COORDINATOR.clear()


def _stop_rag_for_run(model: str, exc: EmbeddingsError) -> None:
    """Turn RAG off for the rest of the process, warning once with the cause and the fix."""
    with _STOP_LOCK:
        if _RAG_STOPPED.is_set():
            return
        _RAG_STOPPED.set()
    emit(RAG_STOPS_TOTAL, 1.0)
    logger.warning(MESSAGES.rag.stopped_for_run.format(model=model, error=exc.message))


def _report_lookup_failure(exc: Exception) -> None:
    """Warn of the run's first failed lookup with its masked cause; log later ones at debug."""
    with _STOP_LOCK:
        first = not _FAILURE_REPORTED.is_set()
        _FAILURE_REPORTED.set()
    if first:
        logger.warning(MESSAGES.rag.lookup_failed.format(error=redact_text(str(exc))[:256]))
    else:
        logger.debug("RAG investigation skipped due to error: %s", redact_text(str(exc))[:256])


def _cached_retriever_if_valid(now: float) -> SemanticRetriever | None:
    """Return cached retriever if within TTL and healthy, else None."""
    if _RETRIEVER_CACHE is not None:
        last_t, retriever = _RETRIEVER_CACHE
        if now - last_t < _CACHE_TTL_SECONDS and retriever.qdrant.is_alive():
            return retriever
    return None


def _get_or_create_retriever(
    st: Settings, top_k: int | None, score_threshold: float | None
) -> SemanticRetriever | None:
    """Get or create cached SemanticRetriever instance."""
    global _RETRIEVER_CACHE
    now = time.monotonic()
    valid = _cached_retriever_if_valid(now)
    if valid is not None:
        return valid

    with _RETRIEVER_LOCK:
        valid = _cached_retriever_if_valid(now)
        if valid is not None:
            return valid

        qdrant_url = st.qdrant.url
        if not qdrant_url:
            logger.debug("Qdrant vector store not configured, skipping RAG investigation")
            return None
        qdrant = QdrantClient(
            base_url=qdrant_url,
            api_key=settings_mod.get_qdrant_api_key(st),
            allow_private_network=st.ai.allow_private_network,
            timeout=st.qdrant.timeout,
        )
        if not qdrant.is_alive():
            logger.debug(
                "Qdrant vector store unreachable at %s, skipping RAG investigation",
                qdrant_server_label(qdrant_url),
            )
            return None

        embedder = EmbeddingsEngine(ai_config=st.ai, api_key=settings_mod.get_ai_api_key(st))
        prefix = st.qdrant.collection_prefix or "devops"
        code_coll = f"{prefix}_code" if prefix else DEFAULT_RAG_COLLECTION
        docs_coll = f"{prefix}_docs" if prefix else DEFAULT_RAG_DOCS_COLLECTION

        eff_top_k = top_k if top_k is not None else st.ai.rag.top_k
        eff_threshold = (
            score_threshold if score_threshold is not None else st.ai.rag.score_threshold
        )

        retriever = SemanticRetriever(
            qdrant=qdrant,
            embedder=embedder,
            code_collection=code_coll,
            docs_collection=docs_coll,
            default_top_k=eff_top_k,
            default_score_threshold=eff_threshold,
        )
        _RETRIEVER_CACHE = (now, retriever)
        return retriever


def _retrieve(
    st: Settings,
    search_query: str,
    *,
    persona: str | None,
    top_k: int | None,
    score_threshold: float | None,
    project: str | None,
    language: str | None,
    category: str | None,
    file_filter: str | None,
    max_chars: int,
) -> RAGContext | None:
    """Retrieve context for the query; None when the store is unreachable, stopped or paused."""
    if _RAG_STOPPED.is_set() or _lookups_paused():
        return None

    retriever = _get_or_create_retriever(st, top_k, score_threshold)
    if retriever is None:
        return None
    search = functools.partial(
        _search,
        retriever,
        search_query,
        persona=persona,
        top_k=top_k,
        score_threshold=score_threshold,
        project=project,
        language=language,
        category=category,
        file_filter=file_filter,
        max_chars=max_chars,
    )
    if not _probe_required():
        return search()
    return _PROBE_COORDINATOR.coordinate(search)


def _search(
    retriever: SemanticRetriever,
    search_query: str,
    *,
    persona: str | None,
    top_k: int | None,
    score_threshold: float | None,
    project: str | None,
    language: str | None,
    category: str | None,
    file_filter: str | None,
    max_chars: int,
) -> RAGContext | None:
    """Search for the query's context; None when RAG is off, paused, or fails."""
    if _RAG_STOPPED.is_set():
        return None
    try:
        # The breaker runs the block outside its lock, so lookups of a closed breaker run at once.
        with _LOOKUP_BREAKER.calling():
            if persona:
                ctx = retriever.retrieve_context_for_persona(
                    search_query,
                    persona=persona,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    project=project,
                    language=language,
                )
            else:
                ctx = retriever.retrieve_context(
                    search_query,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    project=project,
                    language=language,
                    category=category,
                    file_filter=file_filter,
                    max_chars=max_chars,
                )
    except CircuitBreakerError:
        return None
    except EmbeddingsError as exc:
        if not exc.is_transient:
            _stop_rag_for_run(retriever.embedder.model, exc)
        return None
    except Exception:
        return None
    _RAG_SERVED.set()
    return ctx


def _investigation_attributes(
    clean_query: str, persona: str | None, project: str | None
) -> dict[str, Any]:
    """Span attributes describing one investigation's query."""
    return {
        "query_length": len(clean_query),
        "search_query_length": min(len(clean_query), DEFAULT_RAG_INVESTIGATION_MAX_QUERY_CHARS),
        "query_truncated": len(clean_query) > DEFAULT_RAG_INVESTIGATION_MAX_QUERY_CHARS,
        "persona": persona or "none",
        "project": project or "all",
    }


def _recorded_results(
    ctx: RAGContext, r_span: Any, clean_query: str, start_time: float
) -> RAGContext | None:
    """Count a finished retrieval as found or empty; the context when it found any, else None."""
    duration_ms = (time.perf_counter() - start_time) * 1000.0
    if not ctx.has_results:
        emit(RAG_INVESTIGATIONS_TOTAL, 1.0, {"outcome": "empty"})
        return None
    r_span.set_attribute("rag.results_count", len(ctx.results))
    r_span.set_attribute("rag.total_chars", ctx.total_chars)
    emit(RAG_INVESTIGATIONS_TOTAL, 1.0, {"outcome": "found"})
    logger.debug(
        "RAG investigation retrieved %d chunks in %.1fms for query: %.50s",
        len(ctx.results),
        duration_ms,
        clean_query,
    )
    return ctx


def investigate_rag_context(
    query: str,
    *,
    persona: str | None = None,
    settings: Settings | None = None,
    top_k: int | None = None,
    score_threshold: float | None = None,
    project: str | None = None,
    language: str | None = None,
    category: str | None = None,
    file_filter: str | None = None,
    max_chars: int = DEFAULT_RAG_INVESTIGATION_MAX_CHARS,
) -> RAGContext | None:
    """Execute a safe, non-blocking RAG investigation step to retrieve relevant context.

    A permanent error from an unknown or unserved embedding model turns RAG off for the rest of
    the process and logs one warning naming the model, the error and the fix. Transient errors
    (timeouts, connection resets, rate limits, 5xx) skip that lookup. After three consecutive
    transient failures, a circuit breaker pauses RAG lookups for 60 seconds; afterwards, a single
    lookup probes to resume lookups once healthy, and a probe that fails pauses them for 60 seconds
    more. Lookups that arrive concurrently while no lookup has succeeded wait for the probe's
    outcome, running concurrently on success and skipping on failure.

    Returns:
        RAGContext if the vector store is available and matching chunks are retrieved;
        None if RAG is disabled, stopped, paused, unreachable, or yields zero relevant results.
    """
    clean_query = query.strip()
    if not clean_query or _RAG_STOPPED.is_set() or _lookups_paused():
        return None

    st = settings or settings_mod.load_settings()
    if not st.ai.rag.enabled:
        return None

    cache_key = (
        f"{clean_query}|{persona}|{top_k}|{score_threshold}|{project}|"
        f"{language}|{category}|{file_filter}|{max_chars}"
    )
    now = time.monotonic()
    cached = _INVESTIGATION_CACHE.get(cache_key)
    if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    start_time = time.perf_counter()
    with trace_span(
        "ai.rag.investigation", _investigation_attributes(clean_query, persona, project)
    ) as r_span:
        try:
            ctx = _retrieve(
                st,
                clean_query[:DEFAULT_RAG_INVESTIGATION_MAX_QUERY_CHARS],
                persona=persona,
                top_k=top_k,
                score_threshold=score_threshold,
                project=project,
                language=language,
                category=category,
                file_filter=file_filter,
                max_chars=max_chars,
            )
        except Exception as exc:
            _report_lookup_failure(exc)
            ctx = None
        found = None if ctx is None else _recorded_results(ctx, r_span, clean_query, start_time)
    if ctx is not None:
        _INVESTIGATION_CACHE[cache_key] = (now, found)
    return found


def format_rag_investigation_for_prompt(
    ctx: RAGContext | None,
    heading: str = "Grounding Architecture & Code Context",
) -> str:
    """Format RAG investigation results into an XML-demarcated prompt block."""
    if not ctx or not ctx.has_results:
        return ""

    return f"\n\n### {heading}\n{ctx.formatted_text}\n"
