## ADDED Requirements

### Requirement: The stage reply renames and removes base requirements
`StageSpec` SHALL hold `renamed`, a list of `from_name` and `to_name` pairs, and `removed`, a list of entries with a `name`, a `reason` and an optional `migration`. `spec_file` SHALL write each rename under `## RENAMED Requirements` as a `- FROM:` line and a `- TO:` line that hold the requirement header in a code span, and each removal under `## REMOVED Requirements` as a requirement header with a `**Reason**:` line and its `**Migration**:` line, after the ADDED and MODIFIED sections.

#### Scenario: A plan renames a requirement
- **WHEN** the plan of #5182 renames its modified requirement to a name that fits the new text and modifies the requirement under that name
- **THEN** the pinned `openspec validate --strict` gives no problem for the rendered change against its base spec

#### Scenario: A plan removes a requirement
- **WHEN** a plan removes a base requirement with a reason and a migration
- **THEN** the spec delta holds a REMOVED block with the requirement header, the reason line and the migration line, and the pinned OpenSpec validation gives no problem

#### Scenario: A plan with no rename and no removal
- **WHEN** a plan holds only added and modified requirements
- **THEN** the spec delta holds no RENAMED section and no REMOVED section

### Requirement: Refuse a rename or a removal that the base spec does not allow
`check_proposal` SHALL refuse a `renamed` or a `removed` entry on a capability that is not in `openspec/specs/`. When the caller gives the requirement names of the capability, it SHALL refuse a `from_name` and a removed `name` that the base spec does not have, and a `to_name` that the base spec has already. `openspec validate` does not compare these names with the base spec, and `openspec archive` refuses them.

#### Scenario: A rename of a requirement that the base spec does not have
- **WHEN** a plan renames `The job stages two items` and the base spec of the capability has no requirement of that name
- **THEN** `check_proposal` returns a problem that names the requirement and the capability

#### Scenario: A new name that the base spec has
- **WHEN** a plan renames a base requirement to the name of another base requirement
- **THEN** `check_proposal` returns a problem that names the new name and the capability

#### Scenario: A removal of a requirement that the base spec does not have
- **WHEN** a plan removes a requirement that the base spec of the capability does not have
- **THEN** `check_proposal` returns a problem that names the requirement and the capability

#### Scenario: A rename on a new capability
- **WHEN** a plan renames or removes a requirement of a capability that is not in `openspec/specs/`
- **THEN** `check_proposal` returns the problem that the capability has no requirement to change

#### Scenario: A caller with no requirement names
- **WHEN** the caller gives no requirement names for an existing capability
- **THEN** `check_proposal` returns no problem about the names of a rename or a removal

### Requirement: The scenario copy follows a rename
`restore_omitted_scenarios` SHALL read the base scenarios of a MODIFIED requirement under the `from_name` of the `renamed` entry whose `to_name` is the name of the requirement, because the archive applies RENAMED before MODIFIED.

#### Scenario: A renamed requirement omits a base scenario
- **WHEN** a plan renames a base requirement with two scenarios and modifies it under the new name with one of them
- **THEN** the MODIFIED block of the new name holds the omitted base scenario, and the pinned OpenSpec validation gives no problem

### Requirement: The review refuses a modified name that no longer fits its text
The review prompt `src/devops_cli/ai/tasks/roadmap_stage_verify.md` SHALL make a `modified` requirement whose name no longer fits its new text a `spec_delta_wrong` finding. The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL tell the planner to rename such a requirement with `renamed`, to give its `modified` entry the new name, and to remove a requirement that the change makes false with `removed` and a reason.

#### Scenario: The prompts state the rename rule
- **WHEN** a test reads the review prompt and the stage prompt
- **THEN** the review prompt names a modified requirement whose name no longer fits its text under `spec_delta_wrong`, and the stage prompt names `renamed`, `removed`, `to_name` and the name of the `modified` entry

## MODIFIED Requirements

### Requirement: The stage prompt requires a modified or removed requirement for a removed command
The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL require a `modified` requirement, or a `removed` entry, for each base requirement that names a command or an option that the issue removes or renames.

#### Scenario: The prompt states the rename rule
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the text holds a rule that names `modified`, `removed`, a command or option that the issue removes or renames, and each base requirement that names the old name

### Requirement: A base requirement that names a removed command is updated or removed
`check_proposal` SHALL count a command or an option as removed only when MUST NOT or SHALL NOT in an ADDED requirement governs its code span: the span is in the subject of exist, be available or a passive such as be registered, or in the object of a verb that offers a name, such as register, list or support. It SHALL return a problem for each base requirement of the capability that names a removed name and that no `modified` requirement rewrites and no `removed` entry removes, and for each `modified` requirement whose text keeps it. A `modified` requirement under the `to_name` of a rename rewrites the base requirement of its `from_name`.

#### Scenario: An added removal leaves a base requirement unchanged
- **WHEN** A proposal adds the requirement "The `devops roadmap intake-eval` command MUST NOT exist.", and the base texts hold an unmodified requirement that names it
- **THEN** `check_proposal` returns a problem that names `devops roadmap intake-eval` and that base requirement

#### Scenario: Other words are in the subject of a removal
- **WHEN** A proposal adds the requirement "The old `devops roadmap intake-eval` command MUST NOT exist.", "The command `devops roadmap intake-eval` and its alias MUST NOT exist." or "`devops roadmap intake-eval` MUST NOT be registered as a command.", and the base texts hold an unmodified requirement that names it
- **THEN** `check_proposal` returns a problem that names `devops roadmap intake-eval`

#### Scenario: Other words are in the object of a removal
- **WHEN** A proposal adds the requirement "The CLI MUST NOT register the old `devops roadmap intake-eval` command." or "`devops pr check-readiness` MUST NOT support `--old`.", and the base texts hold unmodified requirements that name the two spans
- **THEN** `check_proposal` returns one problem, and it names the span after the verb

#### Scenario: The stage prompt gives the removal sentence
- **WHEN** the planner reads the rule of `roadmap_stage_change.md` for a command or an option that the issue removes or renames
- **THEN** the rule gives the sentence "`<old name>` MUST NOT exist.", and `check_proposal` reads the old name from that sentence

#### Scenario: A removal is the object of a verb
- **WHEN** A proposal adds a requirement that MUST NOT register `devops roadmap intake-eval` as a command, and the base texts hold an unmodified requirement that names it
- **THEN** `check_proposal` returns a problem that names `devops roadmap intake-eval`

#### Scenario: An option of a command is removed
- **WHEN** A proposal adds the requirement "The `--old` option of `devops pr check-readiness` MUST NOT exist.", and unmodified base requirements name `--old` and `devops pr check-readiness`
- **THEN** `check_proposal` returns one problem, and it names `--old`

#### Scenario: A span after a preposition is not removed
- **WHEN** A proposal adds the requirement "When `devops pr check-readiness` runs, the `--old` option MUST NOT be available.", and unmodified base requirements name `--old` and `devops pr check-readiness`
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

#### Scenario: The planner removes or renames a stale requirement
- **WHEN** A proposal adds a removal requirement for `devops roadmap intake-eval`, removes one base requirement that names it, and renames the other and modifies it under the new name with text that omits the name
- **THEN** `check_proposal` returns no problem about `devops roadmap intake-eval`

## RENAMED Requirements

- FROM: `### Requirement: The stage prompt requires a modified requirement for a removed command`
- TO: `### Requirement: The stage prompt requires a modified or removed requirement for a removed command`

- FROM: `### Requirement: A base requirement that names a removed command is updated`
- TO: `### Requirement: A base requirement that names a removed command is updated or removed`
