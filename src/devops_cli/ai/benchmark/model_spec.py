"""Model spec parsing for benchmark commands and runners."""

from __future__ import annotations


def parse_model_spec(entry: str) -> tuple[str, str | None]:
    """Parse a 'model[@endpoint]' specification.

    Returns (model, endpoint) where endpoint is None if '@' is not present in entry.
    """
    if "@" not in entry:
        return entry, None
    model, _, endpoint = entry.partition("@")
    return model, endpoint


def parse_model_list(models: str | None, default_model: str | None = None) -> list[str]:
    """Parse comma-separated model string into list of models."""
    if models:
        return [m.strip() for m in models.split(",") if m.strip()]
    if default_model is not None:
        return [default_model]
    return []


__all__ = [
    "parse_model_list",
    "parse_model_spec",
]
