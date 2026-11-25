"""High-level content store operations: publish, sync, ls, get, url, presign, and doctor."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from devops_cli.config.constants import CONST_STORE_MAX_PRESIGN_SECONDS, CONST_STORE_MULTIPART_BYTES
from devops_cli.config.settings import (
    Settings,
    get_store_access_key_id,
    get_store_secret_access_key,
    load_settings,
)
from devops_cli.exceptions import (
    ConfigurationError,
    StoreError,
    StoreImmutablePathError,
    ValidationError,
)
from devops_cli.store.client import StoreClient, StoreObjectSummary, resolve_store_client
from devops_cli.store.indexes import rebuild_kind_indexes
from devops_cli.store.kinds import ContentKindSpec, full_object_key, resolve_content_kind
from devops_cli.store.queue import (
    PendingUpload,
    append_pending_upload,
    read_pending_uploads,
    set_pending_uploads_gauge,
    write_pending_uploads,
)

_HASH_CHUNK_BYTES = 1024 * 1024
_DEFAULT_BINARY_CONTENT_TYPE = "application/octet-stream"


@dataclass(frozen=True)
class PublishResult:
    """Outcome of publishing one artifact to the store or pending queue."""

    status: Literal["uploaded", "skipped", "pending"]
    kind: str
    bucket: str
    key: str
    sha256: str
    size: int
    content_type: str
    url: str | None = None


@dataclass(frozen=True)
class SyncResult:
    """Summary of draining the local pending queue."""

    uploaded: int
    skipped: int
    remaining: int


@dataclass(frozen=True)
class DoctorEndpointReport:
    """Canary verification result for one store endpoint."""

    endpoint: str
    canary_key: str
    operations: tuple[str, ...]


def compute_file_sha256(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file in streaming chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def guess_content_type(path: Path) -> str:
    """Infer a MIME Content-Type via Python `mimetypes`, defaulting cleanly."""
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or _DEFAULT_BINARY_CONTENT_TYPE


def require_s3_endpoint(settings: Settings) -> str:
    """Return `store.s3_endpoint` or raise `ConfigurationError` naming `store.s3_endpoint`."""
    endpoint = settings.store.s3_endpoint
    if not endpoint or not str(endpoint).strip():
        raise ConfigurationError(
            "Content store S3 endpoint is not configured; set `store.s3_endpoint`.",
            key="store.s3_endpoint",
        )
    return str(endpoint).rstrip("/")


def require_web_base_url(settings: Settings) -> str:
    """Return `store.web_base_url` or raise `ConfigurationError` naming `store.web_base_url`."""
    web_base = settings.store.web_base_url
    if not web_base or not str(web_base).strip():
        raise ConfigurationError(
            "Content store web base URL is not configured; set `store.web_base_url`.",
            key="store.web_base_url",
        )
    return str(web_base).rstrip("/")


def build_client_from_settings(
    settings: Settings,
    *,
    endpoint_url: str | None = None,
) -> StoreClient:
    """Resolve endpoint, region, and keyring credentials to construct a `StoreClient`."""
    target_endpoint = endpoint_url.rstrip("/") if endpoint_url else require_s3_endpoint(settings)
    return resolve_store_client(
        endpoint_url=target_endpoint,
        region=settings.store.region,
        access_key_id=get_store_access_key_id(settings),
        secret_access_key=get_store_secret_access_key(settings),
    )


def _public_url_if_web(settings: Settings, spec: ContentKindSpec, full_key: str) -> str | None:
    if spec.visibility != "web":
        return None
    web_base = settings.store.web_base_url
    if not web_base:
        return None
    return f"{str(web_base).rstrip('/')}/{full_key}"


def _upload_with_immutable_guard(
    client: StoreClient,
    spec: ContentKindSpec,
    source: Path,
    full_key: str,
    *,
    sha256: str,
    content_type: str,
    replace: bool,
) -> Literal["uploaded", "skipped"]:
    head = client.head_object(spec.bucket, full_key)
    if head is not None:
        if head.sha256 == sha256:
            return "skipped"
        if spec.immutable and not replace:
            raise StoreImmutablePathError(
                f"Immutable path s3://{spec.bucket}/{full_key} already exists with a different "
                "checksum; pass `--replace` to overwrite.",
                bucket=spec.bucket,
                key=full_key,
                endpoint=client.endpoint_url,
            )
    client.upload_file(
        spec.bucket,
        full_key,
        source,
        content_type=content_type,
        sha256=sha256,
        multipart_threshold=CONST_STORE_MULTIPART_BYTES,
        multipart_chunksize=CONST_STORE_MULTIPART_BYTES,
    )
    return "uploaded"


def publish_file(
    kind: str,
    source: Path,
    *,
    key: str | None = None,
    replace: bool = False,
    settings: Settings | None = None,
) -> PublishResult:
    """Publish a local artifact to its content kind, queueing offline if unreachable."""
    cfg_settings = settings or load_settings()
    spec = resolve_content_kind(kind)
    if not source.is_file():
        raise ValidationError(f"Source file does not exist: {source}", field="path")
    full_key = full_object_key(spec, key or source.name)
    require_s3_endpoint(cfg_settings)
    client = build_client_from_settings(cfg_settings)

    size = source.stat().st_size
    sha256 = compute_file_sha256(source)
    content_type = guess_content_type(source)

    try:
        outcome = _upload_with_immutable_guard(
            client,
            spec,
            source,
            full_key,
            sha256=sha256,
            content_type=content_type,
            replace=replace,
        )
        if outcome == "uploaded":
            rebuild_kind_indexes(
                client,
                spec,
                written_objects=[(full_key, size, sha256, content_type)],
            )
    except StoreError as exc:
        if not exc.unreachable:
            raise
        append_pending_upload(
            PendingUpload(
                kind=spec.name,
                local_path=str(source.resolve()),
                key=full_key,
                sha256=sha256,
                content_type=content_type,
                replace=replace,
            )
        )
        return PublishResult(
            status="pending",
            kind=spec.name,
            bucket=spec.bucket,
            key=full_key,
            sha256=sha256,
            size=size,
            content_type=content_type,
            url=None,
        )

    return PublishResult(
        status=outcome,
        kind=spec.name,
        bucket=spec.bucket,
        key=full_key,
        sha256=sha256,
        size=size,
        content_type=content_type,
        url=_public_url_if_web(cfg_settings, spec, full_key),
    )


def sync_pending(*, settings: Settings | None = None) -> SyncResult:
    """Drain queued uploads from `store/pending.jsonl`, skipping identical remote checksums."""
    entries = read_pending_uploads()
    if not entries:
        set_pending_uploads_gauge(0)
        return SyncResult(uploaded=0, skipped=0, remaining=0)

    cfg_settings = settings or load_settings()
    require_s3_endpoint(cfg_settings)
    client = build_client_from_settings(cfg_settings)

    uploaded = 0
    skipped = 0
    written_by_kind: dict[str, list[tuple[str, int, str | None, str | None]]] = defaultdict(list)
    remaining = list(entries)

    try:
        for entry in entries:
            spec = resolve_content_kind(entry.kind)
            local_file = Path(entry.local_path)
            if not local_file.is_file():
                raise ValidationError(
                    f"Queued local file no longer exists: {local_file}",
                    field="local_path",
                )
            sha256 = compute_file_sha256(local_file)
            size = local_file.stat().st_size
            outcome = _upload_with_immutable_guard(
                client,
                spec,
                local_file,
                entry.key,
                sha256=sha256,
                content_type=entry.content_type,
                replace=entry.replace,
            )
            if outcome == "skipped":
                skipped += 1
            else:
                uploaded += 1
                written_by_kind[spec.name].append((entry.key, size, sha256, entry.content_type))
            remaining.pop(0)
    finally:
        write_pending_uploads(remaining)

    for kind_name, written in written_by_kind.items():
        rebuild_kind_indexes(client, resolve_content_kind(kind_name), written_objects=written)

    return SyncResult(uploaded=uploaded, skipped=skipped, remaining=len(remaining))


def list_kind_objects(
    kind: str,
    *,
    prefix: str = "",
    settings: Settings | None = None,
) -> list[StoreObjectSummary]:
    """List stored objects under `kind` (optionally narrowed by sub-prefix)."""
    cfg_settings = settings or load_settings()
    spec = resolve_content_kind(kind)
    require_s3_endpoint(cfg_settings)
    client = build_client_from_settings(cfg_settings)
    query_prefix = full_object_key(spec, prefix) if prefix.strip() else spec.prefix
    return client.list_objects(spec.bucket, query_prefix)


def get_object_to_file(
    kind: str,
    key: str,
    destination: Path,
    *,
    settings: Settings | None = None,
) -> int:
    """Download one object of `kind` into `destination` and return bytes written."""
    cfg_settings = settings or load_settings()
    spec = resolve_content_kind(kind)
    full_key = full_object_key(spec, key)
    require_s3_endpoint(cfg_settings)
    client = build_client_from_settings(cfg_settings)
    return client.download_file(spec.bucket, full_key, destination)


def resolve_web_url(
    kind: str,
    key: str,
    *,
    settings: Settings | None = None,
) -> str:
    """Build the public web URL for a `web`-visibility content kind, refusing private kinds."""
    cfg_settings = settings or load_settings()
    spec = resolve_content_kind(kind)
    full_key = full_object_key(spec, key)
    if spec.visibility != "web":
        raise StoreError(
            f"Content kind '{spec.name}' is private and has no web URL; "
            "use `devops store presign` instead.",
            bucket=spec.bucket,
            key=full_key,
        )
    base_url = require_web_base_url(cfg_settings)
    return f"{base_url}/{full_key}"


def presign_object(
    kind: str,
    key: str,
    *,
    expires_in: int = 3600,
    settings: Settings | None = None,
) -> str:
    """Generate a SigV4 presigned GET URL capped at 7 days (604,800 seconds)."""
    if expires_in <= 0 or expires_in > CONST_STORE_MAX_PRESIGN_SECONDS:
        raise ValidationError(
            f"Presign expiry must be between 1 and {CONST_STORE_MAX_PRESIGN_SECONDS} seconds (7 days).",
            field="expires",
        )
    spec = resolve_content_kind(kind)
    full_key = full_object_key(spec, key)
    cfg_settings = settings or load_settings()
    require_s3_endpoint(cfg_settings)
    client = build_client_from_settings(cfg_settings)
    return client.presign_get(spec.bucket, full_key, expires_in=expires_in)


def run_doctor(
    *,
    extra_endpoints: Sequence[str] = (),
    settings: Settings | None = None,
) -> list[DoctorEndpointReport]:
    """Run put, list, get, presign, and delete canary checks against every target endpoint."""
    cfg_settings = settings or load_settings()
    primary = require_s3_endpoint(cfg_settings)
    endpoints: list[str] = [primary]
    for raw_ep in extra_endpoints:
        cleaned = raw_ep.strip().rstrip("/")
        if cleaned and cleaned not in endpoints:
            endpoints.append(cleaned)

    canary_spec = resolve_content_kind("review-session")
    canary_token = uuid.uuid4().hex
    canary_prefix = f"{canary_spec.prefix}.doctor-canary/"
    canary_key = f"{canary_prefix}{canary_token}.json"
    canary_payload = (json.dumps({"canary": canary_token}) + "\n").encode("utf-8")
    canary_sha = hashlib.sha256(canary_payload).hexdigest()

    reports: list[DoctorEndpointReport] = []
    for endpoint in endpoints:
        client = build_client_from_settings(cfg_settings, endpoint_url=endpoint)
        client.put_bytes(
            canary_spec.bucket,
            canary_key,
            canary_payload,
            content_type="application/json",
            metadata={"sha256": canary_sha},
        )
        listed = client.list_objects(canary_spec.bucket, canary_prefix)
        if not any(item.key == canary_key for item in listed):
            raise StoreError(
                f"Canary object {canary_key} missing from listing on {endpoint}.",
                bucket=canary_spec.bucket,
                key=canary_key,
                endpoint=endpoint,
            )
        fetched = client.get_bytes(canary_spec.bucket, canary_key)
        if fetched != canary_payload:
            raise StoreError(
                f"Canary readback mismatch for {canary_key} on {endpoint}.",
                bucket=canary_spec.bucket,
                key=canary_key,
                endpoint=endpoint,
            )
        presigned = client.presign_get(canary_spec.bucket, canary_key, expires_in=60)
        if not presigned:
            raise StoreError(
                f"Presign returned empty URL for {canary_key} on {endpoint}.",
                bucket=canary_spec.bucket,
                key=canary_key,
                endpoint=endpoint,
            )
        client.delete_object(canary_spec.bucket, canary_key)
        reports.append(
            DoctorEndpointReport(
                endpoint=endpoint,
                canary_key=canary_key,
                operations=("put", "list", "get", "presign", "delete"),
            )
        )
    return reports
