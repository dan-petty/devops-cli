## MODIFIED Requirements

### Requirement: Failure taxonomy in staging context
Staging context SHALL include the failure class table and action rules of the installed `devops_cli.roadmap.failure` module when the plan cites retry, review, stop, tier or failure. A staged commit that holds no devops-cli file gets them too.

#### Scenario: Retry plan gets class table
- **WHEN** A staging run gets a plan that cites `retry`, and the staged commit holds no `src/devops_cli/roadmap/failure.py`.
- **THEN** The planner context contains the class table and the `ACTION_BY_CLASS` rules of the installed module, and the run raises no `RoadmapStageError`.

### Requirement: Runner capability facts in staging context
Staging context SHALL include the runner tools and the `NOT_IN_RUNNER` entries of the installed `devops_cli.roadmap.runner_tools` module, each entry with its reason text, when the plan cites a command or tool name. A staged commit that holds no devops-cli file gets them too.

#### Scenario: Review command gets runner facts
- **WHEN** A staging run on a devops-cli commit gets a plan that adds `devops review` to the Job.
- **THEN** The planner context contains the image tool list, the `NOT_IN_RUNNER` entry of each program with its reason text and the pod security settings.

#### Scenario: A commit of another repository
- **WHEN** A staging run gets a plan that cites `uv`, and the staged commit holds none of the devops-cli files.
- **THEN** The planner context contains the runner tools and the `NOT_IN_RUNNER` entries, and the run raises no `RoadmapStageError`.

### Requirement: Repository-derived facts
The context builder MUST read the Dockerfile packages and the pod security settings from the files of the staged commit only when that commit holds `src/devops_cli/roadmap/runner_tools.py`. It MUST leave each fact out when the commit lacks that path or the file of the fact. It MUST NOT copy them into a static prompt.

#### Scenario: Another repository's commit holds a Dockerfile
- **WHEN** The staged commit holds a `Dockerfile` and `k8s/devops/cronjob-runner.yaml` but no `src/devops_cli/roadmap/runner_tools.py`, and the plan cites `uv`.
- **THEN** The planner context holds no installed packages line and no pod security section, and the run raises no `RoadmapStageError`.

#### Scenario: Source move fails the test
- **WHEN** A change moves or renames `runner_tools.py`, the `Dockerfile` or the pod security manifest of the repository.
- **THEN** The test of the fact files fails and names the moved path.
