## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: The cached issue key names its repository and number
The key of a cached issue MUST be `valkey:roadmap:v1:issue:<owner>/<name>:<number>`, under the prefix `CONST_VALKEY_ROADMAP_PREFIX` that the `sweep` ACL user writes and the `brain` ACL user reads, with the casefolded name of `RepoRef.key` as the key of the shared snapshot has it. The `:` after the name MUST end the repository part, so no key of a repository is a key of a repository whose name starts with the same text.

#### Scenario: A key names its repository and object
- **WHEN** The brain builds the key for issue 6013 of `Dan-Petty/DevOps-CLI`, and for issue 6013 of `dan-petty/devops-cli-2`.
- **THEN** The first key is `valkey:roadmap:v1:issue:dan-petty/devops-cli:6013`, and the second key does not start with the key prefix of the first repository and `:`.

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
