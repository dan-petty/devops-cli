"""Unit tests for Pydantic AI Media externalization and content-addressed binary storage."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.agents import (
    BinaryContent,
    DiskMediaStore,
    InMemoryMediaStore,
    MediaExternalizer,
    RunContext,
    SqliteMediaStore,
    externalize_media,
    restore_media,
)


def test_binary_content_and_in_memory_store() -> None:
    """Verify BinaryContent SHA256 hashing, URI format, and InMemoryMediaStore."""
    raw_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    content = BinaryContent(data=raw_png, media_type="image/png")

    assert content.sha256_hex is not None
    assert content.uri.startswith("media+sha256://")
    assert "media_type=image%2Fpng" in content.uri

    store = InMemoryMediaStore()
    uri = store.put(content)
    assert uri == content.uri

    retrieved = store.get(uri)
    assert retrieved is not None
    assert retrieved.data == raw_png
    assert retrieved.media_type == "image/png"

    assert store.delete(uri) is True
    assert store.get(uri) is None


def test_disk_media_store(tmp_path: Path) -> None:
    """Verify DiskMediaStore writing and reading binary blobs to disk."""
    store = DiskMediaStore(root_dir=tmp_path / "media")
    raw_data = b"AUDIO_RAW_STREAM_DATA"
    content = BinaryContent(data=raw_data, media_type="audio/wav")

    uri = store.put(content)
    assert uri.startswith("media+sha256://")

    # Read back
    retrieved = store.get(uri)
    assert retrieved is not None
    assert retrieved.data == raw_data
    assert retrieved.media_type == "audio/wav"

    # Delete
    assert store.delete(uri) is True
    assert store.get(uri) is None


def test_sqlite_media_store() -> None:
    """Verify SqliteMediaStore database storage and retrieval."""
    store = SqliteMediaStore(db_path=":memory:")
    raw_data = b"PDF_DOCUMENT_STREAM"
    content = BinaryContent(data=raw_data, media_type="application/pdf")

    uri = store.put(content)
    assert uri.startswith("media+sha256://")

    retrieved = store.get(uri)
    assert retrieved is not None
    assert retrieved.data == raw_data
    assert retrieved.media_type == "application/pdf"

    assert store.delete(uri) is True
    assert store.get(uri) is None


def test_externalize_and_restore_media_recursive() -> None:
    """Verify recursive replacement of BinaryContent with URIs and restoration."""
    store = InMemoryMediaStore()
    raw_img = b"PNG_BYTES"
    content = BinaryContent(data=raw_img, media_type="image/png")

    payload = {
        "text": "Hello world",
        "nested": {
            "image": content,
            "list": [content, "regular_string"],
        },
    }

    # Externalize
    externalized = externalize_media(payload, store)
    assert externalized["text"] == "Hello world"
    assert isinstance(externalized["nested"]["image"], str)
    assert externalized["nested"]["image"].startswith("media+sha256://")
    assert isinstance(externalized["nested"]["list"][0], str)
    assert externalized["nested"]["list"][1] == "regular_string"

    # Restore
    restored = restore_media(externalized, store)
    assert restored["text"] == "Hello world"
    assert isinstance(restored["nested"]["image"], BinaryContent)
    assert restored["nested"]["image"].data == raw_img
    assert isinstance(restored["nested"]["list"][0], BinaryContent)


def test_media_externalizer_capability() -> None:
    """Verify MediaExternalizer capability lifecycle hooks."""
    cap = MediaExternalizer()
    hooks = cap.get_hooks()
    assert hooks is not None
    assert len(hooks.after_tool_execute) > 0

    ctx = RunContext()
    content = BinaryContent(data=b"SCREENSHOT", media_type="image/png")
    tool_result = {"screenshot": content}

    hooks.after_tool_execute[0](ctx, "take_screenshot", tool_result)
    assert len(cap.store.storage) == 1
