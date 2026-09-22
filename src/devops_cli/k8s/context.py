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

logger = logging.getLogger(__name__)


def configured_context() -> str | None:
    """Return the context recorded in settings, or ``None`` when unset.

    Settings are read on every call rather than captured once. A long-running process --
    the dashboard, the MCP server -- would otherwise keep talking to the cluster that was
    configured when it started, long after the operator switched.
    """
    try:
        from devops_cli.config.settings import load_settings

        value = getattr(getattr(load_settings(), "k8s", None), "context", None)
    except Exception as exc:
        # Configuration problems must not make the cluster unreachable; falling back to
        # the ambient kubeconfig is what the caller did before this resolver existed.
        logger.debug("Could not read the configured Kubernetes context: %s", exc)
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def resolve_context(explicit: str | None = None) -> str | None:
    """Resolve the context to connect to.

    An explicit argument wins, because a `--context` flag is a deliberate override for one
    command. Otherwise the configured context is used, and only if none is configured does
    the ambient `kubectl` current-context apply.
    """
    if explicit and explicit.strip():
        return explicit.strip()
    return configured_context()


__all__ = ["configured_context", "resolve_context"]
