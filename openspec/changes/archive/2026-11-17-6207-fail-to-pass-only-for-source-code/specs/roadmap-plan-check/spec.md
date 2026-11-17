## MODIFIED Requirements

### Requirement: The plan reader reads the kind of each task group
The plan reader SHALL take the kind of a task group from its `Kind:` line when the word of the line is a kind. A group with no `Kind:` line, or with a word that is no kind, SHALL read as `behavior` when its first task fails on the base and it changes a `.py` file under `src/` outside the knowledge base, as `manifest` when its first task fails on the base and it changes no such file, and as `other` otherwise. A prompt, a pin or other data under `src/` is no such file.

#### Scenario: A Kind line sets the kind
- **WHEN** a group says `Kind: other.` and its first task fails on the base
- **THEN** the reader gives the group the kind `other` with no test

#### Scenario: A word that is no kind
- **WHEN** a group says `Kind: documentation.` and its first task passes
- **THEN** the reader gives the group the kind `other`, as for a group with no `Kind:` line

#### Scenario: A plan head with no Kind line
- **WHEN** the reader reads the change folder of #4963 at 9c4b2cf75c64, whose group 3 changes only a dashboard and its test, with its case first
- **THEN** the reader gives group 3 the kind `manifest`, and groups 1 and 2 the kind `behavior`
