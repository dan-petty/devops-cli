# project-brain/shared-cache Specification

## Purpose
The shared tier of the project brain in the cache Valkey `valkey-devops` (ADR 0023 section 2): the listing snapshot of each public repository and the tool facts that the alternatives check reads, over the in-process tier, with a fallback to the local tier or the source when Valkey is slow or down.

## Requirements

### Requirement: A cold process reads the shared listing snapshot
When a process has no local snapshot of a public repository and the shared tier holds a fit snapshot of it, the listing read SHALL start from the shared snapshot and read only the issues changed since its watermark, and SHALL count the full read that it saved in `devops_cli_brain_github_requests_saved_total{store="snapshot"}`.

#### Scenario: Warm shared snapshot, cold process
- **WHEN** a test saves a snapshot of 250 issues of a public repository through one `TieredSnapshotStore` on the `valkey_server` fake, and a new `TieredSnapshotStore` with an empty local directory reads the listing of that repository through `IncrementalListing` while GitHub lists 3 issues as changed
- **THEN** the read sends at most 2 listing requests, each with `since=<watermark>`, it returns 250 issues with the new title of each changed issue, the local file holds the new snapshot, and `devops_cli_brain_github_requests_saved_total{store="snapshot"}` rises by 3

#### Scenario: The newer of the two copies
- **WHEN** the local file holds a snapshot with the watermark 09:00 and the shared tier holds one with the watermark 10:00, both with the current schema key and a full read of less than 24 hours
- **THEN** the listing read sends `since=` with the watermark 10:00

### Requirement: A load counts the tier that gave the snapshot
A load of the tiered snapshot store SHALL count `devops_cli_brain_reads_total{store="snapshot"}` with `result="local"` when it gives the fit local copy, `result="shared"` when it gives the shared copy, and `result="source"` only when no tier holds a fit copy, so the run reads the whole listing. A private or an unknown visibility answer, and a failed shared tier, SHALL count `private`, `unknown` or `fallback` in place of `local` or `source`.

#### Scenario: Local and source loads
- **WHEN** a load runs with no copy in either tier, and a second load runs after a save that put the same snapshot in both tiers
- **THEN** the first load counts `source`, and the second load returns the local copy and counts `local`

### Requirement: A read of the shared tier fills the in-process tier
A `TieredMapping` read that misses the in-process tier and hits the shared tier SHALL read the value and the remaining TTL of its key (`GET` and `PTTL`) in one round trip, and SHALL put the value in the in-process tier until the shared key expires, or until the TTL of the mapping ends when that is sooner. A next read of the key in that time SHALL send no command to Valkey. A failed round trip SHALL count `devops_cli_valkey_cache_errors_total{op="get"}`.

#### Scenario: T1 read fills the in-process tier
- **WHEN** one `TieredMapping` writes a fact on the `valkey_server` fake, and a second `TieredMapping` with an empty in-process tier reads the key twice
- **THEN** both reads return the fact, the second read sends no command to the fake, and `devops_cli_brain_reads_total{store="fact"}` counts one `shared` and one `memory`

#### Scenario: A fact read near the end of its TTL
- **WHEN** the `valkey_server` fake holds a fact with a TTL of 5 s, a `TieredMapping` with a TTL of 60 s reads it, and the `clock` fixture moves 6 s
- **THEN** the next read of the key misses the in-process tier and the shared tier and raises `KeyError`, and `devops_cli_brain_reads_total{store="fact"}` counts one `shared` and one `source`

#### Scenario: The value and the TTL of a key in one round trip
- **WHEN** a `ValkeyCacheTier` on the `valkey_server` fake reads a key with a TTL of 5 s and a key that does not exist, and then reads a key while the fake has `connected = False`
- **THEN** the first read gives the value and a TTL of 5,000 ms, the second gives no value and -2, the third gives no answer, and `devops_cli_valkey_cache_errors_total{op="get",error="connection"}` rises by one

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

### Requirement: The lanes of one process scan a shared copy once
A load SHALL take the records of the shared snapshot from the shared store of the process, and SHALL send no `HSCAN`, when the process last wrote or read the records that the stored `meta` names. Two loads of one repository at the same time in one process SHALL send one `HSCAN` scan: a load takes a lock for its repository before it scans, and a load that waited reads the known records again. A load SHALL NOT replace the known records that the process kept during its scan.

#### Scenario: A lane after another lane of the process
- **WHEN** lane B of a process saved a snapshot with the watermark 09:00, lane A of the same process saved one with the watermark 10:00, and lane B loads
- **THEN** lane B gets the records and the watermark 10:00 of lane A, and sends only the read of `meta` to Valkey

#### Scenario: Two lanes load one repository at the same time
- **WHEN** thread A of a process loads a shared snapshot of 3 records, and its `HSCAN` waits until thread B of the same store starts the budget of its load of the same `meta`
- **THEN** the `valkey_server` fake gets one `HSCAN`, and both loads give the 3 records and the watermark of the shared snapshot

#### Scenario: A save of the process during a scan
- **WHEN** a snapshot store loads issues 3, 2 and 1 with the watermark 09:00, another lane of the same store saves issues 4, 3, 2 and 1 with the watermark 10:00 after the `HSCAN` of the load, and the store then saves issue 2 with a new title
- **THEN** the load gives the records of 09:00, the compressor of the last save gets only the JSON of issue 2, the last save sends no `HSET` of a temporary key, and the shared snapshot holds the records of the last save

### Requirement: A save of the records that the shared copy holds writes no record
A save whose records, schema key and watermark the shared snapshot already holds, with a full read that is not newer than the stored one, SHALL send no record and no transaction: it SHALL set the TTL of the key again, keep the stored `meta`, and count `devops_cli_brain_writes_total{result="unchanged"}`.

#### Scenario: Two lanes and a new process with the same records
- **WHEN** two lanes of one process save the same 1,200 records and watermark with full reads at 08:00 and 09:00, and then each saves them again twice, and a new process saves them once
- **THEN** after the first save of each lane, the lanes send only `EXPIRE` alone, beside the read of `meta` and its `PTTL` in one pipeline, the stored `meta` does not change, `devops_cli_brain_writes_total{result="unchanged"}` rises by five, and no temporary key stays

### Requirement: A load uses only the records that its meta names
A load SHALL use the records of the shared snapshot only when their digest is the digest of the `meta` that the load read first. A new `meta` of the same records during the scan SHALL NOT make the load a miss. A value of the shared tier is untrusted: a `meta` or a record with a time with no UTC offset, a record under a field that is not its issue number, and a record that expands past 1 MiB, SHALL make the shared copy a miss, and the next save SHALL replace it.

#### Scenario: A new meta of the same records during a load
- **WHEN** a writer saves the same 1,200 records with a newer full read after the first `HSCAN` of a cold load
- **THEN** the load gives the 1,200 records of the shared copy and counts `result="shared"`

#### Scenario: A time with no offset or a record past the bound
- **WHEN** the shared snapshot is newer than the local one, and its `meta` holds a time with no UTC offset, or a record holds one, or a record expands to more than 1 MiB of JSON
- **THEN** the load gives the local snapshot and raises no error, and the next save leaves the shared snapshot with its own watermark and records

#### Scenario: A record under the field of another number
- **WHEN** the shared snapshot is newer than the local one, and another writer keeps issue 2 under the field `02`, alone or as well as under `2`, with a `meta` whose digest names these fields
- **THEN** the load gives the local snapshot, and the next save of the process raises no error and leaves the shared snapshot with its own watermark and records

### Requirement: Each value has a bound and each key a TTL
The shared tier SHALL NOT receive a value whose encoded form is over 1 MiB; such a value SHALL stay in the in-process tier and count `devops_cli_brain_writes_total{result="oversize"}`. Each key that the mapping or the snapshot store writes SHALL have a TTL: 24 hours for a fact, 24 hours for a cached issue object and 7 days for a snapshot.

#### Scenario: T5 oversize value
- **WHEN** a `TieredMapping` stores a value whose encoded form is 1 MiB and one byte, and then a value of 1 KiB
- **THEN** no command carries the first value, a read in the same process returns it from the in-process tier, the shared tier holds the second value, and each key on the `valkey_server` fake has a TTL above 0

### Requirement: A value of another kind or schema is a miss
A reader SHALL treat a shared value under an older key version, or with another schema key, as a miss, SHALL read the source, and SHALL write the value under the current key.

#### Scenario: T6 old kind
- **WHEN** the shared tier holds a PyPI fact under an older key version and a fact under the current key with another schema key
- **THEN** each read returns the value of the source, and the shared tier then holds the source value under the current key with the current schema key

### Requirement: A private repository's snapshot is shared only under the sweep user
The visibility check SHALL give public, private or unknown, and a failed read SHALL give unknown. The snapshot store SHALL write, read and keep the shared copy of a private repository only when the process sends the ACL user `sweep`, and SHALL remove that copy under any other user or none. The store SHALL write no shared key and read no record of a repository whose visibility is unknown. The shared copy of a private repository SHALL keep the key and the TTL of a public repository.

#### Scenario: Private repository
- **WHEN** A listing round runs for a repository whose visibility read gives `isPrivate: true` and the process sends no ACL user
- **THEN** The `valkey_server` fake holds no key that names the repository, the round reads GitHub, GitHub gets one visibility read, and `devops_cli_brain_reads_total{store="snapshot",result="private"}` and `devops_cli_brain_writes_total{store="snapshot",result="private"}` each rise by one

#### Scenario: Private repository under the sweep user
- **WHEN** A listing round runs for a repository whose visibility read gives `isPrivate: true` and the process sends the `sweep` user
- **THEN** The `valkey_server` fake holds the snapshot key of the repository with its metadata, and `devops_cli_brain_writes_total{store="snapshot",result="shared"}` rises by one

#### Scenario: The sweep user reads the shared copy of a private repository
- **WHEN** A process that sends the `sweep` user loads the listing of a private repository that the shared tier holds
- **THEN** The load gives the shared records and `devops_cli_brain_reads_total{store="snapshot",result="shared"}` rises by one

#### Scenario: No visibility read without the shared tier
- **WHEN** The `valkey_server` fake has `connected = False` and a listing round runs
- **THEN** The round sends no visibility read to GitHub

#### Scenario: A repository that became private
- **WHEN** A round of a public repository writes its shared snapshot, and a round in a new process that sends no ACL user finds that the repository is private
- **THEN** The `valkey_server` fake holds no key, the round uses no shared copy, and `devops_cli_brain_writes_total{result="removed"}` rises by one

### Requirement: An unknown answer removes a stale shared copy
An unknown answer SHALL remove the shared copy of a repository and count `devops_cli_brain_writes_total{result="removed"}` when its last save is older than `DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS` (30 min). The age SHALL be the TTL of a snapshot less the `PTTL` of its key, read with `meta` in one round trip. Valkey SHALL read the `PTTL` again and remove the key in one script. A fresher copy, a key with no TTL and a missing key SHALL stay.

#### Scenario: A failed visibility read leaves a fresh shared copy
- **WHEN** a round of a public repository writes its shared snapshot, and a round in a new process 20 min later finds that its visibility read fails with `API rate limit exceeded`
- **THEN** the snapshot key keeps its `meta` and its records, the second round sends no command alone for the key because it reads `meta` and its `PTTL` in one pipeline, GitHub gets one visibility read in the second round, and `devops_cli_brain_reads_total{store="snapshot",result="unknown"}` and `devops_cli_brain_writes_total{store="snapshot",result="unknown"}` each rise by one

#### Scenario: A failed visibility read removes a stale shared copy
- **WHEN** a round of a public repository writes its shared snapshot, and a round in a new process 31 min later finds that its visibility read fails with `Could not resolve to a Repository`
- **THEN** the `valkey_server` fake holds no key, the second round sends one `EVAL` script and no other command alone for the key, `devops_cli_brain_reads_total{store="snapshot",result="unknown"}` rises by one, and `devops_cli_brain_writes_total{store="snapshot"}` counts one `removed` and one `unknown`

#### Scenario: No age of a save to read
- **WHEN** the shared key of a public repository is removed or loses its TTL, and a round in a new process 31 min later finds that its visibility read fails
- **THEN** the round removes nothing, sends no command alone for the key, and counts only `unknown` on `devops_cli_brain_reads_total{store="snapshot"}` and `devops_cli_brain_writes_total{store="snapshot"}`

#### Scenario: A save during the visibility read
- **WHEN** a process saves the shared snapshot of a public repository, 61 min pass, and a new process loads the repository while its visibility read fails and another process with a public answer saves the same records
- **THEN** the `valkey_server` fake keeps the snapshot key, `devops_cli_brain_reads_total{store="snapshot",result="unknown"}` rises by one, and `devops_cli_brain_writes_total{store="snapshot"}` counts only one `unchanged`

### Requirement: One key for each repository
The key of a shared snapshot, the visibility answer of a process, and the records of the shared copy that the snapshot store of a process knows SHALL use the casefolded name of `RepoRef.key`, so each spelling of a repository name gives one key, one visibility read and one set of known records.

#### Scenario: Two spellings of one name
- **WHEN** a process saves the snapshot of `Dan-Petty/DevOps-CLI`, a new process loads `dan-petty/devops-cli`, and the visibility of both spellings is read
- **THEN** the fake holds one key, the load gives the saved records, and GitHub gets one visibility read

#### Scenario: Two spellings in turn in one process
- **WHEN** one snapshot store of a process saves six snapshots, each with one more record and a newer watermark, in turn as `Dan-Petty/DevOps-CLI` and `dan-petty/devops-cli`
- **THEN** only the first save writes a temporary key, and each later save writes its changed records to the snapshot key in one WATCH transaction

### Requirement: A shared load has a budget
A load of a shared snapshot SHALL stop when it passes `DEFAULT_BRAIN_SNAPSHOT_LOAD_BUDGET_SECONDS` (20 s) from its miss of the known records, in its wait for the scan of another load, its `HSCAN`, or the inflate and validation of its records. It SHALL count `devops_cli_valkey_cache_errors_total{op="hscan",error="budget"}`, and the reader SHALL take the local copy or read GitHub.

#### Scenario: Slow shared tier
- **WHEN** the `clock` fixture moves 21 s during the second `HSCAN` of a shared load of 1,200 records
- **THEN** the load sends no third `HSCAN`, the reader returns the local snapshot, and the budget counter rises by one

#### Scenario: The budget passes in the last HSCAN
- **WHEN** the shared snapshot of 3 records is newer than the local one, and the `clock` fixture moves 21 s during the only `HSCAN` of its load
- **THEN** the reader returns the local snapshot, the budget counter rises by one, and `devops_cli_brain_reads_total{store="snapshot",result="fallback"}` rises by one

#### Scenario: The budget passes in the validation
- **WHEN** a snapshot store loads a shared snapshot of 3 records, and the `clock` fixture moves 21 s after the clock reading of the inflate of the last record
- **THEN** the load gives no snapshot, the `valkey_server` fake gets one `HSCAN`, and the budget counter rises by one

#### Scenario: A lane waits past the budget
- **WHEN** thread A of a process loads a shared snapshot of 3 records, and its `HSCAN` waits until thread B of the same store starts the budget of its load of the same `meta`, and then the `clock` fixture moves 21 s
- **THEN** the `valkey_server` fake gets one `HSCAN`, both loads give no snapshot, and the budget counter rises by two

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

### Requirement: A visibility answer is kept for its lifetime
A process SHALL keep a public or a private answer of the visibility check for `DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS` (30 min), and an unknown answer for `DEFAULT_BRAIN_VISIBILITY_FAILURE_TTL_SECONDS` (60 s), before it reads the visibility again. Thus the shared copy of a repository that became private SHALL go at most 1 hour after the change, at the first run after that time.

#### Scenario: A public answer is kept for 30 min
- **WHEN** the visibility read of a repository gives `isPrivate: false`, the `clock` fixture moves 29 min before a second check, and 2 min more before a third check whose read gives `isPrivate: true`
- **THEN** the first two checks give public with one GitHub read, and the third check reads GitHub once more and gives private

#### Scenario: An unknown answer is kept for 60 s
- **WHEN** the visibility read of a repository fails, the `clock` fixture moves 59 s before a second check, and 2 s more before a third check whose read gives `isPrivate: false`
- **THEN** the first two checks give unknown with one GitHub read, and the third check reads GitHub once more and gives public

### Requirement: A shared snapshot has a bound on its expanded records
A load of a shared snapshot SHALL expand at most `DEFAULT_BRAIN_SNAPSHOT_LOAD_MAX_BYTES` (128 MiB) of record JSON in total, in addition to the bound of 1 MiB for each record. A load past the bound SHALL be a miss, SHALL count `result="fallback"`, and the reader SHALL take the local copy or read GitHub. A save whose record JSON passes the bound SHALL write nothing and SHALL count `devops_cli_brain_writes_total{result="oversize"}`.

#### Scenario: Many small records past the total bound
- **WHEN** the shared snapshot is newer than the local one and holds two records that each expand to less than 1 MiB of JSON, and the reader snapshot store is built with a total bound below the sum of the two
- **THEN** the load gives the local snapshot and raises no error, and `devops_cli_brain_reads_total{store="snapshot",result="fallback"}` rises by one

#### Scenario: A save past the total bound
- **WHEN** a snapshot store built with a total bound of 512 KiB saves a snapshot of two records of about 300,000 bytes of JSON each
- **THEN** the `valkey_server` fake holds no key, `devops_cli_brain_writes_total{store="snapshot",result="oversize"}` rises by one, and the local file holds the snapshot

#### Scenario: A delta past the total bound
- **WHEN** a snapshot store built with a total bound of 512 KiB wrote two records of about 200,000 bytes of JSON each, and saves them again with a newer watermark and one record of about 400,000 bytes of JSON
- **THEN** the save counts `devops_cli_brain_writes_total{store="snapshot",result="oversize"}`, the compressor gets no record, and the shared snapshot keeps the two records and the `meta` of the first save

### Requirement: A save compresses only the records that it sends
A save SHALL compress only the records that it sends to Valkey: none for an older or an unchanged save, the changed and new records for a save that knows the stored records, and all records only for a write to a temporary key. A store that knows the stored records SHALL compare them with the records of the save before it encodes, and its new `meta` SHALL be the one that an encode of all records gives.

#### Scenario: A save with no changed record
- **WHEN** a snapshot store whose compressor records each JSON that it gets saves 1,200 records, and saves them again with the same watermark and full read
- **THEN** the second save counts `devops_cli_brain_writes_total{result="unchanged"}`, and the compressor gets no record

#### Scenario: An older save
- **WHEN** the shared snapshot has the watermark 10:00 that a snapshot store wrote, and the same store saves a snapshot with the watermark 09:00 and the same schema key
- **THEN** the save counts `devops_cli_brain_writes_total{result="older"}`, the compressor gets no record, and the shared snapshot keeps the watermark 10:00

#### Scenario: One changed, new or removed record
- **WHEN** a snapshot store wrote issues 3, 2 and 1 with the watermark 09:00, and saves with the watermark 10:00 issue 2 with a new title, or issue 4 in addition, or issues 3 and 2 only
- **THEN** the compressor gets only the JSON of issue 2, only the JSON of issue 4, or no record, the save sends no `HSET` of a temporary key, the shared snapshot holds the records of the save, and its `meta` is the `meta` that a new store writes for the same snapshot to an empty `valkey_server` fake

#### Scenario: A delta that loses its transaction
- **WHEN** a snapshot store read issues 3, 2 and 1 with the watermark 09:00 and saves issue 2 with a new title and the watermark 10:00, and another client writes issues 3 and 1 with the watermark 10:00 before the EXEC of the delta
- **THEN** the compressor gets the JSON of issue 2, then the JSON of issues 3, 2 and 1, the `valkey_server` fake holds only the snapshot key, and the shared snapshot holds the records of the save

### Requirement: The brain holds the issue that a row reads
The project brain SHALL hold one entry for each issue that a roadmap row reads in a Service repository that the shared tier takes from the process (a public repository, and a private repository under the `sweep` ACL user), with the title, body, labels, state, update time and job record of that issue.

#### Scenario: A stored issue comes back
- **WHEN** A row asks the brain for an issue of a public repository that a fake webhook has written.
- **THEN** The brain gives the title, body, labels, state, update time and job record of that issue, and the fake GitHub client receives no request.

### Requirement: A row reads the cached issue before GitHub
Each row MUST read the brain entry of an issue before it reads the issue from GitHub, and MUST read the issue from GitHub only on a miss, for a write, when the entry is older than one hour, or when the caller asks for live state with `fresh=True`. The visibility read of the repository is no read of the issue: a process sends it at most one time in the lifetime of its answer.

#### Scenario: A fresh entry sends no request
- **WHEN** A row of a new process reads an issue that the fake tier holds and whose last check is younger than one hour.
- **THEN** The row returns the stored issue, and the fake GitHub client receives the visibility read and no request of the issue.

#### Scenario: A miss reads GitHub once and fills the entry
- **WHEN** A row of a new process reads an issue that the fake tier does not hold.
- **THEN** The row sends the visibility read, reads the issue from the fake GitHub once, writes the entry, and counts one miss for its row.

#### Scenario: A live read bypasses a fresh cached entry
- **WHEN** A caller invokes `store.issue(number, fresh=True)` or `store.item(number, fresh=True)` while the fake tier holds an entry younger than one hour, and GitHub holds a newer state for that issue.
- **THEN** `GitHubRoadmapStore` queries the fake GitHub (`If-None-Match` when an `ETag` is stored, else a direct issue read), returns the live issue state, updates the stored brain entry and `self._all`, and counts one cache miss.

### Requirement: A Service write fills the cached issue
A write that the Service makes to an issue of a repository that the shared tier takes from the process MUST write the issue that the Service holds into the brain entry.

#### Scenario: A label write fills the entry
- **WHEN** The Service adds a label to an issue of a public repository that its store has read, through the fake GitHub client.
- **THEN** The fake tier holds the new label set before the fake webhook for that label is delivered.

### Requirement: A row reads GitHub when the shared tier is down
When the shared tier of the cache Valkey does not answer, a row MUST read GitHub as it does on a miss and MUST NOT fail its round on the cache.

#### Scenario: The tier refuses a connection
- **WHEN** The fake tier raises a connection error during a row round.
- **THEN** The row reads the fake GitHub, the round returns its normal result, and the Service logs the cache outage.

### Requirement: The cached issue key names its repository and number
The key of a cached issue MUST be `valkey:roadmap:v1:issue:<owner>/<name>:<number>`, under the prefix `CONST_VALKEY_ROADMAP_PREFIX` that the `sweep` ACL user writes and the `brain` ACL user reads, with the casefolded name of `RepoRef.key` as the key of the shared snapshot has it. The `:` after the name MUST end the repository part, so no key of a repository is a key of a repository whose name starts with the same text.

#### Scenario: A key names its repository and object
- **WHEN** The brain builds the key for issue 6013 of `Dan-Petty/DevOps-CLI`, and for issue 6013 of `dan-petty/devops-cli-2`.
- **THEN** The first key is `valkey:roadmap:v1:issue:dan-petty/devops-cli:6013`, and the second key does not start with the key prefix of the first repository and `:`.

### Requirement: A revalidation leaves an unchanged issue in the brain
A row MUST send a conditional read of an issue whose entry is older than one hour, with the `ETag` that the entry holds, and a `304` answer MUST leave the stored issue unchanged and MUST NOT spend GitHub's primary rate limit.

#### Scenario: A second read in the same hour sends no request
- **WHEN** A row reads an issue twice within one hour.
- **THEN** The second read returns the stored issue and sends no GitHub request.

#### Scenario: A 304 answer keeps the stored issue
- **WHEN** The revalidation sends `If-None-Match` with the stored `ETag` and the fake GitHub runner answers `304`.
- **THEN** The entry keeps its issue and its `ETag`, the time of its last check moves, and the fake runner receives one conditional request.

### Requirement: The cache counts a hit and a miss for each row
The Service MUST count each read of a cached issue as `devops_cli_brain_cache_total{row,result}`, with `result` `hit` when the brain answered and `miss` when GitHub was read, and with the row of the read as `row`.

#### Scenario: A cache hit is counted for its row
- **WHEN** A row named `refine` reads a cached issue that the brain holds and whose last check is younger than one hour.
- **THEN** `devops_cli_brain_cache_total{row="refine",result="hit"}` rises by one, and the fake GitHub client receives no request of the issue.

### Requirement: A quiet Service repository stays inside the request budget
A Service repository with little work MUST cost fewer than 20 GitHub requests an hour, with the visibility reads of the repository.

#### Scenario: One simulated hour of a quiet repository
- **WHEN** A test reads the six issues of a quiet repository in each 5-minute round of one simulated hour, with a fake clock and a fake GitHub client.
- **THEN** The fake GitHub client records one visibility read and six requests of issues, and each read after the first of an issue sends no request.

### Requirement: Authoritative callers pass fresh=True for live issue state
After an out-of-process Job completes (`implement_submit._fresh`, `stage_job.check_in`, `stage_job._return_for_split`, `fix_checks_row._record_unit`), before clearing stops (`stop_clear._clear_one`), and when reading back a Status mutation (`status_sync._read_back`), callers SHALL read with `fresh=True`.

#### Scenario: Read back checks live GitHub even when Valkey has a fresh entry
- **WHEN** `status_sync._read_back` verifies a Status write while the brain holds an entry younger than one hour.
- **THEN** `status_sync._read_back` reads with `fresh=True` against GitHub rather than trusting the unverified cache entry alone.

### Requirement: Webhook issue caching decodes job records
`issue_from_event` SHALL decode the split job record dictionary through `decode_job_record` before constructing `IssueRecord`, normalizing integer `implement.repair_rounds` values and filtering unknown or malformed record keys.

#### Scenario: An issue webhook carries integer repair rounds and an unknown key
- **WHEN** a signed `issues` or `issue_comment` webhook arrives for an issue whose body holds `implement.repair_rounds` as an integer and an unknown or malformed key
- **THEN** the webhook returns HTTP 202 and the cached `IssueRecord.job_record` holds the string value for `implement.repair_rounds` without raising a validation error

### Requirement: A private repository's issue entries are shared only under the sweep user
The issue cache SHALL take the visibility of a repository from the visibility check of the listing snapshot. A process SHALL send no command for the entry of an issue of a private repository unless it sends the ACL user `sweep`, and none for a repository whose visibility is unknown: a read SHALL give no entry, so its caller reads GitHub, and a write SHALL NOT occur. The issue cache SHALL keep no entry in the memory of the process.

#### Scenario: Private repository
- **WHEN** a store reads one issue of a repository two times, the visibility read gives `isPrivate: true`, and the process sends no ACL user
- **THEN** the `valkey_server` fake holds no key, GitHub gets one visibility read and two requests of the issue, and `devops_cli_brain_reads_total{store="issue",result="private"}` and `devops_cli_brain_writes_total{store="issue",result="private"}` each rise by two

#### Scenario: An issue that the Service opens in a private repository
- **WHEN** a store opens an issue in a repository whose visibility read gives `isPrivate: true`, and the process sends no ACL user
- **THEN** the `valkey_server` fake holds no key, GitHub gets the visibility read after the write, and `devops_cli_brain_writes_total{store="issue",result="private"}` rises by one

#### Scenario: Private repository under the sweep user
- **WHEN** a store reads one issue of a private repository two times and the process sends the `sweep` user
- **THEN** the `valkey_server` fake holds the key of the issue, and GitHub gets one visibility read and one request of the issue

#### Scenario: Public repository
- **WHEN** a store reads an issue of a repository whose visibility read gives `isPrivate: false`, and a store of a new process reads the same issue
- **THEN** the `valkey_server` fake holds the key of the issue, GitHub gets one request of the issue and one visibility read for each process, and the counters of the store `issue` count one `source` read, one `shared` read and one `shared` write

#### Scenario: Unknown visibility
- **WHEN** a store reads one issue of a repository two times and the visibility read fails with `API rate limit exceeded`
- **THEN** the `valkey_server` fake holds no key, GitHub gets one visibility read and two requests of the issue, and each of the two counters counts `unknown` two times for the store `issue`

### Requirement: A refused issue entry counts its cause
A read of an entry that the issue cache refuses SHALL count `devops_cli_brain_reads_total{store="issue"}`, and a refused write SHALL count `devops_cli_brain_writes_total{store="issue"}`, each one time with the result `private` or `unknown`.

#### Scenario: An answer that the caller holds
- **WHEN** a caller writes and reads the entry of a repository with the answer private, first with no ACL user and then with the `sweep` user
- **THEN** the first write and read send no entry to the `valkey_server` fake and each counts `private` one time, and the second write and read store and return the entry and each counts `shared` one time

### Requirement: The issue cache reads the visibility only after the shared tier answered
In a process that holds no visibility answer for a repository, the issue cache SHALL send one `GET` of the key prefix `valkey:roadmap:v1:issue`, which names no repository, before the visibility read. When Valkey does not answer it, the cache SHALL send no visibility read, a read SHALL count `fallback` and a write SHALL count `skipped`.

#### Scenario: No visibility read without the shared tier
- **WHEN** the `valkey_server` fake has `connected = False`, and a caller reads and writes an entry with a visibility read
- **THEN** the visibility read is not called, `devops_cli_brain_reads_total{store="issue",result="fallback"}` rises by one, and `devops_cli_brain_writes_total{store="issue",result="skipped"}` rises by one

### Requirement: A caller with no visibility read gets the answer of the process
A caller of the issue cache that gives no answer and no visibility read SHALL get the answer that the process holds, and an unknown answer when the process holds none.

#### Scenario: A caller with no answer and no read
- **WHEN** a caller writes and reads an entry with no answer and no visibility read, first in a process that holds no answer and then after a public answer of the visibility check
- **THEN** the first write and read send no entry to the `valkey_server` fake and each counts `unknown`, and the second write and read store and return the entry

### Requirement: The brain holds no entry of a number that is no issue of the repository
When GitHub answers a read of a number with status 404 or with an answer that names another issue, `GitHubRoadmapStore` SHALL remove the brain entry of that number and SHALL write no entry for the answer. The store SHALL send the removal only for a repository whose entries the shared tier takes from the process.

#### Scenario: A conditional read that answers with another issue
- **WHEN** the `valkey_server` fake holds an entry of issue 7 of `acme/widgets` that is older than one hour, and the fake GitHub answers the read with `If-None-Match` with status 200 and a payload whose `number` is 12 and whose `repository_url` names `acme/other`
- **THEN** `issue(7)` returns None, and the `valkey_server` fake holds no entry of issue 7 and no entry of issue 12 of `acme/widgets`

### Requirement: The store uses an entry only for the issue that it names
The store SHALL use a brain entry only when its record names the requested number and the repository of the store. It SHALL remove any other entry and read the issue from GitHub.

#### Scenario: An entry whose record names another issue
- **WHEN** the `valkey_server` fake holds, under issue 12 of `acme/widgets`, a fresh entry whose record names issue 12 of `acme/other`, and the fake GitHub answers the read of `repos/acme/widgets/issues/12` with issue 12 of `acme/widgets`
- **THEN** `issue(12)` sends one read to the fake GitHub and returns its issue, and the entry that the fake holds names `acme/widgets`

#### Scenario: A 304 answer gives the entry of the requested issue
- **WHEN** the `valkey_server` fake holds an entry of issue 7 of `acme/widgets` that is older than one hour, and the fake GitHub answers the read with `If-None-Match` with status 304
- **THEN** `issue(7)` returns the record of the entry

### Requirement: A delivery that says that an issue left removes its entry
For a delivery `issues` with the action `transferred` or `deleted`, the roadmap consumer of the webhook route SHALL remove the brain entry of the issue of the delivery before it wakes the lanes, and SHALL write no entry from the payload of the delivery. The trigger of the delivery SHALL name the number of the issue as its subject. For such a delivery whose sender is the bot of the App, the route SHALL remove the entry, SHALL write none and SHALL wake no lane.

#### Scenario: A transferred issue and a deleted issue
- **WHEN** a signed delivery `issues` with the action `labeled` wrote the entry of issue 42 of a public repository, and a signed delivery `issues` with the action `transferred`, or with the action `deleted`, comes for issue 42
- **THEN** the route answers 202, the shared tier holds no entry of issue 42 when the lanes wake and after, and the trigger of the delivery names the event `issues`, the action and the subject 42

#### Scenario: A delivery of the App itself
- **WHEN** a signed delivery `issues` with the action `transferred`, or with the action `deleted`, whose sender is the bot of the App comes for issue 42, one time while the shared tier holds no entry of issue 42 and one time while it holds one
- **THEN** the route answers 200 each time, the shared tier holds no entry of issue 42 after each delivery, and no trigger is queued
