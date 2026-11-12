# roadmap-stage/spec-delta Specification

## Purpose
The spec delta of a plan: the OpenSpec validation against the base specs, the capabilities that the model reads, and the checks of the added, modified and scenario requirements.

## Requirements

### Requirement: The change passes the OpenSpec validation
When the `openspec` binary is on `PATH`, the job SHALL run `openspec validate <change> --strict --json` on the change before it writes to git. A failed validation SHALL go back to the model with the output of the tool, `roadmap.stage.gate_returns` times at most. A failure after the last return SHALL stop the item. Without the binary, the comment on the issue SHALL say that the validation did not run.

#### Scenario: The validation fails once
- **WHEN** the first plan fails the validation and the second plan passes it
- **THEN** the job stages the second plan and the model got the output of the first failure

#### Scenario: The validation fails twice
- **WHEN** the first plan and the plan after each return fail the validation
- **THEN** the job stops the item after the last return, pushes nothing, and reports the output of the last failure

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

### Requirement: The stage prompt requires a modified requirement for a removed command
The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL require a `modified` requirement for each base requirement that names a command or an option that the issue removes or renames.

#### Scenario: The prompt states the rename rule
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the text holds a rule that names `modified`, a command or option that the issue removes or renames, and each base requirement that names the old name

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
