# Design

## Decisions

- **S3 SDK and addressing**: Use `boto3` configured with `signature_version="s3v4"`, `s3={"addressing_style": "path"}`, and `store.region` defaulting to `us-east-1` (`DEFAULT_STORE_REGION`). Import `boto3` and `botocore` lazily in `BotoStoreClient` so CLI `--help` startup stays within the module-count budget.
- **Typed dependency stubs without mypy suppressions**: Declare `boto3==1.44.11` and `botocore==1.44.11` in `pyproject.toml` and add local `.pyi` stubs under `typings/` rather than adding `[[tool.mypy.overrides]]`.
- **Credentials and required config**: Register `store.access_key_id` and `store.secret_access_key` in `CREDENTIALS` without `in_file=True`, read through the shared `SecretResolver` chain, and fail with `ConfigurationError` naming `store.s3_endpoint` or `store.web_base_url` when required and unset.
- **Content-kind mapping**: Centralize buckets, prefixes, visibility (`web` or `private`), and immutability in `CONTENT_KINDS` (`review-window` -> `reports`/`windows/`, `study` -> `reports-private`/`studies/`, `review-session` -> `reports-private`/`sessions/`).
- **Offline pending queue & checksum deduplication**: Store queued uploads in `resolve_store_path("store/pending.jsonl")` and report depth via `STORE_PENDING_UPLOADS` (`devops_cli_store_pending_uploads`). Connection/timeout errors queue and exit `0` with `pending`; HTTP error responses raise `StoreError` without queueing; changed immutable paths without `--replace` raise `StoreImmutablePathError`; matching remote `sha256` skips `PutObject`.
- **Lagging-listing index merge**: Build `<prefix>index.html` and `<prefix>index.json` by merging `ListObjectsV2` results with objects written in the current run.
- **Seam and testing**: Isolate S3 behind the `StoreClient` protocol and `install_store_client` seam, provide `InMemoryStoreClient` in `tests/support/fakes/store.py`, and verify `BotoStoreClient` parameters (`ContentType`, `sha256` metadata, 64 MiB multipart chunks) with `botocore.stub.Stubber`.

## Rejected alternatives

- **AWS CLI or rclone subprocesses**: Adds an external binary dependency and lacks keyring, queue, and merged-index handling.
- **SQLite queue**: Adds schema migration overhead for a small append-only JSONL queue.
- **Virtual-hosted SigV4**: Requires per-bucket DNS instead of the single SeaweedFS S3 gateway host.
- **moto test server**: Unnecessary heavy test dependency when `StoreClient` seam + `botocore.stub.Stubber` verify both behavior and wire parameters.
