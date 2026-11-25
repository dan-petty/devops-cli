# Content Store Specification

## Purpose

Defines the `devops store` CLI command group, S3 client configuration, credential lookup, content-kind mapping, offline pending queue, index pages, and observability guarantees.

## ADDED Requirements

### Requirement: Store command group
The CLI SHALL expose a `devops store` command group with the `publish`, `sync`, `ls`, `get`, `url`, `presign` and `doctor` subcommands.

#### Scenario: Help lists store subcommands
- **WHEN** A user runs `devops store --help`.
- **THEN** The output lists the seven subcommands and the command exits 0.

### Requirement: Required store endpoint
The store commands MUST stop with a non-zero exit and an error that names `store.s3_endpoint` when the setting is unset.

#### Scenario: Unset endpoint
- **WHEN** A user runs `devops store publish` with no `store.s3_endpoint` value.
- **THEN** The command exits non-zero, its error code is `CONFIGURATION_ERROR`, and its text contains `store.s3_endpoint`.

### Requirement: Required web base URL
`url` MUST stop with a non-zero exit and an error that names `store.web_base_url` when the setting is unset.

#### Scenario: Unset web base URL
- **WHEN** A test runs `url` for a web kind with no `store.web_base_url` value.
- **THEN** The command exits non-zero, its error code is `CONFIGURATION_ERROR`, and its text contains `store.web_base_url`.

### Requirement: Content kind mapping
The store module SHALL resolve each content kind to its bucket, prefix, web or private visibility and immutable flag from one named table.

#### Scenario: Kind lookup
- **WHEN** A test looks up the study kind.
- **THEN** The result holds bucket `reports-private`, prefix `studies/`, private visibility and an immutable flag.

### Requirement: Path-style SigV4 and region
The S3 client MUST use path-style addressing and SigV4 with the region from `store.region`, defaulting to `us-east-1`.

#### Scenario: Client configuration
- **WHEN** A test builds the store client with `store.region` unset.
- **THEN** The client config uses path-style addressing, SigV4 and region `us-east-1`.

### Requirement: Keyring credentials
The store client MUST read its access key id and secret access key from the OS keyring through the shared credential seam.

#### Scenario: Credentials from keyring
- **WHEN** A test sets `store.access_key_id` and `store.secret_access_key` in the keyring fake and sets different values in the environment.
- **THEN** The client uses the keyring values and reads no environment variable.

### Requirement: Publish an object
`publish` MUST upload a local file to the bucket and prefix of its content kind.

#### Scenario: Publish a study file
- **WHEN** A test runs `publish` for a study file through the in-memory store fake.
- **THEN** The fake records a PutObject for the study bucket and prefix and the command exits 0.

### Requirement: Object Content-Type and checksum
Each uploaded object MUST carry a `sha256` metadata value and a Content-Type from Python `mimetypes`.

#### Scenario: Upload a JSON file
- **WHEN** A test uploads a `.json` file through the real store client with a botocore Stubber.
- **THEN** The PutObject request holds the file checksum in `sha256` metadata and `application/json` as Content-Type.

### Requirement: Multipart part size
An upload larger than the multipart threshold MUST use 64 MiB parts.

#### Scenario: Large upload
- **WHEN** A test uploads a file larger than the multipart threshold through the real store client with a botocore Stubber.
- **THEN** Each `UploadPart` request declares a part size of 64 MiB, except the last part.

### Requirement: Immutable path guard
A publish that changes an existing immutable path MUST fail unless the command receives `--replace`.

#### Scenario: Changed immutable object
- **WHEN** A test publishes a different checksum to an immutable path without `--replace` through the in-memory store fake.
- **THEN** The command exits non-zero with `STORE_IMMUTABLE_PATH` before the fake records a PutObject request.

### Requirement: Immutable replace override
A publish with `--replace` MUST overwrite an existing immutable path.

#### Scenario: Replace an immutable object
- **WHEN** A test publishes a different checksum to an immutable path with `--replace` through the in-memory store fake.
- **THEN** The fake records a PutObject request and the command exits 0.

### Requirement: Pending queue on store failure
When the store does not answer, `publish` MUST keep the local file, append one line to the pending queue under the resolved data directory, and return status `pending` with exit 0.

#### Scenario: Unreachable store
- **WHEN** A test runs `publish` through the in-memory store fake, which raises a connection error.
- **THEN** The file remains, the pending queue has one new JSON line, and the command exits 0 with status `pending`.

### Requirement: Store answer is not pending
A store that answers with an error status MUST fail with `STORE_ERROR` and MUST NOT append a pending queue line.

#### Scenario: Store answers 500
- **WHEN** A test runs `publish` through the in-memory store fake, which raises a 500 answer.
- **THEN** The command exits non-zero with `STORE_ERROR`, and the pending queue is empty.

### Requirement: Sync drains pending queue
`sync` MUST upload each queued file and remove its queue line after a successful upload.

#### Scenario: Drain pending queue
- **WHEN** A test runs `sync` with one queued file through the in-memory store fake.
- **THEN** The fake records the upload, the queue is empty, and the command exits 0.

### Requirement: Repeat checksum skip
A repeat upload of the same checksum MUST count as sent and MUST make no PutObject request.

#### Scenario: Second sync of same checksum
- **WHEN** A test syncs a file, queues the same file and checksum again, and syncs it through the in-memory store fake.
- **THEN** The second sync records a HeadObject request, records no PutObject request, and exits 0.

### Requirement: Kind index pages
`publish` MUST write `index.html` and `index.json` at the kind root from ListObjectsV2 plus the keys that the command just wrote.

#### Scenario: New window appears in index
- **WHEN** A test publishes a new review window through the in-memory store fake whose ListObjectsV2 answer omits the new key.
- **THEN** Both index objects contain the new key and the command exits 0.

### Requirement: Dry-run network guard
Each store command MUST declare a `request-plan` dry-run class and MUST send no network request, read no keyring entry and write no queue line under `--dry-run`.

#### Scenario: Socket and keyring guard
- **WHEN** A test runs each store command with `--dry-run` under `refuse_requests` and a keyring fake that records reads.
- **THEN** No socket connection opens, no keyring entry is read, no queue line is written, and each command exits 0.

### Requirement: Presign expiry limit
`presign` MUST reject an expiry longer than 7 days.

#### Scenario: Eight-day expiry
- **WHEN** A test requests `presign` with an expiry of 8 days.
- **THEN** The command exits non-zero and the fake records no request.

### Requirement: Presign URL generation
`presign` MUST return a presigned URL for an expiry of at most 7 days.

#### Scenario: Seven-day expiry
- **WHEN** A test requests `presign` with an expiry of 7 days through the in-memory store fake.
- **THEN** The command returns a URL and exits 0.

### Requirement: Web URL command
`url` MUST return the web URL for a key from `store.web_base_url` and the kind prefix.

#### Scenario: URL for a web kind
- **WHEN** A test runs `url` for a key in a web kind.
- **THEN** The command returns the expected URL and exits 0.

### Requirement: Private kind URL refused
`url` MUST refuse a key in a private kind with a non-zero exit and MUST NOT return a web URL.

#### Scenario: URL for a private kind
- **WHEN** A test runs `url` for a key in a private kind.
- **THEN** The command exits non-zero with a typed error and prints no URL.

### Requirement: List kind objects
`ls` MUST list objects under the prefix of a content kind.

#### Scenario: List study objects
- **WHEN** A test runs `ls` for the study kind through the in-memory store fake.
- **THEN** The output contains the stored key and the command exits 0.

### Requirement: Download an object
`get` MUST download the named object to a local path.

#### Scenario: Get a stored file
- **WHEN** A test runs `get` for a stored key through the in-memory store fake.
- **THEN** The local file holds the object bytes and the command exits 0.

### Requirement: Doctor canary
`doctor` MUST put, list, get, presign and delete a canary through `store.s3_endpoint` and through each `--endpoint` given.

#### Scenario: Canary through two endpoints
- **WHEN** A test runs `doctor --endpoint https://s3.example.com` through the in-memory store fake, which records the endpoint of each call.
- **THEN** The fake records the five canary calls against both endpoints and the command exits 0.

### Requirement: Pending upload gauge
The store module MUST set the `devops_cli_store_pending_uploads` gauge to the number of queued uploads.

#### Scenario: Gauge after queue change
- **WHEN** A test appends and drains one pending queue line.
- **THEN** The gauge reads 1 after the append and 0 after the drain.

### Requirement: Cleanup keeps pending files
`devops workspace clean` MUST leave the store directory and the pending queue untouched.

#### Scenario: Cleanup with pending file
- **WHEN** A test writes a stale pending queue and a file it references under the resolved `store/` directory and runs `devops workspace clean`.
- **THEN** Both files remain and the command exits 0.

### Requirement: Store error codes
The store commands MUST return stable typed error codes for configuration, immutable-path and store-answer failures.

#### Scenario: Error code table
- **WHEN** A test triggers each configuration, immutable-path and store-answer failure through the in-memory store fake.
- **THEN** Each failure returns `CONFIGURATION_ERROR`, `STORE_IMMUTABLE_PATH` or `STORE_ERROR` with a non-zero exit.

### Requirement: Store command documentation
The generated CLI reference and `docs/commands/store.md` MUST list each `devops store` subcommand and its purpose.

#### Scenario: Generated docs
- **WHEN** A user runs `uv run devops ci docs`.
- **THEN** The docs check passes and the generated reference and `docs/commands/store.md` list one row for each of the seven subcommands.

### Requirement: boto3 pin
The project MUST pin boto3 to one exact version, resolve that version in the lockfile, and take the newest release that passes the tests with no minimum release age.

#### Scenario: Dependency pin
- **WHEN** A user runs `uv run devops ci lockfile`, `uv run devops ci deps` and `uv run devops ci outdated`.
- **THEN** The lockfile and dependency checks pass, and `ci outdated` names no newer boto3 release.
