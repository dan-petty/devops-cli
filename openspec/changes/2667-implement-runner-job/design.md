# Design

## Decisions

- **The runner stage is the builder plus git and the dev dependencies.** The builder holds uv, gh, the Node runtime and the OpenSpec of the lockfile, and the Service stage copies them. The runner needs the same files and the dev tools, so it starts from the builder and adds two layers. It stands before `service`, so `docker build` with no `--target` still gives the Service image, and `service` stays the last stage that the CI job and the release job build.
- **The venv of the image is for `devops` and the tool programs, the worktree has its own.** The job and the step run `uv run ...` in a worktree. `uv` makes a `.venv` in that worktree from the lockfile, with the cache in `UV_CACHE_DIR` on the home volume, because the root is read-only. The packages come from public HTTPS (the egress rule admits it). Measured: 12.7 s for the first `uv run` and 1.1 GB of the 4 GiB volume. `ruff`, `mypy` and `pytest` are also on `PATH` from the image's venv, for a step that calls them directly.
- **The image is built in its own CI job.** It shares the `builder` stage with the Service job through the GitHub Actions cache, runs in parallel with the other jobs, and runs only when image content changed, as the Service job does. The release builds it once per release.
- **The runner CronJob is the Service CronJob with other values.** `devops k8s run-job` builds a Job from a CronJob and changes only the args, the name and the labels (`cluster_job.build_job`). A `JobTemplate` names the CronJob and the container, and the two templates are `default` and `runner`. The Service calls the same builder, so a Job from the Service and a Job from a person are equal.
- **The Service uses the API that the repository has.** `CustomObjectsApi` is the generic client of the `kubernetes` package. It reads `cronjobs`, and creates and lists `jobs`, of group `batch`, and returns dicts, which `build_job` reads. `CoreV1Api` lists the pods and reads their log. The seam `KubernetesApis` and its fake `FakeCustomObjects` are enough: the change adds no Protocol and no API object. The fake learns the equality label selectors that the real API takes.
- **A Role of six rules.** `create`, `get`, `list` on `jobs`; `get` on the one CronJob; `list` on `pods`; `get` on `pods/log`. The RBAC documentation says that `resourceNames` cannot limit `list` and `create`, so those two stay namespace-wide. A holder of the Role can create any pod that Pod Security `restricted` admits in namespace `devops`, and such a pod can take Secret `devops-cli` through `envFrom`. The Service pod already holds that Secret, so the Role gives no secret that the account does not have. It is the cost of letting the Service create a Job; a person who wants less must give the Job creation to another component.
- **Own ServiceAccount, projected token.** ServiceAccount `devops-cli` keeps `automountServiceAccountToken: false` and no Role, and the runner Jobs use it. ServiceAccount `roadmap-service` also sets `automountServiceAccountToken: false`, and the Deployment mounts the token as a projected volume (`serviceAccountToken` with `expirationSeconds: 3600`, the CA bundle `kube-root-ca.crt` and the namespace). The kubelet rotates the token, and the client reads the file again each minute.
- **Egress to the API server is a rule of the Service pod only.** The default perimeter selects every pod of the namespace. A second policy, `roadmap-service-egress`, selects the Service pod and admits TCP 6443 to an `ipBlock` with the metadata address excluded: the `kubernetes` Service resolves to a node address that no namespace selector matches (the reason in `k8s/argo-workflows/networkpolicy.yaml`). The union of the two policies is the Service's egress. The Job pods get no rule for 6443 and keep no token, so two layers deny the API to a step.
- **One Job at a time, from the Jobs themselves.** The round lists the Jobs by a label that holds a digest of the repository name (`owner/name` is no valid label value). A Job without the condition Complete or Failed blocks the round. The Kubernetes API is the lock, so a restart of the Service loses nothing. The record `implement.job` on the item says which Job to report.
- **A Job that ends with the item neither In Review nor stopped is a stop.** A Job that dies (out of memory, deadline, image pull) leaves its item In Progress, or Ready and eligible. Without a rule, the next round would create the same Job again every ten minutes. So the round that reports the Job sets such an item to Ready and records `implement.stopped` as `job`. The comment has the marker of the job, so a person's `implement: retry` after it clears the stop.
- **The token of a Job names one repository.** The Service sets `DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY` on the container of the Job it creates. `_exchange` adds `repositories` to the body when the setting is set. The setting is `owner/name`, as `service.repos` is, and only the name goes to GitHub, whose installation belongs to the owner.
- **The process of the job is not dumpable.** `prctl(PR_SET_DUMPABLE, 0)` makes `/proc/<pid>/environ` and `/proc/<pid>/mem` of the process unreadable for a process of the same user without `CAP_SYS_PTRACE`. The agent's shell is such a process. The job calls it in `apply_implement`, after `require_runner` and before the first read. The call is `ctypes` over `libc`; Linux only, and the runner pod is Linux.

## What is guaranteed and what is not

Guaranteed by a manifest, a test or the kernel:

- The step's shell has none of the variables of the job. It has `PATH`, `HOME` (a scratch directory), `LANG`, `LC_ALL` and `LC_CTYPE`.
- A step cannot read the environment or the memory of the job process. The App key, the gateway key and the token are in the environment and the memory of that process only. Tested with a real child process on Linux.
- The Job pod has no Kubernetes token, and no policy admits it to the API server. It has a read-only root, no Linux capability, `RuntimeDefault` seccomp and no privilege escalation.
- The installation token that the Job mints names one repository and the permissions of #2473, and lasts one hour. The job mints a new one before it expires.
- The Job reaches DNS, the gateway, the cache, the OTLP collector and public HTTPS, and nothing in the private ranges or at the metadata address.
- The Role admits the six rules above, in namespace `devops`.
- The Job ends after 7200 s at most and is not retried.

Not guaranteed:

- Public HTTPS is open. A step that runs `uv run python -c` can send the clone, and anything else it can read, to a public host. The step runs only `git`, `uv`, `ruff` and `mypy` by its shell policy, which is no boundary. The clone holds a public repository's content and the Job holds no other secret in a place a step can read, so the loss is the repository content and the scratch files. A private repository's content would be exposed in the same way.
- A step runs as the same user as the job, so it can write anything on the home volume and the `/tmp` volume, including the files that the job reads later (the clone, `.git/config`, hooks). A hook or a changed `uv.lock` runs when the job runs `git` or `uv` in the worktree. The job's `git` and `uv` children get the session token. So a step can make the job run code that holds the token of the one repository. The token is limited to that repository, to the permissions of #2473 and to one hour, so the harm stays in that repository's issues, pull requests and contents. The branch is the staged branch and a person merges.
- The non-dumpable flag stops `/proc` reads of the same user. It does not stop a kernel flaw, a capability that the pod does not have, or a process that runs as another user.
- Nothing stops the model from writing bad code. Review, the required checks and a person's merge do.

## Rejected alternatives

- **The Service runs the step in its pod.** The image lacks the dev tools, the pod has 1 CPU and a read-only root, and a step of an hour would hold the model lane.
- **A long-lived token in the Service pod.** `automountServiceAccountToken: true` gives a token that never expires, and the pod holds it all its life. The projected token expires in one hour.
- **One ServiceAccount for the Service and the Jobs.** The Job pods would then be bound by the Role if a template ever mounted the token. Two accounts keep the Role off the Job pods by construction. The test checks that no CronJob mounts a token.
- **Kubernetes Jobs through `kubectl` in the Service image.** The Service image has no kubectl, and a subprocess adds a binary to the image and a path to parse. The `kubernetes` package is already a dependency, and the seam already has a fake.
- **A new `BatchV1Api` in the seam.** It needs a Protocol, a field in `KubernetesApis`, a service method and a new fake with a contract suite. `CustomObjectsApi` reaches the same paths and gives the dicts that the builder takes.
- **Argo Workflows as the engine.** ADR 0008 asks for a measured go, and #1535 did not record it. No roadmap job runs on it. The Job moves when the go exists.
- **A host check for `in_runner`.** #2665 rejected it: a guess about the host. The CronJob sets the variable.
- **Mint the token in the Service and pass it to the Job.** The Job would then hold no App key. But a token lasts one hour and a Job lasts up to two, and a Job that cannot renew its token ends in the middle of a push. The Secret `devops-cli` also holds the gateway key, which the Job needs in its environment, so the environment is not free of secrets either way. The hardening protects both.
- **`python-prctl`.** The project is unmaintained. The standard library's `ctypes` makes the one call.
- **A separate Secret for the runner.** It would hold only what the Job needs. It is the better end state, but a person makes secrets (AGENTS.md), and the issue names Secret `devops-cli`. The follow-up is a note in `k8s/README.md`.
- **Seed the uv cache in the image.** A cache on the read-only root cannot take uv's locks, and a copy to the home volume costs more than the download it saves (12.7 s measured).

## Risks

- The runner image does not exist in GHCR until a release publishes it, and a person must make the package public as for the Service image. Until then the CronJob's image cannot be pulled and a Job ends by its deadline after 7200 s. The round that finds it records the stop and comments. This is also true of a Service that runs the new row before the next release: its row finds no Job template if Argo CD has not synced the CronJob, and fails with a message that names it.
- A first release with the new job needs a person to make the `runner` package public and to merge the release pull request.
