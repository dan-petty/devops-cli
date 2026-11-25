"""Content-kind mappings and normalized object key helpers for the content store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from devops_cli.exceptions import ValidationError


@dataclass(frozen=True)
class ContentKindSpec:
    """Bucket, prefix, visibility, and immutability policy for one store content kind."""

    name: str
    bucket: str
    prefix: str
    visibility: Literal["web", "private"]
    immutable: bool


CONTENT_KINDS: Final[dict[str, ContentKindSpec]] = {
    "review-window": ContentKindSpec(
        name="review-window",
        bucket="reports",
        prefix="windows/",
        visibility="web",
        immutable=True,
    ),
    "study": ContentKindSpec(
        name="study",
        bucket="reports-private",
        prefix="studies/",
        visibility="private",
        immutable=True,
    ),
    "review-session": ContentKindSpec(
        name="review-session",
        bucket="reports-private",
        prefix="sessions/",
        visibility="private",
        immutable=False,
    ),
}


def resolve_content_kind(kind: str) -> ContentKindSpec:
    """Look up a content kind specification or raise `ValidationError`."""
    spec = CONTENT_KINDS.get(kind)
    if spec is None:
        valid = ", ".join(sorted(CONTENT_KINDS))
        raise ValidationError(
            f"Unknown content kind '{kind}'. Expected one of: {valid}.",
            field="kind",
        )
    return spec


def full_object_key(spec: ContentKindSpec, key: str) -> str:
    """Normalize an object key under `spec.prefix` and reject parent traversal."""
    normalized = key.strip().lstrip("/")
    if not normalized:
        raise ValidationError("Object key must not be empty.", field="key")
    parts = [part for part in normalized.split("/") if part]
    if any(part in {".", ".."} for part in parts):
        raise ValidationError(
            f"Object key '{key}' must not contain '.' or '..' path segments.",
            field="key",
        )
    joined = "/".join(parts)
    if joined.startswith(spec.prefix):
        return joined
    return f"{spec.prefix}{joined}"


def index_keys(spec: ContentKindSpec) -> tuple[str, str]:
    """Return the `(index.html, index.json)` object keys at the root of `spec.prefix`."""
    return (f"{spec.prefix}index.html", f"{spec.prefix}index.json")
