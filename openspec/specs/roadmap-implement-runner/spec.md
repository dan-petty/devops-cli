# roadmap-implement-runner Specification

## Purpose
The pod in which the implement job runs its steps, and what the cluster gives it: the runner image and its publication, the suspended CronJob that Jobs come from, the Role with which the Service creates one Job, and the network rules of the Service and of the Job. The runner is the sandbox of the job, because the shell of a step is no security boundary.

## Requirements

### Requirement: The runner stage holds the tools of a step
The `runner` stage of `Dockerfile` SHALL be built from the `builder` stage and SHALL run `uv sync --locked`, so that the dev dependencies of `uv.lock` are in the venv. It SHALL install `git`, SHALL put the pinned OpenSpec, gh and the Node runtime of the builder stage on the stage's `PATH`, SHALL run as user 1000, and SHALL set `ENTRYPOINT ["devops"]`. It SHALL come before the `service` stage, so that a build with no `--target` builds the Service image.

#### Scenario: The stage is read offline
- **WHEN** a test reads the stages of `Dockerfile`
- **THEN** the `runner` stage names `builder` as its base, runs `uv sync --locked` with no `--no-dev`, installs `git`, puts `/opt/devops-tools/bin` and `/app/.venv/bin` on `PATH`, sets `USER 1000:1000` and `ENTRYPOINT ["devops"]`, and stands before the `service` stage, which is the last stage of the file

#### Scenario: The base images stay pinned
- **WHEN** a test reads every `FROM` and `COPY --from` of `Dockerfile`
- **THEN** each image carries a digest, the `runner` stage included

### Requirement: The runner stage names its interpreter
The `runner` stage SHALL set `UV_PYTHON` to the interpreter of its base image, and the shell of a step SHALL get that variable. The builder stage forbids a Python download, and the `.python-version` of a checkout can name a patch release that the pinned base image lacks, so `uv run` would find no interpreter.

#### Scenario: uv finds an interpreter
- **WHEN** a test reads the `runner` stage, and CI runs `uv run --locked ruff --version` in a copy of the checkout on a read-only root
- **THEN** the stage sets `UV_PYTHON=/usr/local/bin/python3` and the command succeeds

### Requirement: The runner stage deletes what only the build needs
The `runner` stage SHALL delete npm, pip and the uv cache of root, because a Job installs no tool and the scan of the image fails on the findings in them.

#### Scenario: The stage is read offline
- **WHEN** a test reads the `runner` stage
- **THEN** one `RUN` deletes `/usr/local/lib/node_modules/npm`, `/usr/local/bin/npm`, `/root/.cache/uv` and the pip files of site-packages

### Requirement: The release publishes the runner image
`release.yml` SHALL have a job that builds the `runner` target of `Dockerfile`, runs a smoke test, scans the image with Trivy for HIGH and CRITICAL findings, pushes it by digest as `ghcr.io/<repository>/runner`, attests its provenance, and tags the attested digest with the release tag and `latest`. `ci.yml` SHALL build, smoke-test and scan the same target on a pull request, push nothing, and run only when image content changed.

#### Scenario: The release workflow is read
- **WHEN** a test reads `.github/workflows/release.yml`
- **THEN** a job runs only when the release is created, builds with `target: runner`, scans with the Trivy version of the Service image job, pushes with `push-by-digest=true`, attests `ghcr.io/${{ github.repository }}/runner`, and tags it with the release tag and `latest`

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
The container of CronJob `devops-cli-runner` SHALL set `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER` to `true`, take Secret `devops-cli` through `envFrom`, mount ConfigMap `devops-cli-config`, and mount an `emptyDir` of 4 Gi as its home and an `emptyDir` of 1 Gi as `/tmp`. The other CronJob SHALL not set that variable. The `ephemeral-storage` limit SHALL cover both volumes.

#### Scenario: The variable
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** both volumes have a `sizeLimit`, only the runner container sets `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER`, and the pod of `roadmap-service` does not

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
ServiceAccount `roadmap-service` SHALL be the account of the Service pod. A Role in namespace `devops` SHALL allow `create`, `get` and `list` on `jobs`, `get` on `cronjobs` named `devops-cli-runner`, `list` on `pods` and `get` on `pods/log`, and nothing else. A RoleBinding SHALL bind the Role to the account and to no other subject. The Service pod SHALL mount a projected service-account token with `expirationSeconds` 3600. The pods of Jobs SHALL keep no token.

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
- **WHEN** a test reads the rendered NetworkPolicy `devops-default-perimeter`
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
The policy SHALL refuse a Job unless each `envFrom` names only Secret `devops-cli`, no `env` entry has `valueFrom`, the volumes are only `tmp` and `home` (`emptyDir`) and `config` (ConfigMap `devops-cli-config`), and the pod sets no `hostNetwork`, `hostPID` or `hostIPC`.

#### Scenario: A Job with another source or volume
- **WHEN** the Job from the template changes in one way: a ConfigMap or another Secret in `envFrom`, an `env` with `valueFrom`, a `hostPath` volume, a Secret volume, a ConfigMap volume of another name, `hostNetwork`, `hostPID` or `hostIPC`
- **THEN** the policy refuses the Job and names the rule

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
The policy SHALL refuse a Job unless it sets `backoffLimit: 0` and an `activeDeadlineSeconds` that is at most the value of CronJob `devops-cli-runner`. A Job that the Job builder makes from that CronJob SHALL pass the policy.

#### Scenario: A Job from the runner template
- **WHEN** a test builds the Job from the rendered CronJob `devops-cli-runner` with `build_job`, the environment value and the labels of the Service, and evaluates the policy for the Service user
- **THEN** the policy admits the Job, also when the image carries a tag, a digest, or both

#### Scenario: A Job that runs too long or retries
- **WHEN** the Job from the template sets a `backoffLimit` above 0, an `activeDeadlineSeconds` one above the template's, or no `activeDeadlineSeconds`
- **THEN** the policy refuses the Job

### Requirement: The runner Job bounds the workers of the test runner to its CPU limit
The container of CronJob `devops-cli-runner` SHALL set `PYTEST_XDIST_AUTO_NUM_WORKERS` to the number of its CPU limit. `pytest-xdist` counts the CPUs of the node, not the CPU limit of the pod, so without the variable a test run starts one worker for each CPU of the node.

#### Scenario: The variable
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** the variable of the runner container equals its CPU limit

### Requirement: The local hooks run only programs that the runner image holds
Each `language: system` hook of `.pre-commit-config.yaml` SHALL start with `uv run`, and the tool that it runs SHALL be a dev dependency of the lock (`ast-grep-cli`, `devops`) or a program that the `runner` stage of the `Dockerfile` installs (`openspec`). The `pre-commit` package SHALL be a dev dependency of the lock. The hook environments SHALL be fetched at run time into the home volume, because the perimeter admits public HTTPS.

#### Scenario: A hook that needs another program
- **WHEN** a local hook has the entry `actionlint`
- **THEN** the test fails and names the hook and the program

#### Scenario: The config as it is
- **WHEN** the test reads `.pre-commit-config.yaml`, `pyproject.toml` and `Dockerfile`
- **THEN** every local hook passes
