# roadmap-implement-runner Specification

## Purpose
The pod in which the implement job runs its steps, and what the cluster gives it: the runner image and its publication, the suspended CronJob that Jobs come from, the Role with which the Service creates one Job, and the network rules of the Service and of the Job. The runner is the sandbox of the job, because the shell of a step is no security boundary.

## Requirements

### Requirement: The runner stage holds the tools of a step
The `runner` stage of `Dockerfile` SHALL build from `runner-deps`, which builds from `deps`, installs the dev requirements of the `lock` stage, installs `git`, `curl` and `jq` with apt, and copies promtool from `runner-tools`, which installs it with `devops install-tools`. The image SHALL put the pinned OpenSpec, gh and Node on `PATH`, run as user 1000, and set `ENTRYPOINT ["devops"]`. `runner` SHALL come before `service`, which SHALL hold none of the added tools.

#### Scenario: The stage is read offline
- **WHEN** a test reads the stages of `Dockerfile`
- **THEN** the `runner` stage names `runner-deps` as its base, `runner-deps` names `deps` and installs `/lock/dev.txt` and `git`, and `runner` puts `/opt/devops-tools/bin` and `/app/.venv/bin` on `PATH`, sets `USER 1000:1000` and `ENTRYPOINT ["devops"]`, and stands before the `service` stage, which is the last stage of the file

#### Scenario: The base images stay pinned
- **WHEN** a test reads every `FROM` and `COPY --from` of `Dockerfile`
- **THEN** each image carries a digest, the `runner` stage included

#### Scenario: The added tools are the tools of the table
- **WHEN** a test reads the `runner-deps` and `runner-tools` stages
- **THEN** the apt packages of `runner-deps` are the apt tools of `RUNNER_TOOLS` and `ca-certificates`, `runner-tools` runs `devops install-tools --tool <name>` for each tool of the lock in the table except OpenSpec, and neither `service` nor `service-deps` runs `devops install-tools`

### Requirement: The runner stage names its interpreter
The `runner` stage SHALL set `UV_PYTHON` to the interpreter of its base image, and the shell of a step SHALL get that variable. The builder stage forbids a Python download, and the `.python-version` of a checkout can name a patch release that the pinned base image lacks, so `uv run` would find no interpreter.

#### Scenario: uv finds an interpreter
- **WHEN** a test reads the `runner` stage, and CI runs `uv run --locked ruff --version` in a copy of the checkout on a read-only root
- **THEN** the stage sets `UV_PYTHON=/usr/local/bin/python3` and the command succeeds

### Requirement: The runner stage deletes what only the build needs
The runner image SHALL hold no npm, no pip and no uv cache of root, because a Job installs no tool and the scan of the image fails on the findings in them. `runner-deps` SHALL delete pip, no stage under `runner` SHALL copy npm, and each uv install SHALL keep its cache in a cache mount.

#### Scenario: The stage is read offline
- **WHEN** a test reads the `runner`, `runner-deps` and `deps` stages
- **THEN** none of them names `node_modules/npm`, a `RUN` of `runner-deps` deletes the pip files of site-packages, and every `uv pip` of them mounts `type=cache,target=/root/.cache/uv`

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
Each `language: system` hook of `.pre-commit-config.yaml` SHALL start with `uv run`, and the tool that it runs SHALL be a dev dependency of the lock (`ast-grep-cli`, `devops`) or a program that the `runner` stage of the `Dockerfile` installs (`openspec`). The `pre-commit` package SHALL be a dev dependency of the lock. The hook environments SHALL be fetched at run time into the home volume, because the perimeter admits public HTTPS.

#### Scenario: A hook that needs another program
- **WHEN** a local hook has the entry `actionlint`
- **THEN** the test fails and names the hook and the program

#### Scenario: The config as it is
- **WHEN** the test reads `.pre-commit-config.yaml`, `pyproject.toml` and `Dockerfile`
- **THEN** every local hook passes

### Requirement: The runner image holds each tool that the gate and the hooks need
`RUNNER_TOOLS` in `devops_cli.roadmap.runner_tools` SHALL list each program that the runner image must hold, its source, why it is there, and the command that proves it runs. `NOT_IN_RUNNER` SHALL name each program that the image leaves out, with the reason.

#### Scenario: A source of the gate needs a program that is in neither table
- **WHEN** a program of a `devops ci` row, of a hook of `.pre-commit-config.yaml`, of a required job of `ci.yml`, of a live-marked test, or of `tools.lock` is in neither `RUNNER_TOOLS` nor `NOT_IN_RUNNER`
- **THEN** a test fails and names the program

#### Scenario: A pin drifts from the Dockerfile
- **WHEN** the version of uv, gh, Node or Python in the table differs from the Dockerfile
- **THEN** a test fails

### Requirement: The build of the runner image fails on a missing tool or a wrong pin
The last step of the `runner` stage SHALL run `python -m devops_cli.roadmap.runner_tools` as user 1000. The check SHALL fail when a version command exits non-zero, when its output lacks the pin, or when a tool of the lock is not linked at its locked version. The pin SHALL come from `uv.lock`, `tools.lock` or the Dockerfile, by the source of the tool.

#### Scenario: A tool is missing or at another version
- **WHEN** a version command exits non-zero, prints no pin, or a tool of the lock is not linked at its locked version
- **THEN** the check names the tool and exits 1

#### Scenario: Every tool passes
- **WHEN** every version command prints its pin
- **THEN** the check prints the number of tools and exits 0

### Requirement: The smoke test of the runner image uses the table and bounds the image size
The smoke test of the runner image in `ci.yml` and in `release.yml` SHALL be the same text, SHALL run `python -m devops_cli.roadmap.runner_tools` on the loaded image, and SHALL fail when the image is larger than 3000000000 bytes. It SHALL hold no version command of its own for a tool of the table.

#### Scenario: The smoke test is read offline
- **WHEN** a test reads the smoke test of both workflows
- **THEN** the two texts are equal, they run the check module and the size bound, and no line runs `--entrypoint <tool> "$IMAGE" --version`

### Requirement: The runner image passes the image scan
The runner image SHALL pass the scan of `ci.yml` and `release.yml` (Trivy, `HIGH,CRITICAL`, fixed findings only) with no `.trivyignore` entry. A tool whose newest release fails the scan SHALL be in `NOT_IN_RUNNER`, with the finding as the reason.

#### Scenario: A tool fails the scan
- **WHEN** the newest release of `actionlint` (Go 1.27.0) and of Trivy (go-jose 4.1.5) hold a fixed HIGH finding
- **THEN** the table `NOT_IN_RUNNER` names `actionlint`, `shellcheck` and `trivy` with the image scan as the reason, and the `runner` stage installs none of them

#### Scenario: The image is scanned
- **WHEN** `trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1` runs on the built `runner` target
- **THEN** it exits 0

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

### Requirement: A network git call of the implement job reads no file that the agent can write
The implement job SHALL run each git call that reaches `origin`, also the calls of `add_worktree`, through `OriginGit`: in a new bare git folder whose `objects` folder links the object folder of the clone, with `CONST_GIT_TOKEN_CALL_CONFIG`, `CONST_GIT_ISOLATED_CONFIG_ENV`, an empty home folder, and the URL of `origin` that the job read before its first item. It SHALL end every leftover process before it makes the folder and again just before the call.

#### Scenario: The options and the environment of the call
- **WHEN** the job fetches a branch
- **THEN** the fetch gets `-c credential.helper=`, `-c credential.https://github.com.helper=`, `-c 'credential.https://github.com.helper=!gh auth git-credential'` and `-c core.hooksPath=/dev/null`, `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1`, and a `HOME` that is gone after the call

#### Scenario: A push sends a commit
- **WHEN** the job pushes the commit `<sha>` to its branch
- **THEN** the push gets `--no-verify` and the refspec `<sha>:refs/heads/<branch>`, runs outside the clone, and the remote-tracking ref of the branch in the clone is `<sha>` after it

#### Scenario: Programs that the home folder of the Job names
- **WHEN** a turn of the agent writes into the git configuration of the home folder a hook folder with a `pre-commit`, `post-commit`, `pre-push` and `reference-transaction` hook and a credential helper, each of which writes the `GH_TOKEN` that it sees, and the job runs a Planned item to its pull request
- **THEN** the branch of the item is on `origin`, the `pre-commit` hook ran with no token, and no program wrote the session's token

#### Scenario: A server that asks for credentials
- **WHEN** a credential helper is in the home folder and in the configuration of the clone, an `http.proxy` with `http.sslVerify=false` is in both, and the job pushes to a loopback server that answers 401 with a Basic challenge
- **THEN** no helper runs, no request reaches the proxy, the server receives no `Authorization` header, and the push fails

#### Scenario: A pre-push hook of the clone
- **WHEN** the configuration of the clone sets `core.hooksPath` to a folder with a `pre-push` hook, and the job pushes to a bare repository on disk
- **THEN** the branch is on the bare repository, and the hook did not run

### Requirement: The leftover processes end before each part of a network git call
`OriginGit` SHALL end every leftover process before the check of the settings, again before it makes the new folder, and again just before the call with the token. A refused setting SHALL stop the call after the first sweep and before the folder exists.

#### Scenario: The order of the calls
- **WHEN** the job fetches a branch
- **THEN** the leftover processes end before the check of the settings, again after the check and before the new folder is made, again after the refs are copied, and only then the fetch with the token runs

#### Scenario: A refused setting before the call
- **WHEN** the configuration of the clone holds `credential.helper`, and the job fetches a branch in a runner
- **THEN** the leftover processes end before the check, the call raises `GitSettingsError` that names `credential.helper`, and no new folder is made

### Requirement: The new git folder of a shallow clone gets its shallow file
The new git folder of a network call SHALL get a copy of the `shallow` file of a shallow clone, which the job SHALL open with `O_NOFOLLOW`. A link, or anything but a regular file, at that place SHALL raise `GitSettingsError` that names `shallow`. A fetch that changes the file SHALL write it back into the clone through a new file with a random name, which then replaces the old file (`os.replace`), so the write follows no link.

#### Scenario: A fetch in a shallow clone
- **WHEN** the clone was made with `--depth 1`, `origin` gets a new commit on `main`, and the job fetches `main`
- **THEN** the remote-tracking ref of `main` in the clone is the new commit, and the clone stays shallow

#### Scenario: A link at the shallow file
- **WHEN** the `shallow` file of the clone is a link, and the job fetches `main`
- **THEN** the call raises `GitSettingsError` that names `shallow`

#### Scenario: A link at a temporary name
- **WHEN** a link waits at `shallow.devops-cli` in the git folder of the clone, and a fetch changes the `shallow` file
- **THEN** the target of the link does not change, `shallow` is a regular file with the new text, and no temporary file stays

### Requirement: A git setting that the job does not allow stops the item
In a runner, the implement job SHALL check the git settings of the checkout when each turn of the agent ends and before each network git call (`check_settings`). A setting that the job does not allow SHALL stop the item with the failure class `git_config` and push nothing. The reason and the log line SHALL name each key, or each attribute with its path, and SHALL hold no value.

#### Scenario: What the job does not allow
- **WHEN** the checkout holds a key of the scope `local` or `worktree` outside `CONST_GIT_ALLOWED_SETTINGS` and its patterns, an attribute `filter` with a value, an attribute `diff` that is no built-in pattern of git, an attribute `merge` other than `text`, `binary` and `union`, or the file `objects/info/alternates` of the clone
- **THEN** `refused_settings` names it

#### Scenario: A filter
- **WHEN** a turn of the agent writes `filter.x.clean` into the configuration of the clone and `* filter=x` into `.gitattributes`
- **THEN** the item stops with the class `git_config`, the job runs no `git add`, `git commit`, `git push` or `git fetch` after the turn, and the comment names `filter.x.clean` and the attribute `filter` of `.gitattributes`, and holds no value of either

#### Scenario: A GPG program
- **WHEN** a turn of the agent writes `gpg.program` and `commit.gpgsign` into the configuration of the clone
- **THEN** the item stops with the class `git_config`, and the comment names `gpg.program` and holds no value

#### Scenario: A credential helper
- **WHEN** a turn of the agent adds `credential.helper` to the configuration of the clone
- **THEN** the item stops with the class `git_config`, and the comment names `credential.helper` and holds no value

#### Scenario: The settings of a new clone
- **WHEN** the job runs an item in a clone that `git clone` made, with the identity that `ensure_checkout` sets
- **THEN** the check refuses no key

### Requirement: A refused setting at a push stops the item at once
A refused setting at the push of a `wip:` commit or of a checkpoint SHALL stop the item with the class `git_config` at once, before the job writes a record of the push. A refused setting at the push of a stop SHALL give the stop the class `git_config`.

#### Scenario: A setting before the push of a `wip:` commit
- **WHEN** the agent writes `credential.helper` into the configuration of the clone, ticks a task of a group of five, and the job pushes the `wip:` commit before the next model request
- **THEN** the item stops with the class `git_config`, and the job asks the model for nothing more

#### Scenario: A setting that an exit check writes
- **WHEN** an exit check of the step writes `credential.helper` into the configuration of the clone and fails, and no repair round is left
- **THEN** the item stops with the class `git_config`, and the comment names `credential.helper` and holds no value
