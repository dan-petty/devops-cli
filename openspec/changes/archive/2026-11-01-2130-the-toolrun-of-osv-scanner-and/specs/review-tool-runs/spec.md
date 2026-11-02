## ADDED Requirements

### Requirement: The ruleset digest of an osv-scanner run follows its offline database
The record of an osv-scanner run SHALL name the file `all.zip` of each ecosystem in the `osv-scalibr` directory of its offline database as ruleset files. So the `ruleset_digest` of the record SHALL change when the content of a database file changes, and SHALL stay the same when it does not. A run with no database file SHALL name no ruleset file.

#### Scenario: The same database
- **WHEN** osv-scanner scans a tree two times and its database holds `PyPI/all.zip` and `npm/all.zip` both times
- **THEN** the two records have the same `ruleset_digest`
- **AND** the request names both files as ruleset files

#### Scenario: A changed database
- **WHEN** the bytes of `PyPI/all.zip` change between two scans
- **THEN** the `ruleset_digest` of the second record differs from the first

#### Scenario: No database
- **WHEN** the offline database directory of osv-scanner holds no `all.zip`
- **THEN** the request names no ruleset file
- **AND** the `ruleset_digest` is the digest of no files

### Requirement: A ruleset file of a data directory is digested at any size
The record SHALL digest a ruleset file that lies below a read-only bind of the request by reading it as a stream, whatever its size. A ruleset file that lies below no bind, and every config file, SHALL still be refused when it is larger than 50 MiB (`DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES`).

#### Scenario: A large database file below a bind
- **WHEN** a request names a ruleset file of 50 MiB and one byte below one of its read-only binds
- **THEN** the run starts and the `ruleset_digest` is the digest of the content of that file

#### Scenario: A large ruleset file below no bind
- **WHEN** a request names a ruleset file of 50 MiB and one byte that lies below no read-only bind
- **THEN** the executor refuses the request with a `SandboxValidationError` and the tool does not start

#### Scenario: A large config file below a bind
- **WHEN** a request names a config file of 50 MiB and one byte that lies below a read-only bind
- **THEN** the executor refuses the request with a `SandboxValidationError` and the tool does not start
