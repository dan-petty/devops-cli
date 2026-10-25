"""Argo CD application synchronization request payload builder."""

from __future__ import annotations

from typing import Any


def build_sync_request_body(
    *,
    prune: bool = False,
    force: bool = False,
    app_namespace: str | None = None,
) -> dict[str, Any]:
    """Construct an Argo CD ApplicationSyncRequest payload dictionary."""
    body: dict[str, Any] = {
        "prune": prune,
        "strategy": {
            "apply": {
                "force": force,
            },
        },
    }
    if app_namespace is not None:
        body["appNamespace"] = app_namespace
    return body


__all__ = ["build_sync_request_body"]
