## ADDED Requirements

### Requirement: A task group has the kind manifest
The stage group schema SHALL accept a group of kind `manifest` that has a `test`, an `implementation` and a `verify`, and no `process`.

#### Scenario: A manifest group validates
- **WHEN** A group has `kind: manifest`, a `test` that names `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml` in a code span, an `implementation`, and `verify: uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`.
- **THEN** `StageGroup.model_validate` returns a group whose `kind` is `manifest` and whose `process` is `None`.

#### Scenario: A manifest group has no case task
- **WHEN** A group has `kind: manifest` and `test: null`.
- **THEN** the validation error names the kind `manifest` and the missing `test`.

### Requirement: A manifest group renders its case first
`group_text` SHALL render the case task of a `manifest` group first, with `fails on the base` under it, and the work of the group second.

#### Scenario: The case comes before the work
- **WHEN** `group_text` renders a `manifest` group whose `test` names `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml` and whose `verify` is `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`.
- **THEN** the first task line holds the case text and a `Verification:` line that ends with `fails on the base`, and the second task line holds the work.

### Requirement: A case path forces the manifest kind
The stage form check MUST refuse a group of kind `other` that creates or changes a case path, and MUST name the kind `manifest` in the problem.

#### Scenario: An other group changes a promtool case
- **WHEN** An `other` group lists `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml` in `changes`.
- **THEN** `form_problems` returns one problem that names `other`, `manifest` and the path.

#### Scenario: A manifest group changes the case
- **WHEN** A `manifest` group lists that path in `changes`, its `test` names the path in a code span, and its `verify` is `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`.
- **THEN** `form_problems` returns no problem for the group.

### Requirement: The manifest verify runs a case of the group
The stage form check MUST refuse a `manifest` verify command that is not `uv run devops ci test ` followed by a path of the group.

#### Scenario: A devops command that runs no case
- **WHEN** A `manifest` group gives `uv run devops ci mutate tests/prometheus` as its verify command.
- **THEN** `form_problems` returns one problem that names the command and the `uv run devops ci test` form.

### Requirement: The planner prompt names the manifest kind
The planner prompt SHALL name the `manifest` kind, its case-first rule and its verify rule.

#### Scenario: Prompt and kinds agree
- **WHEN** the prompt-vs-rules test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md` and the names of `GroupKind`.
- **THEN** the test finds `manifest` in both and passes.
