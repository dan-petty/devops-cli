# roadmap-stage/references Specification

## Purpose
The references of a moved or removed module: the stage job probes each reference, and a task group covers it or the design records it as unchanged.

## Requirements

### Requirement: A quoted reference search names only covered files
`check_proposal` SHALL refuse each file that a quoted `References to` answer lists outside `openspec/changes/archive/` and that no group `changes` or `creates` path and no design decision names.

#### Scenario: A quoted search lists an untouched test file
- **WHEN** `feasibility` holds `References to 'SingleBinary': files 1, lines 1.` and `tests/commands/k8s/test_k8s.py: 1 (line 12)`, and no group or design decision names `tests/commands/k8s/test_k8s.py`.
- **THEN** `check_proposal` returns one problem that names `tests/commands/k8s/test_k8s.py`.

#### Scenario: A design decision names the test file
- **WHEN** The same `feasibility` lines are given, and a decision names `tests/commands/k8s/test_k8s.py` as left unchanged.
- **THEN** `check_proposal` returns no reference problem.

#### Scenario: An archived plan is skipped
- **WHEN** `feasibility` lists `openspec/changes/archive/2026-10-24-1000-old/proposal.md` in a quoted `References to` answer.
- **THEN** `check_proposal` returns no reference problem.

### Requirement: The job probes each reference of a moved module
The stage job SHALL take the old path and the dotted name of each Python module that a group moves from the old path in `changes` and the new path in `creates`, and SHALL run `git grep` on the staging commit for both names with no cap on the files. It SHALL give the path of each hit to `check_proposal`. It SHALL read no test module and no `conftest.py` as a moved module.

#### Scenario: A string literal names the old module
- **WHEN** the staging commit holds `devops_cli.roadmap.store` in a string literal of `tests/roadmap/test_store.py`, and a group moves `src/devops_cli/roadmap/store.py` to `src/devops_cli/roadmap/db/store.py`.
- **THEN** the probe gives `tests/roadmap/test_store.py` to `check_proposal`.

#### Scenario: A move names more hits than the tool keeps
- **WHEN** the old dotted name of a moved module is in 70 files, and the `references` tool keeps at most 60.
- **THEN** `reference_files` returns the path of all 70 files.

#### Scenario: A snapshot path names the old module
- **WHEN** a group moves a test module, and a snapshot file is keyed by the old test path.
- **THEN** the probe gives the path of the snapshot file to `check_proposal`.

#### Scenario: A test module is no moved module
- **WHEN** a group moves `tests/roadmap/test_store.py`.
- **THEN** the probe gives no path to `check_proposal`.

### Requirement: A reference is covered by a group or left unchanged
`check_proposal` SHALL refuse a probed path that no group lists in `changes` and that the reply does not mark unchanged with a reason.

#### Scenario: A reference is missing from the plan
- **WHEN** a probed path is `tests/roadmap/test_x.py`, no group lists that path in `changes`, and the reference is not unchanged.
- **THEN** `check_proposal` returns a problem that names `tests/roadmap/test_x.py`.

#### Scenario: A group changes the reference file
- **WHEN** a probed path is `tests/roadmap/test_x.py` and one group lists that path in `changes`.
- **THEN** `check_proposal` returns no reference problem for that path.

#### Scenario: An unchanged reference has no reason
- **WHEN** a reply marks a reference unchanged and gives no reason.
- **THEN** The schema refuses the reply with a problem that names the path.

#### Scenario: The reply lists a hit that the job does not probe
- **WHEN** a reply lists a reference that is in none of the probed paths.
- **THEN** `check_proposal` returns no problem for that reference.

### Requirement: The design records each unchanged reference
`_design_file` SHALL write the path, the kind and the reason of each unchanged reference into the rendered `design.md`.

#### Scenario: A snapshot stays keyed by the old module
- **WHEN** A reply marks `tests/snapshots/roadmap/test_x.ambr` unchanged with the kind `snapshot file` and a reason.
- **THEN** The rendered `design.md` holds that path, that kind and that reason.

### Requirement: The prompt names the references that an import rewrite misses
The stage prompt SHALL name a quoted target, a logger name and a snapshot file as references that an import rewrite does not update, and SHALL ask a move plan for a `! git grep` check on the old dotted name over `src/` and `tests/`. For a move by name prefix, the check SHALL name the old dotted prefix and no single module.

#### Scenario: The prompt lists the reference kinds
- **WHEN** The stage prompt is read.
- **THEN** It holds the words `quoted target`, `logger name` and `snapshot file`.

#### Scenario: The prompt states the verification of a direct move
- **WHEN** The stage prompt is read.
- **THEN** It holds the `! git grep` form, the old dotted name and both `src/` and `tests/`.

#### Scenario: The prompt states the verification of a prefix move
- **WHEN** The stage prompt is read.
- **THEN** It holds the old dotted prefix with no single module, and it says that a literal of one module is refused.

#### Scenario: The prompt names both searches
- **WHEN** The stage prompt is read.
- **THEN** It holds the `references` tool, the old module path and the dotted name.

#### Scenario: The prompt tells a planner to narrow a search that leaves files out
- **WHEN** The stage prompt is read.
- **THEN** It tells the planner to search a narrower name when the `references` answer leaves files out.

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

### Requirement: A reference in a file of a tool or a record needs no task group
The stage job SHALL accept a probed reference to a moved module with no task group and no `unchanged` entry when the file is of class `tool-owned` or `record` in the inventory of the documents. It SHALL refuse any other probed file that no group changes and that the reply does not mark unchanged.

#### Scenario: The changelog names a moved module
- **WHEN** the probe lists `CHANGELOG.md`, and no group changes it.
- **THEN** `check_proposal` returns no problem for `CHANGELOG.md`.

#### Scenario: The folder of another change names a moved module
- **WHEN** the probe lists `openspec/changes/3253-map-all-issue-requirements-to-a/proposal.md`, and no group changes it.
- **THEN** `check_proposal` returns no problem for that path.

#### Scenario: A hand-written document names a moved module
- **WHEN** the probe lists `docs/ROADMAP_WORKFLOW.md`, and no group changes it.
- **THEN** `check_proposal` returns a problem that names `docs/ROADMAP_WORKFLOW.md`.
