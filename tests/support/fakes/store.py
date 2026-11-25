"""In-memory S3 content-store fake and pytest fixture (#4761).

Provides an in-memory object store implementing `StoreClient` so tests exercise
`publish`, `sync`, `ls`, `get`, `url`, `presign`, and `doctor` without reaching
a network endpoint or importing boto3 during CLI-only tests.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest


@dataclass(frozen=True)
class StoreCall:
    """One recorded S3 operation issued against the store fake."""

    operation: str
    endpoint_url: str
    bucket: str
    key: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class StoredObject:
    """One object stored inside the in-memory fake."""

    bucket: str
    key: str
    data: bytes
    content_type: str
    sha256: str
    metadata: dict[str, str] = field(default_factory=dict)


class _BoundStoreClient:
    """Endpoint-scoped view over an `InMemoryStoreClient`."""

    def __init__(self, fake: InMemoryStoreClient, endpoint_url: str) -> None:
        self._fake = fake
        self._endpoint_url = endpoint_url

    @property
    def endpoint_url(self) -> str:
        return self._endpoint_url

    def head_object(self, bucket: str, key: str) -> Any:
        from devops_cli.store.client import StoreObjectMeta

        self._fake._record("HeadObject", self._endpoint_url, bucket, key)
        obj = self._fake.objects.get((bucket, key))
        if obj is None:
            return None
        return StoreObjectMeta(
            bucket=bucket,
            key=key,
            sha256=obj.sha256,
            content_type=obj.content_type,
            size=len(obj.data),
        )

    def put_bytes(
        self,
        bucket: str,
        key: str,
        data: bytes,
        *,
        content_type: str,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        meta = dict(metadata or {})
        sha256 = meta.get("sha256") or hashlib.sha256(data).hexdigest()
        self._fake._record(
            "PutObject",
            self._endpoint_url,
            bucket,
            key,
            content_type=content_type,
            sha256=sha256,
            size=len(data),
        )
        self._fake.objects[(bucket, key)] = StoredObject(
            bucket=bucket,
            key=key,
            data=bytes(data),
            content_type=content_type,
            sha256=sha256,
            metadata=meta,
        )

    def upload_file(
        self,
        bucket: str,
        key: str,
        source: Path,
        *,
        content_type: str,
        sha256: str,
        multipart_threshold: int | None = None,
        multipart_chunksize: int | None = None,
    ) -> None:
        data = source.read_bytes()
        self._fake._record(
            "PutObject",
            self._endpoint_url,
            bucket,
            key,
            content_type=content_type,
            sha256=sha256,
            size=len(data),
        )
        self._fake.objects[(bucket, key)] = StoredObject(
            bucket=bucket,
            key=key,
            data=data,
            content_type=content_type,
            sha256=sha256,
            metadata={"sha256": sha256},
        )
        if self._fake.omit_recent_uploads_from_list:
            self._fake.omitted_from_list.add((bucket, key))

    def list_objects(self, bucket: str, prefix: str) -> list[Any]:
        from devops_cli.store.client import StoreObjectSummary

        self._fake._record("ListObjectsV2", self._endpoint_url, bucket, prefix)
        results: list[StoreObjectSummary] = []
        for (obj_bucket, obj_key), obj in sorted(self._fake.objects.items()):
            if obj_bucket != bucket or not obj_key.startswith(prefix):
                continue
            if (obj_bucket, obj_key) in self._fake.omitted_from_list:
                continue
            results.append(
                StoreObjectSummary(
                    key=obj_key,
                    size=len(obj.data),
                    sha256=obj.sha256,
                )
            )
        return results

    def download_file(self, bucket: str, key: str, destination: Path) -> int:
        data = self.get_bytes(bucket, key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return len(data)

    def get_bytes(self, bucket: str, key: str) -> bytes:
        from devops_cli.exceptions.store import StoreError

        self._fake._record("GetObject", self._endpoint_url, bucket, key)
        obj = self._fake.objects.get((bucket, key))
        if obj is None:
            raise StoreError(
                f"Object s3://{bucket}/{key} was not found.",
                bucket=bucket,
                key=key,
                endpoint=self._endpoint_url,
                status_code=404,
            )
        return obj.data

    def delete_object(self, bucket: str, key: str) -> None:
        self._fake._record("DeleteObject", self._endpoint_url, bucket, key)
        self._fake.objects.pop((bucket, key), None)

    def presign_get(self, bucket: str, key: str, *, expires_in: int) -> str:
        self._fake._record(
            "PresignGetObject", self._endpoint_url, bucket, key, expires_in=expires_in
        )
        base = self._endpoint_url.rstrip("/")
        return f"{base}/{bucket}/{key}?X-Amz-Expires={expires_in}&X-Amz-Algorithm=AWS4-HMAC-SHA256"


class InMemoryStoreClient:
    """In-memory object store supporting scripted connection failures, HTTP errors, and stale listings."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], StoredObject] = {}
        self.calls: list[StoreCall] = []
        self.connection_error: str | None = None
        self.status_error: int | None = None
        self.failing_operations: dict[str, int | str] = {}
        self.omit_recent_uploads_from_list: bool = False
        self.omitted_from_list: set[tuple[str, str]] = set()

    def bind(
        self,
        *,
        endpoint_url: str,
        region: str = "us-east-1",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> _BoundStoreClient:
        _ = (region, access_key_id, secret_access_key)
        return _BoundStoreClient(self, endpoint_url)

    def _record(
        self,
        operation: str,
        endpoint_url: str,
        bucket: str,
        key: str = "",
        **details: Any,
    ) -> None:
        from devops_cli.exceptions.store import StoreError

        self.calls.append(
            StoreCall(
                operation=operation,
                endpoint_url=endpoint_url,
                bucket=bucket,
                key=key,
                details=details,
            )
        )
        if self.connection_error is not None:
            raise StoreError(
                self.connection_error,
                bucket=bucket,
                key=key or None,
                endpoint=endpoint_url,
                unreachable=True,
            )
        if self.status_error is not None:
            raise StoreError(
                f"Content store returned HTTP {self.status_error} during {operation}.",
                bucket=bucket,
                key=key or None,
                endpoint=endpoint_url,
                status_code=self.status_error,
                unreachable=False,
            )
        if operation in self.failing_operations:
            failure = self.failing_operations[operation]
            if isinstance(failure, int):
                raise StoreError(
                    f"Content store returned HTTP {failure} during {operation}.",
                    bucket=bucket,
                    key=key or None,
                    endpoint=endpoint_url,
                    status_code=failure,
                    unreachable=False,
                )
            raise StoreError(
                str(failure),
                bucket=bucket,
                key=key or None,
                endpoint=endpoint_url,
                unreachable=True,
            )

    def calls_for(self, operation: str, *, endpoint_url: str | None = None) -> list[StoreCall]:
        """Return recorded calls matching `operation` and optionally `endpoint_url`."""
        return [
            call
            for call in self.calls
            if call.operation == operation
            and (endpoint_url is None or call.endpoint_url == endpoint_url)
        ]

    def seed(
        self,
        bucket: str,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        sha256: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> StoredObject:
        """Seed one object directly into memory without recording a client call."""
        digest = sha256 or hashlib.sha256(data).hexdigest()
        meta = dict(metadata or {})
        meta.setdefault("sha256", digest)
        obj = StoredObject(
            bucket=bucket,
            key=key,
            data=data,
            content_type=content_type,
            sha256=digest,
            metadata=meta,
        )
        self.objects[(bucket, key)] = obj
        return obj

    def operations_by_endpoint(self, endpoints: Sequence[str]) -> dict[str, list[str]]:
        """Group recorded operation names in call order for each named endpoint."""
        return {ep: [c.operation for c in self.calls if c.endpoint_url == ep] for ep in endpoints}


@pytest.fixture
def store_client() -> Iterator[InMemoryStoreClient]:
    """Install an in-memory StoreClient seam override and yield the fake."""
    from devops_cli.store.client import install_store_client, reset_store_client

    fake = InMemoryStoreClient()
    install_store_client(fake.bind)
    try:
        yield fake
    finally:
        reset_store_client()
