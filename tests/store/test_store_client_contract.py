"""Contract suite verifying `BotoStoreClient` and `InMemoryStoreClient` parity and SigV4 config."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import boto3
import pytest
from botocore.config import Config
from botocore.stub import ANY, Stubber

from devops_cli.config.constants import CONST_STORE_MULTIPART_BYTES
from devops_cli.config.settings import (
    Settings,
    StoreConfig,
    get_store_access_key_id,
    get_store_secret_access_key,
    load_settings,
)
from devops_cli.exceptions.store import StoreError
from devops_cli.store.client import BotoStoreClient
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.store import InMemoryStoreClient

_ENDPOINT = "https://s3.example.com"


def test_boto_client_defaults_to_path_style_sigv4_and_us_east_1(
    config: Callable[..., Path],
) -> None:
    """When `store.region` is unset, `BotoStoreClient` uses path-style SigV4 in `us-east-1`."""
    config({"store": {"s3_endpoint": _ENDPOINT}})
    settings = load_settings()
    client = BotoStoreClient(
        endpoint_url=str(settings.store.s3_endpoint),
        region=settings.store.region,
        access_key_id="key-1",
        secret_access_key="secret-1",
    )
    meta = client.s3.meta
    assert (
        settings.store.region,
        meta.region_name,
        meta.config.signature_version,
        dict(meta.config.s3),
    ) == (
        "us-east-1",
        "us-east-1",
        "s3v4",
        {"addressing_style": "path"},
    )


def test_store_credentials_prefer_keyring_over_environment(
    keyring_store: FakeKeyring,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keyring credentials take precedence over environment variables through `SecretResolver`."""
    keyring_store.values["store_access_key_id"] = "keyring-ak"
    keyring_store.values["store_secret_access_key"] = "keyring-sk"
    monkeypatch.setenv("DEVOPS_CLI_STORE_ACCESS_KEY_ID", "env-ak")
    monkeypatch.setenv("DEVOPS_CLI_STORE_SECRET_ACCESS_KEY", "env-sk")

    settings = Settings(store=StoreConfig(s3_endpoint=_ENDPOINT))
    ak = get_store_access_key_id(settings)
    sk = get_store_secret_access_key(settings)

    assert (ak, sk) == ("keyring-ak", "keyring-sk")
    assert set(keyring_store.secret_reads()) == {"store_access_key_id", "store_secret_access_key"}


def test_boto_client_small_json_upload_sends_sha256_metadata_and_content_type(
    tmp_path: Path,
) -> None:
    """Small `.json` upload sends `PutObject` with `sha256` metadata and `application/json`."""
    source = tmp_path / "study.json"
    payload = b'{"status": "ok"}\n'
    source.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()

    raw_s3 = boto3.client(
        "s3",
        region_name="us-east-1",
        endpoint_url=_ENDPOINT,
        aws_access_key_id="k",
        aws_secret_access_key="s",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    client = BotoStoreClient(endpoint_url=_ENDPOINT, boto_client=raw_s3)

    with Stubber(raw_s3) as stub:
        stub.add_response(
            "put_object",
            {"ETag": '"etag-1"'},
            expected_params={
                "Bucket": "reports-private",
                "Key": "studies/study.json",
                "Body": ANY,
                "ContentType": "application/json",
                "Metadata": {"sha256": digest},
                "ChecksumAlgorithm": ANY,
            },
        )
        client.upload_file(
            "reports-private",
            "studies/study.json",
            source,
            content_type="application/json",
            sha256=digest,
        )
        stub.assert_no_pending_responses()


def test_boto_client_large_upload_uses_64_mib_multipart_parts(tmp_path: Path) -> None:
    """Files larger than 64 MiB upload via multipart parts of 64 MiB (except the last)."""
    large_file = tmp_path / "large.bin"
    total_size = CONST_STORE_MULTIPART_BYTES + 1024
    with large_file.open("wb") as handle:
        os.ftruncate(handle.fileno(), total_size)

    raw_s3 = boto3.client(
        "s3",
        region_name="us-east-1",
        endpoint_url=_ENDPOINT,
        aws_access_key_id="k",
        aws_secret_access_key="s",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    recorded_part_sizes: list[int] = []

    def _capture_part(params: dict[str, Any] | None = None, **_kwargs: Any) -> None:
        assert params is not None
        body = params["Body"]
        body.seek(0, 2)
        recorded_part_sizes.append(body.tell())
        body.seek(0)

    raw_s3.meta.events.register("before-parameter-build.s3.UploadPart", _capture_part)
    client = BotoStoreClient(endpoint_url=_ENDPOINT, boto_client=raw_s3)

    with Stubber(raw_s3) as stub:
        stub.add_response(
            "create_multipart_upload",
            {"UploadId": "upload-42"},
            expected_params={
                "Bucket": "reports-private",
                "Key": "studies/large.bin",
                "ContentType": "application/octet-stream",
                "Metadata": {"sha256": "deadbeef"},
                "ChecksumAlgorithm": ANY,
            },
        )
        stub.add_response(
            "upload_part",
            {"ETag": '"part-1"'},
            expected_params={
                "Bucket": "reports-private",
                "Key": "studies/large.bin",
                "PartNumber": 1,
                "UploadId": "upload-42",
                "Body": ANY,
                "ChecksumAlgorithm": ANY,
            },
        )
        stub.add_response(
            "upload_part",
            {"ETag": '"part-2"'},
            expected_params={
                "Bucket": "reports-private",
                "Key": "studies/large.bin",
                "PartNumber": 2,
                "UploadId": "upload-42",
                "Body": ANY,
                "ChecksumAlgorithm": ANY,
            },
        )
        stub.add_response(
            "complete_multipart_upload",
            {"ETag": '"final-42"'},
            expected_params={
                "Bucket": "reports-private",
                "Key": "studies/large.bin",
                "UploadId": "upload-42",
                "MultipartUpload": {"Parts": ANY},
            },
        )
        client.upload_file(
            "reports-private",
            "studies/large.bin",
            large_file,
            content_type="application/octet-stream",
            sha256="deadbeef",
        )
        stub.assert_no_pending_responses()

    assert recorded_part_sizes == [CONST_STORE_MULTIPART_BYTES, 1024]


@pytest.mark.parametrize("backend", ["fake", "boto"])
def test_store_client_contract_head_list_get_presign_delete_and_errors(
    backend: str, tmp_path: Path
) -> None:
    """Both `InMemoryStoreClient` and `BotoStoreClient` implement head, list, get, presign, delete, and HTTP error mapping."""
    payload = b"hello store"
    digest = hashlib.sha256(payload).hexdigest()

    if backend == "fake":
        fake = InMemoryStoreClient()
        fake.seed("reports", "windows/a.txt", payload, content_type="text/plain", sha256=digest)
        client = fake.bind(endpoint_url=_ENDPOINT)
        assert client.head_object("reports", "windows/missing.txt") is None
        head = client.head_object("reports", "windows/a.txt")
        assert head is not None
        assert head.sha256 == digest
        listed = client.list_objects("reports", "windows/")
        assert [entry.key for entry in listed] == ["windows/a.txt"]
        assert client.get_bytes("reports", "windows/a.txt") == payload
        url = client.presign_get("reports", "windows/a.txt", expires_in=300)
        assert "reports/windows/a.txt" in url
        assert "300" in url
        client.delete_object("reports", "windows/a.txt")
        assert client.head_object("reports", "windows/a.txt") is None
        fake.status_error = 500
        with pytest.raises(StoreError) as raised:
            client.list_objects("reports", "windows/")
        assert (raised.value.error_code, raised.value.unreachable) == ("STORE_ERROR", False)
        return

    raw_s3 = boto3.client(
        "s3",
        region_name="us-east-1",
        endpoint_url=_ENDPOINT,
        aws_access_key_id="k",
        aws_secret_access_key="s",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    boto_client = BotoStoreClient(endpoint_url=_ENDPOINT, boto_client=raw_s3)
    with Stubber(raw_s3) as stub:
        stub.add_client_error("head_object", service_error_code="404", http_status_code=404)
        stub.add_response(
            "head_object",
            {
                "ContentLength": len(payload),
                "ContentType": "text/plain",
                "Metadata": {"sha256": digest},
            },
            expected_params={"Bucket": "reports", "Key": "windows/a.txt"},
        )
        stub.add_response(
            "list_objects_v2",
            {"Contents": [{"Key": "windows/a.txt", "Size": len(payload)}], "IsTruncated": False},
            expected_params={"Bucket": "reports", "Prefix": "windows/"},
        )
        stub.add_response(
            "delete_object",
            {},
            expected_params={"Bucket": "reports", "Key": "windows/a.txt"},
        )
        stub.add_client_error(
            "list_objects_v2", service_error_code="InternalError", http_status_code=500
        )

        assert boto_client.head_object("reports", "windows/missing.txt") is None
        head = boto_client.head_object("reports", "windows/a.txt")
        assert head is not None
        assert head.sha256 == digest
        listed = boto_client.list_objects("reports", "windows/")
        assert [entry.key for entry in listed] == ["windows/a.txt"]
        presigned = boto_client.presign_get("reports", "windows/a.txt", expires_in=300)
        assert "reports/windows/a.txt" in presigned
        assert "X-Amz-Expires=300" in presigned
        boto_client.delete_object("reports", "windows/a.txt")
        with pytest.raises(StoreError) as raised:
            boto_client.list_objects("reports", "windows/")
        assert (raised.value.error_code, raised.value.unreachable) == ("STORE_ERROR", False)
        stub.assert_no_pending_responses()
