"""Unit tests for content-kind mappings, pending queue persistence, gauge updates, and indexes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.exceptions import ValidationError
from devops_cli.store.indexes import rebuild_kind_indexes
from devops_cli.store.kinds import CONTENT_KINDS, full_object_key, index_keys, resolve_content_kind
from devops_cli.store.queue import (
    PendingUpload,
    append_pending_upload,
    read_pending_uploads,
    write_pending_uploads,
)
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.store import InMemoryStoreClient


def test_content_kind_lookup_resolves_buckets_prefixes_visibility_and_immutability() -> None:
    """Each known content kind maps to its bucket, prefix, visibility, and immutability."""
    study = resolve_content_kind("study")
    window = resolve_content_kind("review-window")
    session = resolve_content_kind("review-session")

    assert (study.bucket, study.prefix, study.visibility, study.immutable) == (
        "reports-private",
        "studies/",
        "private",
        True,
    )
    assert (window.bucket, window.prefix, window.visibility, window.immutable) == (
        "reports",
        "windows/",
        "web",
        True,
    )
    assert (session.bucket, session.prefix, session.visibility, session.immutable) == (
        "reports-private",
        "sessions/",
        "private",
        False,
    )
    assert set(CONTENT_KINDS) == {"review-window", "study", "review-session"}


def test_resolve_content_kind_rejects_unknown_kind() -> None:
    """Unknown content kinds raise ValidationError rather than guessing a bucket."""
    with pytest.raises(ValidationError) as raised:
        resolve_content_kind("unknown-kind")
    assert "unknown-kind" in raised.value.message


def test_full_object_key_normalizes_prefix_and_rejects_traversal() -> None:
    """Keys normalize under their kind prefix and refuse parent directory traversal."""
    study = resolve_content_kind("study")
    assert full_object_key(study, "report.json") == "studies/report.json"
    assert full_object_key(study, "studies/report.json") == "studies/report.json"
    assert index_keys(study) == ("studies/index.html", "studies/index.json")

    with pytest.raises(ValidationError) as raised:
        full_object_key(study, "../secret.txt")
    assert ".." in raised.value.message


def test_pending_queue_append_and_drain_emit_pending_uploads_gauge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, otlp: FakeCollector
) -> None:
    """Appending and draining the queue emits `devops_cli_store_pending_uploads` at 1 then 0."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / "data"))
    artifact = tmp_path / "study.json"
    artifact.write_text('{"ok": true}\n', encoding="utf-8")

    entry = PendingUpload(
        kind="study",
        local_path=str(artifact),
        key="studies/study.json",
        sha256="abc123",
        content_type="application/json",
    )
    count_after_append = append_pending_upload(entry)
    assert count_after_append == 1
    assert [value for _attrs, value in otlp.points("devops_cli_store_pending_uploads")] == [1.0]
    queued = read_pending_uploads()
    assert [(item.kind, item.key, item.sha256) for item in queued] == [
        ("study", "studies/study.json", "abc123")
    ]

    count_after_drain = write_pending_uploads([])
    assert count_after_drain == 0
    assert read_pending_uploads() == []

    values = [value for _attrs, value in otlp.points("devops_cli_store_pending_uploads")]
    assert values == [1.0, 0.0]


def test_rebuild_kind_indexes_merges_lagging_listing_with_newly_written_keys(
    store_client: InMemoryStoreClient, tmp_path: Path
) -> None:
    """Index pages include newly written keys even when ListObjectsV2 omits them."""
    store_client.omit_recent_uploads_from_list = True
    window_spec = resolve_content_kind("review-window")
    store_client.seed(
        "reports",
        "windows/2026-10/report.html",
        b"<html>old</html>",
        content_type="text/html",
        sha256="oldsha",
    )

    payload = b"<html>new</html>"
    new_file = tmp_path / "2026-11.html"
    new_file.write_bytes(payload)
    bound = store_client.bind(endpoint_url="https://s3.example.com")
    bound.upload_file(
        "reports",
        "windows/2026-11/report.html",
        new_file,
        content_type="text/html",
        sha256="newsha",
    )

    rebuild_kind_indexes(
        bound,
        window_spec,
        written_objects=[
            ("windows/2026-11/report.html", len(payload), "newsha", "text/html"),
        ],
    )

    html_obj = store_client.objects[("reports", "windows/index.html")]
    json_obj = store_client.objects[("reports", "windows/index.json")]
    parsed = json.loads(json_obj.data.decode("utf-8"))
    listed_keys = [row["key"] for row in parsed["objects"]]

    assert listed_keys == ["windows/2026-10/report.html", "windows/2026-11/report.html"]
    html_text = html_obj.data.decode("utf-8")
    assert "windows/2026-10/report.html" in html_text
    assert "windows/2026-11/report.html" in html_text
