# Design

## Decisions

### 1. Static CronWorkflow with `devops infra drift --all`
- **Decision**: Define a single CronWorkflow `infra-drift` running `devops infra drift --all`.
- **Reason**: `infra.repos` changes dynamically via ConfigMap. A static step loops over repos and checks access levels at runtime.

### 2. Launch `infra-plan` via webhook router
- **Decision**: The webhook router launches the `infra-plan` Job on `pull_request` `synchronize` deliveries through `job_launcher.launch`.
- **Reason**: ADR 0021 defines the webhook router as the creator of cluster units. `job_launcher` is the established seam.

### 3. Stable marker without head SHA for pull request comment
- **Decision**: Mark the pull request comment with `<!-- devops roadmap infra-plan -->` and update it on subsequent pushes.
- **Reason**: A marker with a commit SHA creates a new comment on every push and clutters the review timeline.

### 4. Read-only Secret volume for SSH key
- **Decision**: Mount Secret `infra-ssh-key` read-only at `/secrets/ssh` with mode 0400.
- **Reason**: Ansible reads private keys from files. Mounting from a Secret keeps keys out of environment variables and arguments.

### 5. NetworkPolicy using node CIDRs
- **Decision**: `infra-ssh-egress` admits egress on TCP 22 to configured node CIDRs (`192.168.1.0/24`) for pods with label `app.kubernetes.io/component: infra`.
- **Reason**: Pods must reach cluster nodes over SSH. Invariants permit CIDR blocks with prefix shorter than 32.

### 6. Add `ansible-runner` to runner tools
- **Decision**: Register `ansible-runner` in `RUNNER_TOOLS` with a `job:` reason.
- **Reason**: The cluster runner image executes Ansible playbooks during scheduled drift and PR plan jobs.

## Rejected alternatives

### 1. Kubernetes CronJob instead of Argo Workflows
- **Rejected**: Duplicates workflow engine scheduling and templates.
- **Evidence**: ADR 0008 and ADR 0021 establish Argo Workflows as the cluster execution standard.

### 2. Separate CronWorkflow step for each repository
- **Rejected**: Requires dynamic manifest rendering when `infra.repos` changes in settings.
- **Evidence**: Argo CD syncs static manifests from Git.

### 3. New comment on every push
- **Rejected**: Clutters pull request history and obscures the latest plan.
- **Evidence**: `steps/comment.py` provides stable upsert functionality for marked comments.

### 4. Broad egress `0.0.0.0/0` on port 22
- **Rejected**: Violates least privilege by permitting SSH egress to arbitrary public and private destinations.
- **Evidence**: SECURITY.md and network policy rules require restricting egress to node subnets.
