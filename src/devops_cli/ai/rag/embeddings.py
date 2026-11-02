"""Embeddings engine for Ollama and OpenAI-compatible providers."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import secrets
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import as_completed
from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

import httpx2
from cachetools import LRUCache
from pydantic_ai.embeddings import (
    EmbeddingModel,
    EmbeddingSettings,
)
from pydantic_ai.embeddings import (
    EmbeddingResult as PydanticEmbeddingResult,
)
from pydantic_ai.usage import RequestUsage

if TYPE_CHECKING:
    from devops_cli.ai.agents.embeddings import Embedder

from devops_cli.ai.client.network import gateway_caller_headers
from devops_cli.config.constants import (
    CONST_AI_BACKEND_HOST_UNKNOWN,
    CONST_AI_GATEWAY_PROVIDER,
    CONST_AI_GATEWAY_PROVIDERS,
    CONST_AIMD_ADDITIVE_INCREASE_STEP,
    CONST_AIMD_MULTIPLICATIVE_DECREASE_FACTOR,
    CONST_AIMD_SUCCESS_THRESHOLD,
    CONST_EMBEDDING_REPLY_EXCERPT_CHARS,
    CONST_KNOWN_EMBEDDING_DIMENSIONS,
    CONST_QWEN3_EMBEDDING_QUERY_PREFIX,
    CONST_RAG_MAX_CHUNK_TOKENS,
    CONST_SPEND_REQUEST_TYPE_EMBEDDING,
    CONST_VALKEY_EMBEDDING_PREFIX,
)
from devops_cli.config.defaults import (
    DEFAULT_DRY_RUN_EMBEDDING_DIMENSION,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RAG_EMBEDDING_BACKOFF_BASE_SECONDS,
    DEFAULT_RAG_EMBEDDING_BATCH_SIZE,
    DEFAULT_RAG_EMBEDDING_BATCH_TIMEOUT,
    DEFAULT_RAG_EMBEDDING_CACHE_SIZE,
    DEFAULT_RAG_EMBEDDING_INCREASE_COOLDOWN_SECONDS,
    DEFAULT_RAG_EMBEDDING_INCREASE_LATENCY_RATIO,
    DEFAULT_RAG_EMBEDDING_LATENCY_THRESHOLD_SECONDS,
    DEFAULT_RAG_EMBEDDING_MAX_BACKOFF_SECONDS,
    DEFAULT_RAG_EMBEDDING_MIN_BATCH_SIZE,
    DEFAULT_RAG_EMBEDDING_TIMEOUT,
    DEFAULT_VALKEY_EMBEDDING_TTL_SECONDS,
)
from devops_cli.config.settings import AIConfig, setting_default
from devops_cli.core import clock
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import configured_level
from devops_cli.lang import ERRORS
from devops_cli.telemetry import (
    ContextPropagatingThreadPoolExecutor as ThreadPoolExecutor,
)
from devops_cli.telemetry import trace_span
from devops_cli.telemetry.instruments import (
    EMBEDDING_CACHE_LOOKUPS_TOTAL,
    EMBEDDING_CACHE_SIZE,
    RAG_EMBEDDING_BATCH_RESIZES_TOTAL,
    RAG_EMBEDDING_BATCH_SIZE,
    emit,
)
from devops_cli.valkey.cache import ValkeyCacheTier, shared_cache_tier

logger = logging.getLogger(__name__)
# Retry jitter, drawn from the operating system's source: it guards nothing, and no seed is shared
# with other draws (#1538).
_JITTER = secrets.SystemRandom()

_DEFAULT_VALKEY: object = object()


def _calculate_backoff_delay(
    attempt: int,
    base: float = DEFAULT_RAG_EMBEDDING_BACKOFF_BASE_SECONDS,
    max_delay: float = DEFAULT_RAG_EMBEDDING_MAX_BACKOFF_SECONDS,
) -> float:
    """Compute exponential backoff delay with bounded jitter."""
    exp_delay = min(max_delay, base * (2**attempt))
    jitter = _JITTER.uniform(0.0, 0.1 * exp_delay)
    return float(round(exp_delay + jitter, 4))


# Shared in-memory cache for resolved (provider, model) -> dimension
_MODEL_DIMENSION_CACHE: dict[tuple[str, str], int] = {}


def reset_model_dimension_cache() -> None:
    """Clear the cached (provider, model) embedding dimensions."""
    _MODEL_DIMENSION_CACHE.clear()


# =============================================================================
# In-Memory SHA-256 Keyed Embedding LRU Cache
# =============================================================================


class _EmbeddingLRUCache:
    """Thread-safe in-memory LRU cache for embedding vectors, keyed by SHA-256 of (text + model)."""

    def __init__(self, maxsize: int = DEFAULT_RAG_EMBEDDING_CACHE_SIZE) -> None:
        self._store: LRUCache[str, list[float]] = LRUCache(maxsize=max(1, maxsize))
        self._lock = threading.Lock()
        self.hits: int = 0
        self.misses: int = 0

    def _key(self, text: str, model: str, *, is_query: bool = False) -> str:
        """Compute deterministic SHA-256 cache key for (model, text) tuple after prompt applied."""
        return hashlib.sha256(f"{model}\x00{text}".encode()).hexdigest()

    def get(self, text: str, model: str, *, is_query: bool = False) -> list[float] | None:
        """Return cached embedding vector or None on miss."""
        key = self._key(text, model, is_query=is_query)
        with self._lock:
            vector = self._store.get(key)
            if vector is not None:
                self.hits += 1
                return vector
            self.misses += 1
            return None

    def put(self, text: str, model: str, vector: list[float], *, is_query: bool = False) -> None:
        """Insert or update a cache entry, evicting the LRU entry when at capacity."""
        key = self._key(text, model, is_query=is_query)
        with self._lock:
            self._store[key] = vector

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        with self._lock:
            return len(self._store)

    def clear(self) -> None:
        """Evict all cached entries and reset counters."""
        with self._lock:
            self._store.clear()
            self.hits = 0
            self.misses = 0


class EmbeddingsError(DevOpsCLIError, RuntimeError):
    """Raised when embeddings generation fails across all endpoints.

    Embeddings come from a model or not at all: the message names the model, each endpoint or
    node that was asked, and the HTTP status or error it gave. No vector stands in for a failed
    request, because a search with one ranks unrelated chunks and an index stores them.

    This carries its own error code rather than reusing `LLM_INFERENCE_ERROR`. It is not an
    `LLMInferenceError` and exits with a different status, so sharing the code meant one
    machine-readable identifier mapped to two exit statuses -- a caller branching on the
    code could not predict which it would get.
    """

    error_code = "EMBEDDINGS_ERROR"

    def __init__(
        self,
        message: str,
        *,
        is_transient: bool = False,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.is_transient = is_transient
        DevOpsCLIError.__init__(
            self,
            message,
            exit_code=exit_code,
            details=details,
        )


def _ollama_embed_endpoint(base_url: str) -> str:
    """The batch embedding endpoint of one Ollama node."""
    return f"{base_url.rstrip('/')}/api/embed"


def _endpoint_text(url: str) -> str:
    """The URL as an error or a log line names it, without the userinfo that the client sends as
    Basic authentication: neither a password nor a user name alone, such as a token. A URL that
    httpx2 cannot read shows as `unknown`."""
    try:
        return str(httpx2.URL(url).copy_with(username=None, password=None))
    except ValueError, httpx2.InvalidURL:
        return CONST_AI_BACKEND_HOST_UNKNOWN


def _openai_reply_vectors(body: Any) -> Any:
    """The vectors of an OpenAI-compatible `/embeddings` reply, in input order."""
    items = sorted(body["data"], key=lambda item: item.get("index", 0))
    return [item["embedding"] for item in items]


def _ollama_reply_vectors(body: Any) -> Any:
    """The vectors of an Ollama `/api/embed` reply, batched or single."""
    return body["embeddings"] if "embeddings" in body else [body["embedding"]]


def _openai_reply_input_tokens(body: Any) -> Any:
    """The input tokens an OpenAI-compatible `/embeddings` reply says it embedded."""
    return body["usage"]["prompt_tokens"]


def _ollama_reply_input_tokens(body: Any) -> Any:
    """The input tokens an Ollama `/api/embed` reply says it embedded."""
    return body["prompt_eval_count"]


def _reply_input_tokens(
    res: httpx2.Response, parse: Callable[[Any], Any], texts: Sequence[str]
) -> int:
    """The input tokens a reply counted; the local count of the texts when it counted none.

    The local count is the one a chat reply without usage gets.
    """
    try:
        tokens = parse(res.json())
    except ValueError, KeyError, TypeError, AttributeError:
        tokens = None
    if isinstance(tokens, int) and not isinstance(tokens, bool) and tokens >= 0:
        return tokens
    from devops_cli.ai.context_budget import count_tokens

    return sum(count_tokens(text) for text in texts)


def embed_counting_tokens[T](embed: Callable[[], T]) -> tuple[T, int]:
    """Run `embed`, with the input tokens of the embedding requests it sent.

    The tokens are those each reply counted, as the spend ledger records them, so a pydantic-ai
    embedding result reports what the provider counted. Texts the cache answered add none.
    """
    from devops_cli.ai.spend.ledger import observe_llm_calls

    counted: list[int] = []

    def count(call: dict[str, Any]) -> None:
        if call.get("request_type") == CONST_SPEND_REQUEST_TYPE_EMBEDDING:
            counted.append(int(call.get("prompt_tokens") or 0))

    with observe_llm_calls(count):
        result = embed()
    return result, sum(counted)


def _parsed_vectors(res: httpx2.Response, parse: Callable[[Any], Any]) -> list[list[float]]:
    """The vectors `parse` finds in a reply's JSON body, or none for a body it cannot read."""
    try:
        vectors = parse(res.json())
    except ValueError, KeyError, TypeError, AttributeError:
        return []
    return vectors if isinstance(vectors, list) else []


def _reply_vectors(
    res: httpx2.Response, endpoint: str, expected: int, parse: Callable[[Any], Any]
) -> list[list[float]]:
    """One embedding reply's vectors; EmbeddingsError naming the endpoint for any other reply."""
    if res.status_code != 200:
        body = " ".join(res.text.split())[:CONST_EMBEDDING_REPLY_EXCERPT_CHARS]
        is_transient = res.status_code in (408, 429) or res.status_code >= 500
        raise EmbeddingsError(
            ERRORS.rag.embedding_endpoint_status.format(
                endpoint=_endpoint_text(endpoint), status=res.status_code, body=body
            ),
            is_transient=is_transient,
            details={"endpoint": _endpoint_text(endpoint), "status": res.status_code},
        )
    vectors = _parsed_vectors(res, parse)
    if len(vectors) != expected or not all(vectors):
        raise EmbeddingsError(
            ERRORS.rag.embedding_endpoint_malformed.format(
                endpoint=_endpoint_text(endpoint), received=len(vectors), expected=expected
            ),
            is_transient=False,
            details={
                "endpoint": _endpoint_text(endpoint),
                "received": len(vectors),
                "expected": expected,
            },
        )
    return vectors


def _endpoint_failure(endpoint: str, exc: Exception) -> str:
    """One endpoint's failed request, phrased for the EmbeddingsError that reports it."""
    if isinstance(exc, EmbeddingsError):
        return exc.message
    error = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
    return ERRORS.rag.embedding_endpoint_error.format(
        endpoint=_endpoint_text(endpoint), error=error
    )


def _is_transient_embedding_error(exc: Exception) -> bool:
    """Check if an exception is a transient network, timeout, or connection reset error."""
    if isinstance(exc, EmbeddingsError):
        return exc.is_transient
    if isinstance(exc, (httpx2.NetworkError, httpx2.TimeoutException)):
        return True
    if isinstance(
        exc, (ConnectionResetError, ConnectionRefusedError, BrokenPipeError, TimeoutError, OSError)
    ):
        return True
    err_str = str(exc).lower()
    return any(
        kw in err_str
        for kw in (
            "connection reset",
            "remote protocol error",
            "server disconnected",
            "broken pipe",
            "connection refused",
            "timed out",
            "timeout",
            "readerror",
            "connecterror",
            "errno 104",
        )
    )


def _compute_retry_delay(attempt: int, res: httpx2.Response | None = None) -> float:
    """Calculate exponential backoff delay with jitter, respecting Retry-After headers."""
    if res is not None and res.status_code == 429:
        retry_after = res.headers.get("retry-after")
        if retry_after and retry_after.isdigit():
            return min(30.0, float(retry_after))
    base = min(10.0, 0.5 * (2 ** (attempt - 1)))
    return float(base + _JITTER.uniform(0.1, 0.5))


def _probe_ollama_show_dimension(client: httpx2.Client, base_url: str, model: str) -> int | None:
    show_res = client.post(f"{base_url}/api/show", json={"model": model})
    if show_res.status_code != 200:
        return None
    model_info = show_res.json().get("model_info") or {}
    for key, val in model_info.items():
        if key.endswith(".embedding_length") and isinstance(val, int) and val > 0:
            return val
    return None


def _apply_model_prefix(text: str, model: str, *, is_query: bool = False) -> str:
    """Apply asymmetric task prompt prefix based on embedding model family."""
    m = model.lower().split(":")[0].strip()
    if m.startswith("bge-m3"):
        return text
    if m.startswith("qwen3-embedding") or "qwen3-embedding" in m:
        if not is_query:
            return text
        if text.startswith(CONST_QWEN3_EMBEDDING_QUERY_PREFIX):
            return text
        return f"{CONST_QWEN3_EMBEDDING_QUERY_PREFIX} {text}"
    if "nomic" in m:
        prefix = "search_query: " if is_query else "search_document: "
        return (
            text if text.startswith(("search_query: ", "search_document: ")) else f"{prefix}{text}"
        )
    if "e5" in m:
        prefix = "query: " if is_query else "passage: "
        return text if text.startswith(("query: ", "passage: ")) else f"{prefix}{text}"
    return text


def _count_batch_resize(batch_size: int, action: str) -> None:
    """Record the batch size after a change of it, and count the change by its action."""
    emit(RAG_EMBEDDING_BATCH_SIZE, float(batch_size))
    emit(RAG_EMBEDDING_BATCH_RESIZES_TOTAL, 1.0, {"action": action})


def _count_cache_lookups(*, memory: int, valkey: int, misses: int) -> None:
    """Add each lookup result that has texts to the embedding cache lookup counter."""
    for count, attributes in (
        (memory, {"result": "hit", "tier": "memory"}),
        (valkey, {"result": "hit", "tier": "valkey"}),
        (misses, {"result": "miss"}),
    ):
        if count:
            emit(EMBEDDING_CACHE_LOOKUPS_TOTAL, count, attributes)


@runtime_checkable
class EmbedderProtocol(Protocol):
    """Protocol for text embedding engines."""

    def embed_texts(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]: ...


_EMBEDDER_OVERRIDE: EmbedderProtocol | None = None


def install_embedder(override: EmbedderProtocol | None) -> None:
    """Install or remove an embedder override for tests."""
    global _EMBEDDER_OVERRIDE
    _EMBEDDER_OVERRIDE = override


def reset_embedder() -> None:
    """Reset the embedder override."""
    global _EMBEDDER_OVERRIDE
    _EMBEDDER_OVERRIDE = None


def get_embedder_override() -> EmbedderProtocol | None:
    """Return the active embedder override, if any."""
    return _EMBEDDER_OVERRIDE


def create_embedder(ai_config: AIConfig | None = None, **kwargs: Any) -> EmbedderProtocol:
    """Build the EmbeddingsEngine from settings or the given AIConfig."""
    if _EMBEDDER_OVERRIDE is not None:
        return _EMBEDDER_OVERRIDE
    return EmbeddingsEngine(ai_config=ai_config, **kwargs)


class EmbeddingsEngine:
    """Generates dense vector embeddings using Ollama or OpenAI endpoints."""

    def __init__(
        self,
        ai_config: AIConfig | None = None,
        *,
        api_key: str | None = None,
        timeout: float | None = None,
        cache_size: int = DEFAULT_RAG_EMBEDDING_CACHE_SIZE,
        valkey_client: Any = _DEFAULT_VALKEY,
        batch_size: int = DEFAULT_RAG_EMBEDDING_BATCH_SIZE,
    ) -> None:
        if ai_config is None:
            try:
                from devops_cli.config.settings import load_settings

                base_config = load_settings().ai
            except Exception:
                base_config = AIConfig()
        else:
            base_config = ai_config

        self.ai_config = base_config.for_task("embedding")
        self.api_key = api_key
        if self.api_key is None and self.ai_config.provider.lower() in (
            "openai",
            "copilot",
            CONST_AI_GATEWAY_PROVIDER,
        ):
            from devops_cli.config.os_keyring import get_keyring_secret

            self.api_key = os.environ.get("OPENAI_API_KEY") or get_keyring_secret("ai_api_key")
        task_timeout = (
            getattr(getattr(base_config.tasks, "embedding", None), "timeout", None)
            or self.ai_config.timeout
        )
        configured_timeout = timeout if timeout is not None else task_timeout
        # The read timeout of one direct Ollama node, and of one batch at the gateway or an
        # OpenAI-compatible API. A configured timeout sets both.
        self.timeout = min(float(configured_timeout or DEFAULT_RAG_EMBEDDING_TIMEOUT), 120.0)
        self.batch_timeout = min(
            float(configured_timeout or DEFAULT_RAG_EMBEDDING_BATCH_TIMEOUT), 120.0
        )
        task_model = getattr(getattr(base_config.tasks, "embedding", None), "model", None)
        self.model = task_model or setting_default("ai.tasks.embedding.model")
        self._dimension: int | None = None
        self._cache = _EmbeddingLRUCache(maxsize=cache_size)
        self._l2 = self._init_cache_tier(valkey_client)
        self._configured_batch_size = max(DEFAULT_RAG_EMBEDDING_MIN_BATCH_SIZE, batch_size)
        self._current_batch_size = self._configured_batch_size
        self._consecutive_successes: int = 0
        # The monotonic time of the last change of the batch size; no change yet, so no cooldown.
        self._batch_size_changed_at = float("-inf")
        self._batch_lock = threading.Lock()
        self._http_client: httpx2.Client | None = None
        self._http_lock = threading.Lock()

    def _new_http_client(self, timeout: httpx2.Timeout) -> httpx2.Client:
        """A client at the configured level of the engine's AI configuration.

        The URLs come from that configuration: loopback, or private when `ai.allow_private_network`
        is set. The connect checks each address, and refuses one that the level does not admit.
        A client for the gateway names devops-cli and its service as the caller (#1668).
        """
        level = configured_level(self.ai_config)
        if self._is_gateway_provider():
            return new_http_client(level=level, timeout=timeout, headers=gateway_caller_headers())
        return new_http_client(level=level, timeout=timeout)

    def _get_http_client(self) -> httpx2.Client:
        """The one HTTP client of the engine's batches, made at the first request.

        Batches in parallel threads send through the same connection pool. When a request fails,
        the pool closes the connection of that request, and a retry gets a new connection. Thus
        no batch closes the client while other batches use it: only `close` closes it.
        """
        with self._http_lock:
            if self._http_client is None:
                client_timeout = httpx2.Timeout(self.batch_timeout, connect=2.0)
                self._http_client = self._new_http_client(client_timeout)
            return self._http_client

    def close(self) -> None:
        """Close the HTTP client of the engine's batches, after the last batch."""
        with self._http_lock:
            client, self._http_client = self._http_client, None
        if client is not None:
            client.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _is_gateway_provider(self) -> bool:
        """Check if active AI provider or task is routed via LLM gateway."""
        provider = self.ai_config.provider.lower()
        return (
            provider == CONST_AI_GATEWAY_PROVIDER
            or provider in CONST_AI_GATEWAY_PROVIDERS
            or getattr(self.ai_config, "gateway_enabled", False)
        )

    def _init_cache_tier(self, valkey_client: Any) -> ValkeyCacheTier | None:
        """The Valkey tier of the cache: over `valkey_client`, or else the tier of the process.

        The tier opens no connection here. When Valkey does not answer, the first read or write
        opens the circuit breaker of the tier, and the tier tries again after the cooldown.
        """
        if valkey_client is None:
            return None
        if valkey_client is not _DEFAULT_VALKEY:
            return ValkeyCacheTier(valkey_client)
        return shared_cache_tier()

    def _apply_aimd_decrease(self, sent_size: int) -> None:
        """Halve the batch size after a slow or timed-out batch of `sent_size` texts (AIMD).

        A batch that holds more texts than the size in use was sent before an earlier decrease,
        and that decrease applies to it too. So only a batch of the size in use or smaller halves
        the size, and the parallel batches of one size halve it once.
        """
        with self._batch_lock:
            if sent_size > self._current_batch_size:
                return
            self._consecutive_successes = 0
            self._batch_size_changed_at = clock.monotonic()
            self._current_batch_size = max(
                DEFAULT_RAG_EMBEDDING_MIN_BATCH_SIZE,
                int(self._current_batch_size * CONST_AIMD_MULTIPLICATIVE_DECREASE_FACTOR),
            )
            _count_batch_resize(self._current_batch_size, "multiplicative_decrease")
            logger.debug(
                "AIMD multiplicative decrease applied: batch_size=%d (configured=%d)",
                self._current_batch_size,
                self._configured_batch_size,
            )

    def _apply_aimd_increase(self) -> None:
        """Count a fast batch, and add to the batch size after enough fast batches in a row (AIMD).

        A fast batch counts only below the configured size and after the cooldown that each change
        of the size starts.
        """
        with self._batch_lock:
            now = clock.monotonic()
            in_cooldown = (
                now - self._batch_size_changed_at < DEFAULT_RAG_EMBEDDING_INCREASE_COOLDOWN_SECONDS
            )
            if in_cooldown or self._current_batch_size >= self._configured_batch_size:
                return
            self._consecutive_successes += 1
            if self._consecutive_successes < CONST_AIMD_SUCCESS_THRESHOLD:
                return
            self._consecutive_successes = 0
            self._batch_size_changed_at = now
            self._current_batch_size = min(
                self._configured_batch_size,
                self._current_batch_size + CONST_AIMD_ADDITIVE_INCREASE_STEP,
            )
            _count_batch_resize(self._current_batch_size, "additive_increase")
            logger.debug(
                "AIMD additive increase applied: batch_size=%d (configured=%d)",
                self._current_batch_size,
                self._configured_batch_size,
            )

    def _record_batch_latency(self, elapsed: float, sent_size: int) -> None:
        """Adapt the batch size to the latency of one batch of `sent_size` texts (AIMD).

        A batch slower than the threshold halves the size. A batch that takes at most the margin
        share of the threshold is fast. A batch between the two is not fast, so it stops the run
        of fast batches.
        """
        if elapsed > DEFAULT_RAG_EMBEDDING_LATENCY_THRESHOLD_SECONDS:
            self._apply_aimd_decrease(sent_size)
        elif elapsed <= (
            DEFAULT_RAG_EMBEDDING_LATENCY_THRESHOLD_SECONDS
            * DEFAULT_RAG_EMBEDDING_INCREASE_LATENCY_RATIO
        ):
            self._apply_aimd_increase()
        else:
            with self._batch_lock:
                self._consecutive_successes = 0

    def _valkey_key(self, text: str, model: str, *, is_query: bool = False) -> str:
        """Generate namespaced deterministic Valkey cache key; hashes text after prompt is applied."""
        sent_text = self._apply_model_prefix([text], is_query=is_query)[0]
        h = hashlib.sha256(f"{model}\x00{sent_text}".encode()).hexdigest()
        return f"{CONST_VALKEY_EMBEDDING_PREFIX}:{h}"

    def _get_valkey_embedding(
        self, text: str, model: str, *, is_query: bool = False
    ) -> list[float] | None:
        """The cached embedding vector from the Valkey L2 cache; None for a miss or a bad entry."""
        if self._l2 is None:
            return None
        raw = self._l2.get(self._valkey_key(text, model, is_query=is_query))
        if not raw:
            return None
        try:
            data = json.loads(raw)
            vector = [float(x) for x in data] if isinstance(data, list) else []
        except (ValueError, TypeError) as exc:
            logger.debug("A cached embedding in Valkey is not a vector: %s", exc)
            return None
        return vector or None

    def _set_valkey_embedding(
        self, text: str, model: str, vector: list[float], *, is_query: bool = False
    ) -> None:
        """Store embedding vector into Valkey L2 cache with configured TTL."""
        if self._l2 is not None:
            key = self._valkey_key(text, model, is_query=is_query)
            self._l2.set(key, json.dumps(vector), ex=DEFAULT_VALKEY_EMBEDDING_TTL_SECONDS)

    def _partition_with_valkey_l2(
        self, texts: list[str], *, is_query: bool = False
    ) -> tuple[dict[int, list[float]], list[int], list[str]]:
        """Partition texts through L1 in-memory cache and L2 Valkey chunk cache.

        Each text counts once on `devops_cli_embedding_cache_lookups_total`: as a hit of the tier
        that held it, or as a miss.
        """
        cached, miss_indices, miss_texts = self._partition_cache(texts, is_query=is_query)
        memory_hits = len(cached)
        if miss_texts and self._l2 is not None:
            l1_miss_indices, l1_miss_texts = miss_indices, miss_texts
            miss_indices, miss_texts = [], []
            for idx, text in zip(l1_miss_indices, l1_miss_texts, strict=True):
                v_hit = self._get_valkey_embedding(text, self.model, is_query=is_query)
                if v_hit is not None:
                    cached[idx] = v_hit
                    self._cache.put(text, self.model, v_hit, is_query=is_query)
                else:
                    miss_indices.append(idx)
                    miss_texts.append(text)

        _count_cache_lookups(
            memory=memory_hits, valkey=len(cached) - memory_hits, misses=len(miss_texts)
        )
        return cached, miss_indices, miss_texts

    @property
    def dimension(self) -> int:
        """Return dynamically resolved or observed vector dimension for the active model."""
        if self._dimension is not None:
            return self._dimension
        cache_key = (self.ai_config.provider.lower(), self.model)
        if cache_key in _MODEL_DIMENSION_CACHE:
            self._dimension = _MODEL_DIMENSION_CACHE[cache_key]
            return self._dimension
        resolved = self._probe_dimension()
        if resolved is not None:
            self._record_dimension(resolved)
            return resolved
        model_clean = self.model.lower().split(":")[0].strip()
        for known_name, known_dim in CONST_KNOWN_EMBEDDING_DIMENSIONS.items():
            if known_name in model_clean:
                self._record_dimension(known_dim)
                return known_dim
        return DEFAULT_DRY_RUN_EMBEDDING_DIMENSION

    def _record_dimension(self, dim: int) -> None:
        """Store observed model dimension in instance and module cache."""
        if dim > 0:
            self._dimension = dim
            _MODEL_DIMENSION_CACHE[(self.ai_config.provider.lower(), self.model)] = dim

    def _get_ollama_urls(self) -> list[str]:
        """Resolve candidate Ollama endpoint URLs."""
        urls = (
            getattr(self.ai_config, "get_ollama_urls", None)
            or self.ai_config.ollama_urls
            or ([self.ai_config.api_base_url] if self.ai_config.api_base_url else [])
        )
        return [u for u in urls if u]

    def _probe_dimension(self) -> int | None:
        """Dynamically probe active provider to determine the model's actual embedding dimension."""
        provider = self.ai_config.provider.lower()
        if provider in ("openai", "copilot") or self._is_gateway_provider():
            return self._probe_openai_dimension()
        if provider == "ollama" or (not provider and self.ai_config.ollama_urls):
            return self._probe_ollama_dimension()
        return None

    def _probe_ollama_dimension(self) -> int | None:
        """Probe Ollama nodes for actual embedding vector dimension or model architecture metadata."""
        urls = self._get_ollama_urls()
        client_timeout = httpx2.Timeout(min(self.timeout, 5.0), connect=min(self.timeout, 2.0))
        for raw_url in urls:
            base_url = raw_url.rstrip("/")
            dim = self._probe_single_ollama_url(base_url, client_timeout)
            if dim is not None:
                return dim
        return None

    def _probe_single_ollama_url(self, base_url: str, timeout: httpx2.Timeout) -> int | None:
        try:
            with self._new_http_client(timeout) as client:
                return self._parse_ollama_node_metadata(client, base_url)
        except Exception as exc:
            logger.debug("Probing Ollama node %s failed: %s", _endpoint_text(base_url), exc)
            return None

    def _parse_ollama_node_metadata(self, client: httpx2.Client, base_url: str) -> int | None:
        return self._probe_ollama_embed_dimension(client, base_url) or _probe_ollama_show_dimension(
            client, base_url, self.model
        )

    @property
    def _ollama_num_ctx(self) -> int:
        """The context length to send with direct Ollama embedding requests."""
        return getattr(self.ai_config, "num_ctx", None) or CONST_RAG_MAX_CHUNK_TOKENS

    def _ollama_embed_payload(self, texts: Sequence[str]) -> dict[str, Any]:
        """The JSON body of an Ollama /api/embed request, with the context length."""
        return {
            "model": self.model,
            "input": list(texts),
            "options": {"num_ctx": self._ollama_num_ctx},
        }

    def _probe_ollama_embed_dimension(self, client: httpx2.Client, base_url: str) -> int | None:
        """The dimension of one probe text's vector; the probe is recorded like any request."""
        endpoint = _ollama_embed_endpoint(base_url)
        texts = ["probe"]
        started = time.monotonic()
        res = client.post(endpoint, json=self._ollama_embed_payload(texts))
        seconds = time.monotonic() - started
        if res.status_code != 200:
            return None
        data = res.json()
        embs = data.get("embeddings") or ([data["embedding"]] if "embedding" in data else None)
        if not (embs and embs[0]):
            return None
        self._record_embedding_request(
            res, endpoint, self.model, texts, _ollama_reply_input_tokens, seconds
        )
        return len(embs[0])

    def _record_embedding_request(
        self,
        res: httpx2.Response,
        endpoint: str,
        model: str,
        texts: Sequence[str],
        parse_tokens: Callable[[Any], Any],
        seconds: float,
    ) -> None:
        """Record one answered embedding request in the spend ledger and the AI usage counters.

        The provider and server are those a chat call names, so both are local or hosted alike;
        a gateway's headers name the backend and the deployment model that served the request.
        """
        from devops_cli.ai.client.models import origin_label
        from devops_cli.ai.client.network import extract_served_by, extract_served_model
        from devops_cli.ai.spend import resolve_spend_stage, track_request_spend

        provider = self.ai_config.provider
        server = origin_label(httpx2.URL(endpoint).origin)
        track_request_spend(
            provider=provider,
            model=model,
            server=server,
            backend_info=f"{provider} ({server})",
            served_by=extract_served_by(res.headers),
            served_model=extract_served_model(res.headers),
            prompt_tokens=_reply_input_tokens(res, parse_tokens, texts),
            request_type=CONST_SPEND_REQUEST_TYPE_EMBEDDING,
            duration_seconds=seconds,
            stage=resolve_spend_stage(None, self.ai_config.task_name),
        )

    def _probe_openai_dimension(self) -> int | None:
        """Probe OpenAI-compatible endpoint for actual embedding vector dimension."""
        base_url = self._openai_compatible_base_url().rstrip("/")
        try:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            endpoint = (
                f"{base_url}/embeddings"
                if base_url.endswith("/v1")
                else f"{base_url}/v1/embeddings"
            )
            client_timeout = httpx2.Timeout(min(self.timeout, 5.0), connect=min(self.timeout, 2.0))
            texts = ["probe"]
            with self._new_http_client(client_timeout) as client:
                started = time.monotonic()
                res = client.post(
                    endpoint,
                    headers=headers,
                    json={"model": self.model, "input": texts},
                )
                seconds = time.monotonic() - started
                if res.status_code == 200:
                    data = res.json()
                    items = data.get("data", [])
                    if items and "embedding" in items[0]:
                        self._record_embedding_request(
                            res, endpoint, self.model, texts, _openai_reply_input_tokens, seconds
                        )
                        return len(items[0]["embedding"])
        except Exception as exc:
            logger.debug("Probing OpenAI endpoint failed: %s", exc)
        return None

    def _partition_cache(
        self, texts: list[str], *, is_query: bool = False
    ) -> tuple[dict[int, list[float]], list[int], list[str]]:
        cached: dict[int, list[float]] = {}
        miss_indices: list[int] = []
        miss_texts: list[str] = []
        for idx, text in enumerate(texts):
            hit = self._cache.get(text, self.model, is_query=is_query)
            if hit is not None:
                cached[idx] = hit
            else:
                miss_indices.append(idx)
                miss_texts.append(text)
        return cached, miss_indices, miss_texts

    def _dispatch_embed(self, prefixed_miss: list[str]) -> list[list[float]]:
        """Embed with the configured provider; raise EmbeddingsError when none is configured."""
        provider = self.ai_config.provider.lower()
        if provider in ("openai", "copilot") or self._is_gateway_provider():
            return self._embed_openai(prefixed_miss)
        if provider == "ollama" or (not provider and self.ai_config.ollama_urls):
            return self._embed_ollama(prefixed_miss)
        if self.ai_config.ollama_urls:
            return self._embed_ollama(prefixed_miss)
        raise EmbeddingsError(
            ERRORS.rag.embedding_no_provider.format(
                model=self.model, provider=self.ai_config.provider
            ),
            details={"model": self.model, "provider": self.ai_config.provider},
        )

    def _embedding_error(
        self, failures: list[str], *, model: str | None = None, is_transient: bool = False
    ) -> EmbeddingsError:
        """The EmbeddingsError for a request no endpoint answered with embeddings."""
        name = model or self.model
        return EmbeddingsError(
            ERRORS.rag.embedding_failed.format(model=name, failures="; ".join(failures)),
            is_transient=is_transient,
            details={"model": name, "provider": self.ai_config.provider, "failures": failures},
        )

    def embed_texts(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        """Generate vector embeddings for a list of text strings with LRU cache acceleration."""
        if not texts:
            return []

        with trace_span(
            "ai.rag.embed_texts",
            attributes={
                "rag.texts_count": len(texts),
                "rag.model": str(self.model),
                "rag.provider": str(self.ai_config.provider),
                "rag.is_query": is_query,
            },
        ):
            prefixed_texts = self._apply_model_prefix(texts, is_query=is_query)
            cached, miss_indices, miss_texts = self._partition_with_valkey_l2(
                prefixed_texts, is_query=is_query
            )
            emit(EMBEDDING_CACHE_SIZE, self._cache.size)

            if miss_texts:
                fresh = self._dispatch_embed(miss_texts)
                if len(fresh) != len(miss_texts):
                    raise EmbeddingsError(
                        f"Embedding provider returned {len(fresh)} vectors for {len(miss_texts)} texts",
                        details={"expected": len(miss_texts), "received": len(fresh)},
                    )
                self._populate_fresh_embeddings(
                    cached, miss_indices, miss_texts, fresh, is_query=is_query
                )

            return [cached[i] for i in range(len(texts))]

    def _populate_fresh_embeddings(
        self,
        cached: dict[int, list[float]],
        miss_indices: list[int],
        miss_texts: list[str],
        fresh: Sequence[list[float]],
        *,
        is_query: bool = False,
    ) -> None:
        """Store fresh embeddings into in-memory L1 and Valkey L2."""
        for miss_idx, sent_text, vector in zip(miss_indices, miss_texts, fresh, strict=True):
            self._cache.put(sent_text, self.model, vector, is_query=is_query)
            self._set_valkey_embedding(sent_text, self.model, vector, is_query=is_query)
            cached[miss_idx] = vector

    def embed_query(self, text: str) -> list[float]:
        """Generate vector embedding for a single search query with LRU cache acceleration."""
        results = self.embed_texts([text], is_query=True)
        if not results:
            raise EmbeddingsError(f"Failed to generate embedding for query: {text[:50]}")
        return results[0]

    def _apply_model_prefix(self, texts: list[str], *, is_query: bool = False) -> list[str]:
        """Apply asymmetric task prefix based on embedding model architecture."""
        return [_apply_model_prefix(t, self.model, is_query=is_query) for t in texts]

    def _query_ollama_node_batch(self, base_url: str, batch_texts: list[str]) -> list[list[float]]:
        """Embed a batch on one Ollama node; raise when the node refuses, fails or misanswers."""
        from devops_cli.ai.client.models import origin_span_attributes
        from devops_cli.http.urls import get_url_origin

        endpoint = _ollama_embed_endpoint(base_url)
        with trace_span(
            "ai.rag.ollama_embed_batch",
            attributes={
                **origin_span_attributes(get_url_origin(endpoint)),
                "rag.batch_size": len(batch_texts),
                "rag.model": str(self.model),
            },
        ):
            start_t = clock.monotonic()
            client_timeout = httpx2.Timeout(self.timeout, connect=min(self.timeout, 2.0))
            with self._new_http_client(client_timeout) as client:
                res = client.post(endpoint, json=self._ollama_embed_payload(batch_texts))
            seconds = clock.monotonic() - start_t
            embs = _reply_vectors(res, endpoint, len(batch_texts), _ollama_reply_vectors)
            self._record_embedding_request(
                res, endpoint, self.model, batch_texts, _ollama_reply_input_tokens, seconds
            )
            self._record_batch_latency(seconds, len(batch_texts))
            self._record_dimension(len(embs[0]))
            return embs

    def _try_single_candidate(
        self, base_url: str, batch_texts: list[str], attempt: int
    ) -> list[list[float]]:
        """Embed a batch on one node, backing off and halving the batch size after a timeout."""
        try:
            return self._query_ollama_node_batch(base_url.rstrip("/"), batch_texts)
        except (httpx2.TimeoutException, TimeoutError) as exc:
            self._apply_aimd_decrease(len(batch_texts))
            delay = _calculate_backoff_delay(attempt)
            logger.debug(
                "Ollama timeout on %s, backoff %.2fs: %s", _endpoint_text(base_url), delay, exc
            )
            time.sleep(delay)
            raise

    def _try_query_candidate_nodes(
        self, urls: list[str], batch_texts: list[str]
    ) -> list[list[float]]:
        """Embed a batch on the first node that answers; raise naming each node's failure."""
        failures: list[str] = []
        is_transient_flags: list[bool] = []
        for attempt, base_url in enumerate(urls):
            try:
                return self._try_single_candidate(base_url, batch_texts, attempt)
            except Exception as exc:
                logger.debug("Ollama embedding on %s failed: %s", _endpoint_text(base_url), exc)
                failures.append(_endpoint_failure(_ollama_embed_endpoint(base_url), exc))
                is_transient_flags.append(_is_transient_embedding_error(exc))
        all_transient = bool(is_transient_flags and all(is_transient_flags))
        raise self._embedding_error(failures, is_transient=all_transient)

    def _embed_batch_with_subdivision(
        self, urls: list[str], batch_texts: list[str]
    ) -> list[list[float]]:
        """Embed a batch, halving it while every node fails, until a single text fails."""
        if not batch_texts:
            return []
        try:
            return self._try_query_candidate_nodes(urls, batch_texts)
        except EmbeddingsError:
            if len(batch_texts) == 1:
                raise
        mid = len(batch_texts) // 2
        left = self._embed_batch_with_subdivision(urls, batch_texts[:mid])
        return left + self._embed_batch_with_subdivision(urls, batch_texts[mid:])

    def _embed_ollama(self, texts: list[str]) -> list[list[float]]:
        """Compute Ollama embeddings with dynamic batch sizing and multi-node distribution."""
        urls = self._get_ollama_urls()
        if not urls:
            raise EmbeddingsError(
                ERRORS.rag.embedding_no_ollama_urls.format(
                    model=self.model, provider=self.ai_config.provider
                ),
                details={"model": self.model, "provider": self.ai_config.provider},
            )
        chunk_batch_size = max(
            DEFAULT_RAG_EMBEDDING_MIN_BATCH_SIZE,
            self._current_batch_size,
        )
        max_parallel = max(1, min(16, getattr(self.ai_config, "ollama_max_parallel", 2)))

        batches = [texts[i : i + chunk_batch_size] for i in range(0, len(texts), chunk_batch_size)]

        def _embed_single_batch(batch_idx: int) -> list[list[float]]:
            start = batch_idx % len(urls)
            return self._embed_batch_with_subdivision(
                urls[start:] + urls[:start], batches[batch_idx]
            )

        total_workers = min(len(batches), max(1, len(urls) * max_parallel))
        if total_workers <= 1:
            return [vec for idx in range(len(batches)) for vec in _embed_single_batch(idx)]

        results: dict[int, list[list[float]]] = {}
        with ThreadPoolExecutor(max_workers=total_workers) as executor:
            futures = {
                executor.submit(_embed_single_batch, idx): idx for idx in range(len(batches))
            }
            try:
                for future in as_completed(futures):
                    results[futures[future]] = future.result()
            except EmbeddingsError:
                # One batch failing on every node fails the call; the queued ones would only
                # send more requests the same nodes refuse.
                executor.shutdown(wait=False, cancel_futures=True)
                raise
        return [vec for idx in range(len(batches)) for vec in results[idx]]

    def _openai_compatible_base_url(self) -> str:
        """Resolve the embeddings base URL: gateway_url for gateway providers, otherwise api_base_url or OpenAI."""
        if self._is_gateway_provider():
            gw_url = self.ai_config.gateway_url or self.ai_config.api_base_url
            if not gw_url:
                raise ConfigurationError(
                    "No AI gateway URL configured. Run: devops config set ai.gateway_url <url>",
                    key="ai.gateway_url",
                )
            return gw_url
        if self.ai_config.api_base_url:
            return self.ai_config.api_base_url
        import openai

        return str(openai.OpenAI(api_key="none").base_url).rstrip("/")

    def _resolve_openai_endpoint_and_model(
        self, base_url: str, is_gateway: bool
    ) -> tuple[str, str]:
        endpoint = (
            f"{base_url}/embeddings" if base_url.endswith("/v1") else f"{base_url}/v1/embeddings"
        )
        model = self.model
        if not is_gateway and model in ("all-minilm", "qwen3-embedding:0.6b"):
            model = "text-embedding-3-small"
        return endpoint, model

    def _post_openai_batch_with_retry(
        self, endpoint: str, headers: dict[str, str], model: str, batch: list[str]
    ) -> tuple[httpx2.Response, float]:
        """Send one embedding batch request with exponential backoff on transient network errors.

        Returns the last reply and the seconds its request took, without the earlier attempts.
        """
        max_retries = max(
            1, getattr(self.ai_config, "max_retries", DEFAULT_MAX_RETRIES) or DEFAULT_MAX_RETRIES
        )
        last_exc: Exception | None = None

        for attempt in range(1, max_retries + 1):
            client = self._get_http_client()
            try:
                started = time.monotonic()
                res = client.post(endpoint, headers=headers, json={"model": model, "input": batch})
                if res.status_code in (429, 502, 503, 504) and attempt < max_retries:
                    delay = _compute_retry_delay(attempt, res)
                    logger.warning(
                        "Transient HTTP %d from %s (attempt %d/%d). Retrying in %.2fs...",
                        res.status_code,
                        _endpoint_text(endpoint),
                        attempt,
                        max_retries,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                return res, time.monotonic() - started
            except Exception as exc:
                last_exc = exc
                if not _is_transient_embedding_error(exc) or attempt >= max_retries:
                    raise
                # The pool closed the connection that failed, and the retry gets a new one. The
                # client stays open for the batches in parallel with this one.
                if isinstance(exc, (httpx2.TimeoutException, TimeoutError)):
                    self._apply_aimd_decrease(len(batch))
                delay = _compute_retry_delay(attempt)
                logger.warning(
                    "Transient network error in embedding %s (attempt %d/%d): %s. Retrying in %.2fs...",
                    _endpoint_text(endpoint),
                    attempt,
                    max_retries,
                    exc,
                    delay,
                )
                time.sleep(delay)

        if last_exc:
            raise last_exc
        raise EmbeddingsError(f"Failed to post embedding request to {_endpoint_text(endpoint)}")

    def _embed_single_openai_batch(
        self, endpoint: str, headers: dict[str, str], model: str, batch: list[str]
    ) -> list[list[float]]:
        """Embed one batch; a batch the endpoint answers is recorded once, after any retry."""
        res, seconds = self._post_openai_batch_with_retry(endpoint, headers, model, batch)
        vectors = _reply_vectors(res, endpoint, len(batch), _openai_reply_vectors)
        self._record_embedding_request(
            res, endpoint, model, batch, _openai_reply_input_tokens, seconds
        )
        return vectors

    def _embed_parallel_openai_batches(
        self,
        endpoint: str,
        headers: dict[str, str],
        model: str,
        batches: list[list[str]],
        is_gateway: bool,
    ) -> list[list[float]]:
        concurrency = 4
        if is_gateway:
            gw_conc = getattr(self.ai_config, "gateway_concurrency", {})
            concurrency = int(gw_conc.get("embedding", 4) if isinstance(gw_conc, dict) else 4)
        max_workers = min(len(batches), max(1, min(16, concurrency)))
        results: dict[int, list[list[float]]] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._embed_single_openai_batch, endpoint, headers, model, b): idx
                for idx, b in enumerate(batches)
            }
            try:
                for future in as_completed(futures):
                    results[futures[future]] = future.result()
            except Exception:
                executor.shutdown(wait=False, cancel_futures=True)
                raise
        return [vec for idx in range(len(batches)) for vec in results[idx]]

    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        """Query the OpenAI-compatible /v1/embeddings API (OpenAI or the LLM gateway).

        Raises EmbeddingsError naming the model, the endpoint and the HTTP status or error.
        """
        base_url = self._openai_compatible_base_url().rstrip("/")
        is_gateway = self._is_gateway_provider()
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        endpoint, model = self._resolve_openai_endpoint_and_model(base_url, is_gateway)
        try:
            batch_size = max(DEFAULT_RAG_EMBEDDING_MIN_BATCH_SIZE, self._current_batch_size)
            batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]
            if len(batches) <= 1:
                embs = self._embed_single_openai_batch(endpoint, headers, model, texts)
            else:
                embs = self._embed_parallel_openai_batches(
                    endpoint, headers, model, batches, is_gateway
                )
        except (DevOpsCLIError, httpx2.HTTPError) as exc:
            is_transient = _is_transient_embedding_error(exc)
            raise self._embedding_error(
                [_endpoint_failure(endpoint, exc)], model=model, is_transient=is_transient
            ) from exc
        if embs:
            self._record_dimension(len(embs[0]))
        return embs

    def to_embedder(self) -> Embedder:
        """Create a standard Pydantic AI Embedder backed by this engine."""
        from devops_cli.ai.agents.embeddings import Embedder, EngineEmbeddingModel

        model = EngineEmbeddingModel(
            self, model_name=self.model, provider_name=self.ai_config.provider
        )
        return Embedder(model=model)


class OllamaEmbeddingModel(EmbeddingModel):
    """Pydantic AI EmbeddingModel implementation for distributed multi-node Ollama clusters."""

    def __init__(
        self,
        model_name: str | None = None,
        *,
        engine: EmbeddingsEngine | None = None,
        ai_config: AIConfig | None = None,
        dimensions: int | None = None,
    ) -> None:
        if ai_config is None:
            try:
                from devops_cli.config.settings import load_settings

                resolved_cfg = load_settings().ai.model_copy(deep=True)
            except Exception:
                resolved_cfg = AIConfig()
        else:
            resolved_cfg = ai_config.model_copy(deep=True)

        # A model that is not given is the embedding task's model of the settings.
        task_model = getattr(getattr(resolved_cfg.tasks, "embedding", None), "model", None)
        resolved_model = model_name or task_model or setting_default("ai.tasks.embedding.model")
        resolved_cfg.tasks.embedding.model = resolved_model

        self._model_name = resolved_model
        self.engine = engine or EmbeddingsEngine(resolved_cfg)
        if dimensions is not None:
            self.engine._dimension = dimensions

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def system(self) -> str:
        return "ollama"

    def __str__(self) -> str:
        return self._model_name

    def __repr__(self) -> str:
        return f"OllamaEmbeddingModel({self._model_name!r})"

    async def embed(
        self,
        inputs: str | Sequence[str],
        *,
        input_type: Literal["query", "document"],
        settings: EmbeddingSettings | None = None,
    ) -> PydanticEmbeddingResult:
        texts = [inputs] if isinstance(inputs, str) else list(inputs)
        is_query = input_type == "query"
        vectors, input_tokens = await asyncio.to_thread(
            embed_counting_tokens, partial(self.engine.embed_texts, texts, is_query=is_query)
        )
        return PydanticEmbeddingResult(
            vectors,
            inputs=texts,
            input_type=input_type,
            model_name=self._model_name,
            provider_name="ollama",
            timestamp=datetime.now(UTC),
            usage=RequestUsage(input_tokens=input_tokens),
        )
