## ADDED Requirements

### Requirement: A base requirement that names a removed command is updated
`check_proposal` SHALL count a command or an option as removed only when MUST NOT or SHALL NOT in an ADDED requirement governs its code span: the span is the subject and the verb is exist or be available, or the span is the object of register, offer, list, accept, expose or provide. It SHALL return a problem for each unmodified base requirement of the capability that names a removed name, and for each `modified` requirement whose text keeps it.

#### Scenario: An added removal leaves a base requirement unchanged
- **WHEN** A proposal adds the requirement "The `devops roadmap intake-eval` command MUST NOT exist.", and the base texts hold an unmodified requirement that names it
- **THEN** `check_proposal` returns a problem that names `devops roadmap intake-eval` and that base requirement

#### Scenario: A removal is the object of a verb
- **WHEN** A proposal adds a requirement that MUST NOT register `devops roadmap intake-eval` as a command, and the base texts hold an unmodified requirement that names it
- **THEN** `check_proposal` returns a problem that names `devops roadmap intake-eval`

#### Scenario: An option of a command is removed
- **WHEN** A proposal adds the requirement "The `--old` option of `devops pr check-readiness` MUST NOT exist.", and unmodified base requirements name `--old` and `devops pr check-readiness`
- **THEN** `check_proposal` returns one problem, and it names `--old`

#### Scenario: A requirement forbids one act of a kept command
- **WHEN** A proposal adds the requirement "The command `devops pr check-readiness` SHALL read the changed files of a pull request from the compare endpoint, and MUST NOT request the pulls files list for them.", and an unmodified base requirement names `devops pr check-readiness`
- **THEN** `check_proposal` returns no problem about `devops pr check-readiness`

#### Scenario: A modified text keeps the old command
- **WHEN** A proposal adds a removal requirement for `devops roadmap intake-eval`, lists the base requirement that names it in `modified`, and the new text still names it
- **THEN** `check_proposal` returns a problem that names `devops roadmap intake-eval` and that requirement

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
