## MODIFIED Requirements

### Requirement: The plan reader builds a StageProposal from a change folder
The plan reader SHALL build a `StageProposal` from the files of a change folder, with the same gate inputs as the proposal that `render_change` wrote. The estimate of the lines of a created file is no gate input, and the reader SHALL give each created path one line. The reader SHALL read the references of `## Unchanged references` of `design.md`.

#### Scenario: A rendered change reads back
- **WHEN** `render_change` writes a valid proposal with groups, specs and criteria
- **THEN** the reader gives a `StageProposal` whose `groups`, `specs`, `criteria` and `skip_specs` equal the original, with one estimated line for each created path.

#### Scenario: A created path reads back with one line
- **WHEN** `render_change` writes a group that creates `tests/test_sample.py` and estimates 40 lines
- **THEN** the reader gives that path in `creates` with an estimate of 1 line.

#### Scenario: A plan with inline verification reads back
- **WHEN** `tasks.md` names the kind of a group and holds `Verify that ... fails on the base` in the task text, as an older stage job wrote it
- **THEN** the reader gives the group its kind, its verification command and the task text without the verification phrase.

#### Scenario: A change folder with no criteria section reads back with no criterion
- **WHEN** `tasks.md` holds no `## Criteria` section
- **THEN** the `StageProposal` of the reader holds an empty `criteria` list.

#### Scenario: An unchanged reference reads back
- **WHEN** `render_change` writes a proposal with one unchanged reference
- **THEN** the reader gives that reference with its path, its kind and its reason

## ADDED Requirements

### Requirement: Write, then read, keeps each fact of the files
For each valid proposal `p` whose texts hold no mark of the reader, `read_change(render_change(p))` SHALL equal `file_facts(p)`, and a read plan SHALL read back to itself. `FIELDS_NOT_IN_FILES` SHALL name the fields that no file holds: `summary`, `pull_request_body`, `builds_own`, `creates_lines` and `weakened_checks`. A changed reference is no fact of the files, because the writer writes only the unchanged references.

#### Scenario: A changed reference is no fact of the files
- **WHEN** `render_change` writes a proposal with one changed and one unchanged reference
- **THEN** the reader gives only the unchanged reference, and `file_facts` gives the same

#### Scenario: Each kind reads back
- **WHEN** `render_change` writes a proposal with one `behavior`, `manifest` or `other` group
- **THEN** the reader gives the group with the same kind

### Requirement: The plan reader reads the kind of each task group
The plan reader SHALL take the kind of a task group from its `Kind:` line when the word of the line is a kind. A group with no `Kind:` line, or with a word that is no kind, SHALL read as `behavior` when its first task fails on the base and it changes a path under `src/`, as `manifest` when its first task fails on the base and it changes no such path, and as `other` otherwise.

#### Scenario: A Kind line sets the kind
- **WHEN** a group says `Kind: other.` and its first task fails on the base
- **THEN** the reader gives the group the kind `other` with no test

#### Scenario: A word that is no kind
- **WHEN** a group says `Kind: documentation.` and its first task passes
- **THEN** the reader gives the group the kind `other`, as for a group with no `Kind:` line

#### Scenario: A plan head with no Kind line
- **WHEN** the reader reads the change folder of #4963 at 9c4b2cf75c64, whose group 3 changes only a dashboard and its test, with its case first
- **THEN** the reader gives group 3 the kind `manifest`, and groups 1 and 2 the kind `behavior`
