"""S3-compatible content store publishing, syncing, and reading subsystem (#4761)."""

from __future__ import annotations

from devops_cli.store.client import (
    BotoStoreClient,
    StoreClient,
    StoreClientFactory,
    StoreObjectMeta,
    StoreObjectSummary,
    install_store_client,
    reset_store_client,
    resolve_store_client,
)
from devops_cli.store.kinds import (
    CONTENT_KINDS,
    ContentKindSpec,
    full_object_key,
    index_keys,
    resolve_content_kind,
)
from devops_cli.store.ops import (
    DoctorEndpointReport,
    PublishResult,
    SyncResult,
    compute_file_sha256,
    get_object_to_file,
    guess_content_type,
    list_kind_objects,
    presign_object,
    publish_file,
    resolve_web_url,
    run_doctor,
    sync_pending,
)
from devops_cli.store.queue import (
    PendingUpload,
    append_pending_upload,
    pending_queue_path,
    read_pending_uploads,
    set_pending_uploads_gauge,
    write_pending_uploads,
)

__all__ = [
    "CONTENT_KINDS",
    "BotoStoreClient",
    "ContentKindSpec",
    "DoctorEndpointReport",
    "PendingUpload",
    "PublishResult",
    "StoreClient",
    "StoreClientFactory",
    "StoreObjectMeta",
    "StoreObjectSummary",
    "SyncResult",
    "append_pending_upload",
    "compute_file_sha256",
    "full_object_key",
    "get_object_to_file",
    "guess_content_type",
    "index_keys",
    "install_store_client",
    "list_kind_objects",
    "pending_queue_path",
    "presign_object",
    "publish_file",
    "read_pending_uploads",
    "reset_store_client",
    "resolve_content_kind",
    "resolve_store_client",
    "resolve_web_url",
    "run_doctor",
    "set_pending_uploads_gauge",
    "sync_pending",
    "write_pending_uploads",
]
