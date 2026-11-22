## RENAMED Requirements

- FROM: `### Requirement: The policy admits envFrom only in the update of a runner Job`
- TO: `### Requirement: The policy refuses envFrom in each Job of the Service`

## MODIFIED Requirements

### Requirement: The policy pins the image and the account of a Job of the Service
The policy SHALL refuse a runner Job unless it has the init containers `prepare` and `agent` and the container `publish`, on a `CREATE` and on an `UPDATE`. A stage Job and a planner run Job SHALL have one container and no init container. Each container SHALL run `ghcr.io/dan-petty/devops-cli/runner` alone or followed by `:` or `@`, and the pod SHALL use ServiceAccount `devops-cli` with `automountServiceAccountToken: false`.

#### Scenario: A Job with another image or account
- **WHEN** the Job from the template changes in one way: another repository, an image that only starts with the repository name, a second container, a third init container, another image of an init container, another ServiceAccount, or a token that mounts or is not set
- **THEN** the policy refuses the Job and names the rule

#### Scenario: The Job of the old template
- **WHEN** the policy checks a runner Job of one container `runner` that holds both keys
- **THEN** it refuses the `CREATE` and the `UPDATE`

### Requirement: The policy refuses envFrom in each Job of the Service
The policy SHALL refuse a Job with `envFrom`, on a `CREATE` and on an `UPDATE`. A stage Job and a runner Job read their keys of Secret `devops-cli` with `valueFrom` (#6518), and no runner Job that the Service made with `envFrom` before #6518 is left in the cluster (#6691).

#### Scenario: A Job with envFrom
- **WHEN** `uv run devops ci --check --only k8s` runs the policy against the Job from the template with `envFrom` of a ConfigMap, of another Secret or of Secret `devops-cli`, and against a stage Job and a planner run Job with `envFrom` of Secret `devops-cli`
- **THEN** the policy refuses the `CREATE` and the `UPDATE` of each, with the message of the `envFrom` rule alone

### Requirement: A network git call of the implement job runs in a folder that no agent wrote
Each git call of the implement job that reaches `origin` SHALL run in a folder that no agent wrote: the new clone of `prepare` in the run folder, before the agent phase, or the new repository of `publish`. Each git call of `prepare` and `publish` SHALL set `CONST_GIT_ISOLATED_CONFIG_ENV` and get the helper of `gh` from `-c` values. `publish` SHALL give its calls a home folder of the run. No call with the token SHALL touch the clone of the agent phase.

#### Scenario: Programs that the home folder of the Job names
- **WHEN** a turn of the agent writes into the git configuration of the home folder a hook folder with a `pre-commit`, `post-commit`, `pre-push` and `reference-transaction` hook and a credential helper, each of which writes the `GH_TOKEN` that it sees, and the job runs a Planned item to its pull request
- **THEN** the branch of the item is on `origin`, the `pre-commit` hook ran at a local commit of the agent phase, and neither the credential helper nor the `pre-push` hook ran

#### Scenario: A credential helper in the clone
- **WHEN** a turn of the agent adds a credential helper and a `pre-push` hook to the configuration of its clone
- **THEN** `publish` pushes from its own repository, and neither program runs

### Requirement: run-job follows each container of the phases in turn
For a Job on the phases, `devops k8s run-job` SHALL follow `prepare`, `agent` and `publish` in turn, SHALL read the exit code of each by its name, and SHALL end with the first exit code that is not 0.

#### Scenario: The agent fails
- **WHEN** `prepare` exits with 0 and `agent` exits with 137
- **THEN** run-job follows `prepare` and `agent`, follows no more containers, and exits with 137

#### Scenario: A dry run of the runner template
- **WHEN** run-job prints the dry run of the runner template, which reads no CronJob
- **THEN** it lists the reads of each phase container, and no read of one container; a run on a CronJob of the three containers makes each request of the dry run

## REMOVED Requirements

### Requirement: The leftover processes end before each part of a network git call
**Reason**: `OriginGit` is deleted (#6691). The agent phase runs in its own container, with no token, so no process of the agent lives next to a git call with the token (#3700).
**Migration**: The withdraw of the review step pushes the delete from the clone of the plan with a plain `git push --force-with-lease`.

### Requirement: The new git folder of a shallow clone gets a copy of its shallow file
**Reason**: `OriginGit` and its new git folder are deleted (#6691). `prepare` makes its own clone, and `publish` pushes from a new repository.
**Migration**: None.

### Requirement: The dry run shows each shape of the runner template under its condition
**Reason**: The runner template in git makes only the three containers (#3700). No running runner Job of one container is left in the cluster, and the ended ones go at their TTL (#6691).
**Migration**: The requirement "The dry run shows the three containers of the runner template" replaces it.

## ADDED Requirements

### Requirement: The dry run shows the three containers of the runner template
The dry run of `devops k8s run-job` SHALL read no CronJob. For the runner template, it SHALL show only the create of a Job of the init containers `prepare` and `agent` and the container `publish`, each with the args and its `--phase` and `--work`, under the condition that the CronJob exists. The template in git makes only these three containers.

#### Scenario: The three containers
- **WHEN** the dry run of `--template runner` runs
- **THEN** it sends no request, and shows one create, of the three containers, and no container `runner`
