## ADDED Requirements

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

## MODIFIED Requirements

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
