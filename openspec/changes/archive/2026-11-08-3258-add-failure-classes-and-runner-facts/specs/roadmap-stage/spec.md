## ADDED Requirements

### Requirement: Failure taxonomy in staging context
Staging context SHALL include the failure class table and action rules from `failure.py` when the plan cites retry, review, stop, tier or failure.

#### Scenario: Retry plan gets class table
- **WHEN** A staging run gets a plan that cites `retry`.
- **THEN** The planner context contains the class table and `ACTION_BY_CLASS` rules read from `failure.py` at the staged commit.

### Requirement: Runner capability facts in staging context
Staging context SHALL include the runner image tools, `NOT_IN_RUNNER` entries and pod security settings when the plan cites a command or tool name.

#### Scenario: Review command gets runner facts
- **WHEN** A staging run gets a plan that adds `devops review` to the Job.
- **THEN** The planner context contains the image tool list, the `NOT_IN_RUNNER` entry for each review tool and the pod security settings.

### Requirement: Repository-derived facts
The context builder MUST read the failure classes, runner tools and pod security settings from repository files at the staged commit. It MUST NOT copy them into a static prompt.

#### Scenario: Source move fails the test
- **WHEN** A test moves or renames `failure.py`, `runner_tools.py` or the pod security manifest.
- **THEN** The context builder test fails and names the moved source.

### Requirement: Planner Feasibility instruction
The planner prompt SHALL tell the planner to state each needed failure class and runner capability in `## Feasibility`.

#### Scenario: Prompt names Feasibility
- **WHEN** The staging prompt includes failure or runner capability facts.
- **THEN** The prompt contains the instruction to state those facts in `## Feasibility`.

### Requirement: Gate refuses unsupported Job command
The staging gate SHALL refuse a plan that adds a command to the Job when its `## Feasibility` section names no runner capability for that command.

#### Scenario: Unsupported Job command is refused
- **WHEN** A plan adds `devops review` to the Job and its Feasibility section names no review tool from `NOT_IN_RUNNER`.
- **THEN** The gate returns a refusal that names `devops review` and the missing runner capability.

### Requirement: Gate refuses unsupported verify program
The staging gate SHALL refuse a plan whose task verify runs a `NOT_IN_RUNNER` program without a `## Feasibility` line that names its runner capability.

#### Scenario: Helm verify is refused
- **WHEN** A plan has a task verify that runs `helm template` and its Feasibility section names no runner capability for `helm`.
- **THEN** The gate returns a refusal that names `helm` and the missing runner capability.

### Requirement: Docker verify is refused
The staging gate SHALL refuse a medium-effort plan whose task verify runs `docker` without a `## Feasibility` line that names its runner capability.

#### Scenario: Medium-effort Docker verify is refused
- **WHEN** A medium-effort plan has a task verify that runs `docker build` and its Feasibility section names no runner capability for `docker`.
- **THEN** The gate returns a refusal that names `docker` and the missing runner capability.

### Requirement: Replay case in golden set
The golden set MUST include one replay case from #3183 or #3225 that exercises the failure taxonomy and runner capability context.

#### Scenario: Replay case runs offline
- **WHEN** The golden-set test runs the #3183 or #3225 replay case.
- **THEN** The case passes with the expected context facts and the expected gate result.
