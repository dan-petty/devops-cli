# roadmap-implement-runner Specification

## Purpose
The pod in which the implement job runs its steps, and what the cluster gives it: the runner image and its publication, the suspended CronJob that Jobs come from, the Role with which the Service creates one Job, and the network rules of the Service and of the Job. The runner is the sandbox of the job, because the shell of a step is no security boundary.

## Requirements

### Requirement: The runner stage names its interpreter
The `runner` stage SHALL set `UV_PYTHON` to the Python of the devtools image and `UV_PYTHON_DOWNLOADS` to `never`, and the shell of a step SHALL get `UV_PYTHON`. The `.python-version` of a checkout can name a patch release that the devtools image lacks, so `uv run` would find no interpreter.

#### Scenario: uv finds an interpreter
- **WHEN** CI runs the bootstrap of a Job and then `uv run ruff --version` in a copy of the checkout, in the runner image with a read-only root, a tmpfs home, no capability and no new privileges
- **THEN** the command prints the ruff version of `uv.lock` and exits 0

### Requirement: The release publishes the runner image
The release SHALL build the `runner` target of `Dockerfile` one time, push it by digest as `ghcr.io/<repository>/runner`, run the smoke test on that digest, scan it with Trivy for HIGH and CRITICAL findings, attest its provenance, and tag the attested digest with the release tag and `latest`. `ci.yml` SHALL build, smoke-test and scan the same target on a pull request, push nothing, and run only when image content changed.

#### Scenario: The release workflow is read
- **WHEN** a person reads the `Runner Image` jobs of the first release after the merge with `uv run devops gh run view <run_id> --log`
- **THEN** `Build` pushed one digest, `Verify` started and scanned that digest, and `Attest & Tag` attested it and put the release tag and `latest` on it

#### Scenario: The pull request check is read
- **WHEN** a test reads `.github/workflows/ci.yml`
- **THEN** a job builds `target: runner` with `push: false` and `load: true`, and each of its build steps runs only if the image content changed

### Requirement: A suspended CronJob is the template of the runner Job
CronJob `devops-cli-runner` in namespace `devops` SHALL be suspended and SHALL never run on a schedule. Its Job template SHALL name the image `ghcr.io/dan-petty/devops-cli/runner` with no tag, request and limit 2 CPU, request 4 Gi and limit 8 Gi of memory, request 2 Gi and limit 6 Gi of `ephemeral-storage`, set `activeDeadlineSeconds` to 7200 and `backoffLimit` to 0, and use the `securityContext` of CronJob `devops-cli`. Its pod SHALL use ServiceAccount `devops-cli`, which mounts no token.

#### Scenario: The manifest is read
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** CronJob `devops-cli-runner` holds the values above, its container is named `runner`, its pod mounts no ServiceAccount token, its root filesystem is read-only, and its capabilities drop `ALL`

#### Scenario: The admission policy
- **WHEN** a test runs the expressions of policy `roadmap-service-jobs` against the Job that the template makes
- **THEN** no expression refuses it

### Requirement: The runner Job knows it is a runner and holds a home volume
The container of CronJob `devops-cli-runner` SHALL set `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER` to `true`, take only the keys `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` and `DEVOPS_CLI_AI_API_KEY` of Secret `devops-cli`, through `secretKeyRef` and with no `envFrom`, mount ConfigMap `devops-cli-config`, and mount an `emptyDir` of 8 Gi as its home and an `emptyDir` of 1 Gi as `/tmp`. The other CronJob SHALL not set that variable. The `ephemeral-storage` limit SHALL cover both volumes.

#### Scenario: The variable
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** both volumes have a `sizeLimit`, only the runner container sets `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER`, and the pod of `roadmap-service` does not

#### Scenario: The keys of the Secret
- **WHEN** `kubectl kustomize k8s/overlays/homelab/devops` renders CronJob `devops-cli-runner`, and `uv run devops ci --check --only k8s` builds the implement Job and the fix-checks Job of the Service from it
- **THEN** the container and both Jobs have no `envFrom` and take only `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` and `DEVOPS_CLI_AI_API_KEY` through `secretKeyRef`

### Requirement: run-job creates a Job from the runner template
`devops k8s run-job --template runner --repo owner/name -- ARGS` SHALL create a Job from CronJob `devops-cli-runner`, changing only the args of container `runner`, the name, the labels and the variable `DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY`, which `--repo` sets. `--template default` SHALL be the default and use CronJob `devops-cli`. The name SHALL start with the name of its CronJob. `--dry-run` SHALL make no request and name the CronJob.

#### Scenario: A Job from the runner template
- **WHEN** the Job builder gets CronJob `devops-cli-runner` with the args `roadmap implement --item 7 --confirm`
- **THEN** the Job has a name that starts with `devops-cli-runner-`, the container `runner` has those args, every other field of the pod template equals the CronJob's, and the Job and its pod carry the label `app.kubernetes.io/name=devops-cli-job`

#### Scenario: A repository that does not fit the template
- **WHEN** `run-job` gets the runner template with no `--repo`, or `--repo` with the default template
- **THEN** the command exits 1, names the option, and sends no request

#### Scenario: A dry run
- **WHEN** `devops k8s run-job --template runner --repo example/project --dry-run -- roadmap implement --item 7` runs
- **THEN** no process starts, and the plan names CronJob `devops-cli-runner`, the token repository and the lookup of the running Jobs

### Requirement: A runner Job carries the label of its repository and is the only one
The Job and its pod of `run-job --template runner` SHALL carry the label `implement-repo` with the digest of `--repo` in lower case, the label that the Service lists its Jobs by. `run-job` SHALL create no Job while a Job with that label has not ended, whoever made it. The lock is best effort: the Service and `run-job` list the Jobs just before they create one, and a Job that starts between the two calls is not seen.

#### Scenario: The label of the repository
- **WHEN** `run-job --template runner --repo example/project` creates a Job
- **THEN** the Job and its pod carry `implement-repo` with the label value that the Service computes for `example/project`

#### Scenario: Another spelling of the repository
- **WHEN** a Job of `example/project` has not ended and `run-job` gets `--repo Example/Project`
- **THEN** the command exits 1 and creates no Job

#### Scenario: A running Job of the repository
- **WHEN** `run-job --template runner --repo example/project` runs and a Job with that label has no Complete or Failed condition
- **THEN** the command exits 1, names the running Job, and creates no Job

### Requirement: The Service creates Jobs through a narrow Role
ServiceAccount `roadmap-service` SHALL be the account of the Service pod. A Role in namespace `devops` SHALL allow `create`, `get`, `list` and `patch` on `jobs`; `get` on `cronjobs` named `devops-cli-runner` and on `deployments` named `roadmap-service`; `list` on `pods`; `get` on `pods/log`; and nothing else. A RoleBinding SHALL bind the Role to the account only. The Service pod SHALL mount a projected token with `expirationSeconds` 3600. The pods of Jobs SHALL keep no token.

#### Scenario: The manifests are read
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** the Role holds exactly those rules, the RoleBinding names one subject, the Deployment `roadmap-service` uses ServiceAccount `roadmap-service` with `automountServiceAccountToken: false` and a projected volume with a token of 3600 seconds, and no pod template of a CronJob mounts a token

### Requirement: Only the Service pod may reach the API server
A NetworkPolicy SHALL admit egress of the pods labeled `app.kubernetes.io/name=roadmap-service` to TCP 6443 through an `ipBlock` that excludes `169.254.169.254/32`. No policy SHALL admit a Job pod to port 6443. The Job pods SHALL keep the egress of `devops-default-perimeter`: DNS, the gateway on 4000, the cache on 6379, the OTLP collector on 4318 and public HTTPS.

#### Scenario: The policies are read
- **WHEN** a test reads the rendered NetworkPolicies of namespace `devops`
- **THEN** the policy for `roadmap-service` holds one egress rule, to port 6443 with the metadata address excluded, and no other policy of the namespace names port 6443

### Requirement: Public HTTPS excludes the non-public ranges
Rule 4 of `devops-default-perimeter` SHALL exclude the private ranges, the shared address space `100.64.0.0/10`, the link-local range `169.254.0.0/16`, `169.254.169.254/32`, `192.0.0.0/24` and `198.18.0.0/15`.

#### Scenario: The policy is read
- **WHEN** `uv run devops ci --check --only k8s` renders Application `devops`, and a person reads NetworkPolicy `devops-default-perimeter` of the render
- **THEN** the `except` list of the port 443 rule holds exactly those ranges

### Requirement: Image Updater keeps the runner image on its latest digest
ImageUpdater `devops` SHALL name `ghcr.io/dan-petty/devops-cli/runner:latest` with the `digest` strategy and `forceUpdate: true`, as it names the Service image.

#### Scenario: The values are read
- **WHEN** a test reads `k8s/argocd/image-updater-values.yaml`
- **THEN** the ImageUpdater lists the images `service` and `runner`, and both use `updateStrategy: digest` and `forceUpdate: true`

### Requirement: An admission policy covers only the Jobs of the Service
A ValidatingAdmissionPolicy and a binding SHALL apply to `CREATE` and `UPDATE` of `batch/v1` `jobs` in namespace `devops`, with `failurePolicy: Fail` and the actions `Deny` and `Audit`. A match condition SHALL limit the policy to the user `system:serviceaccount:devops:roadmap-service`, which is the subject of the RoleBinding `roadmap-service-jobs`. The expressions SHALL use only standard CEL.

#### Scenario: The scope is read
- **WHEN** a test reads the rendered policy, binding and RoleBinding
- **THEN** the rules cover `CREATE` and `UPDATE` of `jobs` only, the binding selects namespace `devops`, the failure policy is `Fail`, the actions are `Deny` and `Audit`, and the match condition is the equality of the request user with the subject of the RoleBinding

#### Scenario: Another identity
- **WHEN** the policy is evaluated for a Job that breaks a rule, made by the CLI user, Argo CD or the CronJob controller
- **THEN** the match condition is false, so the policy does not refuse the Job

### Requirement: The policy pins the image and the account of a Job of the Service
The policy SHALL refuse a Job unless it has one container and no init container, the image of the container is `ghcr.io/dan-petty/devops-cli/runner` alone or followed by `:` or `@`, and the pod uses ServiceAccount `devops-cli` with `automountServiceAccountToken: false`.

#### Scenario: A Job with another image or account
- **WHEN** the Job from the template changes in one way: another repository, an image that only starts with the repository name, a second container, an init container, another ServiceAccount, or a token that mounts or is not set
- **THEN** the policy refuses the Job and names the rule

### Requirement: The policy pins the secrets, the volumes and the host of a Job of the Service
The policy SHALL refuse a Job unless each `env` entry with `valueFrom` reads the key `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` or `DEVOPS_CLI_AI_API_KEY` of Secret `devops-cli` through `secretKeyRef` in the variable of its name, the volumes are only `tmp` and `home` (`emptyDir`) and `config` (ConfigMap `devops-cli-config`), and the pod sets no `hostNetwork`, `hostPID` or `hostIPC`.

#### Scenario: A Job with another source or volume
- **WHEN** `uv run devops ci --check --only k8s` changes the Job from the template in one way: an `env` with `valueFrom` from another Secret, a third key of Secret `devops-cli` such as `DEVOPS_CLI_VALKEY_PASSWORD` or `DEVOPS_CLI_MCP_IMPLEMENT_TOKEN`, a `hostPath` volume, a Secret volume, a ConfigMap volume of another name, `hostNetwork`, `hostPID` or `hostIPC`
- **THEN** the policy refuses the Job and names the rule

#### Scenario: The keys of the template
- **WHEN** a person creates the Job from the template as the Service with `kubectl --as=system:serviceaccount:devops:roadmap-service create --dry-run=server`
- **THEN** the policy admits the Job with its 2 keys in `secretKeyRef`

### Requirement: The policy admits envFrom only in the update of a runner Job
The policy SHALL refuse a Job with `envFrom`, but not in the `UPDATE` of a runner Job whose `envFrom` names only Secret `devops-cli`. A runner Job that the Service made before #6518 has that `envFrom`, and the Service patches its deadline and resumes it. A Job keeps its pod template, so an `UPDATE` cannot add `envFrom`.

#### Scenario: A Job with envFrom
- **WHEN** `uv run devops ci --check --only k8s` runs the policy against the Job from the template with `envFrom` of a ConfigMap, of another Secret or of Secret `devops-cli`
- **THEN** the policy refuses the `CREATE` of each, admits the `UPDATE` of a runner Job with Secret `devops-cli` in `envFrom`, and refuses the `UPDATE` of a runner Job with another Secret in `envFrom`

### Requirement: The policy keeps a Job of the Service from reaching beyond its pod
The policy SHALL refuse a Job unless the label `app.kubernetes.io/name` of its pod template is `devops-cli-job`, the pod sets no `priorityClassName`, `nodeName` or `imagePullSecrets`, the container sets no `command`, the Job sets no `manualSelector`, and `completions` and `parallelism` are 1 or not set.

#### Scenario: A pod with the label of the Service
- **WHEN** the Job from the template changes the label `app.kubernetes.io/name` of its pod to `roadmap-service`, to the name of another pod, or removes the labels
- **THEN** the policy refuses the Job and names the rule

#### Scenario: A Job that reaches beyond the pod
- **WHEN** the Job from the template changes in one way: a `priorityClassName`, a `nodeName`, an `imagePullSecrets` entry, a container `command`, `manualSelector`, 2 for `completions`, or 2 for `parallelism`
- **THEN** the policy refuses the Job and names the rule

#### Scenario: The default values
- **WHEN** the Job from the template names `completions: 1`, `parallelism: 1` and `manualSelector: false`
- **THEN** the policy admits the Job

### Requirement: The policy bounds the run of a Job of the Service
The policy SHALL refuse a Job unless it sets `backoffLimit: 0` and an `activeDeadlineSeconds` that is at most 14400, the cap of `CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS`. A Job that the Job builder makes from CronJob `devops-cli-runner` SHALL pass the policy.

#### Scenario: A Job from the runner template
- **WHEN** a test builds the Job from the rendered CronJob `devops-cli-runner` with `build_job`, the environment value and the labels of the Service, and evaluates the policy for the Service user
- **THEN** the policy admits the Job, also when the image carries a tag, a digest, or both

#### Scenario: A Job that runs too long or retries
- **WHEN** the Job from the template sets a `backoffLimit` above 0, an `activeDeadlineSeconds` above the cap, or no `activeDeadlineSeconds`
- **THEN** the policy refuses the Job

#### Scenario: A Job at the cap
- **WHEN** the Job from the template sets `activeDeadlineSeconds` to the cap
- **THEN** the policy admits the Job

### Requirement: The runner Job bounds the workers of the test runner to its CPU limit
The container of CronJob `devops-cli-runner` SHALL set `PYTEST_XDIST_AUTO_NUM_WORKERS` to the number of its CPU limit. `pytest-xdist` counts the CPUs of the node, not the CPU limit of the pod, so without the variable a test run starts one worker for each CPU of the node.

#### Scenario: The variable
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** the variable of the runner container equals its CPU limit

### Requirement: The local hooks run only programs that the runner image holds
Each `language: system` hook of `.pre-commit-config.yaml` SHALL start with `uv run`, and the tool that it runs SHALL be a dev dependency of the lock (`ast-grep-cli`, `devops`) or a program of `RUNNER_TOOLS` (`openspec`). The `pre-commit` package SHALL be a dev dependency of the lock. The hook environments SHALL be fetched at run time into the home volume, because the perimeter admits public HTTPS.

#### Scenario: A hook that needs another program
- **WHEN** a local hook has the entry `vale`
- **THEN** the test fails and names the hook and the program

#### Scenario: The config as it is
- **WHEN** the test reads `.pre-commit-config.yaml`, `pyproject.toml` and `RUNNER_TOOLS`
- **THEN** every local hook passes

### Requirement: The policy admits only the sizes in the table
The policy SHALL refuse a Job of the Service unless the CPU request of its container equals the CPU limit, the pair of the CPU and the memory request is a row of `RUNNER_SIZES`, the container has a memory limit, and the value of `PYTEST_XDIST_AUTO_NUM_WORKERS` equals the CPU limit. It SHALL not pin the memory limit.

#### Scenario: A Job of each row
- **WHEN** a test builds the Job that the Service makes for each row of the table and evaluates the policy for the Service user
- **THEN** the policy admits the Job

#### Scenario: A size outside the table
- **WHEN** a test tries each pair of CPU and memory request from a grid that holds the rows and values near them
- **THEN** the policy admits exactly the pairs of the table

#### Scenario: A worker count that differs
- **WHEN** the Job sets `PYTEST_XDIST_AUTO_NUM_WORKERS` to a value other than its CPU limit, or sets a CPU request other than its CPU limit
- **THEN** the policy refuses the Job

#### Scenario: A raised memory limit
- **WHEN** the Job of a row sets a memory limit of 12Gi
- **THEN** the policy admits the Job

### Requirement: The leftover processes end before each part of a network git call
`OriginGit` SHALL end every leftover process before it makes the new folder, and again just before the call with the token.

#### Scenario: The order of the calls
- **WHEN** the job reads the heads of a branch
- **THEN** the leftover processes end before the new folder is made, again after the new git folder is ready, and only then the read with the token runs

#### Scenario: A link at the shallow file before the call
- **WHEN** the `shallow` file of the clone is a link, and the job reads the heads of a branch in a runner
- **THEN** the leftover processes end first, the call raises `GitSettingsError` that names `shallow`, and the read with the token does not run

### Requirement: The new git folder of a shallow clone gets a copy of its shallow file
The new git folder of a network call SHALL get a copy of the `shallow` file of a shallow clone, which the job SHALL open with `O_NOFOLLOW`. A link, or anything but a regular file, at that place SHALL raise `GitSettingsError` that names `shallow`.

#### Scenario: A push from a shallow clone
- **WHEN** the clone was made with `--depth 1`, and the job pushes a new commit of the clone
- **THEN** `origin` holds the new commit on the branch, and the clone stays shallow

#### Scenario: A link at the shallow file
- **WHEN** the `shallow` file of the clone is a link, and the job reads the heads of `main`
- **THEN** the call raises `GitSettingsError` that names `shallow`

### Requirement: Repository and item labels
`build_job` SHALL set `roadmap.devops-cli/owner`, `roadmap.devops-cli/repo` and `roadmap.devops-cli/item` on the Job metadata and on the pod template metadata.

#### Scenario: Labels on the Job and on its pod
- **WHEN** `build_job` builds a runner Job for repository `Dan-Petty/DevOps-CLI` and item 4558.
- **THEN** both metadata blocks hold `roadmap.devops-cli/owner: dan-petty`, `roadmap.devops-cli/repo: devops-cli` and `roadmap.devops-cli/item: 4558`.

### Requirement: Repository annotation on the pod
`build_job` SHALL set the annotation `roadmap.devops-cli/repository` to the casefolded `owner/name` on the Job and on the pod template.

#### Scenario: The annotation reaches the pod
- **WHEN** `build_job` builds a Job for `Dan-Petty/DevOps-CLI`.
- **THEN** the Job metadata and the pod template metadata hold the annotation `roadmap.devops-cli/repository: dan-petty/devops-cli`.

### Requirement: Component and ownership labels
`build_job` SHALL set `app.kubernetes.io/component: roadmap-<row>`, `app.kubernetes.io/part-of: devops-cli-stack` and `app.kubernetes.io/managed-by: devops-cli` on the Job and on the pod template.

#### Scenario: The component of the runner Job
- **WHEN** the Service builds a runner Job for the `implement` row.
- **THEN** both metadata blocks hold `app.kubernetes.io/component: roadmap-implement` and `app.kubernetes.io/part-of: devops-cli-stack`.

### Requirement: Runner Job name
The runner Job of the Service SHALL be named `devops-cli-implement-<slug>-<item>-<6 hex>` and MUST hold 63 characters or fewer.

#### Scenario: A long slug is cut
- **WHEN** the slug and the item number make the name longer than 63 characters.
- **THEN** the name holds 63 characters, keeps the `-<6 hex>` suffix, and matches the DNS-1123 subdomain form.

### Requirement: Dry run shows the Job
`devops k8s run-job --template runner --dry-run` MUST show the Job name and the repository labels and MUST send no request.

#### Scenario: The dry run of a runner Job
- **WHEN** a user runs the command with `--repo dan-petty/devops-cli -- true`.
- **THEN** the printed plan holds the Job name placeholder and the `roadmap.devops-cli/*` labels, and no kubectl command runs.

### Requirement: Runner telemetry service name
The runner CronJob MUST set `OTEL_SERVICE_NAME` to `roadmap-implement`, and the two dashboards that name `devops-cli-job` MUST name `roadmap-implement`.

#### Scenario: The runner reports under its own service name
- **WHEN** the runner CronJob is read from `k8s/devops/cronjob-runner.yaml`.
- **THEN** its `runner` container holds `OTEL_SERVICE_NAME` with the value `roadmap-implement`.

### Requirement: The runner tools table names each tool that the gate and the hooks need
`RUNNER_TOOLS` in `devops_cli.roadmap.runner_tools` SHALL list each program that a runner Job needs, its source (the base system, the devtools image, the project or the venv of the checkout), why it is there, and the command that proves it runs. `NOT_IN_RUNNER` SHALL name each program that a step of the Job does not count on, with the reason. The module SHALL hold no tool version: the devtools image and `uv.lock` give them.

#### Scenario: A source of the gate needs a program that is in neither table
- **WHEN** a program of a `devops ci` row, of a hook of `.pre-commit-config.yaml`, of a required job of `ci.yml` or of a live-marked test is in neither `RUNNER_TOOLS` nor `NOT_IN_RUNNER`
- **THEN** a test fails and names the program

#### Scenario: A Dockerfile pin bump changes no runner code
- **WHEN** a pull request moves the tag and the digest of the devtools image in `Dockerfile`
- **THEN** it changes no line of `src/devops_cli/roadmap/runner_tools.py`, because `RUNNER_TOOLS` holds no version

### Requirement: The runner image builds FROM the devtools image
The `runner` stage SHALL build from `runner-deps`, which builds FROM the devtools image, pinned by tag and digest. `runner-deps` SHALL add the user `devops` (uid and gid 1000) and install only the runtime requirements of the `lock` stage, with the `review` extra, into `/app/.venv`. The devtools image SHALL give each image tool of `RUNNER_TOOLS`. The image SHALL run as user 1000 with `ENTRYPOINT ["devops"]`, `/app/.venv/bin` first on `PATH` and `UV_COMPILE_BYTECODE=0`.

#### Scenario: The image is built and started
- **WHEN** a person builds `--target runner` and runs `docker run --rm --entrypoint id <image> -u` and `docker run --rm <image> --version`
- **THEN** the build exits 0, the first command prints `1000`, and the second prints the version of devops-cli

#### Scenario: The image venv holds no dev tool
- **WHEN** a person runs `docker run --rm --entrypoint sh <runner image> -c 'ls /app/.venv/bin'`
- **THEN** the output lists no `ruff`, `mypy`, `pytest` or `pre-commit`

### Requirement: The runner image holds no uv cache and no build input
The runner image SHALL hold no uv cache of root and no requirement file of the build. Each uv install of the `Dockerfile` SHALL keep its cache in a cache mount, and the requirement files of the `lock` stage SHALL come in as bind mounts.

#### Scenario: The image holds no uv cache
- **WHEN** a person runs `docker run --rm --user 0 --entrypoint sh <runner image> -c 'test -z "$(find /root/.cache/uv /lock -type f 2>/dev/null)"'`
- **THEN** the command exits 0

### Requirement: The runner tool check fails on a missing tool
The smoke test of the runner image SHALL run `python -m devops_cli.roadmap.runner_tools` as user 1000 on the loaded image, which checks each image tool, and with a copy of the checkout as its argument, which runs the bootstrap and checks each tool of the checkout. The check SHALL fail when an image program is not on PATH, a checkout program is not in `<checkout>/.venv/bin`, a version command fails, the project prints another version, or the bootstrap fails. It SHALL compare no other version.

#### Scenario: A tool is missing or at another version
- **WHEN** a program of the image is not on PATH, its version command exits non-zero, or the project prints a version other than the version of its installed distribution
- **THEN** the check names the tool and exits 1

#### Scenario: A tool of the devtools image prints any version
- **WHEN** the version command of a tool that the devtools image gives exits 0
- **THEN** the check of the tool passes, and the check runs only that version command

#### Scenario: Every tool passes
- **WHEN** every version command of an image tool exits 0, and the project prints its installed version
- **THEN** the check prints the number of image tools, runs no version command of a tool of the checkout, and exits 0

#### Scenario: A tool of the checkout is missing from its venv
- **WHEN** the check runs with a checkout whose `.venv/bin` lacks `ruff`
- **THEN** the check names `ruff` and the checkout and exits 1

#### Scenario: The check of a checkout runs its bootstrap first
- **WHEN** the check runs with a checkout that holds `uv.lock`
- **THEN** it runs `uv sync --locked --group dev` in the checkout, then the version command of each tool of the checkout there, and exits 1 with the output of the sync when the sync fails

### Requirement: The smoke test of the runner image runs the tool check and bounds the size
The smoke test of the runner image in `ci.yml` and in the `Verify` job of `release-image.yml` SHALL be the same text, SHALL run the tool check of the image and the tool check of a copy of the checkout, SHALL then run `uv run ruff --version`, `uv run pytest --version` and `uv run mypy --version` in that copy, and SHALL fail when the image is larger than 7000000000 bytes.

#### Scenario: The smoke test runs on the loaded image
- **WHEN** the Runner Image job of `ci.yml` runs its smoke test on the loaded image
- **THEN** the check module prints that every runner tool is on PATH and runs, for the image and for the checkout, the three `uv run` commands exit 0, and the step fails when `docker image inspect` reports more than 7000000000 bytes

### Requirement: The scan of the runner image reports and stops no build
The Runner Image job of `ci.yml` and the `Verify` job of the runner image in the release SHALL scan the `runner` image with `.github/actions/image-scan` (Trivy, `HIGH,CRITICAL`, fixed findings only) with exit code 0, and SHALL upload the SARIF under the category `trivy-image-runner`. SECURITY.md SHALL record the exception in its table, with the scope, the compensating control, the evidence, the approval and the review.

#### Scenario: The scan of a runner image with findings
- **WHEN** the Runner Image job scans a runner image whose devtools tools hold fixed HIGH findings
- **THEN** the scan step exits 0, the job log names each finding, and code scanning lists them under `trivy-image-runner`

### Requirement: A Job builds the coder environment of its checkout
The implement Job and the model fix of the fix-checks Job SHALL call `bootstrap_checkout` (`devops_cli.roadmap.runner_tools`) on their checkout before their first agent step. It SHALL run `uv sync --group dev` when `uv.lock` exists and an npm install when a root `package-lock.json` exists: `--locked` and `npm ci` on the new branch of a Planned item, else `--frozen` and `npm install --no-save`. It SHALL write no tracked file. Tier 1 of fix-checks SHALL run no bootstrap.

#### Scenario: The implement Job bootstraps before the hooks and the first model request
- **WHEN** the implement Job runs a staged item whose default branch holds `uv.lock` and `package-lock.json`
- **THEN** it runs `uv sync --frozen --group dev` and then `npm install --no-save --ignore-scripts` in the worktree, after the rebase, before `pre-commit install-hooks` and before the first model request

#### Scenario: A stale lock of a staged branch stays for the agent
- **WHEN** the implement Job runs a staged item whose `uv.lock` and `package-lock.json` do not match `pyproject.toml` and `package.json`
- **THEN** the sync installs `uv.lock` as it is, npm writes no lock, `uv run --frozen pre-commit install-hooks` writes no `uv.lock`, and the item does not stop before its first model request

#### Scenario: A Planned item syncs with its lock
- **WHEN** the implement Job runs a Planned item whose default branch holds `uv.lock`
- **THEN** the sync is `uv sync --locked --group dev`

#### Scenario: A checkout with no lock file
- **WHEN** the bootstrap runs in a checkout that holds neither `uv.lock` nor `package-lock.json`
- **THEN** it runs no command

#### Scenario: Tier 1 repairs a stale lock with no bootstrap
- **WHEN** the fix-checks checkout opens a branch whose `uv.lock` is stale and tier 1 gets a lockfile failure
- **THEN** the checkout opens, tier 1 runs `uv lock` and `uv lock --check`, and no sync runs

#### Scenario: The model fix bootstraps its worktree
- **WHEN** the fix-checks round reaches the model fix on a branch that holds `uv.lock`
- **THEN** it runs `uv sync --frozen --group dev` in the worktree before the first model request

#### Scenario: A stale lock of a fix-checks branch stays for the agent
- **WHEN** the model fix of fix-checks runs on a head branch whose `uv.lock` and `package-lock.json` do not match `pyproject.toml` and `package.json`, and the default branch holds `.pre-commit-config.yaml`
- **THEN** the bootstrap and the install of the hook environments write no tracked file, and the model fix reaches its first model request

### Requirement: The hook commands of a Job lock nothing
The Job SHALL start each `pre-commit` command with `uv run --frozen`, so the install of the hook environments and the hook stages write no `uv.lock`.

#### Scenario: The install of the hook environments on a stale lock
- **WHEN** the implement Job or the model fix of fix-checks installs the hook environments in a worktree whose `uv.lock` does not match `pyproject.toml`
- **THEN** the command is `uv run --frozen pre-commit install-hooks --config <config>`, and `uv.lock` stays as it is

### Requirement: A failed bootstrap ends the Job before its first agent step
A bootstrap command that exits non-zero or runs out of time SHALL raise `ToolExecutionError` with the command and its output. The implement Job SHALL stop the item at the step `bootstrap` with nothing to push, and the model fix of fix-checks SHALL fail with the error and make no model request.

#### Scenario: A failed bootstrap stops the implement item
- **WHEN** the sync of the implement Job exits 2
- **THEN** the item stops at the step `bootstrap` with no model request and no push, and the comment holds the output of the sync

#### Scenario: A failed bootstrap fails the model fix
- **WHEN** the sync of the model fix of fix-checks exits 2
- **THEN** the round ends as failed with the output of the sync, and no model request was made

### Requirement: The bootstrap uses the uv seed when it fits
`bootstrap_checkout` SHALL use the uv-seed volume `/opt/uv-seed` only when it holds `cache/` and a `seed.json` that names the uv version, the `<major>.<minor>` Python version of the Job and the sha256 of the checkout's `uv.lock`. Then it SHALL copy `cache/` into `UV_CACHE_DIR` and run the `--locked` or `--frozen` sync offline with `UV_MALWARE_CHECK=0`. Else it SHALL sync online with `UV_HTTP_RETRIES=5` and `UV_MALWARE_CHECK=1`.

#### Scenario: No seed
- **WHEN** the bootstrap runs with no seed volume
- **THEN** it runs the online sync with `UV_HTTP_RETRIES=5` and `UV_MALWARE_CHECK=1`, and writes nothing into the uv cache

#### Scenario: A seed that fits
- **WHEN** the seed holds a cache entry and a `seed.json` that fits the uv, the Python and the `uv.lock` of the checkout
- **THEN** the cache entry is in `UV_CACHE_DIR`, and the last command is the offline sync with `UV_MALWARE_CHECK=0`: `--locked` on a new branch, `--frozen` on an existing branch

#### Scenario: A seed of another lock or another uv
- **WHEN** `seed.json` names another lock hash or another uv version
- **THEN** the bootstrap runs the online sync and copies nothing

### Requirement: The agent and the checks of a Job find the tools of the checkout first
The shell of the agent of a step, the `pre-commit` runs, the scoped checks, the exit checks of a step other than the base replay, the project programs of the implement Job and the tier-1 commands of fix-checks SHALL get a PATH that starts with `<checkout>/node_modules/.bin` and `<checkout>/.venv/bin`, then the PATH of the Job process. The Job process and each child that gets a token SHALL keep the PATH of the image.

#### Scenario: The checks of the implement Job
- **WHEN** the implement Job runs the `pre-commit` stage, the `pre-push` stage and the static scoped check
- **THEN** the PATH of each child starts with `node_modules/.bin` and `.venv/bin` of the worktree

#### Scenario: The shell of the agent
- **WHEN** a step builds the shell of its agent for a checkout
- **THEN** the PATH of the shell starts with `node_modules/.bin` and `.venv/bin` of that checkout

### Requirement: The base replay of a step runs the pytest of the checkout
The base replay of a behavior group SHALL run the pytest of `<checkout>/.venv/bin/python` by its absolute path. The replay names its interpreter and does not read PATH, the image venv holds no pytest, and the replay runs in the folder of the base tree.

#### Scenario: The base replay of a behavior group
- **WHEN** a step replays the test files of a behavior group on its base commit
- **THEN** the replay starts `<checkout>/.venv/bin/python -m pytest`

#### Scenario: A step in the current folder
- **WHEN** a person runs a step with no `--source`, so the checkout is `.`
- **THEN** the replay starts the absolute path of `.venv/bin/python` of the current folder

### Requirement: The runner image holds the scanners of a review
The runner image SHALL hold Gitleaks, Pluto, osv-scanner, golangci-lint and Semgrep from the devtools image, at the versions of the installed tools. Each of the five SHALL be an entry of `RUNNER_TOOLS` with the source `ToolSource.DEVTOOLS` and SHALL NOT be an entry of `NOT_IN_RUNNER`. Each binary of the analyzer table of the review SHALL be an entry of `RUNNER_TOOLS`.

#### Scenario: Each added scanner in the table
- **WHEN** the runner tool table is read after the change
- **THEN** Gitleaks, Pluto, osv-scanner, golangci-lint and Semgrep are entries of `RUNNER_TOOLS`, and none of the five is an entry of `NOT_IN_RUNNER`

#### Scenario: Each analyzer binary in the table
- **WHEN** the runner tool table is read after the change
- **THEN** each binary of `STATIC_ANALYZERS` is an entry of `RUNNER_TOOLS`

### Requirement: The implement job runs on three phases
`devops roadmap implement --confirm` SHALL take `--phase prepare|agent|publish|all` and `--work <folder>` (#3702). `prepare` and `publish` SHALL hold the App token and run no code of the pull request; `agent` SHALL hold the model key only. `all`, the default, SHALL run the three phases in one process. Each phase SHALL first make the process unreadable to its children.

#### Scenario: All runs the phases in order
- **WHEN** the runner Job runs `roadmap implement --item 1 --confirm`
- **THEN** `prepare`, then `agent`, then `publish` run in one process, and the item reaches the draft

#### Scenario: The phases in separate calls
- **WHEN** `prepare`, `agent` and `publish` run in three calls on one run folder
- **THEN** the item reaches the draft as it does with `all`

#### Scenario: The agent phase with a GitHub token
- **WHEN** `--phase agent` starts in an environment that holds `GH_TOKEN`
- **THEN** the command refuses before it reads the inputs

### Requirement: A network git call of the implement job runs in a folder that no agent wrote
Each git call of the implement job that reaches `origin` SHALL run in a folder that no agent wrote: the new clone of `prepare` in the run folder, before the agent phase, or the new repository of `publish`. Until #3700 only these calls SHALL set `CONST_GIT_ISOLATED_CONFIG_ENV` and get the helper of `gh` from `-c` values. `publish` SHALL end every leftover process first, and give its calls a home folder of the run. No call with the token SHALL touch the clone of the agent phase.

#### Scenario: Programs that the home folder of the Job names
- **WHEN** a turn of the agent writes into the git configuration of the home folder a hook folder with a `pre-commit`, `post-commit`, `pre-push` and `reference-transaction` hook and a credential helper, each of which writes the `GH_TOKEN` that it sees, and the job runs a Planned item to its pull request
- **THEN** the branch of the item is on `origin`, and no program wrote the session's token

#### Scenario: A credential helper in the clone
- **WHEN** a turn of the agent adds a credential helper and a `pre-push` hook to the configuration of its clone
- **THEN** `publish` pushes from its own repository, and neither program runs

### Requirement: The Job builder sets each container of the phases
When the pod template holds the init containers `prepare` and `agent` and the container `publish`, `build_job` SHALL give each container the args with its own `--phase` and `--work /run/roadmap`, and the same environment. Only `agent` SHALL get the resources of the unit. A template with one container SHALL keep the args, the environment and the resources on its container.

#### Scenario: A template on the phases
- **WHEN** `build_job` builds a runner Job with a `TRACEPARENT` and a memory limit of `4Gi` from a template on the phases
- **THEN** each container runs the args with its `--phase`, all three get the same `TRACEPARENT`, and only `agent` gets the limit `4Gi`

#### Scenario: The template with one container
- **WHEN** `build_job` builds the same Job from the template with the container `runner`
- **THEN** `runner` gets the args with no `--phase`, the `TRACEPARENT` and the limit `4Gi`

### Requirement: The Service reads each runner container by name
`log_tail` SHALL read the container that the reader names, else the container that runs, else the container that ended the pod, and SHALL read a pod with one container whatever the name. `pod_end` SHALL read the init containers first and SHALL give the first container that failed, else the last one that ended. The fix-checks row SHALL read the result line from `publish`, then from `prepare`.

#### Scenario: The deadline reads the agent
- **WHEN** `prepare` ended, `agent` runs and its log changed
- **THEN** the Service extends the deadline from the log of `agent`

#### Scenario: An OOM kill of the agent
- **WHEN** `agent` ended with exit status 137 and the reason `OOMKilled`, and `publish` waits
- **THEN** the report of the Job records the failure class `oom`

### Requirement: run-job follows each container of the phases in turn
For a Job on the phases, `devops k8s run-job` SHALL follow `prepare`, `agent` and `publish` in turn, SHALL read the exit code of each by its name, and SHALL end with the first exit code that is not 0.

#### Scenario: The agent fails
- **WHEN** `prepare` exits with 0 and `agent` exits with 137
- **THEN** run-job follows `prepare` and `agent`, follows no more containers, and exits with 137

#### Scenario: A dry run of the runner template
- **WHEN** run-job prints the dry run of the runner template, which reads no CronJob
- **THEN** it lists the reads of one container under the condition that the CronJob holds one container, and the reads of each phase container under the condition that the CronJob holds the init containers `prepare` and `agent`
