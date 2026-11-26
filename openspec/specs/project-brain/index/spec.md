# project-brain/index Specification

## Purpose

The brain index of the alternatives results in `valkey-roadmap` (ADR 0023 section 3): the entry that the block and the job record of an issue give, the keys of the index, the step `brain-sync` of the alternatives row that writes them from the listing snapshot, its instruments, and the roadmap Service pod as the first client of the store.

## Requirements

### Requirement: Snapshot-only sync
The step `brain-sync` of the alternatives row SHALL build the brain entries of each changed issue from the issues that the store of the round holds, which are the listing snapshot and the writes of the round, and SHALL send no GitHub request. It SHALL run after the checks of the round, also when the round selected no item.

#### Scenario: Three changed issues and no GitHub call
- **WHEN** the snapshot holds 3 changed issues that each hold a check, and the brain index is empty
- **THEN** the sync writes 3 `brain-item` hashes, and the fake GitHub API records 0 requests

#### Scenario: The row copies the checks of its round
- **WHEN** the alternatives row checks 5 items of a public repository with the store installed
- **THEN** the index holds one `brain-item` hash for each of the 5 items, each with the verdict of its block

### Requirement: The entry of an issue comes from its job record and its block
The entry of an issue SHALL take the verdict, `checked_at`, `body_hash`, `adr_hash`, the URL of the tool and its canonical id from the keys `alternatives.*` of the job record, and the name of the tool from the tool line of the alternatives block. A check that recorded no canonical id SHALL take the canonical id of its tool URL.

#### Scenario: A check with a tool
- **WHEN** a closed issue holds the block and the record of a `covers` check with a tool
- **THEN** the entry holds each value of the record, the name that the tool line writes for the tool, and the state `closed`

#### Scenario: A check from before the canonical id
- **WHEN** the record holds the URL of a PyPI page as its tool and no canonical id
- **THEN** the entry holds the package URL `pkg:pypi/<name>` of that page as its tool id

### Requirement: Both forms of the block give one entry
The entry SHALL read the block of the check alone and the block with the sections of the reference step as the same entry. An issue with no block of the job, with no recorded verdict or with no recorded time of a check, and a pull request, SHALL give no entry.

#### Scenario: Both forms of the block
- **WHEN** one job record is read with the block of the check alone and with the block that also holds the sections `Reference implementations:` and `Official documentation:`
- **THEN** both give the same entry

#### Scenario: A skip class
- **WHEN** the block holds `Class: docs, no search.` or `Class: docs, no model call.` and the record holds the verdict `not-applicable` and no tool
- **THEN** the entry holds the verdict `not-applicable`, no tool id and no ADR hash

#### Scenario: A record with no block
- **WHEN** the record holds a verdict and a time, and the body holds no block of the job
- **THEN** the issue gives no entry

### Requirement: Item hash contents
Each `roadmap:v1:brain-item:<owner>/<name>:<n>` hash SHALL hold the verdict, the tool id, at most 3 reference ids, at most 5 near items, `checked_at`, `body_hash`, `adr_hash`, the state of the issue, the used entries of `alternatives.brain_used` (at most 10) and the schema, with a TTL of 45 days. A reference SHALL be the GitHub repository of a link of `alternatives.refs`, one time for each repository, and its id SHALL be 16 hex characters of the SHA-256 of the URL of the repository.

#### Scenario: A check with 4 references keeps 3
- **WHEN** the record of an issue gives the verdict `covers`, one tool id and links to 4 GitHub repositories in `alternatives.refs`
- **THEN** the item hash holds 3 reference ids and each named field, and `TTL` returns 3888000

#### Scenario: Two links to one repository
- **WHEN** `alternatives.refs` holds two permalinks to one repository and a link to a documentation page outside GitHub
- **THEN** the entry holds that repository one time, and no reference for the documentation page

### Requirement: Tool and reference entries name their items
Each `roadmap:v1:brain-tool:<owner>/<name>:<id>` hash SHALL hold the canonical id of the tool, its URL, the name that the check wrote and the numbers of the items of the repository whose check names the tool, with `<id>` as 16 hex characters of the SHA-256 of the canonical id. Each `roadmap:v1:brain-ref:<owner>/<name>:<id>` hash SHALL hold the URL of the repository and the numbers of the items that link it.

#### Scenario: The hashes of one item
- **WHEN** the sync writes an item with a tool that 3 items name and two references
- **THEN** the tool hash holds the id, the URL, the name and the 3 item numbers, and each reference hash holds its URL and its item numbers

### Requirement: Near items name the same tool
The near items of an item SHALL be the other items of the same repository whose check names the same tool, the newest check first, at most 5. An entry SHALL NOT name an item of another repository.

#### Scenario: Seven items of one tool
- **WHEN** 7 items of one repository name one tool, with checks of 7 different times
- **THEN** the item hash of the item with the oldest check names the 5 other items with the newest checks, the newest first, and the tool hash names the 7 items

### Requirement: Catch-up after an outage
The step SHALL keep the `updated_at` and the number of the last issue that it examined in the watermark `roadmap:v1:brain-sync:<owner>/<name>`, and SHALL copy each issue after that place, the oldest change first, at most 500 in one round. An issue that changed and holds no check SHALL move the place and write no entry.

#### Scenario: Three issues changed during an outage
- **WHEN** the watermark is older than the `updated_at` of 3 issues, a fourth issue did not change, and the sync runs
- **THEN** the sync copies exactly the 3 issues, the stream gets 3 entries, and the watermark holds the `updated_at` and the number of the last of them

#### Scenario: More changed issues than the bound
- **WHEN** 3 issues changed in the same second and the bound of a sync is 2
- **THEN** the sync copies the 2 issues with the lower numbers, and the next sync copies the third and no issue a second time

### Requirement: Newer check wins
The brain entry MUST keep the copy with the newer `checked_at`. A block with a `checked_at` that is equal to or after the one of the entry SHALL replace the entry, and a block with an older `checked_at` SHALL change nothing.

#### Scenario: An older index entry meets a newer block
- **WHEN** the index holds an entry with an older `checked_at`, and the block gives a newer `checked_at` and another `body_hash`
- **THEN** the sync overwrites the entry, and the hash holds the newer `checked_at` and `body_hash`

#### Scenario: A late copy of an older block
- **WHEN** the index holds the entry of a check, and a copy of the issue from before that check is written
- **THEN** the hash keeps the newer `checked_at` and `body_hash`, and the client sends no second transaction

### Requirement: One transaction for each item
The step SHALL write the keys of one item and its `brain-events` entry in one MULTI/EXEC transaction that watches the item key.

#### Scenario: One item, one transaction
- **WHEN** the sync writes the keys of one changed item with a tool and two references
- **THEN** the fake Valkey records one MULTI/EXEC that holds the item hash, the tool hash, the two reference hashes and one `XADD` of `roadmap:v1:brain-events:<owner>/<name>` with `MAXLEN ~ 10000`, each with its `EXPIRE`

### Requirement: Instruments
A sync that completes SHALL observe `devops_cli_brain_entries` and `devops_cli_brain_sync_lag_seconds` with the labels `store="brain_index"` and `repo`, and SHALL add the first reads of the round to `devops_cli_brain_first_reads_total` with the label `row`. The lag SHALL be the time from the end of the last sync that completed to the start of this one. Each of the three SHALL be an entry of `INSTRUMENTS`.

#### Scenario: A round reports the three instruments
- **WHEN** the sync writes one item, no check ran in the round, and the last sync ended 120 s before
- **THEN** `devops_cli_brain_entries` reads 1, `devops_cli_brain_sync_lag_seconds{store="brain_index"}` reads 120, and `devops_cli_brain_first_reads_total` reads 0

### Requirement: Prefix scan stays in one repository
The SCAN pattern of the item entries of one repository SHALL NOT match a key of a repository whose name starts with the same characters.

#### Scenario: `o/n` does not match `o/nn`
- **WHEN** the index holds the item keys of `o/n` and of `o/nn`, and the index of `o/n` scans `roadmap:v1:brain-item:o/n:*`
- **THEN** the scan returns the keys of `o/n` only

### Requirement: TTL or one owner
Each key of the brain index SHALL start with `roadmap:v1:brain-` and SHALL have a TTL of 45 days, the stream `brain-events` too, except the watermark key, which MUST have no TTL and one owner, the step `brain-sync`.

#### Scenario: Scan of the store
- **WHEN** the index wrote the item, tool, reference, stream and watermark keys of one repository, and a second client scans each key of the store
- **THEN** each `brain-item`, `brain-tool`, `brain-ref` and `brain-events` key has a TTL of 3888000, the `brain-sync` key has no TTL, and no transaction of an item names the `brain-sync` key

### Requirement: A round without a connection
The alternatives round SHALL finish and SHALL add one `fallback` to `devops_cli_brain_reads_total` with the store `brain_index` when the store of the brain index is not configured or does not answer. A sync that stops at a write SHALL write no sync time and SHALL keep the place of its last copy.

#### Scenario: No connection to Valkey
- **WHEN** `connected` is `False` and a round checks 3 items
- **THEN** the round writes its 3 blocks, finishes, counts one `fallback`, and writes no brain key

#### Scenario: No store
- **WHEN** the process names no `roadmap.state.url` and a sync runs
- **THEN** the sync finishes and counts one `fallback`

#### Scenario: The store refuses a later write
- **WHEN** the store answers the copy of the first of 2 changed issues and refuses the copy of the second
- **THEN** the sync counts one `fallback`, the watermark holds the place of the first issue and no sync time, and the next sync copies the second issue only

### Requirement: First read of an unchecked item
The alternatives check SHALL write the verdict that it finds when the brain index has no entry for the item, and the round SHALL count that check as one first read.

#### Scenario: T8, the index is empty
- **WHEN** the index holds no entry for the item and the check finds the verdict `none`
- **THEN** the round writes `none` to the block and to the index, and `devops_cli_brain_first_reads_total` counts 1

### Requirement: No entry of a private repository
The step SHALL make no sync for a round whose check is off, as for a private repository.

#### Scenario: A private repository
- **WHEN** the alternatives round of a private repository runs with the store installed
- **THEN** the step makes no sync, counts no `fallback`, and the store holds no key

### Requirement: The roadmap Service pod reaches valkey-roadmap
The pod template of Deployment `roadmap-service` SHALL have the label `valkey-client: "true"`. The policy `roadmap-service-egress` SHALL hold one rule to the pods with the label `app.kubernetes.io/name: valkey` of namespace `devops` on TCP 6379, and no wider rule to the store.

#### Scenario: The k8s check validates the policy
- **WHEN** a person runs `uv run devops ci --check --only k8s,kube-linter`
- **THEN** both rows pass, and the egress list of `roadmap-service-egress` is the rule of the API server and the rule of the store

### Requirement: The roadmap Service pod sends the user brain
The container of Deployment `roadmap-service` SHALL read `DEVOPS_CLI_ROADMAP_STATE_PASSWORD` from key `brain` of Secret `valkey-roadmap-auth` through an optional `secretKeyRef`, and `k8s/devops/configmap.example.yaml` SHALL name the user `brain` in `roadmap.state.username`. No Job template and no container `agent` SHALL get a key of the store. The aclfile of `valkey-roadmap` gives `brain` read and write on `~roadmap:v1:brain-*` and `agent` read only (`roadmap-state/store`).

#### Scenario: The k8s check validates the Deployment
- **WHEN** a person runs `uv run devops ci --check --only k8s`
- **THEN** the row builds `k8s/devops` with the variable of the Deployment, reports no finding for the aclfile of `valkey-roadmap`, and exits 0

### Requirement: Pending a person after the merge
After the merge and the release, the alternatives step MUST run as the App on 3 items and write their results to the brain index.

#### Scenario: Live proof on 3 items
- **WHEN** after the merge and the release, ConfigMap `devops-cli-config` holds `roadmap.state.url` and `roadmap.state.username`, and the alternatives row of the Service checks 3 items as the App
- **THEN** a comment on the issue gives the result line of each item, its brain index entry from `HGETALL roadmap:v1:brain-item:<owner>/<name>:<n>`, and `devops_cli_brain_sync_lag_seconds{store="brain_index"}` against the interval of the alternatives row
