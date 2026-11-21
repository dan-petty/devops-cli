## MODIFIED Requirements

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

### Requirement: No key of a private repository
The visibility check SHALL give public, private or unknown; a failed read SHALL give unknown. The snapshot store SHALL write no key of a repository that the check does not give as public, and SHALL NOT use its shared copy. A private answer SHALL count `result="private"`, and SHALL remove a shared key of the repository and count `result="removed"`. An unknown answer SHALL count `result="unknown"`, and the store SHALL NOT read the records of or write the shared copy.

#### Scenario: Private repository
- **WHEN** a listing round runs for a repository whose visibility read gives `isPrivate: true`
- **THEN** the `valkey_server` fake holds no key that names the repository, the round reads GitHub, GitHub gets one visibility read, and `devops_cli_brain_reads_total{store="snapshot",result="private"}` and `devops_cli_brain_writes_total{store="snapshot",result="private"}` each rise by one

#### Scenario: No visibility read without the shared tier
- **WHEN** the `valkey_server` fake has `connected = False` and a listing round runs
- **THEN** the round sends no visibility read to GitHub

#### Scenario: A repository that became private
- **WHEN** a round of a public repository writes its shared snapshot, and a round in a new process finds that the repository is private
- **THEN** the `valkey_server` fake holds no key, the round uses no shared copy, and `devops_cli_brain_writes_total{result="removed"}` rises by one

### Requirement: A save of the records that the shared copy holds writes no record
A save whose records, schema key and watermark the shared snapshot already holds, with a full read that is not newer than the stored one, SHALL send no record and no transaction: it SHALL set the TTL of the key again, keep the stored `meta`, and count `devops_cli_brain_writes_total{result="unchanged"}`.

#### Scenario: Two lanes and a new process with the same records
- **WHEN** two lanes of one process save the same 1,200 records and watermark with full reads at 08:00 and 09:00, and then each saves them again twice, and a new process saves them once
- **THEN** after the first save of each lane, the lanes send only `EXPIRE` alone, beside the read of `meta` and its `PTTL` in one pipeline, the stored `meta` does not change, `devops_cli_brain_writes_total{result="unchanged"}` rises by five, and no temporary key stays

### Requirement: One key for each repository
The key of a shared snapshot, the visibility answer of a process, and the records of the shared copy that the snapshot store of a process knows SHALL use the casefolded name of `RepoRef.key`, so each spelling of a repository name gives one key, one visibility read and one set of known records.

#### Scenario: Two spellings of one name
- **WHEN** a process saves the snapshot of `Dan-Petty/DevOps-CLI`, a new process loads `dan-petty/devops-cli`, and the visibility of both spellings is read
- **THEN** the fake holds one key, the load gives the saved records, and GitHub gets one visibility read

#### Scenario: Two spellings in turn in one process
- **WHEN** one snapshot store of a process saves six snapshots, each with one more record and a newer watermark, in turn as `Dan-Petty/DevOps-CLI` and `dan-petty/devops-cli`
- **THEN** only the first save writes a temporary key, and each later save writes its changed records to the snapshot key in one WATCH transaction

## ADDED Requirements

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

### Requirement: A visibility answer is kept for its lifetime
A process SHALL keep a public or a private answer of the visibility check for `DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS` (30 min), and an unknown answer for `DEFAULT_BRAIN_VISIBILITY_FAILURE_TTL_SECONDS` (60 s), before it reads the visibility again. Thus the shared copy of a repository that became private SHALL go at most 1 hour after the change, at the first run after that time.

#### Scenario: A public answer is kept for 30 min
- **WHEN** the visibility read of a repository gives `isPrivate: false`, the `clock` fixture moves 29 min before a second check, and 2 min more before a third check whose read gives `isPrivate: true`
- **THEN** the first two checks give public with one GitHub read, and the third check reads GitHub once more and gives private

#### Scenario: An unknown answer is kept for 60 s
- **WHEN** the visibility read of a repository fails, the `clock` fixture moves 59 s before a second check, and 2 s more before a third check whose read gives `isPrivate: false`
- **THEN** the first two checks give unknown with one GitHub read, and the third check reads GitHub once more and gives public

### Requirement: A shared snapshot has a bound on its expanded records
A load of a shared snapshot SHALL expand at most `DEFAULT_BRAIN_SNAPSHOT_LOAD_MAX_BYTES` (128 MiB) of record JSON in total, in addition to the bound of 1 MiB for each record. A load past the bound SHALL be a miss, SHALL count `result="fallback"`, and the reader SHALL take the local copy or read GitHub. A save whose record JSON passes the bound SHALL write no key and SHALL count `devops_cli_brain_writes_total{result="oversize"}`.

#### Scenario: Many small records past the total bound
- **WHEN** the shared snapshot is newer than the local one and holds two records that each expand to less than 1 MiB of JSON, and the reader snapshot store is built with a total bound below the sum of the two
- **THEN** the load gives the local snapshot and raises no error, and `devops_cli_brain_reads_total{store="snapshot",result="fallback"}` rises by one

#### Scenario: A save past the total bound
- **WHEN** a snapshot store built with a total bound of 512 KiB saves a snapshot of two records of about 300,000 bytes of JSON each
- **THEN** the `valkey_server` fake holds no key, `devops_cli_brain_writes_total{store="snapshot",result="oversize"}` rises by one, and the local file holds the snapshot
