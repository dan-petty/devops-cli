## ADDED Requirements

### Requirement: A plan text is no placeholder
The stage job SHALL refuse a plan whose `why`, `existing_tool` or task text is shorter than `PLAN_FIELD_MIN_CHARS` or holds only a placeholder word.

#### Scenario: Short why is refused
- **WHEN** A plan gives `why` as `x`.
- **THEN** `check_proposal` returns a problem that names `why` and the minimum length.

#### Scenario: Placeholder existing tool is refused
- **WHEN** A plan gives `existing_tool` as `todo`.
- **THEN** `check_proposal` returns a problem that names `existing_tool` and the placeholder rule.

#### Scenario: A short real sentence is accepted
- **WHEN** A plan gives `why` as `No alternative.`
- **THEN** `check_proposal` returns no placeholder problem for `why`.

#### Scenario: The placeholder rule is the rule of the pull request form
- **WHEN** The content gate judges the text `TBD`.
- **THEN** It refuses the text through `is_placeholder` of `src/devops_cli/roadmap/pull_form.py`.

### Requirement: Feasibility quotes a probe line
When `probes` is not empty, the stage job SHALL refuse a `feasibility` list that holds no line of `probes` word for word.

#### Scenario: No quoted probe
- **WHEN** `probes` holds `def f(): pass` and `feasibility` holds `The function exists.`
- **THEN** `check_proposal` returns a problem that names `feasibility` and the quote rule.

#### Scenario: Exact probe quote
- **WHEN** `probes` holds `def f(): pass` and `feasibility` holds `The probe shows def f(): pass.`
- **THEN** `check_proposal` returns no quote problem.

#### Scenario: A job that read no probe is not judged
- **WHEN** `probes` is empty and `feasibility` holds `The function exists.`
- **THEN** `check_proposal` returns no quote problem.

### Requirement: Existing tool holds a build cost
A plan that sets `builds_own` to true SHALL give a token count and a time in `existing_tool`.

#### Scenario: Build cost missing
- **WHEN** `builds_own` is true and `existing_tool` is `Pydantic can set a minimum length.`
- **THEN** `check_proposal` returns a problem that names `existing_tool` and the cost rule.

#### Scenario: Build cost given
- **WHEN** `builds_own` is true and `existing_tool` is `Cost to build: about 80k tokens and 4 hours.`
- **THEN** `check_proposal` returns no cost problem.

#### Scenario: A plan that adopts a tool needs no cost
- **WHEN** `builds_own` is false and `existing_tool` is `Pydantic covers the need.`
- **THEN** `check_proposal` returns no cost problem.

### Requirement: A verify command can fail
The stage job SHALL refuse `true`, `:` and `exit 0` as the `verify` command of a group.

#### Scenario: True verify command
- **WHEN** A group gives `verify` as `true`.
- **THEN** `check_proposal` returns a problem that names the group and its `verify` command.

#### Scenario: A project command is accepted
- **WHEN** A group gives `verify` as `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py`.
- **THEN** `check_proposal` returns no verify problem.

### Requirement: The summary of a plan is not cut
The stage plan SHALL refuse a `summary` that is longer than `SUMMARY_MAX_CHARS` or that ends with `...`.

#### Scenario: Long summary
- **WHEN** A reply gives a `summary` of 41 characters.
- **THEN** The schema returns a problem that names `summary` and the 40-character bound.

#### Scenario: Cut summary
- **WHEN** A reply gives a `summary` that ends with `...`.
- **THEN** The schema returns a problem that names `summary` and the cut rule.

### Requirement: A title holds the full summary
`staging_title` and `delivery_title` SHALL use the full summary and SHALL add no `...`.

#### Scenario: Long delivery summary
- **WHEN** `delivery_title` receives `feat(roadmap): a summary that is longer than the bound of the title`.
- **THEN** The returned title ends with the full summary and holds no added `...`.

#### Scenario: Staging title holds the summary
- **WHEN** `staging_title` receives item 3200 and the summary `Refuse placeholder text`.
- **THEN** The returned title is `docs(openspec): plan #3200 Refuse placeholder text`.

### Requirement: The replay judges a placeholder plan
The stage replay SHALL catch a recorded placeholder plan as a defect of type `other` through the `content` gate.

#### Scenario: Gate lookup
- **WHEN** The replay asks `gate_for(DefectType.OTHER)`.
- **THEN** The answer is `GateName.CONTENT`, not `none` or `pending`.

#### Scenario: Placeholder case replayed
- **WHEN** A golden-set case holds a placeholder in `why` and an `other` defect with the gate `content`.
- **THEN** `replay_case` marks the defect `caught` and reports no failure.
