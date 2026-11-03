## ADDED Requirements

### Requirement: A move plan lists each reference of the old module
The stage reply SHALL hold a `StageReference` for each file of `src/` and `tests/` that the `references` tool returns for the old module path or its dotted name.

#### Scenario: A string literal names the old module
- **WHEN** A move plan lists a reference in a string literal under `tests/`.
- **THEN** The parsed `StageProposal` holds a `StageReference` for that test path.

#### Scenario: A snapshot path names the old module
- **WHEN** A move plan lists a snapshot file keyed by the path of a test module.
- **THEN** The parsed `StageProposal` holds a `StageReference` for that snapshot path.

### Requirement: A reference is covered by a group or left unchanged
`check_proposal` SHALL refuse a reference that no group lists in `changes` and that the reply does not mark unchanged with a reason.

#### Scenario: A reference is missing from the plan
- **WHEN** A reference names `tests/roadmap/test_x.py`, no group lists that path in `changes`, and the reference is not unchanged.
- **THEN** `check_proposal` returns a problem that names `tests/roadmap/test_x.py`.

#### Scenario: A group changes the reference file
- **WHEN** A reference names `tests/roadmap/test_x.py` and one group lists that path in `changes`.
- **THEN** `check_proposal` returns no reference problem for that path.

#### Scenario: An unchanged reference has no reason
- **WHEN** A reply marks a reference unchanged and gives no reason.
- **THEN** The schema refuses the reply with a problem that names the path.

### Requirement: The design records each unchanged reference
`_design_file` SHALL write the path and the reason of each unchanged reference into the rendered `design.md`.

#### Scenario: A snapshot stays keyed by the old module
- **WHEN** A reply marks `tests/snapshots/roadmap/test_x.ambr` as unchanged with a reason.
- **THEN** The rendered `design.md` holds that path and that reason.

### Requirement: The prompt names the references that an import rewrite misses
The stage prompt SHALL name a quoted target, a logger name and a snapshot file as references that an import rewrite does not update, and SHALL ask a move plan for a `! git grep` check on the old dotted name over `src/` and `tests/`.

#### Scenario: The prompt lists the reference kinds
- **WHEN** The stage prompt is read.
- **THEN** It holds the words `quoted target`, `logger name` and `snapshot file`.

#### Scenario: The prompt states the verification of a move
- **WHEN** The stage prompt is read.
- **THEN** It holds the `! git grep` form, the old dotted name and both `src/` and `tests/`.

#### Scenario: The prompt names both searches
- **WHEN** The stage prompt is read.
- **THEN** It holds the `references` tool, the old module path and the dotted name.
