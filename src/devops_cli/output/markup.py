"""Markup and text escaping utilities for terminal presentations."""

from __future__ import annotations

from rich.markup import escape as _rich_escape


def escape_text(text: str) -> str:
    """Escape Rich markup tags in string."""
    return _rich_escape(text)
