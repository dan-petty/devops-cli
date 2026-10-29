# Proposal

## Why

Issue #2667, the third sub-issue of #2661. The implement job of #2665 runs tests, ruff, mypy and OpenSpec. The Service image holds none of the dev tools. The Service pod has 1 CPU, a read-only root and no Kubernetes token, and it cannot create a Job. So nothing runs the job today: `devops roadmap implement --confirm` refuses unless the setting `roadmap.implement.in_runner` is true, and no pod sets it.

The step's shell checks only the first word of a command, so it is no security boundary. The pod of the runner Job is the boundary, and this change makes it real: a read-only root, no Kubernetes token, egress to DNS, the gateway, OTLP and public HTTPS only, a GitHub token for one repository, and a job process that its own agent shell cannot read.

## What Changes

- A `runner` stage in `Dockerfile`, before `service`, from the `builder` stage: `uv sync --locked` adds the dev dependencies to the venv, and `apt-get` adds git. The builder already holds uv, gh, the Node runtime and the OpenSpec of `src/devops_cli/tools_lock/openspec`. The stage runs as user 1000 with `ENTRYPOINT ["devops"]`. It sits before `service`, so a build with no `--target` still builds the Service image.
- `release.yml` gets the job `runner-image`. It builds, smoke-tests, scans, pushes by digest, attests and tags `ghcr.io/dan-petty/devops-cli/runner`, as `service-image` does for the Service image. `ci.yml` gets the same job as a check that pushes nothing and runs only when the image content changed.
- CronJob `devops-cli-runner` in `k8s/devops/`: suspended, the `runner` image, 2 CPU and 4 Gi, `activeDeadlineSeconds` 7200, an `emptyDir` home of 4 Gi, the `securityContext` of `devops-cli`, Secret `devops-cli`, the ConfigMap and `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER=true`. It uses the ServiceAccount `devops-cli`, which holds no token and no Role.
- `devops k8s run-job --template runner -- roadmap implement --item N --confirm` creates a Job from that CronJob. `--template` takes `default` (CronJob `devops-cli`) or `runner`.
- The Service row `implement` on the model lane. A round lists the implement Jobs of the repository. A Job that ended gets reported on its item: the state in `implement.job_state` and the tail of the Job's log in a comment. When a Job still runs, the round ends. Else the round plans the items that the filter names and creates one Job for the first of them, with the item's arguments, and records `implement.job`. The Service never runs a step.
- The Service gets its own ServiceAccount `roadmap-service`, a Role and a RoleBinding. The Role allows `create`, `get` and `list` on `jobs`, `get` on `cronjobs` named `devops-cli-runner`, and `list` on `pods` and `get` on `pods/log`, all in namespace `devops`. The pod mounts a projected token with a one-hour expiry. The Job pods keep no token.
- A NetworkPolicy `roadmap-service-egress` admits the Service pod to the API server on 6443 through an `ipBlock` that excludes the cloud metadata address, as `k8s/argo-workflows/` does. The Job pods keep the policy `devops-default-perimeter`: DNS, the gateway on 4000, the cache, the OTLP collector and public HTTPS.
- ImageUpdater `devops` also keeps the `runner` image on its `latest` digest.
- The setting `service.github_app.token_repository` (variable `DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY`). When it holds `owner/name`, the installation token request names only `name` in `repositories`. The Service sets it on each Job it creates.
- The job in a runner makes its process non-dumpable (`prctl(PR_SET_DUMPABLE, 0)`) before it reads a repository. A process of the same user cannot then read `/proc/<pid>/environ` or the memory of the job, where the App key and the other secrets of the Job are.
- `k8s/README.md` ("Roadmap service" and "devops-cli in the cluster"), `docs/ROUTINE_TASKS.md`, `RELEASE_CYCLE.md`, `CONTEXT.md` and the generated documents describe the runner and the Job.
- A consumer observes the manifests, the image, the command option, the setting and the row, so the change carries spec deltas: a new capability `roadmap-implement-runner`, added requirements in `roadmap-implement-job` and `github-app-identity`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-implement-runner`: the runner image, its publication, the Job template, the Role of the Service, and the network rules of the Service and of the Job.

### Modified Capabilities

- `roadmap-implement-job`: added requirements for the Service row and for the non-dumpable process.
- `github-app-identity`: one added requirement for the token of one repository.

## Impact

- `Dockerfile`, `.github/workflows/release.yml`, `.github/workflows/ci.yml`, `RELEASE_CYCLE.md`.
- `k8s/devops/` (CronJob, ServiceAccount, Role, RoleBinding, NetworkPolicy, Deployment), `k8s/argocd/image-updater-values.yaml`, `k8s/README.md`.
- `src/devops_cli/k8s/cluster_job.py`, `src/devops_cli/commands/k8s/cluster_jobs.py`, `src/devops_cli/roadmap/implement_submit.py` (new), `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/github/app_installation.py`, `src/devops_cli/config/settings.py`, `constants.py`, `defaults.py`, `src/devops_cli/core/process_hardening.py` (new), `src/devops_cli/lang/en/`.
- `tests/`: the image invariants, the manifests, the Job builder, the row, the token request and the hardening.
- `docs/ROUTINE_TASKS.md`, `CONTEXT.md`, and the documents that `devops docs generate --sync-readme` writes.

## Feasibility

Each point below was checked on 2026-10-29 against the real system.

1. The Kubernetes API client. `pyproject.toml` pins `kubernetes==36.0.3`, and `k8s/api.py` already wraps it: `KubernetesClientSource.connect` falls back to the pod's service account when the kubeconfig names no context. Read in the installed package, `InClusterConfigLoader` reads `KUBERNETES_SERVICE_HOST` and `KUBERNETES_SERVICE_PORT`, the token file and the CA file, and its `refresh_api_key_hook` reads the token file again once a minute. So a projected token that the kubelet rotates after one hour works in a long-lived pod. `CustomObjectsApi` builds `/apis/<group>/<version>/namespaces/<ns>/<plural>` for any group, so `batch/v1` `jobs` and `cronjobs` need no new API object, no new Protocol and no new fake: the existing seam (`KubernetesApis`) and `FakeCustomObjects` cover them, and they return the dicts that `build_job` already reads. The pod log comes from `CoreV1Api.read_namespaced_pod_log`, which the seam has.
2. Node and OpenSpec. The `builder` stage already copies `node` and `npm` from the digest-pinned `node` image and runs `devops install-tools --tool openspec` (`npm ci` from the lockfile, sha512 checked), as the Service stage does since #2659. The runner stage inherits both, so it adds no Node step. Measured with `docker build --target runner` on this host: the image runs `openspec 1.14.3`, `gh 2.102.1`, `git 2.47.3`, `uv 0.13.6`, `ruff 0.16.8`, `mypy 2.3.1`, `pytest 9.1.1` and `node v24.22.2` as user 1000. The image has 2.23 GB on disk, against 1.01 GB for the Service image built on the same host. The extra 1.2 GB are the dev dependencies and the builder layers that the stage inherits. A node pulls it once, because the pull policy is `IfNotPresent`. In a read-only root with a 4 GiB home volume, the first `uv run --locked ruff --version` in a copy of the project took 12.7 s in total and used 1.1 GB of the volume, so the clone and the worktree venv fit.
3. The build time. The runner stage adds one `apt-get` layer and one `uv sync` to the builder stage. `docker build --target runner` took 2 min 8 s on this host with a warm cache of the shared stages. `ci.yml` builds it in its own job, which runs in parallel with the others, only when `Dockerfile`, `src`, `pyproject.toml`, `uv.lock` or another image content path changed (the rule of the `service-image` job), and the GitHub Actions cache gives the shared stages. The two jobs share the `builder` stage, so neither one builds it twice. `release.yml` builds it only when a release is created.
4. Image Updater and the Image Pins check. `k8s/argocd/image-updater-values.yaml` lists one image, `service`, with `forceUpdate: true` because no pod of the Application's tree runs it. The same holds for CronJob `devops-cli-runner`, which is suspended and outside the tree for its Jobs. So the ImageUpdater gets a second entry, alias `runner`. `k8s/image_pins.py` skips each image that an `ImageUpdater` object names (`managed`), and refuses an image with no digest and the tag `latest` or none otherwise. So the manifest names `ghcr.io/dan-petty/devops-cli/runner` untagged and the ImageUpdater names `...runner:latest`, and the check passes without a registry read. Read in the source of `image_pins.py`, tested by the manifest tests below.
5. The permissions of the Role. The issue lists `create`, `get` and `list` on `jobs` and `get` on `pods/log`. Two more are needed, and the issue's premise fails on them as written. The Service builds the Job from CronJob `devops-cli-runner`, so it must read that CronJob: `get` on `cronjobs`, limited to that name with `resourceNames`. A pod's log is read by the pod's name, and the Job controller gives the pod a random name, so the Service must find the pod: `list` on `pods`. Both are read-only. The Kubernetes RBAC documentation says that `resourceNames` limits `get`, and does not limit `list` or `create`, so `list` on `pods` covers every pod of namespace `devops`. The pods of that namespace hold no secret value: Secret `devops-cli` comes in through `envFrom`, and a pod object names the Secret, not its content.
6. The sandbox. Verified here, with the files, with the pydantic-ai source that #2665 recorded, and with the commands below. The shell of the agent gets `PATH`, `HOME`, `LANG`, `LC_ALL` and `LC_CTYPE` and a scratch `HOME` (`pydantic_ai/workspaces/local.py`, #2665). It gets no variable of the job. A process of the same user can read `/proc/<pid>/environ` of its parent: a Python 3.14 script run as user 1000 on this host read it. The same script printed `PermissionError: [Errno 13]` for `/proc/<pid>/environ` after `prctl(PR_SET_DUMPABLE, 0)` on the parent. That call needs no capability and no seccomp exception (`RuntimeDefault` allows `prctl`). So the manifest alone does not keep the App key from a step, and the process hardening does. Python's standard library has no `prctl`; `ctypes` calls it, and `python-prctl` is unmaintained, so the project does not take it.

What is guaranteed and what is not is in `design.md`.

## Existing Tool Considered

- The cluster Job template and `devops k8s run-job` (the engine in place today): reused, with one option added.
- The Kubernetes API through `kubernetes==36.0.3` and the existing `KubernetesApis` seam: reused with no new API object.
- Argo CD and Image Updater for the rollout: reused, one entry added.
- GitHub's `repositories` body parameter of the installation token request: used, through the existing `_exchange`.
- Argo Workflows (ADR 0008) is the engine after a measured go, which #1535 did not record. The Job moves with the other jobs when it does. Rejected for now.
- The published devcontainer image as the runner is rejected: it is built from `debian:sid` and fills its venv at post-create, so a Job would sync at every start. GitHub-hosted runners are rejected on #2661.
- `python-prctl` is rejected because the project is unmaintained; `ctypes` from the standard library calls `prctl`.

The change builds the runner stage and its publication, the CronJob, the RBAC and the policy, the row, and a 20-line hardening function. Written cost, estimated: about 900 lines of code, configuration and tests; about 400k tokens of agent work to build, keep and fix it; about one day of elapsed time. Upkeep is small: the row follows the Job API, which is stable, and the runner stage follows the builder stage.

The change deletes no code.
