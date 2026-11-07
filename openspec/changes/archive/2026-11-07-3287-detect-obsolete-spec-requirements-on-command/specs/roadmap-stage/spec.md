## ADDED Requirements

### Requirement: A base requirement that names a removed command is updated
`check_proposal` SHALL return a problem when an ADDED requirement states that a command or an option must not exist and an unmodified base requirement of the same capability names that command or option.

#### Scenario: An added removal leaves a base requirement unchanged
- **WHEN** A proposal adds a requirement that `devops roadmap intake-eval` must not exist, and the base texts hold an unmodified requirement that names it
- **THEN** `check_proposal` returns a problem that names `devops roadmap intake-eval` and that base requirement

#### Scenario: A modified text keeps the old command
- **WHEN** A proposal adds a removal requirement for `devops roadmap intake-eval`, lists the base requirement that names it in `modified`, and the new text still names it
- **THEN** `check_proposal` returns a problem that names `devops roadmap intake-eval` and that requirement

#### Scenario: An added requirement removes an option
- **WHEN** A proposal adds a requirement that `--old` must not exist, and an unmodified base requirement names `--old`
- **THEN** `check_proposal` returns a problem that names `--old`

#### Scenario: The planner updates every stale requirement
- **WHEN** A proposal adds a removal requirement for `devops roadmap intake-eval` and lists each base requirement that names it in `modified` with text that omits the name
- **THEN** `check_proposal` returns no problem about `devops roadmap intake-eval`

### Requirement: The stale-command check reads the base requirement texts of its caller
`check_proposal` MUST run the stale-command check only when the caller passes the base requirement texts, and MUST skip it when the caller passes none.

#### Scenario: A caller passes no base texts
- **WHEN** A proposal adds a requirement that `devops roadmap intake-eval` must not exist, and the caller passes no `requirement_texts`
- **THEN** `check_proposal` returns no problem about `devops roadmap intake-eval`

#### Scenario: The stage job passes the base texts
- **WHEN** The stage job reads a base spec that names `devops roadmap intake-eval` and checks a proposal that removes that command
- **THEN** the job passes the base requirement texts to `check_proposal`, which returns a problem for the unmodified requirement

#### Scenario: A base spec gives the statement of each requirement
- **WHEN** `read_spec` reads a spec with two requirements and a scenario under the first
- **THEN** the base spec holds each requirement name with its statement, and the statement holds no scenario line

### Requirement: The stage prompt requires a modified requirement for a removed command
The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL require a `modified` requirement for each base requirement that names a command or an option that the issue removes or renames.

#### Scenario: The prompt states the rename rule
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the text holds a rule that names `modified`, a command or option that the issue removes or renames, and each base requirement that names the old name

## MODIFIED Requirements

### Requirement: The tool references keeps files of every group
`references` SHALL keep at most 60 files. It SHALL take them in turn from the specs, the source, the tests, the documents, the change folders and the other files, so that a long list of one group hides no other group. It SHALL say how many files it left out.

#### Scenario: Files left out
- **WHEN** a name is in more than 60 files, among them a spec and a document
- **THEN** the answer lists 60 files that include the spec and the document, and says how many files it left out

#### Scenario: A command name exists in a spec and in source
- **WHEN** a name is in a file under the specs and in a file under the source, and the answer keeps both files
- **THEN** the answer lists the spec file before the source file
