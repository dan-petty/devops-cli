"""Network security and IP validation helpers (delegates to devops_cli.core.validation)."""

from __future__ import annotations

from devops_cli.core.validation import is_non_public_ip

__all__ = [
    "is_non_public_ip",
]
