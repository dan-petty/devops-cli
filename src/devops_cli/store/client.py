"""StoreClient protocol, boto3 path-style SigV4 implementation, and test override seam."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from devops_cli.config.constants import CONST_STORE_MULTIPART_BYTES
from devops_cli.config.settings import setting_default
from devops_cli.exceptions.store import StoreError


class _BotoS3Protocol(Protocol):
    @property
    def meta(self) -> Any: ...
    def head_object(self, **kwargs: Any) -> dict[str, Any]: ...
    def put_object(self, **kwargs: Any) -> dict[str, Any]: ...
    def upload_file(self, *args: Any, **kwargs: Any) -> None: ...
    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]: ...
    def get_object(self, **kwargs: Any) -> dict[str, Any]: ...
    def download_file(self, *args: Any, **kwargs: Any) -> None: ...
    def delete_object(self, **kwargs: Any) -> dict[str, Any]: ...
    def generate_presigned_url(self, *args: Any, **kwargs: Any) -> str: ...


@dataclass(frozen=True)
class StoreObjectMeta:
    """Metadata returned by `HeadObject` for an existing stored object."""

    bucket: str
    key: str
    sha256: str | None
    content_type: str | None
    size: int | None
    etag: str | None = None


@dataclass(frozen=True)
class StoreObjectSummary:
    """Summary entry returned by `ListObjectsV2`."""

    key: str
    size: int
    etag: str | None = None
    last_modified: str | None = None
    sha256: str | None = None


@runtime_checkable
class StoreClient(Protocol):
    """Abstract interface over an S3-compatible object store endpoint."""

    @property
    def endpoint_url(self) -> str:
        """Return the endpoint URL this client targets."""

    def head_object(self, bucket: str, key: str) -> StoreObjectMeta | None:
        """Return object metadata or None when the key does not exist."""

    def put_bytes(
        self,
        bucket: str,
        key: str,
        data: bytes,
        *,
        content_type: str,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        """Write in-memory bytes directly via PutObject."""

    def upload_file(
        self,
        bucket: str,
        key: str,
        source: Path,
        *,
        content_type: str,
        sha256: str,
        multipart_threshold: int = CONST_STORE_MULTIPART_BYTES,
        multipart_chunksize: int = CONST_STORE_MULTIPART_BYTES,
    ) -> None:
        """Upload a local file using 64 MiB multipart parts when above threshold."""

    def list_objects(self, bucket: str, prefix: str) -> list[StoreObjectSummary]:
        """List all objects under `prefix` within `bucket`."""

    def download_file(self, bucket: str, key: str, destination: Path) -> int:
        """Download an object directly to `destination` and return bytes written."""

    def get_bytes(self, bucket: str, key: str) -> bytes:
        """Fetch an object body as bytes."""

    def delete_object(self, bucket: str, key: str) -> None:
        """Delete an object from `bucket`."""

    def presign_get(self, bucket: str, key: str, *, expires_in: int) -> str:
        """Return a SigV4 presigned GET URL valid for `expires_in` seconds."""


StoreClientFactory = Callable[..., StoreClient]

_STORE_CLIENT_FACTORY: StoreClientFactory | StoreClient | None = None


def install_store_client(
    factory_or_client: StoreClientFactory | StoreClient,
) -> StoreClientFactory | StoreClient | None:
    """Install a custom StoreClient factory or instance for tests."""
    global _STORE_CLIENT_FACTORY
    previous = _STORE_CLIENT_FACTORY
    _STORE_CLIENT_FACTORY = factory_or_client
    return previous


def reset_store_client() -> None:
    """Restore the default boto3 StoreClient resolver."""
    global _STORE_CLIENT_FACTORY
    _STORE_CLIENT_FACTORY = None


def resolve_store_client(
    *,
    endpoint_url: str,
    region: str | None = None,
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
) -> StoreClient:
    """Return an override client if installed, or construct a path-style SigV4 `BotoStoreClient`."""
    resolved_region = region or str(setting_default("store.region"))
    if _STORE_CLIENT_FACTORY is not None:
        if isinstance(_STORE_CLIENT_FACTORY, StoreClient):
            return _STORE_CLIENT_FACTORY
        return _STORE_CLIENT_FACTORY(
            endpoint_url=endpoint_url,
            region=resolved_region,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
        )
    return BotoStoreClient(
        endpoint_url=endpoint_url,
        region=resolved_region,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
    )


def _error_status_and_code(exc: Any) -> tuple[int | None, str]:
    response = getattr(exc, "response", None) or {}
    meta = response.get("ResponseMetadata", {})
    err = response.get("Error", {})
    status = meta.get("HTTPStatusCode")
    return (int(status) if isinstance(status, int) else None, str(err.get("Code", "")))


def _translate_boto_error(
    exc: Exception,
    *,
    bucket: str,
    key: str | None,
    endpoint_url: str,
    operation: str,
) -> StoreError:
    from botocore import exceptions as botocore_exceptions

    if isinstance(
        exc,
        (
            botocore_exceptions.EndpointConnectionError,
            botocore_exceptions.ConnectTimeoutError,
            botocore_exceptions.ReadTimeoutError,
            ConnectionError,
            TimeoutError,
            OSError,
        ),
    ):
        return StoreError(
            f"Cannot reach content store at {endpoint_url} during {operation}: {exc}",
            bucket=bucket,
            key=key,
            endpoint=endpoint_url,
            unreachable=True,
        )
    if isinstance(exc, botocore_exceptions.ClientError):
        status_code, code = _error_status_and_code(exc)
        return StoreError(
            f"Content store returned {code or 'ClientError'} ({status_code or 'error'}) during {operation}: {exc}",
            bucket=bucket,
            key=key,
            endpoint=endpoint_url,
            status_code=status_code,
            unreachable=False,
        )
    return StoreError(
        f"Content store failure during {operation}: {exc}",
        bucket=bucket,
        key=key,
        endpoint=endpoint_url,
        unreachable=False,
    )


class BotoStoreClient:
    """Real S3 client backed by `boto3` with path-style addressing and SigV4."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        region: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        boto_client: _BotoS3Protocol | None = None,
    ) -> None:
        self._endpoint_url = endpoint_url.rstrip("/")
        self._region = region or str(setting_default("store.region"))
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._use_threads = boto_client is None
        self._s3: _BotoS3Protocol | None = boto_client

    @property
    def endpoint_url(self) -> str:
        """Return the endpoint URL targeted by this client."""
        return self._endpoint_url

    @property
    def s3(self) -> _BotoS3Protocol:
        """Lazily construct the underlying `boto3` S3 client with path-style SigV4 config."""
        if self._s3 is None:
            import boto3
            from botocore.config import Config

            cfg = Config(
                region_name=self._region,
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            )
            self._s3 = boto3.client(
                "s3",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                config=cfg,
            )
        return self._s3

    @contextmanager
    def _s3_errors(self, *, bucket: str, key: str | None, operation: str) -> Iterator[None]:
        from botocore import exceptions as botocore_exceptions

        try:
            yield
        except (
            botocore_exceptions.ClientError,
            botocore_exceptions.BotoCoreError,
            OSError,
        ) as exc:
            raise _translate_boto_error(
                exc,
                bucket=bucket,
                key=key,
                endpoint_url=self._endpoint_url,
                operation=operation,
            ) from exc

    def head_object(self, bucket: str, key: str) -> StoreObjectMeta | None:
        """Return object metadata or `None` when the key does not exist."""
        from botocore import exceptions as botocore_exceptions

        try:
            resp = self.s3.head_object(Bucket=bucket, Key=key)
        except botocore_exceptions.ClientError as exc:
            status_code, code = _error_status_and_code(exc)
            if status_code == 404 or code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise _translate_boto_error(
                exc,
                bucket=bucket,
                key=key,
                endpoint_url=self._endpoint_url,
                operation="HeadObject",
            ) from exc
        except (botocore_exceptions.BotoCoreError, OSError) as exc:
            raise _translate_boto_error(
                exc,
                bucket=bucket,
                key=key,
                endpoint_url=self._endpoint_url,
                operation="HeadObject",
            ) from exc

        raw_meta = resp.get("Metadata") or {}
        lowered = {str(k).lower(): str(v) for k, v in raw_meta.items()}
        size_val = resp.get("ContentLength")
        return StoreObjectMeta(
            bucket=bucket,
            key=key,
            sha256=lowered.get("sha256"),
            content_type=resp.get("ContentType"),
            size=int(size_val) if isinstance(size_val, int) else None,
            etag=resp.get("ETag"),
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
        """Write bytes directly to S3 with Content-Type and optional user metadata."""
        with self._s3_errors(bucket=bucket, key=key, operation="PutObject"):
            self.s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                Metadata=dict(metadata or {}),
            )

    def upload_file(
        self,
        bucket: str,
        key: str,
        source: Path,
        *,
        content_type: str,
        sha256: str,
        multipart_threshold: int = CONST_STORE_MULTIPART_BYTES,
        multipart_chunksize: int = CONST_STORE_MULTIPART_BYTES,
    ) -> None:
        """Upload `source` via `TransferConfig` using 64 MiB parts above threshold."""
        from boto3.s3.transfer import TransferConfig

        config = TransferConfig(
            multipart_threshold=multipart_threshold,
            multipart_chunksize=multipart_chunksize,
            use_threads=self._use_threads,
        )
        with self._s3_errors(bucket=bucket, key=key, operation="PutObject"):
            self.s3.upload_file(
                str(source),
                bucket,
                key,
                ExtraArgs={"ContentType": content_type, "Metadata": {"sha256": sha256}},
                Config=config,
            )

    def list_objects(self, bucket: str, prefix: str) -> list[StoreObjectSummary]:
        """List all objects under `prefix` within `bucket` using ListObjectsV2."""
        entries: list[StoreObjectSummary] = []
        token: str | None = None
        with self._s3_errors(bucket=bucket, key=prefix, operation="ListObjectsV2"):
            while True:
                if token is None:
                    resp = self.s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
                else:
                    resp = self.s3.list_objects_v2(
                        Bucket=bucket, Prefix=prefix, ContinuationToken=token
                    )
                for item in resp.get("Contents") or []:
                    last_mod = item.get("LastModified")
                    entries.append(
                        StoreObjectSummary(
                            key=str(item["Key"]),
                            size=int(item.get("Size", 0)),
                            etag=item.get("ETag"),
                            last_modified=last_mod.isoformat()
                            if hasattr(last_mod, "isoformat")
                            else (str(last_mod) if last_mod is not None else None),
                        )
                    )
                if not resp.get("IsTruncated"):
                    break
                token = str(resp.get("NextContinuationToken", ""))
                if not token:
                    break
        entries.sort(key=lambda entry: entry.key)
        return entries

    def download_file(self, bucket: str, key: str, destination: Path) -> int:
        """Download an object directly into `destination` and return bytes written."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._s3_errors(bucket=bucket, key=key, operation="GetObject"):
            self.s3.download_file(bucket, key, str(destination))
        return destination.stat().st_size

    def get_bytes(self, bucket: str, key: str) -> bytes:
        """Read the full object payload into memory."""
        with self._s3_errors(bucket=bucket, key=key, operation="GetObject"):
            resp = self.s3.get_object(Bucket=bucket, Key=key)
            body = resp["Body"]
            return bytes(body.read())

    def delete_object(self, bucket: str, key: str) -> None:
        """Delete one object from `bucket`."""
        with self._s3_errors(bucket=bucket, key=key, operation="DeleteObject"):
            self.s3.delete_object(Bucket=bucket, Key=key)

    def presign_get(self, bucket: str, key: str, *, expires_in: int) -> str:
        """Generate a SigV4 presigned GET URL valid for `expires_in` seconds."""
        with self._s3_errors(bucket=bucket, key=key, operation="PresignGetObject"):
            return self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )
