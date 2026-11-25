## MODIFIED Requirements

### Requirement: A row reads the cached issue before GitHub
Each row MUST read the brain entry of an issue before it reads GitHub, and MUST read GitHub only on a miss, for a write, when the entry is older than one hour, or when the caller asks for live state with `fresh=True`.

#### Scenario: A fresh entry sends no request
- **WHEN** A row reads an issue that the fake tier holds and whose last check is younger than one hour.
- **THEN** The row returns the stored issue, and the fake GitHub client receives no request.

#### Scenario: A miss reads GitHub once and fills the entry
- **WHEN** A row reads an issue that the fake tier does not hold.
- **THEN** The row reads the fake GitHub once, writes the entry, and counts one miss for its row.

#### Scenario: A live read bypasses a fresh cached entry
- **WHEN** A caller invokes `store.issue(number, fresh=True)` or `store.item(number, fresh=True)` while the fake tier holds an entry younger than one hour, and GitHub holds a newer state for that issue.
- **THEN** `GitHubRoadmapStore` queries the fake GitHub (`If-None-Match` when an `ETag` is stored, else a direct issue read), returns the live issue state, updates the stored brain entry and `self._all`, and counts one cache miss.

## ADDED Requirements

### Requirement: Authoritative callers pass fresh=True for live issue state
After an out-of-process Job completes (`implement_submit._fresh`, `stage_job.check_in`, `stage_job._return_for_split`, `fix_checks_row._record_unit`), before clearing stops (`stop_clear._clear_one`), and when reading back a Status mutation (`status_sync._read_back`), callers SHALL read with `fresh=True`.

#### Scenario: Read back checks live GitHub even when Valkey has a fresh entry
- **WHEN** `status_sync._read_back` verifies a Status write while the brain holds an entry younger than one hour.
- **THEN** `status_sync._read_back` reads with `fresh=True` against GitHub rather than trusting the unverified cache entry alone.
