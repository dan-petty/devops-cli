# Proposal: #4761

## Why

`devops-cli` writes review windows, research studies, and review sessions only to local files. Workstations need a `devops store` command group to publish and read objects in SeaweedFS S3 buckets with OS keyring credentials, handle an unreachable store with a local pending queue, and publish root index pages.

## What Changes

- Add runtime dependencies `boto3==1.44.11` and `botocore==1.44.11` with local `.pyi` stubs under `typings/`.
- Add `StoreConfig` (`store.s3_endpoint`, `store.web_base_url`, `store.region`) in settings and register `store.access_key_id` and `store.secret_access_key` in `CREDENTIALS`.
- Add `StoreError` (`STORE_ERROR`) and `StoreImmutablePathError` (`STORE_IMMUTABLE_PATH`) exceptions and export them cleanly.
- Add `STORE_PENDING_UPLOADS` (`devops_cli_store_pending_uploads`) gauge in telemetry instruments.
- Add `src/devops_cli/store/` (`kinds`, `client`, `queue`, `indexes`, `ops`, `store_plans`) and `src/devops_cli/commands/store.py` exposing `publish`, `sync`, `ls`, `get`, `url`, `presign`, and `doctor`.
- Add an in-memory `StoreClient` seam fake in `tests/support/fakes/store.py`, contract tests using `botocore.stub.Stubber`, CLI tests, and cleanup retention tests.
- Regenerate CLI, configuration, and error reference docs including `docs/commands/store.md`.

## Capabilities

### New Capabilities

- `content-store`: CLI and domain layer for publishing, queueing, syncing, listing, reading, URL generation, presigning, and canary probing across platform object-store buckets.

## Impact

- Users gain `devops store` subcommands backed by OS keyring credentials and explicit endpoint configuration.
- `devops workspace clean` continues to preserve `.data/store/` and `pending.jsonl` because `store/` sits outside `PRUNED_SUBDIRECTORIES`.
- Startup import budgets remain intact because `boto3` and `botocore` are imported lazily inside `BotoStoreClient`.

## Feasibility

Verified locally: SeaweedFS platform buckets (`reports`, `reports-private`) and `TransferConfig` 64 MiB usage already exist in `k8s/object-store/build-test/scripts.yaml`, and `boto3==1.44.11` / `botocore==1.44.11` are already resolved in `uv.lock`.

## Existing Tool Considered

Use `boto3` (Apache-2.0) for S3 API calls, path-style SigV4 signing, 64 MiB multipart transfer, metadata headers, and presigned URLs. Build keyring credential lookup, content-kind mapping, JSONL pending queue, index pages, doctor canary, dry-run request plans, and tests in `devops-cli`. Rejected alternatives: AWS CLI, `rclone`, and custom HTTP S3 signing.
