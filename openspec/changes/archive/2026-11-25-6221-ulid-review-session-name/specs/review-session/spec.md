## Purpose
How review sessions are named so concurrent or sub-second runs never collide, and how `ReviewSessionStore` orders ULID and legacy timestamp session folders by start time.

## ADDED Requirements

### Requirement: Unique session names
The session-name helper `new_session_name()` SHALL return a different name on each call.

#### Scenario: One hundred calls in one process
- **WHEN** a caller invokes `new_session_name()` 100 times in one process
- **THEN** all 100 returned strings are distinct

### Requirement: ULID session name
Each session name returned by `new_session_name()` MUST be a 26-character Crockford base32 ULID string matching `^[0-7][0-9A-HJKMNP-TV-Z]{25}$`.

#### Scenario: Name pattern
- **WHEN** a caller invokes `new_session_name()`
- **THEN** the returned string matches `^[0-7][0-9A-HJKMNP-TV-Z]{25}$`

### Requirement: Start-time order
Session names MUST sort in start-time order at the millisecond resolution that the name records.

#### Scenario: Two names one millisecond apart
- **WHEN** the clock is frozen with `time_machine.travel` with `tick=False`, one name is generated, the clock shifts one millisecond forward, and a second name is generated
- **THEN** the first name sorts before the second name

### Requirement: Both review commands use the helper
`devops review pr` and `devops review branch` MUST both name their session with `new_session_name()`.

#### Scenario: Each command asks for a name
- **WHEN** `devops review branch` and `devops review pr` run with test fakes at distinct frozen instants
- **THEN** each command publishes a 26-character ULID session directory whose decoded timestamp matches its frozen instant

### Requirement: Path review gets a unique name
A review pipeline built with no session name MUST take a different default name from `new_session_name()` on each build.

#### Scenario: Two builds with no session name
- **WHEN** two `ReviewPipelineOrchestrator` instances are constructed without a `session_id` argument
- **THEN** both `session_id` values match `^[0-7][0-9A-HJKMNP-TV-Z]{25}$` and differ from each other

### Requirement: Two sessions publish in one data folder
Two sessions named by `new_session_name()` MUST both publish into one data folder without colliding.

#### Scenario: Two publishes
- **WHEN** two sessions created from `new_session_name()` are published into one data folder
- **THEN** both publishes return their directories and `ReviewSessionStore.sessions()` lists two sessions

### Requirement: Duplicate session refusal stays
A publish under the name of an already published session MUST still raise `ReviewSessionExistsError`.

#### Scenario: Forced duplicate name
- **WHEN** two sessions of the same name are published into one data folder
- **THEN** the second publish raises `ReviewSessionExistsError` with message starting `Review session <name> was not published: a session of that name already exists`

### Requirement: Mixed name formats sort by start time
`ReviewSessionStore.sessions()`, `ReviewSessionStore.latest()`, and `fetch_review_status()` MUST order sessions by their decoded start time when a data folder holds both legacy `%Y%m%d-%H%M%S` timestamp names and ULID names, placing non-timestamp names last.

#### Scenario: Older timestamp session and newer ULID session
- **WHEN** a data folder holds a published session named `20261001-120000` and a published ULID session generated at `2026-11-17T00:00:00Z`
- **THEN** `ReviewSessionStore.sessions()` lists the ULID session first and `ReviewSessionStore.latest()` and `fetch_review_status()` return the ULID session

### Requirement: python-ulid is pinned and mapped
The project MUST declare `python-ulid` with an exact `==` pin in `pyproject.toml`, map `"python-ulid" = "ulid"` in `[tool.deptry] package_module_name_map`, and record it in `uv.lock`.

#### Scenario: Lockfile and dependency check
- **WHEN** `uv run devops ci --check --only lockfile,deps` runs
- **THEN** both `lockfile` and `deps` pass with no missing or unused dependency
