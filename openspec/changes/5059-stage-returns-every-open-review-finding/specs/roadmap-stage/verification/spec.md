## ADDED Requirements

### Requirement: Every open finding returns the plan to the planner
Each open finding of a review SHALL return the plan to the planner while a repair round remains, with each open finding of the review in `problem`. An open finding is a quoted finding of an open type (`OPEN_TYPES`: `missing_path`, `false_premise`, `ignores_existing_code`, `task_order`, `verify_form`, `spec_delta_wrong` or `criterion_dropped`), or a finding that reports a placeholder that the request holds.

#### Scenario: A quoted dropped criterion finding returns the plan
- **WHEN** the verifier returns a `criterion_dropped` finding whose quote is in the issue, and the review of the revised plan finds nothing
- **THEN** the planner gets a second request with the finding in `problem` and the first plan as `previous`, and the staged change holds the revised plan and no open finding

#### Scenario: A quoted spec delta finding returns the plan
- **WHEN** the verifier returns a `spec_delta_wrong` finding whose quote is in the issue, and the review of the revised plan finds nothing
- **THEN** the planner gets a second request with the finding in `problem`, and the staged change holds no open finding

#### Scenario: A placeholder finding returns the plan
- **WHEN** the verifier returns a finding that reports a placeholder that the issue holds, and the review of the revised plan finds nothing
- **THEN** the planner gets a second request with the finding in `problem`, and the staged change holds no open finding

### Requirement: The planner prompt tells how to fix a returned finding
The planner prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL say that `problem` can list the open findings of a model review, and SHALL tell the planner how to fix a `criterion_dropped` finding and a `spec_delta_wrong` finding.

#### Scenario: The planner prompt tells how to fix the two types
- **WHEN** the planner prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` is read
- **THEN** it names the open findings of a model review, `criterion_dropped` and `spec_delta_wrong` in the text that explains `problem`
