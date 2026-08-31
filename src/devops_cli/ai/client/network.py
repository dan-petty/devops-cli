"""Network validation, limited JSON parsing, and concurrency coordination."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx2

from devops_cli.ai.client.models import AIClientError

logger = logging.getLogger(__name__)

ALLOW_PRIVATE_NETWORK_ENV = "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK"
active_ollama_requests: dict[str, int] = {}
ollama_active_lock = threading.Lock()
ollama_semaphores: dict[str, threading.Semaphore] = {}
ollama_sem_lock = threading.Lock()
global_ollama_url_index: int = 0
global_ollama_url_lock = threading.Lock()


def load_and_increment_rr_index(n: int) -> int:
    """Atomically fetch and increment the round-robin server index across runs."""
    global global_ollama_url_index
    if n <= 1:
        return 0
    uid = os.getuid() if hasattr(os, "getuid") else 0
    state_file = Path(tempfile.gettempdir()) / f"devops_cli_ollama_rr_{uid}"
    with global_ollama_url_lock:
        idx = global_ollama_url_index
        try:
            if state_file.exists():
                idx = int(state_file.read_text(encoding="utf-8").strip())
        except Exception:
            pass
        next_idx = (idx + 1) % n
        global_ollama_url_index = next_idx
        try:
            state_file.write_text(str(next_idx), encoding="utf-8")
        except Exception:
            pass
        return idx % n


def get_ollama_semaphore(url: str, max_parallel: int) -> threading.Semaphore:
    with ollama_sem_lock:
        if (
            url not in ollama_semaphores
            or getattr(ollama_semaphores[url], "_max_parallel", None) != max_parallel
        ):
            sem = threading.Semaphore(max(1, max_parallel))
            setattr(sem, "_max_parallel", max_parallel)
            ollama_semaphores[url] = sem
        return ollama_semaphores[url]


@contextmanager
def track_ollama_url(url: str, max_parallel: int = 2) -> Generator[None]:
    """Acquire concurrency slot and track active in-flight requests per Ollama server node."""
    sem = get_ollama_semaphore(url, max_parallel)
    sem.acquire()
    try:
        with ollama_active_lock:
            active_ollama_requests[url] = active_ollama_requests.get(url, 0) + 1
        yield
    finally:
        with ollama_active_lock:
            active_ollama_requests[url] = max(0, active_ollama_requests.get(url, 0) - 1)
        sem.release()


def read_limited_json(
    response: httpx2.Response, limit_bytes: int = 20 * 1024 * 1024
) -> dict[str, Any]:
    """Parse JSON response while enforcing a maximum response body size limit."""
    headers = getattr(response, "headers", {})
    content_length = headers.get("content-length") if hasattr(headers, "get") else None
    if content_length and content_length.isdigit() and int(content_length) > limit_bytes:
        raise AIClientError(
            f"Response body exceeded maximum size ({limit_bytes // (1024 * 1024)}MB)."
        )
    if hasattr(response, "content") and response.content is not None:
        body = response.content
        if len(body) > limit_bytes:
            raise AIClientError(
                f"Response body exceeded maximum size ({limit_bytes // (1024 * 1024)}MB)."
            )
        try:
            res: dict[str, Any] = json.loads(body)
            return res
        except json.JSONDecodeError as exc:
            raise AIClientError(f"Invalid JSON response payload from AI provider: {exc}") from exc

    try:
        raw_res: dict[str, Any] = response.json()
        return raw_res
    except Exception as exc:
        raise AIClientError(f"Failed to parse JSON response body from AI provider: {exc}") from exc


def validate_base_url(
    base_url: str,
    purpose: str = "API",
    *,
    allow_private_network: bool = False,
    allow_loopback_for_local_tooling: bool = False,
) -> str:
    """Validate base URL against SSRF and network egress rules."""
    if not base_url or not base_url.strip():
        raise AIClientError(f"Missing {purpose} base URL.")

    try:
        parsed = urlparse(base_url.strip())
    except Exception as exc:
        raise AIClientError(f"Invalid {purpose} base URL format: {base_url!r}") from exc

    if parsed.scheme not in ("http", "https"):
        raise AIClientError(
            f"Invalid {purpose} URL scheme '{parsed.scheme}'. Only http and https are permitted."
        )

    host = parsed.hostname
    if not host:
        raise AIClientError(f"Missing hostname in {purpose} base URL: {base_url!r}")

    is_allowed_local = allow_loopback_for_local_tooling and host in (
        "localhost",
        "127.0.0.1",
        "::1",
    )
    if not allow_private_network and not is_allowed_local:
        try:
            from devops_cli.core.validation import validate_service_url

            validate_service_url(base_url, purpose=purpose, allow=False)
        except ValueError as exc:
            raise AIClientError(str(exc)) from exc

    return base_url.rstrip("/")
