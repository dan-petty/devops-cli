"""Kind root index page generation (`index.html` and `index.json`)."""

from __future__ import annotations

import html
import json
from collections.abc import Sequence
from dataclasses import dataclass

from devops_cli.store.client import StoreClient
from devops_cli.store.kinds import ContentKindSpec, index_keys


@dataclass(frozen=True)
class IndexObjectEntry:
    """One artifact listed under a content kind's index pages."""

    key: str
    size: int
    sha256: str | None = None
    content_type: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize one entry for `index.json`."""
        return {
            "key": self.key,
            "name": self.key.rsplit("/", 1)[-1],
            "size": self.size,
            "sha256": self.sha256,
            "content_type": self.content_type,
        }


def render_index_json(spec: ContentKindSpec, entries: Sequence[IndexObjectEntry]) -> bytes:
    """Render deterministic `index.json` bytes for one content kind."""
    payload = {
        "kind": spec.name,
        "bucket": spec.bucket,
        "prefix": spec.prefix,
        "objects": [entry.to_dict() for entry in entries],
    }
    return (json.dumps(payload, indent=2, sort_keys=False) + "\n").encode("utf-8")


def render_index_html(spec: ContentKindSpec, entries: Sequence[IndexObjectEntry]) -> bytes:
    """Render simple escaped HTML listing all indexed artifacts under `spec`."""
    title = html.escape(f"devops-cli store: {spec.name}")
    items = []
    for entry in entries:
        rel_href = entry.key.removeprefix(spec.prefix)
        items.append(
            f'    <li><a href="{html.escape(rel_href)}">{html.escape(entry.key)}</a>'
            f" ({entry.size} bytes)</li>"
        )
    list_body = "\n".join(items)
    doc = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>{title}</title>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>{title}</h1>\n"
        "  <ul>\n"
        f"{list_body}\n"
        "  </ul>\n"
        "</body>\n"
        "</html>\n"
    )
    return doc.encode("utf-8")


def rebuild_kind_indexes(
    client: StoreClient,
    spec: ContentKindSpec,
    *,
    written_objects: Sequence[tuple[str, int, str | None, str | None]] = (),
) -> tuple[str, str]:
    """Merge `ListObjectsV2` with `written_objects` and write `index.html` and `index.json`."""
    html_key, json_key = index_keys(spec)
    excluded = {html_key, json_key}
    merged: dict[str, IndexObjectEntry] = {}

    for listed in client.list_objects(spec.bucket, spec.prefix):
        if listed.key in excluded:
            continue
        merged[listed.key] = IndexObjectEntry(
            key=listed.key,
            size=listed.size,
            sha256=listed.sha256,
        )

    for full_key, size, sha256, content_type in written_objects:
        if full_key in excluded:
            continue
        merged[full_key] = IndexObjectEntry(
            key=full_key,
            size=size,
            sha256=sha256,
            content_type=content_type,
        )

    ordered = [merged[key] for key in sorted(merged)]
    client.put_bytes(
        spec.bucket,
        json_key,
        render_index_json(spec, ordered),
        content_type="application/json",
    )
    client.put_bytes(
        spec.bucket,
        html_key,
        render_index_html(spec, ordered),
        content_type="text/html; charset=utf-8",
    )
    return (html_key, json_key)
