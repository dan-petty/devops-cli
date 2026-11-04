## ADDED Requirements

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

#### Scenario: The reply lists a hit that the guard does not probe
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
