## ADDED Requirements

### Requirement: Modified requirement length
`devops openspec check` SHALL refuse each `MODIFIED` requirement of an active change whose text has more than `REQUIREMENT_MAX_CHARS` characters, reporting the requirement name, length, and limit before CLI validation runs.

#### Scenario: Long modified requirement
- **WHEN** the test scripts an active change with a `MODIFIED` requirement of 523 characters and runs `uv run devops openspec check`
- **THEN** the command exits 1 and prints the requirement name, its length `523`, and the limit `500`

### Requirement: Added requirement length
`devops openspec check` SHALL refuse each `ADDED` requirement of an active change whose text has more than `REQUIREMENT_MAX_CHARS` characters, reporting the requirement name, length, and limit before CLI validation runs.

#### Scenario: Long added requirement
- **WHEN** the test scripts an active change with an `ADDED` requirement of 523 characters and runs `uv run devops openspec check`
- **THEN** the command exits 1 and prints the requirement name, its length `523`, and the limit `500`

### Requirement: One copy of the rule
The OpenSpec gate MUST use `REQUIREMENT_MAX_CHARS` and the requirement length helper from `src/devops_cli/roadmap/stage/stage_change.py`, with no second copy of either definition.

#### Scenario: Shared definition
- **WHEN** a test imports `REQUIREMENT_MAX_CHARS` and `requirement_length_problem` from `devops_cli.openspec.gate` and from `devops_cli.roadmap.stage.stage_change`
- **THEN** both names refer to the exact same objects and `devops_cli.openspec.gate` defines no requirement limit constant of its own

### Requirement: UTF-16 count
The OpenSpec gate SHALL measure requirement text length in UTF-16 code units, so each character outside the Basic Multilingual Plane counts as two code units.

#### Scenario: Surrogate pair
- **WHEN** an active change holds a `MODIFIED` requirement with 500 UTF-16 code units plus one astral character (encoded as a surrogate pair) and `uv run devops openspec check` runs
- **THEN** the command exits 1 and prints its UTF-16 length `502`

### Requirement: Openspec CI row
The `openspec` row of `devops ci` SHALL run `devops openspec check` and fail when an active change holds a long `ADDED` or `MODIFIED` requirement.

#### Scenario: CI row on a long requirement
- **WHEN** a test executes the `openspec` row via `devops ci --check --only openspec` with the row command routed to `devops openspec check` against a scripted change with a 523-character `MODIFIED` requirement
- **THEN** the row exits non-zero and prints the requirement name and length `523`

### Requirement: Archived changes out of scope
The OpenSpec gate SHALL inspect active changes only and MUST NOT fail on a long requirement under `openspec/changes/archive/`.

#### Scenario: Archived long requirement
- **WHEN** an archived change under `openspec/changes/archive/` holds a `MODIFIED` requirement of 523 characters and no active change holds a long requirement, and `uv run devops openspec check` runs
- **THEN** the command exits 0
