## ADDED Requirements

### Requirement: removal-reference scan
The stage job SHALL scan `tests/` and `src/` for each name that the change folder declares as removed, before the draft pull request opens.

#### Scenario: a test file references a removed name
- **WHEN** a temporary repository holds a change folder that names `valkey_set` as removed and `tests/example_test.py` references it
- **THEN** the scan reports `tests/example_test.py` as an unhandled reference to `valkey_set`.

### Requirement: removed names come from a removal verb
The scan SHALL take each backticked identifier that a removal verb governs in `proposal.md` or `design.md` as a removed name.

#### Scenario: a removal sentence names two identifiers
- **WHEN** a fixture `proposal.md` holds the sentence `removes `valkey_set` from `CONST_MCP_EXPOSURE_TABLE``
- **THEN** the scan searches for `valkey_set` and does not search for `CONST_MCP_EXPOSURE_TABLE`.

### Requirement: a task that names the file accounts for the reference
The scan SHALL treat a reference as accounted for only when the change's `tasks.md` names the file that holds it.

#### Scenario: tasks.md names the test file
- **WHEN** a fixture `tasks.md` names `tests/example_test.py` and that file references the removed name
- **THEN** the scan reports no unhandled reference for `tests/example_test.py`.

### Requirement: stage fails on an unhandled test reference
`devops roadmap stage` MUST exit non-zero with each unhandled test reference and MUST open no draft pull request.

#### Scenario: an unhandled test reference stops the stage
- **WHEN** the scan finds an unhandled reference in `tests/`
- **THEN** the command exits non-zero, the message names the file and the removed name, and the stage opens no draft pull request.

### Requirement: a source reference is a warning
The scan SHALL report an unhandled reference in `src/` as a warning and SHALL NOT fail the stage for it.

#### Scenario: only a source file references the removed name
- **WHEN** a fixture `src/example.py` references the removed name and `tasks.md` does not name it
- **THEN** the stage succeeds and its comment names `src/example.py` as a warning.

### Requirement: a change with no removal passes
A change folder that names no removed entity SHALL pass the scan with no finding.

#### Scenario: a plan removes nothing
- **WHEN** no sentence in `proposal.md` or `design.md` has a removal verb and a backticked identifier
- **THEN** the scan reports no finding and the stage proceeds.
