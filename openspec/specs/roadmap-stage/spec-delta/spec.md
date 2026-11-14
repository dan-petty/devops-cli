# roadmap-stage/spec-delta Specification

## Purpose
The spec delta of a plan: the OpenSpec validation against the base specs, the capabilities that the model reads, and the checks of the added, modified and scenario requirements.

## Requirements

### Requirement: The change passes the OpenSpec validation
When the `openspec` binary is on `PATH`, the job SHALL run `openspec validate <change> --strict --json` on the change before it writes to git. A failed validation SHALL go back to the model with the output of the tool, `roadmap.stage.gate_returns` times at most, and one more time when the item gets its extra return (`roadmap-stage/returns`, #4851). A failure after the last return SHALL stop the item. Without the binary, the comment on the issue SHALL say that the validation did not run.

#### Scenario: The validation fails once
- **WHEN** the first plan fails the validation and the second plan passes it
- **THEN** the job stages the second plan and the model got the output of the first failure

#### Scenario: The validation fails twice
- **WHEN** the first plan and the plan after each return fail the validation
- **THEN** the job stops the item after the last return, pushes nothing, and reports the output of the last failure

#### Scenario: Each failed validation is new
- **WHEN** each plan fails the validation with an output that differs from the output before it
- **THEN** the planner gets 1 + `roadmap.stage.gate_returns` + 1 requests, and the failure says that the item used its extra return

#### Scenario: No openspec binary
- **WHEN** the `openspec` binary is not on `PATH`
- **THEN** the job stages the item and its comment says that the validation did not run

### Requirement: The validation judges the change against the base specs
The job SHALL run the validation in a scratch directory that also holds the base spec of each capability the change has a delta for. Any issue in the report of OpenSpec SHALL count as a problem and SHALL go back to the model with its text, as a refused reply does, even for a valid change, such as a delta that `openspec archive` would refuse. The one exception is the INFO note that a change sets `skip_specs`.

#### Scenario: A MODIFIED requirement that the base spec lacks
- **WHEN** the plan modifies a requirement whose name is not in the base spec of an existing capability
- **THEN** the validation reports the refusal and the model gets it as the problem to correct

#### Scenario: A change that sets skip_specs
- **WHEN** OpenSpec reports only the INFO message that `skip_specs` is set
- **THEN** the validation gives no problem

#### Scenario: Another issue next to the skip_specs message
- **WHEN** OpenSpec reports the `skip_specs` message and a second INFO issue
- **THEN** the validation gives a problem that holds the second issue and not the `skip_specs` message

### Requirement: Refuse a spec delta that the changed paths do not need
`check_proposal` SHALL refuse a proposal with `skip_specs: false` when every path of every group's `changes` is under `tests/`, `.github/workflows/`, `docs/`, `openspec/` or `src/devops_cli/ai/knowledge_base/`, or is a markdown document outside `src/`.

#### Scenario: Every changed path is a test, CI, document or plan path
- **WHEN** A proposal has `skip_specs: false` and every `changes` path starts with `tests/`, `.github/workflows/`, `docs/` or `openspec/`
- **THEN** `check_proposal` returns a problem that says no spec delta is needed

#### Scenario: One changed path is source code
- **WHEN** A proposal has `skip_specs: false` and one `changes` path starts with `src/`
- **THEN** `check_proposal` returns no problem about the spec delta

#### Scenario: Root documents with a delta
- **WHEN** A plan changes only `SECURITY.md` and `CONTRIBUTING.md` and gives a spec delta
- **THEN** `check_proposal` reports that these paths need no spec delta

#### Scenario: Knowledge-base file and test path with a delta
- **WHEN** A plan changes only `src/devops_cli/ai/knowledge_base/example.md` and a path under `tests/`, and gives a spec delta
- **THEN** `check_proposal` reports that these paths need no spec delta

#### Scenario: Knowledge-base file and test path without a delta
- **WHEN** A plan changes only `src/devops_cli/ai/knowledge_base/example.md` and a path under `tests/`, and sets `skip_specs: true`
- **THEN** `check_proposal` reports no problem about a spec delta

#### Scenario: Task prompt with a delta
- **WHEN** A plan changes only `src/devops_cli/ai/tasks/roadmap_stage_change.md` and gives a spec delta
- **THEN** `check_proposal` reports no problem about a spec delta

### Requirement: Refuse an added requirement that the base spec already has
`check_proposal` SHALL refuse an ADDED requirement whose name equals the name of a requirement in the base spec of that capability.

#### Scenario: An added requirement name is in the base spec
- **WHEN** A spec delta ADDs a requirement whose name is a requirement name of `openspec/specs/<capability>/spec.md`
- **THEN** `check_proposal` returns a problem that names the duplicate requirement

#### Scenario: An added requirement name is new
- **WHEN** A spec delta ADDs a requirement whose name is in no requirement of the base spec of that capability
- **THEN** `check_proposal` returns no problem about a duplicate

### Requirement: The model input holds the purpose and the requirement names of each capability
The stage job SHALL give the model every capability under `openspec/specs/`. A plan run that has the tool `read_spec` SHALL get the names of the capabilities in the first request and SHALL read the purpose and the requirement names of one capability with `read_spec`. A call with no tool SHALL get the purpose and the requirement names of every capability in the input.

#### Scenario: The input lists a capability
- **WHEN** The stage job builds the model input for a proposal that is planned with one call and no tool
- **THEN** the input holds the purpose and the requirement names of each capability

#### Scenario: The input of a run with read_spec
- **WHEN** The stage job builds the first request of a plan run that has `read_spec`, for a checkout with many capabilities
- **THEN** the `capabilities` key holds the name of every capability in order, the request holds no purpose and no requirement name, and the run offers `read_spec`

### Requirement: The stage prompt requires a modified or removed requirement for a removed command
The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL require a `modified` requirement, or a `removed` entry, for each base requirement that names a command or an option that the issue removes or renames.

#### Scenario: The prompt states the rename rule
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the text holds a rule that names `modified`, `removed`, a command or option that the issue removes or renames, and each base requirement that names the old name

### Requirement: A scenario that names code has a behavior test
`check_proposal` SHALL refuse a spec scenario that names a function or a file when no behavior group's `test` or `verify` names it and the scenario names no command. It SHALL judge the code spans of the `then`, and the code spans of the `when` that are no path or whose path a behavior group changes, creates or reads. It SHALL NOT judge a path of the `when` that no behavior group touches, because that path is input data.

#### Scenario: A scenario names `_loki_mode` and no task tests it
- **WHEN** A spec scenario's `then` names `_loki_mode` in a code span, and no behavior group's `test` or `verify` names `_loki_mode`.
- **THEN** `check_proposal` returns one problem that names the scenario and `_loki_mode`.

#### Scenario: A scenario that cites `helm template`
- **WHEN** A spec scenario's `then` names `_loki_mode` and `helm template` in code spans, and no behavior group's `test` names `_loki_mode`.
- **THEN** `check_proposal` returns no scenario problem.

#### Scenario: A behavior test names the function
- **WHEN** A spec scenario's `then` names `_loki_mode` in a code span, and a behavior group's `test` names `_loki_mode`.
- **THEN** `check_proposal` returns no scenario problem.

#### Scenario: A data file in the condition
- **WHEN** A spec scenario's `when` says `.github/labels.yml` declares no `scope/floor`, and no behavior group changes, creates or reads `.github/labels.yml`, and no test names it.
- **THEN** `check_proposal` returns no scenario problem.

#### Scenario: A file that a behavior group reads
- **WHEN** A spec scenario's `when` names `.github/labels.yml`, a behavior group reads it, and no behavior group's `test` or `verify` names it.
- **THEN** `check_proposal` returns one problem that names the scenario and `.github/labels.yml`.

#### Scenario: A file in the result
- **WHEN** A spec scenario's `then` names `.github/labels.yml` and no behavior group's `test` or `verify` names it.
- **THEN** `check_proposal` returns one problem that names the scenario and `.github/labels.yml`.

### Requirement: Refuse a requirement text over the OpenSpec limit
`check_proposal` SHALL refuse each ADDED and MODIFIED requirement of a spec delta whose text is longer than `REQUIREMENT_MAX_CHARS`, the 500 characters that the strict OpenSpec validation of a spec allows. It SHALL count UTF-16 code units, as OpenSpec does. The problem SHALL name the requirement, its length and the limit, and `devops roadmap plan-check` SHALL report it with the rule `stage`.

#### Scenario: An ADDED requirement of 543 characters
- **WHEN** a spec delta ADDs a requirement whose text has 543 characters
- **THEN** `check_proposal` returns one problem that names the requirement, the length 543 and the limit 500

#### Scenario: The MODIFIED requirement of the #3462 plan
- **WHEN** a spec delta modifies a requirement with the text of 543 characters of the #3462 plan
- **THEN** `check_proposal` returns one problem that names the requirement and the length 543

#### Scenario: A requirement at the limit
- **WHEN** a spec delta holds a requirement text of exactly 500 characters
- **THEN** `check_proposal` returns no problem

#### Scenario: A character outside the Basic Multilingual Plane
- **WHEN** a requirement text holds 499 other characters and one emoji
- **THEN** `check_proposal` returns a problem with the length 501

#### Scenario: plan-check on a long requirement
- **WHEN** `devops roadmap plan-check` reads a change folder with a requirement text of 543 characters
- **THEN** the result holds one problem with the rule `stage` that names the requirement and the length 543

### Requirement: The stage job reads the capabilities that OpenSpec lists
The stage job SHALL read the base capabilities of the checkout from `openspec list --specs --json`, flat as `<name>` or nested as `<area>/<name>`, and SHALL read the purpose and the requirement names of each from its `spec.md`. A spec delta of a reply SHALL name a flat or a nested capability, and the validation SHALL see the base spec of a nested one. With no OpenSpec, the job SHALL know no base capability.

#### Scenario: A nested capability beside a flat one
- **WHEN** the checkout holds `openspec/specs/alpha/spec.md`, `openspec/specs/area/cap-one/spec.md` and an empty folder `openspec/specs/empty`, and OpenSpec lists `alpha` and `area/cap-one`
- **THEN** the base capabilities are `alpha` and `area/cap-one`, each with the requirement names of its file

#### Scenario: No OpenSpec
- **WHEN** the stage job reads the base capabilities with no OpenSpec
- **THEN** it knows no base capability

#### Scenario: A delta of a nested capability
- **WHEN** a reply gives a delta for `roadmap-stage/paths-gate`, and another reply gives a delta for `roadmap-stage/` or `a/../b`
- **THEN** the job accepts the first name and refuses the second reply with the message that names the form of a capability

#### Scenario: The validation of a delta of a nested capability
- **WHEN** the job validates a change with a delta for `area/comment-thread`, and the checkout holds `openspec/specs/area/comment-thread/spec.md`
- **THEN** OpenSpec validates the change in a tree that holds that base spec

### Requirement: A base requirement that names a removed command is updated or removed
`check_proposal` SHALL count a command or an option as removed only when MUST NOT or SHALL NOT in an ADDED requirement governs its code span: the span is in the subject of exist, be available or a passive such as be registered, or in the object of a verb that offers a name, such as register, list or support. It SHALL return a problem for each base requirement that names a removed name and that no `modified` or `removed` entry covers, and for each `modified` requirement whose text keeps it.

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
`check_proposal` SHALL refuse a `renamed` or a `removed` entry on a capability that is not in `openspec/specs/`. When the caller gives the requirement names of the capability, it SHALL refuse a `from_name` and a removed `name` that the base spec does not have, and a `to_name` that the base spec has already. `openspec validate --strict` passes these names. `openspec archive` refuses such a rename and skips such a removal.

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

### Requirement: A scenario that names no code has a behavior task
`check_proposal` SHALL refuse a scenario of an added or modified requirement that names no code in a code span when no behavior group covers it. A behavior group covers a scenario when its `test` holds the scenario name or the requirement name, or when its `verify` runs a test module that the group changes or creates. A scenario whose name the base spec of the capability already holds SHALL be exempt. The problem SHALL name the scenario and the requirement.

#### Scenario: A scenario that names only a field
- **WHEN** a plan modifies a requirement, adds the scenario `A What Changes line below the least length`, and its only behavior group tests another rule
- **THEN** `check_proposal` returns one problem that names the scenario and the requirement

#### Scenario: A task that names the scenario
- **WHEN** a behavior group's `test` text holds the name of the scenario or of its requirement
- **THEN** `check_proposal` returns no problem for the scenario

#### Scenario: A verify command that runs the changed test module
- **WHEN** a behavior group changes or creates a test module under `tests/` and its `verify` runs that module
- **THEN** `check_proposal` returns no problem for the scenario

#### Scenario: A scenario of the base spec
- **WHEN** a plan restates in a MODIFIED requirement a scenario that the base spec of the capability already holds
- **THEN** `check_proposal` returns no problem for that scenario

### Requirement: The stage prompt asks for a behavior task for each new scenario
The stage prompt SHALL tell the planner that each scenario of an added or modified requirement that names no code needs a behavior group whose `test` names the scenario or the requirement, or whose `verify` runs a changed or created test module, and that a base-spec scenario is exempt.

#### Scenario: The prompt holds the rule
- **WHEN** a test reads the text of `roadmap_stage_change.md`
- **THEN** the text holds the sentence of the rule
