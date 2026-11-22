## MODIFIED Requirements

### Requirement: A suspended CronJob is the template of the runner Job
CronJob `devops-cli-runner` in namespace `devops` SHALL be suspended and SHALL never run on a schedule. Its Job template SHALL run the init containers `prepare` and `agent` and the container `publish`, each of the image `ghcr.io/dan-petty/devops-cli/runner` with no tag and the `securityContext` of CronJob `devops-cli`, and SHALL set `activeDeadlineSeconds` to 7200 and `backoffLimit` to 0. Its pod SHALL use ServiceAccount `devops-cli`, which mounts no token.

#### Scenario: The manifest is read
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** CronJob `devops-cli-runner` holds the values above, its pod mounts no ServiceAccount token, each root filesystem is read-only, and each container drops `ALL` capabilities

#### Scenario: The admission policy
- **WHEN** a test runs the expressions of policy `roadmap-service-jobs` against the Job that the template makes, on a `CREATE` and on an `UPDATE`
- **THEN** no expression refuses it

### Requirement: The runner Job knows it is a runner and holds a home volume
Each container of CronJob `devops-cli-runner` SHALL set `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER` to `true`, mount ConfigMap `devops-cli-config` read-only and an `emptyDir` of its own as its home and as `/tmp`, and use no `envFrom`. Only `prepare` and `publish` SHALL take `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, and only `agent` `DEVOPS_CLI_AI_API_KEY`. The `ephemeral-storage` limit of `agent` SHALL cover every volume.

#### Scenario: The variable
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** each volume has a `sizeLimit`, each runner container sets `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER`, and the pod of `roadmap-service` does not

#### Scenario: The keys of the Secret
- **WHEN** `kubectl kustomize k8s/overlays/homelab/devops` renders CronJob `devops-cli-runner`, and `uv run devops ci --check --only k8s` builds the implement Job and the fix-checks Job of the Service from it
- **THEN** no container has `envFrom`, `prepare` and `publish` take only `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, and `agent` takes only `DEVOPS_CLI_AI_API_KEY`

### Requirement: The policy pins the image and the account of a Job of the Service
The policy SHALL refuse a runner Job unless it has the init containers `prepare` and `agent` and the container `publish`, or in an `UPDATE` the one container of the template before #3700. A stage Job and a planner run Job SHALL have one container and no init container. Each container SHALL run `ghcr.io/dan-petty/devops-cli/runner` alone or followed by `:` or `@`, and the pod SHALL use ServiceAccount `devops-cli` with `automountServiceAccountToken: false`.

#### Scenario: A Job with another image or account
- **WHEN** the Job from the template changes in one way: another repository, an image that only starts with the repository name, a second container, a third init container, another image of an init container, another ServiceAccount, or a token that mounts or is not set
- **THEN** the policy refuses the Job and names the rule

#### Scenario: The Job of the old template
- **WHEN** the policy checks a runner Job of one container `runner` that holds both keys
- **THEN** it refuses the `CREATE` and admits the `UPDATE`

### Requirement: The policy pins the secrets, the volumes and the host of a Job of the Service
The policy SHALL refuse a Job unless each `env` entry with `valueFrom` reads `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` or `DEVOPS_CLI_AI_API_KEY` of Secret `devops-cli` through `secretKeyRef` in the variable of its name, on the three containers the model key only in `agent` and the App key only elsewhere, the volumes are those of the template, and the pod sets no `hostNetwork`, `hostPID` or `hostIPC`.

#### Scenario: A Job with another source or volume
- **WHEN** `uv run devops ci --check --only k8s` changes the Job from the template in one way: an `env` with `valueFrom` from another Secret, a third key of Secret `devops-cli` such as `DEVOPS_CLI_VALKEY_PASSWORD` or `DEVOPS_CLI_MCP_IMPLEMENT_TOKEN`, the App key in `agent`, the model key in `prepare` or `publish`, a `hostPath` volume, a Secret volume, a ConfigMap volume of another name, `hostNetwork`, `hostPID` or `hostIPC`
- **THEN** the policy refuses the Job and names the rule

#### Scenario: The keys of the template
- **WHEN** a person creates the Job from the template as the Service with `kubectl --as=system:serviceaccount:devops:roadmap-service create --dry-run=server`
- **THEN** the policy admits the Job with the key of each container in `secretKeyRef`

### Requirement: run-job creates a Job from the runner template
`devops k8s run-job --template runner --repo owner/name -- ARGS` SHALL create a Job from CronJob `devops-cli-runner`, changing only the args of each container, with its `--phase` and `--work` (#3700), the name, the labels and the variable `DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY`, which `--repo` sets. `--template default` SHALL be the default and use CronJob `devops-cli`. The name SHALL start with the name of its CronJob. `--dry-run` SHALL make no request and name the CronJob.

#### Scenario: A Job from the runner template
- **WHEN** the Job builder gets CronJob `devops-cli-runner` with the args `roadmap implement --item 7 --confirm`
- **THEN** the Job has a name that starts with `devops-cli-runner-`, `prepare`, `agent` and `publish` have those args with their `--phase` and `--work`, every other field of the pod template equals the CronJob's, and the Job and its pod carry the label `app.kubernetes.io/name=devops-cli-job`

#### Scenario: A repository that does not fit the template
- **WHEN** `run-job` gets the runner template with no `--repo`, or `--repo` with the default template
- **THEN** the command exits 1, names the option, and sends no request

#### Scenario: A dry run
- **WHEN** `devops k8s run-job --template runner --repo example/project --dry-run -- roadmap implement --item 7` runs
- **THEN** no process starts, and the plan names CronJob `devops-cli-runner`, the token repository, the lookup of the running Jobs, and the Job of the three containers with the args of each

### Requirement: The runner Job bounds the workers of the test runner to its CPU limit
The container `agent` of CronJob `devops-cli-runner`, which runs the tests of a step (#3700), SHALL set `PYTEST_XDIST_AUTO_NUM_WORKERS` to the number of its CPU limit. `pytest-xdist` counts the CPUs of the node, not the CPU limit of the pod, so without the variable a test run starts one worker for each CPU of the node.

#### Scenario: The variable
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** the variable of the container `agent` equals its CPU limit

### Requirement: Runner telemetry service name
The runner CronJob MUST set `OTEL_SERVICE_NAME` to `roadmap-implement`, and the two dashboards that name `devops-cli-job` MUST name `roadmap-implement`.

#### Scenario: The runner reports under its own service name
- **WHEN** the runner CronJob is read from `k8s/devops/cronjob-runner.yaml`.
- **THEN** each of its containers `prepare`, `agent` and `publish` holds `OTEL_SERVICE_NAME` with the value `roadmap-implement`.

### Requirement: A network git call of the implement job runs in a folder that no agent wrote
Each git call of the implement job that reaches `origin` SHALL run in a folder that no agent wrote: the new clone of `prepare` in the run folder, before the agent phase, or the new repository of `publish`. Each git call of `prepare` and `publish` SHALL set `CONST_GIT_ISOLATED_CONFIG_ENV` and get the helper of `gh` from `-c` values. `publish` SHALL end every leftover process first, and give its calls a home folder of the run. No call with the token SHALL touch the clone of the agent phase.

#### Scenario: Programs that the home folder of the Job names
- **WHEN** a turn of the agent writes into the git configuration of the home folder a hook folder with a `pre-commit`, `post-commit`, `pre-push` and `reference-transaction` hook and a credential helper, each of which writes the `GH_TOKEN` that it sees, and the job runs a Planned item to its pull request
- **THEN** the branch of the item is on `origin`, and no program wrote the session's token

#### Scenario: A credential helper in the clone
- **WHEN** a turn of the agent adds a credential helper and a `pre-push` hook to the configuration of its clone
- **THEN** `publish` pushes from its own repository, and neither program runs

## ADDED Requirements

### Requirement: The policy keeps the three containers of a runner Job apart
On the three containers, the policy SHALL refuse a mount other than `run` at `/run/roadmap`, `state` at `/run/roadmap/state`, the own tmp and home of the container and `config` read-only, a `subPath`, `state` in `agent`, and a writable `run` or `state` in `publish`. It SHALL refuse `shareProcessNamespace`, and `restartPolicy` or `restartPolicyRules` on any container. Argo CD SHALL apply the policy and its binding before the CronJob.

#### Scenario: A Job that breaks the split
- **WHEN** the Job from the template changes in one way: `state` or the home of `publish` in `agent`, a writable `run` or `state` in `publish`, `shareProcessNamespace: true`, a `restartPolicy` on an init container or on `publish`, `restartPolicyRules`, or a `command` on an init container
- **THEN** the policy refuses the Job and names the rule

#### Scenario: The order of the sync
- **WHEN** Argo CD syncs Application `devops` after the merge
- **THEN** it applies the policy and its binding before CronJob `devops-cli-runner`

### Requirement: The policy pins the phase and the environment of the three containers
On the three containers, the policy SHALL refuse a container whose args do not end with `--phase` and its name and `--work /run/roadmap`, or hold another `--phase` or `--work`, a pod with a `restartPolicy` other than `Never`, a `lifecycle`, a probe or a `workingDir`, and a plain `env` value that the template and the Service do not set, or a `DEVOPS_CLI_CONFIG` or `DEVOPS_CLI_DATA_DIR` at another path.

#### Scenario: A Job that runs another phase or loads other code
- **WHEN** the Job from the template changes in one way: `publish` with `--work /run/roadmap/work`, `prepare` with `--phase all`, a second `--phase` or `--work`, `restartPolicy: OnFailure`, a `lifecycle`, a probe, a `workingDir`, `PYTHONPATH`, `LD_PRELOAD`, `GIT_CONFIG_GLOBAL` or `HOME` as a plain value, or `DEVOPS_CLI_DATA_DIR` in the run folder
- **THEN** the policy refuses the Job and names the rule

#### Scenario: The patches of the Service
- **WHEN** the Service patches the deadline of a Job of the three containers, marks its stall, or resumes a fix-checks Job that waited
- **THEN** the policy admits each `UPDATE`
