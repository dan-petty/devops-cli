## Purpose
The shared tier of the project brain in the cache Valkey `valkey-devops` (ADR 0023 section 2): the listing snapshot of each public repository and the tool facts that the alternatives check reads, over the in-process tier, with a fallback to the local tier or the source when Valkey is slow or down, and the memory bound of the cache Valkey that holds them.

## ADDED Requirements

### Requirement: A cold process reads the shared listing snapshot
When a process has no local snapshot of a public repository and the shared tier holds a fit snapshot of it, the listing read SHALL start from the shared snapshot and read only the issues changed since its watermark, and SHALL count the full read that it saved in `devops_cli_brain_github_requests_saved_total{store="snapshot"}`.

#### Scenario: Warm shared snapshot, cold process
- **WHEN** a test saves a snapshot of 250 issues of a public repository through one `TieredSnapshotStore` on the `valkey_server` fake, and a new `TieredSnapshotStore` with an empty local directory reads the listing of that repository through `IncrementalListing` while GitHub lists 3 issues as changed
- **THEN** the read sends at most 2 listing requests, each with `since=<watermark>`, it returns 250 issues with the new title of each changed issue, the local file holds the new snapshot, and `devops_cli_brain_github_requests_saved_total{store="snapshot"}` rises by 3

#### Scenario: The newer of the two copies
- **WHEN** the local file holds a snapshot with the watermark 09:00 and the shared tier holds one with the watermark 10:00, both with the current schema key and a full read of less than 24 hours
- **THEN** the listing read sends `since=` with the watermark 10:00

### Requirement: A load counts the tier that gave the snapshot
A load of the tiered snapshot store SHALL count `devops_cli_brain_reads_total{store="snapshot"}` with `result="local"` when it gives the fit local copy, `result="shared"` when it gives the shared copy, and `result="source"` only when no tier holds a fit copy, so the run reads the whole listing.

#### Scenario: Local and source loads
- **WHEN** a load runs with no copy in either tier, and a second load runs after a save that put the same snapshot in both tiers
- **THEN** the first load counts `source`, and the second load returns the local copy and counts `local`

### Requirement: A read of the shared tier fills the in-process tier
A `TieredMapping` read that misses the in-process tier and hits the shared tier SHALL put the value in the in-process tier, and the next read of the key SHALL send no command to Valkey.

#### Scenario: T1 read fills the in-process tier
- **WHEN** one `TieredMapping` writes a fact on the `valkey_server` fake, and a second `TieredMapping` with an empty in-process tier reads the key twice
- **THEN** both reads return the fact, the fake receives one read command for the key, and `devops_cli_brain_reads_total{store="fact"}` counts one `shared` and one `memory`

### Requirement: The tiers fall back while the shared tier is down
While the shared tier fails or its breaker is open, a read SHALL return the value of the in-process tier, the local tier or the source, a write SHALL stay in the in-process tier or the local file, and the counters SHALL count `fallback` and `skipped`. After one failed command the process SHALL send no command to Valkey until the cooldown of 60 s ends.

#### Scenario: T2 disconnected tier
- **WHEN** the `valkey_server` fake has `connected = False` and a listing round and two fact reads run within one cooldown
- **THEN** the round returns the issues that GitHub lists, the local file holds the new snapshot, each fact read returns the source value, the fake receives no second command after the first failure, `devops_cli_brain_reads_total{result="fallback"}` and `devops_cli_brain_writes_total{result="skipped"}` rise, and no error reaches the caller

#### Scenario: T3 silent shared tier
- **WHEN** the shared tier is a loopback listener that accepts the connection and answers no command, and `valkey.timeout` is 0.05 s
- **THEN** the tier's client has a connect timeout of at most 0.25 s, the first read ends with `devops_cli_valkey_cache_errors_total{error="timeout"}` and returns the source value, the breaker opens, and the next read sends nothing to the listener

#### Scenario: A lost connection in a WATCH transaction
- **WHEN** the `valkey_server` fake stops after the WATCH, or after the read of the watched field and before the EXEC
- **THEN** the WATCH transaction gives no result, `devops_cli_valkey_cache_errors_total{op="watch",error="connection"}` rises by one, and the breaker opens, as for each other failed command, and not as for a lost race

### Requirement: A trial after the cooldown and the newest watermark
After the cooldown the first command SHALL be a trial that closes the breaker when it succeeds. A writer of the shared snapshot SHALL write only when its watermark is not older than the stored watermark or the stored copy has another schema key, and a writer whose WATCH transaction another client made fail SHALL write nothing and SHALL NOT retry.

#### Scenario: T4 trial, newer local copy and lost WATCH
- **WHEN** the breaker is open with a shared snapshot of watermark 09:00, the `clock` fixture passes the cooldown, a process saves a snapshot of watermark 10:00, and then a second writer with watermark 09:30 loses its WATCH transaction to a write of watermark 10:30 by another client
- **THEN** the trial closes the breaker, the shared snapshot has watermark 10:00 after the first save, the second writer's transaction writes nothing, the shared snapshot keeps watermark 10:30, and `devops_cli_brain_writes_total{result="older"}` rises by one

#### Scenario: An older writer
- **WHEN** the shared snapshot has watermark 10:00 and a writer saves a snapshot with watermark 09:00 and the same schema key
- **THEN** the shared snapshot keeps watermark 10:00 and its records, and the local file holds the snapshot with watermark 09:00

### Requirement: A save leaves the shared snapshot with its records only
A save that may replace the shared snapshot SHALL leave it with the records of the saved snapshot only, so it holds no issue that a full read did not list. A save that knows the stored records SHALL send only the changed and removed records and the new `meta` in one WATCH transaction. Any other save SHALL write the records to a temporary key with a TTL and RENAME it onto the snapshot key in one transaction.

#### Scenario: An issue left the repository
- **WHEN** the shared snapshot holds issues 1, 2 and 3, and a full read lists issues 1 and 3
- **THEN** the shared snapshot holds issues 1 and 3 only, and no temporary key stays

### Requirement: A save of the records that the shared copy holds writes no record
A save whose records, schema key and watermark the shared snapshot already holds, with a full read that is not newer than the stored one, SHALL send no record and no transaction: it SHALL set the TTL of the key again, keep the stored `meta`, and count `devops_cli_brain_writes_total{result="unchanged"}`.

#### Scenario: Two lanes and a new process with the same records
- **WHEN** two lanes of one process save the same 1,200 records and watermark with full reads at 08:00 and 09:00, and then each saves them again twice, and a new process saves them once
- **THEN** after the first save of each lane, the lanes send only `HGET` and `EXPIRE` commands, the stored `meta` does not change, `devops_cli_brain_writes_total{result="unchanged"}` rises by five, and no temporary key stays

### Requirement: A load uses only the records that its meta names
A load SHALL use the records of the shared snapshot only when their digest is the digest of the `meta` that the load read first. A new `meta` of the same records during the scan SHALL NOT make the load a miss. A value of the shared tier is untrusted: a `meta` or a record with a time with no UTC offset, and a record that expands past 1 MiB, SHALL make the shared copy a miss, and the next save SHALL replace it.

#### Scenario: A new meta of the same records during a load
- **WHEN** a writer saves the same 1,200 records with a newer full read after the first `HSCAN` of a cold load
- **THEN** the load gives the 1,200 records of the shared copy and counts `result="shared"`

#### Scenario: A time with no offset or a record past the bound
- **WHEN** the shared snapshot is newer than the local one, and its `meta` holds a time with no UTC offset, or a record holds one, or a record expands to more than 1 MiB of JSON
- **THEN** the load gives the local snapshot and raises no error, and the next save leaves the shared snapshot with its own watermark and records

### Requirement: Each value has a bound and each key a TTL
The shared tier SHALL NOT receive a value whose encoded form is over 1 MiB; such a value SHALL stay in the in-process tier and count `devops_cli_brain_writes_total{result="oversize"}`. Each key that the mapping or the snapshot store writes SHALL have a TTL: 24 hours for a fact and 7 days for a snapshot.

#### Scenario: T5 oversize value
- **WHEN** a `TieredMapping` stores a value whose encoded form is 1 MiB and one byte, and then a value of 1 KiB
- **THEN** no command carries the first value, a read in the same process returns it from the in-process tier, the shared tier holds the second value, and each key on the `valkey_server` fake has a TTL above 0

### Requirement: A value of another kind or schema is a miss
A reader SHALL treat a shared value under an older key version, or with another schema key, as a miss, SHALL read the source, and SHALL write the value under the current key.

#### Scenario: T6 old kind
- **WHEN** the shared tier holds a PyPI fact under an older key version and a fact under the current key with another schema key
- **THEN** each read returns the value of the source, and the shared tier then holds the source value under the current key with the current schema key

### Requirement: No key of a private repository
The snapshot store SHALL write no key of a repository that the visibility check does not give as public, SHALL NOT use a shared copy of it, and SHALL count `result="private"`. A failed visibility read SHALL count as private. When the shared tier holds a copy of a repository that the check does not give as public, the store SHALL remove the key and count `devops_cli_brain_writes_total{result="removed"}`.

#### Scenario: Private repository
- **WHEN** a listing round runs for a repository whose visibility read gives `isPrivate: true`, and a second round runs for a repository whose visibility read fails
- **THEN** the `valkey_server` fake holds no key that names either repository, each round reads the local file or GitHub, and `devops_cli_brain_writes_total{store="snapshot",result="private"}` rises by two

#### Scenario: No visibility read without the shared tier
- **WHEN** the `valkey_server` fake has `connected = False` and a listing round runs
- **THEN** the round sends no visibility read to GitHub

#### Scenario: A repository that became private
- **WHEN** a round of a public repository writes its shared snapshot, and a round in a new process finds that the repository is not public
- **THEN** the `valkey_server` fake holds no key, the round uses no shared copy, and `devops_cli_brain_writes_total{result="removed"}` rises by one

### Requirement: One key for each repository
The key of a shared snapshot and the visibility answer of a process SHALL use the casefolded name of `RepoRef.key`, so each spelling of a repository name gives one key and one visibility read.

#### Scenario: Two spellings of one name
- **WHEN** a process saves the snapshot of `Dan-Petty/DevOps-CLI`, a new process loads `dan-petty/devops-cli`, and the visibility of both spellings is read
- **THEN** the fake holds one key, the load gives the saved records, and GitHub gets one visibility read

### Requirement: A shared load has a budget
A load of a shared snapshot SHALL stop when it passes `DEFAULT_BRAIN_SNAPSHOT_LOAD_BUDGET_SECONDS` (20 s), SHALL count `devops_cli_valkey_cache_errors_total{op="hscan",error="budget"}`, and the reader SHALL take the local copy or read GitHub.

#### Scenario: Slow shared tier
- **WHEN** the `clock` fixture moves 21 s during the second `HSCAN` of a shared load of 1,200 records
- **THEN** the load sends no third `HSCAN`, the reader returns the local snapshot, and the budget counter rises by one

### Requirement: The tool facts come from the shared cache
A second read of the same PyPI package or the same deps.dev project within the TTL SHALL come from the shared or the in-process tier and SHALL send no request to PyPI or deps.dev. A failed source read SHALL keep nothing.

#### Scenario: PyPI fact reuse across processes
- **WHEN** two `pypi_package` calls for `Scanner` and `scanner` run with an empty in-process tier between them on one `valkey_server` fake
- **THEN** the `web` fake receives one request to PyPI, and both calls return the same facts

#### Scenario: deps.dev fact reuse
- **WHEN** two inventory reads link the packages of `github.com/example/tool` with an empty in-process tier between them
- **THEN** the `web` fake receives one request to deps.dev

#### Scenario: A failed PyPI read
- **WHEN** PyPI answers 503 for a package, and then 200
- **THEN** the first call answers the failure as text, and the second call sends a request and returns the facts

### Requirement: The brain counters have bounded labels
The counters `devops_cli_brain_reads_total`, `devops_cli_brain_writes_total`, `devops_cli_valkey_cache_errors_total` and `devops_cli_brain_github_requests_saved_total` SHALL take each label value from a fixed set in the source, and SHALL NOT hold a repository name, a key, an issue number or a package name.

#### Scenario: The labels of a round
- **WHEN** a test runs a listing round and two fact reads on the OTLP fake, one with the shared tier up and one with it down
- **THEN** each exported data point of the four counters has only the labels `store`, `result`, `op` or `error`, each value is one of the fixed values, and no value names the repository or the package

### Requirement: The cache Valkey keeps its data bound below its limit
The valkey container of the Deployment `valkey-devops` SHALL start valkey-server with `--maxmemory 256mb` under a container memory limit of `384Mi`, so its data bound is two thirds of its limit. The live check after the Argo CD sync is the proof of the bound. The `k8s` row of `devops ci` proves only that the manifests render: it does not compare `--maxmemory` with the limit.

#### Scenario: The manifests render
- **WHEN** a person runs `uv run devops ci --check --only k8s` on the pull request
- **THEN** the `k8s` row renders `k8s/llm` with no error

#### Scenario: Live memory bound
- **WHEN** a person runs `kubectl -n llm get deployment valkey-devops -o jsonpath='{.spec.template.spec.containers[0].command}{.spec.template.spec.containers[0].resources.limits.memory}'` after the Argo CD sync, and reads `redis_config_maxmemory{job="valkey-devops"}` in Prometheus
- **THEN** the command holds `--maxmemory 256mb` and the limit is `384Mi`, and the metric is 268435456
