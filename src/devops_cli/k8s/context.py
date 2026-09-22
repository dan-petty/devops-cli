"""Resolution of the Kubernetes context a command should connect to.

`settings.k8s.context` was write-only: `devops k8s context <name>` stored it and
`devops config` displayed it, but nothing consulted it when opening a connection.
`KubernetesService.load_config()` passed `context=None` straight through to
`load_kube_config`, which falls back to whatever `kubectl config current-context` happens
to be. A workstation configured for one cluster therefore talked to another, and the only
symptom was a connection error naming an address the user never configured.

This module is the single place that decides which context to use, so the configured value
is consulted by every caller rather than by none of them.
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


_CACHE: tuple[float, str | None] | None = None
_CACHE_LOCK = threading.RLock()


def _config_signature() -> float:
    """Return a value that changes when the active configuration file changes."""
    try:
        from devops_cli.config.settings import get_active_config_path

        path = get_active_config_path()
    except Exception:
        return 0.0
    try:
        return float(path.stat().st_mtime) if path else 0.0
    except OSError:
        return 0.0


def configured_context() -> str | None:
    """Return the context recorded in settings, or ``None`` when unset.

    Cached against the configuration file's modification time rather than captured once. A
    long-running process -- the dashboard, the MCP server -- must follow a context change
    instead of talking to whichever cluster was configured when it started, but reloading
    settings per call cost 10.8 ms, and this is consulted on every cluster request.
    """
    global _CACHE
    signature = _config_signature()
    with _CACHE_LOCK:
        cached = _CACHE
        if cached is not None and cached[0] == signature:
            return cached[1]

    try:
        from devops_cli.config.settings import load_settings

        value = getattr(getattr(load_settings(), "k8s", None), "context", None)
    except Exception as exc:
        # Configuration problems must not make the cluster unreachable; falling back to
        # the ambient kubeconfig is what the caller did before this resolver existed.
        logger.debug("Could not read the configured Kubernetes context: %s", exc)
        return None

    resolved = value.strip() if isinstance(value, str) and value.strip() else None
    with _CACHE_LOCK:
        _CACHE = (signature, resolved)
    return resolved


def reset_context_cache() -> None:
    """Discard the cached context, forcing a settings reload on the next call."""
    global _CACHE
    with _CACHE_LOCK:
        _CACHE = None


def resolve_context(explicit: str | None = None) -> str | None:
    """Resolve the context to connect to.

    An explicit argument wins, because a `--context` flag is a deliberate override for one
    command. Otherwise the configured context is used, and only if none is configured does
    the ambient `kubectl` current-context apply.
    """
    if explicit and explicit.strip():
        return explicit.strip()
    return configured_context()


__all__ = ["configured_context", "reset_context_cache", "resolve_context"]
