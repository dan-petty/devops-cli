"""Tests for the `devops store` CLI command group (#4761)."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.commands.store import (
    app as store_app,
)
from devops_cli.commands.store import (
    store_doctor,
    store_get,
    store_ls,
    store_presign,
    store_publish,
    store_sync,
    store_url,
)
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import ConfigurationError, StoreError, StoreImmutablePathError
from devops_cli.store.ops import presign_object, publish_file, resolve_web_url
from devops_cli.store.queue import pending_queue_path, read_pending_uploads
from tests.support.dry_run_classes import misclassified
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.store import InMemoryStoreClient

_S3_ENDPOINT = "https://store.example.com"
_EXTRA_ENDPOINT = "https://s3.example.com"
_WEB_BASE = "https://files.example.com"

_REQUEST_PLAN_COMMANDS = [
    ("store publish", store_publish, ["store", "publish", "study", "report.json", "--dry-run"]),
    ("store sync", store_sync, ["store", "sync", "--dry-run"]),
    ("store ls", store_ls, ["store", "ls", "study", "--dry-run"]),
    ("store get", store_get, ["store", "get", "study", "report.json", "--dry-run"]),
    ("store url", store_url, ["store", "url", "review-window", "report.html", "--dry-run"]),
    ("store presign", store_presign, ["store", "presign", "study", "report.json", "--dry-run"]),
    ("store doctor", store_doctor, ["store", "doctor", "--dry-run"]),
]


def _configure_store(
    config: Callable[..., Path],
    keyring_store: FakeKeyring,
    *,
    s3_endpoint: str | None = _S3_ENDPOINT,
    web_base_url: str | None = _WEB_BASE,
) -> None:
    store_cfg: dict[str, Any] = {}
    if s3_endpoint is not None:
        store_cfg["s3_endpoint"] = s3_endpoint
    if web_base_url is not None:
        store_cfg["web_base_url"] = web_base_url
    config({"store": store_cfg})
    keyring_store.values["store_access_key_id"] = "test-ak"
    keyring_store.values["store_secret_access_key"] = "test-sk"


def test_store_help_lists_all_seven_subcommands(cli: Callable[..., Any]) -> None:
    """`devops store --help` exposes all seven required subcommands and exits 0."""
    res = cli("store", "--help")
    assert res.exit_code == 0
    for sub in ("publish", "sync", "ls", "get", "url", "presign", "doctor"):
        assert sub in res.output


def test_store_commands_dry_run_guard_and_classification(
    cli: Callable[..., Any],
    refuse_requests: list[str],
    keyring_store: FakeKeyring,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every store command has `request-plan` classification and makes no network, keyring, or queue write under `--dry-run`."""
    assert misclassified(_REQUEST_PLAN_COMMANDS, "request-plan") == {}
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / "data"))
    artifact = tmp_path / "report.json"
    artifact.write_text("{}", encoding="utf-8")

    dry_invocations = [
        ("store", "publish", "study", str(artifact), "--dry-run"),
        ("store", "sync", "--dry-run"),
        ("store", "ls", "study", "--dry-run"),
        ("store", "get", "study", "report.json", str(tmp_path / "out.json"), "--dry-run"),
        ("store", "url", "review-window", "report.html", "--dry-run"),
        ("store", "presign", "study", "report.json", "--dry-run"),
        ("store", "doctor", "--dry-run"),
    ]
    for argv in dry_invocations:
        res = cli(*argv)
        assert res.exit_code == 0, f"{argv}: {res.output}"

    assert refuse_requests == []
    assert keyring_store.secret_reads() == set()
    assert not pending_queue_path().exists()


def test_unset_s3_endpoint_fails_naming_setting(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    tmp_path: Path,
) -> None:
    """Running `publish` with no `store.s3_endpoint` exits non-zero with `CONFIGURATION_ERROR`."""
    config({"store": {}})
    sample = tmp_path / "study.json"
    sample.write_text('{"x": 1}\n', encoding="utf-8")

    with pytest.raises(ConfigurationError) as raised:
        publish_file("study", sample, settings=load_settings())
    assert raised.value.error_code == "CONFIGURATION_ERROR"
    assert "store.s3_endpoint" in raised.value.message

    res = cli("store", "publish", "study", str(sample))
    assert res.exit_code == 1
    assert "store.s3_endpoint" in res.output


def test_unset_web_base_url_fails_naming_setting(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    keyring_store: FakeKeyring,
) -> None:
    """Running `url` for a web kind with no `store.web_base_url` exits non-zero with `CONFIGURATION_ERROR`."""
    _configure_store(config, keyring_store, web_base_url=None)
    with pytest.raises(ConfigurationError) as raised:
        resolve_web_url("review-window", "2026-11/index.html", settings=load_settings())
    assert raised.value.error_code == "CONFIGURATION_ERROR"
    assert "store.web_base_url" in raised.value.message

    res = cli("store", "url", "review-window", "2026-11/index.html")
    assert res.exit_code == 1
    assert "store.web_base_url" in res.output


def test_publish_study_and_immutable_guard_and_replace(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    keyring_store: FakeKeyring,
    store_client: InMemoryStoreClient,
    tmp_path: Path,
) -> None:
    """`publish` uploads to bucket+prefix, blocks changed immutable paths unless `--replace` is given."""
    _configure_store(config, keyring_store)
    study_file = tmp_path / "notes.json"
    study_file.write_text('{"version": 1}\n', encoding="utf-8")

    res = cli("store", "publish", "study", str(study_file))
    assert res.exit_code == 0, res.output
    puts = store_client.calls_for("PutObject")
    assert any(c.bucket == "reports-private" and c.key == "studies/notes.json" for c in puts)

    study_file.write_text('{"version": 2}\n', encoding="utf-8")
    before_count = len(store_client.calls_for("PutObject"))
    with pytest.raises(StoreImmutablePathError) as raised:
        publish_file("study", study_file, settings=load_settings())
    assert raised.value.error_code == "STORE_IMMUTABLE_PATH"
    assert len(store_client.calls_for("PutObject")) == before_count

    blocked = cli("store", "publish", "study", str(study_file))
    assert blocked.exit_code == 1
    assert len(store_client.calls_for("PutObject")) == before_count

    replaced = cli("store", "publish", "study", str(study_file), "--replace")
    assert replaced.exit_code == 0, replaced.output
    assert len(store_client.calls_for("PutObject")) > before_count


def test_unreachable_store_queues_pending_and_sync_drains_with_checksum_skip(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    keyring_store: FakeKeyring,
    store_client: InMemoryStoreClient,
    otlp: FakeCollector,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unreachable store keeps file, queues 1 JSON line, exits 0 as pending, emits gauge, then sync drains and deduplicates."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / "data"))
    _configure_store(config, keyring_store)

    artifact = tmp_path / "session.json"
    payload = b'{"session": 1}\n'
    artifact.write_bytes(payload)

    store_client.connection_error = "connection refused"
    res = cli("store", "publish", "review-session", str(artifact))
    assert res.exit_code == 0, res.output
    assert "pending" in res.output.lower()
    assert artifact.exists()
    queued = read_pending_uploads()
    assert len(queued) == 1
    assert [v for _a, v in otlp.points("devops_cli_store_pending_uploads")][-1] == 1.0

    store_client.connection_error = None
    otlp.clear()
    sync_res = cli("store", "sync")
    assert sync_res.exit_code == 0, sync_res.output
    assert read_pending_uploads() == []
    assert [v for _a, v in otlp.points("devops_cli_store_pending_uploads")][-1] == 0.0
    assert any(
        c.bucket == "reports-private" and c.key == "sessions/session.json"
        for c in store_client.calls_for("PutObject")
    )

    # Re-queue identical checksum; second sync records HeadObject and no PutObject.
    from devops_cli.store.queue import PendingUpload, append_pending_upload

    append_pending_upload(
        PendingUpload(
            kind="review-session",
            local_path=str(artifact),
            key="sessions/session.json",
            sha256=hashlib.sha256(payload).hexdigest(),
            content_type="application/json",
        )
    )
    store_client.calls.clear()
    second_sync = cli("store", "sync")
    assert second_sync.exit_code == 0, second_sync.output
    assert [c.operation for c in store_client.calls_for("HeadObject")] == ["HeadObject"]
    assert store_client.calls_for("PutObject") == []


def test_store_500_error_fails_with_store_error_and_writes_no_queue_line(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    keyring_store: FakeKeyring,
    store_client: InMemoryStoreClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An HTTP 500 response from the store raises `STORE_ERROR` and adds nothing to the queue."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / "data"))
    _configure_store(config, keyring_store)
    sample = tmp_path / "study.json"
    sample.write_text('{"x": 1}\n', encoding="utf-8")

    store_client.status_error = 500
    with pytest.raises(StoreError) as raised:
        publish_file("study", sample, settings=load_settings())
    assert raised.value.error_code == "STORE_ERROR"

    res = cli("store", "publish", "study", str(sample))
    assert res.exit_code == 1
    assert read_pending_uploads() == []


def test_publish_review_window_updates_kind_index_pages_beyond_lagging_list(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    keyring_store: FakeKeyring,
    store_client: InMemoryStoreClient,
    tmp_path: Path,
) -> None:
    """Publishing a `review-window` writes `index.html` and `index.json` including the new key."""
    _configure_store(config, keyring_store)
    store_client.omit_recent_uploads_from_list = True
    window_file = tmp_path / "2026-11-report.html"
    window_file.write_text("<html>report</html>", encoding="utf-8")

    res = cli("store", "publish", "review-window", str(window_file), "--key", "2026-11/report.html")
    assert res.exit_code == 0, res.output

    index_html = store_client.objects[("reports", "windows/index.html")].data.decode("utf-8")
    index_json = json.loads(
        store_client.objects[("reports", "windows/index.json")].data.decode("utf-8")
    )
    assert "windows/2026-11/report.html" in index_html
    assert any(obj["key"] == "windows/2026-11/report.html" for obj in index_json["objects"])


def test_presign_url_ls_get_and_private_url_refusal(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    keyring_store: FakeKeyring,
    store_client: InMemoryStoreClient,
    tmp_path: Path,
) -> None:
    """Cover `presign` (limit 7d vs 8d), `url` (web allowed, private refused), `ls`, and `get`."""
    _configure_store(config, keyring_store)
    store_client.seed(
        "reports-private", "studies/data.txt", b"payload-bytes", content_type="text/plain"
    )
    store_client.seed("reports", "windows/2026-11.html", b"<html/>", content_type="text/html")

    too_long = cli("store", "presign", "study", "data.txt", "--expires", str(8 * 86400))
    assert too_long.exit_code != 0
    assert store_client.calls == []

    seven_days = cli("store", "presign", "study", "data.txt", "--expires", str(7 * 86400))
    assert seven_days.exit_code == 0, seven_days.output
    assert "studies/data.txt" in seven_days.output
    assert presign_object("study", "data.txt", expires_in=7 * 86400, settings=load_settings())

    web_url = cli("store", "url", "review-window", "2026-11.html")
    assert web_url.exit_code == 0, web_url.output
    assert "https://files.example.com/windows/2026-11.html" in web_url.output

    private_url = cli("store", "url", "study", "data.txt")
    assert private_url.exit_code != 0
    assert "https://files.example.com" not in private_url.output

    listed = cli("store", "ls", "study")
    assert listed.exit_code == 0, listed.output
    assert "studies/data.txt" in listed.output

    downloaded = tmp_path / "downloaded.txt"
    got = cli("store", "get", "study", "data.txt", str(downloaded))
    assert got.exit_code == 0, got.output
    assert downloaded.read_bytes() == b"payload-bytes"


def test_doctor_runs_five_canary_operations_against_configured_and_extra_endpoints(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    keyring_store: FakeKeyring,
    store_client: InMemoryStoreClient,
) -> None:
    """`doctor --endpoint <url>` puts, lists, gets, presigns, and deletes a canary on every endpoint."""
    _configure_store(config, keyring_store)
    res = cli("store", "doctor", "--endpoint", _EXTRA_ENDPOINT)
    assert res.exit_code == 0, res.output

    ops = store_client.operations_by_endpoint([_S3_ENDPOINT, _EXTRA_ENDPOINT])
    expected = ["PutObject", "ListObjectsV2", "GetObject", "PresignGetObject", "DeleteObject"]
    assert ops == {_S3_ENDPOINT: expected, _EXTRA_ENDPOINT: expected}


def test_workspace_clean_preserves_pending_store_queue_and_referenced_file(
    cli: Callable[..., Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`devops workspace clean` leaves `store/pending.jsonl` and queued artifacts intact."""
    data_dir = tmp_path / "data"
    store_dir = data_dir / "store"
    store_dir.mkdir(parents=True)
    queued_artifact = store_dir / "pending-study.json"
    queued_artifact.write_text('{"pending": true}\n', encoding="utf-8")
    pending_file = store_dir / "pending.jsonl"
    pending_file.write_text(
        json.dumps(
            {
                "kind": "study",
                "local_path": str(queued_artifact),
                "key": "studies/pending-study.json",
                "sha256": "abc",
                "content_type": "application/json",
                "replace": False,
                "queued_at": "2026-01-01T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    stale = time.time() - (30 * 86400)
    os.utime(queued_artifact, (stale, stale))
    os.utime(pending_file, (stale, stale))

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(data_dir))
    res = cli("workspace", "clean", "--older-than", "7")
    assert res.exit_code == 0, res.output
    assert pending_file.exists()
    assert queued_artifact.exists()
    assert store_app is not None
