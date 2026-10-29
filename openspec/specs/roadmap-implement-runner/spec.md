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
CronJob `devops-cli-runner` in namespace `devops` SHALL be suspended and SHALL never run on a schedule. Its Job template SHALL name the image `ghcr.io/dan-petty/devops-cli/runner` with no tag, request and limit 2 CPU and 4 Gi, request 2 Gi and limit 6 Gi of `ephemeral-storage`, set `activeDeadlineSeconds` to 7200 and `backoffLimit` to 0, and use the `securityContext` of CronJob `devops-cli`. Its pod SHALL use ServiceAccount `devops-cli`, which mounts no token.

#### Scenario: The manifest is read
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** CronJob `devops-cli-runner` holds the values above, its container is named `runner`, its pod mounts no ServiceAccount token, its root filesystem is read-only, and its capabilities drop `ALL`

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
- **THEN** no process starts, and the plan names CronJob `devops-cli-runner` and the token repository

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
