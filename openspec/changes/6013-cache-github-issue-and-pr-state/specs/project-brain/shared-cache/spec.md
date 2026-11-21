## ADDED Requirements

### Requirement: The brain holds the issue that a row reads
The project brain SHALL hold one entry for each issue of a Service repository that a roadmap row reads, with the title, body, labels, state, update time and job record of that issue.

#### Scenario: A stored issue comes back
- **WHEN** A row asks the brain for an issue that a fake webhook has written.
- **THEN** The brain gives the title, body, labels, state, update time and job record of that issue, and the fake GitHub client receives no request.

### Requirement: A row reads the cached issue before GitHub
Each row MUST read the brain entry of an issue before it reads GitHub, and MUST read GitHub only on a miss, for a write, or when the entry is older than one hour.

#### Scenario: A fresh entry sends no request
- **WHEN** A row reads an issue that the fake tier holds and whose last check is younger than one hour.
- **THEN** The row returns the stored issue, and the fake GitHub client receives no request.

#### Scenario: A miss reads GitHub once and fills the entry
- **WHEN** A row reads an issue that the fake tier does not hold.
- **THEN** The row reads the fake GitHub once, writes the entry, and counts one miss for its row.

### Requirement: A Service write fills the cached issue
A write that the Service makes to an issue MUST write the issue that the Service holds into the brain entry.

#### Scenario: A label write fills the entry
- **WHEN** The Service adds a label to an issue that its store has read, through the fake GitHub client.
- **THEN** The fake tier holds the new label set before the fake webhook for that label is delivered.

### Requirement: A row reads GitHub when the shared tier is down
When the shared tier of the cache Valkey does not answer, a row MUST read GitHub as it does on a miss and MUST NOT fail its round on the cache.

#### Scenario: The tier refuses a connection
- **WHEN** The fake tier raises a connection error during a row round.
- **THEN** The row reads the fake GitHub, the round returns its normal result, and the Service logs the cache outage.

### Requirement: The cached issue key names its repository and number
The key of a cached issue MUST be the key that `RepoRef.valkey_key("brain-issue", <number>)` builds, `roadmap:v1:brain-issue:<owner>/<name>:<number>`, with no empty part and no glob character.

#### Scenario: A key names its repository and object
- **WHEN** The brain builds the key for issue 6013 of a Service repository.
- **THEN** The key is `roadmap:v1:brain-issue:<owner>/<name>:6013`, and `RepoRef.valkey_patterns` finds it and no key of another repository.

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
- **THEN** `devops_cli_brain_cache_total{row="refine",result="hit"}` rises by one, and the GitHub request counter of that row does not change.

### Requirement: A quiet Service repository stays inside the request budget
A Service repository with little work MUST cost fewer than 20 GitHub requests an hour.

#### Scenario: One simulated hour of a quiet repository
- **WHEN** A test reads the six issues of a quiet repository in each 5-minute round of one simulated hour, with a fake clock and a fake GitHub client.
- **THEN** The fake GitHub client records six requests, and each read after the first in the hour sends no request.

## MODIFIED Requirements

### Requirement: Each value has a bound and each key a TTL
The shared tier SHALL NOT receive a value whose encoded form is over 1 MiB; such a value SHALL stay in the in-process tier and count `devops_cli_brain_writes_total{result="oversize"}`. Each key that the mapping or the snapshot store writes SHALL have a TTL: 24 hours for a fact, 24 hours for a cached issue object and 7 days for a snapshot.

#### Scenario: T5 oversize value
- **WHEN** a `TieredMapping` stores a value whose encoded form is 1 MiB and one byte, and then a value of 1 KiB
- **THEN** no command carries the first value, a read in the same process returns it from the in-process tier, the shared tier holds the second value, and each key on the `valkey_server` fake has a TTL above 0
