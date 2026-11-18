## ADDED Requirements

### Requirement: The indexed row reads the points of the project
`devops roadmap onboard` SHALL print `present` in the `indexed` row when both collections hold at least one point of the project, `missing` when neither holds a point, and `partial` with the count of each collection when only one of them holds points.

#### Scenario: Both collections hold points
- **WHEN** Both collections hold at least one point for the project owner/name
- **THEN** The indexed row reads present.

#### Scenario: One collection holds points
- **WHEN** The code collection holds at least one point for the project owner/name and the docs collection holds none
- **THEN** The indexed row reads partial and prints the count of each collection.

#### Scenario: Neither collection holds a point
- **WHEN** Neither collection holds a point for the project owner/name
- **THEN** The indexed row reads missing.

### Requirement: The indexed row reports an unreadable Qdrant
`devops roadmap onboard` SHALL print `not readable` and the reason in the `indexed` row when the Qdrant client cannot be built or a count request fails, and SHALL print every other row.

#### Scenario: Qdrant is unreachable
- **WHEN** The Qdrant client cannot be built, or a count request fails
- **THEN** The indexed row reads not readable with the reason, and every other row still prints.

### Requirement: The visibility row compares the points with the repository read
`devops roadmap onboard` SHALL print private or public in the `rag visibility` row when the visibility of the points of the project equals the value of the repository read, and SHALL print `mismatch` with both values when they differ or when the points hold no visibility value.

#### Scenario: The points agree with the repository read
- **WHEN** The points of the project record private and the repository read returns private
- **THEN** The rag visibility row reads private.

#### Scenario: The points disagree with the repository read
- **WHEN** The points of the project record private and the repository read returns public
- **THEN** The rag visibility row reads mismatch and prints both values.

#### Scenario: The points hold no visibility value
- **WHEN** The points of the project hold no visibility field and the repository read returns private
- **THEN** The rag visibility row reads mismatch and prints not recorded beside private.

#### Scenario: The project holds no point
- **WHEN** Neither collection holds a point for the project owner/name
- **THEN** The rag visibility row reads not indexed.

### Requirement: The schedule row reads the repository list
`devops roadmap onboard` SHALL print `present` in the `rag schedule` row when `service.repos` includes the repository, and `missing` with the line to add when it does not, and MUST NOT write `config.yaml`.

#### Scenario: The repository is in the schedule
- **WHEN** service.repos includes the repository
- **THEN** The rag schedule row reads present.

#### Scenario: The repository is absent from the schedule
- **WHEN** service.repos leaves out the repository
- **THEN** The rag schedule row reads missing and the command prints the line to add.

#### Scenario: The configuration file stays unchanged
- **WHEN** The user runs the command with any mode flag
- **THEN** The configuration file is byte for byte the same after the command as before it.

### Requirement: The confirmed start runs the pass for one repository
`devops roadmap onboard --confirm` SHALL start the ingestion pass for the named repository only when `service.repos` includes it, SHALL print the number of points of the code collection and of the docs collection after the pass, and MUST start no ingestion when the list leaves the repository out.

#### Scenario: The pass runs for one repository
- **WHEN** service.repos includes the repository and the user passes --confirm
- **THEN** The command runs the ingestion pass for that one repository and prints the point count of the code collection and of the docs collection.

#### Scenario: The pass is refused for a repository outside the list
- **WHEN** service.repos leaves out the repository and the user passes --confirm
- **THEN** The command prints an error and starts no ingestion.

### Requirement: A second confirmed start writes no point
A second `devops roadmap onboard --confirm` run SHALL write no point when the repository is current.

#### Scenario: The repository is current
- **WHEN** The repository is current and the user passes --confirm again
- **THEN** The pass reports that it skipped the repository and the drift check of the project reads clean.

### Requirement: The page describes the RAG rows
`docs/roadmap/onboard.md` SHALL describe the `indexed`, `rag visibility` and `rag schedule` rows, the value of each, the `--confirm` start of the ingestion pass and the exit-code rule.

#### Scenario: The RAG rows are described
- **WHEN** A reader opens the onboard page
- **THEN** The page describes each RAG row, its values, the confirmed start of the pass and the exit-code rule.

## MODIFIED Requirements

### Requirement: The exit code follows the missing rows
The command SHALL exit 1 when one of the seven prerequisite rows is `missing`, and 0 when every one of them is `present` or `not readable`; a row of the index, of the visibility or of the schedule SHALL NOT change the exit code.

#### Scenario: One missing row
- **WHEN** exactly one row is `missing`
- **THEN** the command exits 1; with no `missing` row it exits 0 even when a row is `not readable`

#### Scenario: A repository that is not yet indexed
- **WHEN** Every prerequisite row is present or not readable and the indexed row reads missing
- **THEN** The command exits 0.
