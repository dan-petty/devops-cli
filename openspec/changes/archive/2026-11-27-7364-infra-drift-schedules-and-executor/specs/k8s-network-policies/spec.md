## ADDED Requirements

### Requirement: Argo Workflow pods reach the API server on TCP 6443 only
The stack SHALL hold NetworkPolicy `argo-workflow-egress`. It SHALL select each pod with the label key `workflows.argoproj.io/workflow` (operator `Exists`), set `policyTypes: [Egress]`, and hold one egress rule: TCP 6443 to `0.0.0.0/0` with `169.254.169.254/32` excluded.

#### Scenario: The rendered Workflow policy
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/devops`
- **THEN** the row passes only when `argo-workflow-egress` has the selector, the type and the one rule of this requirement

### Requirement: Only the Service pod and the Workflow pods reach the API server
Only `roadmap-service-egress` and `argo-workflow-egress` SHALL hold an egress rule on TCP 6443. The pod templates of the CronJobs `devops-cli`, `devops-cli-runner` and `roadmap-stage` SHALL carry no label `workflows.argoproj.io/workflow`, so no Job pod reaches the API server.

#### Scenario: A third policy with TCP 6443
- **WHEN** `uv run devops ci --check --only k8s` runs on a tree where a NetworkPolicy other than the two holds an egress rule on TCP 6443
- **THEN** it exits non-zero

#### Scenario: A Job pod template with the Workflow label
- **WHEN** `uv run devops ci --check --only k8s` runs on a tree whose CronJob `devops-cli-runner` gives its pod the label `workflows.argoproj.io/workflow`
- **THEN** it exits non-zero
