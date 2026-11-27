# k8s-network-policies Specification

## Purpose
The isolation invariants of the NetworkPolicies of the product base `k8s/devops`.

## Requirements

### Requirement: Egress to Qdrant on TCP 6333
The devops perimeter SHALL admit egress from the pods of namespace `devops` to namespace `llm` on TCP 6333 only.

#### Scenario: The policy admits the Qdrant port
- **WHEN** a throwaway pod in namespace `devops` runs `nc -w 3 qdrant.llm.svc.cluster.local 6333` and `nc -w 3 qdrant.llm.svc.cluster.local 6334`, started with `kubectl run --rm -i --restart=Never`
- **THEN** the connect to TCP 6333 succeeds, and the connect to TCP 6334 times out

### Requirement: The planner run Job denies all egress
The stack SHALL hold a NetworkPolicy that selects the pod label `app.kubernetes.io/name: devops-cli-planner-run`, sets `policyTypes: [Egress]` and holds no egress rule. The default perimeter NetworkPolicies `devops-default-perimeter-ingress` and `devops-default-perimeter-egress` SHALL exclude `devops-cli-planner-run` from their pod selectors so that the planner run pod reaches no network.

#### Scenario: The egress rules of the planner run Job pod
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/devops`
- **THEN** the row passes only when the planner policy is the one NetworkPolicy that selects the pod of CronJob `devops-cli-planner-run`, and that policy holds `Egress` and no egress rule

#### Scenario: A pod with the planner label reaches no address
- **WHEN** a throwaway pod with the label `app.kubernetes.io/name: devops-cli-planner-run` in namespace `devops` runs `nc -w 3 <CoreDNS Service address> 53`, started with `kubectl run --rm -i --restart=Never`
- **THEN** the connect times out, so the pod reaches not even DNS

### Requirement: Each product NetworkPolicy has both apply paths
The `k8s` row SHALL refuse a NetworkPolicy of `k8s/devops/` that the build of the root kustomization does not hold, or that no product table of `deploy-stack` applies.

#### Scenario: The root kustomization drops a policy
- **WHEN** `uv run devops ci --check --only k8s` runs on a tree whose `k8s/devops/kustomization.yaml` does not list a file of a NetworkPolicy
- **THEN** it exits non-zero

### Requirement: No product NetworkPolicy has both types
The `k8s` row SHALL refuse each NetworkPolicy of `k8s/devops/` whose types hold `Ingress` and `Egress`. The row SHALL read the types as the API server sets them: `policyTypes` as written; with no `policyTypes`, `Ingress`, and `Egress` when the policy has an egress rule. The problem SHALL name the policy and kube-router, which lets the rules of one type of such a policy skip the rules of the other type for traffic between two pods that the policy selects.

#### Scenario: A policy that writes both types
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on a fixture policy with `policyTypes: [Ingress, Egress]`
- **THEN** the rule reports a problem that names the fixture policy and kube-router

#### Scenario: A policy with no types and an egress rule
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on a fixture policy with no `policyTypes` and an egress rule
- **THEN** the rule reports a problem that names the fixture policy

#### Scenario: Single-type policies
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on a policy with `policyTypes: [Ingress]`, a policy with `policyTypes: [Egress]`, a policy with no `policyTypes` and no egress section, and a policy with no `policyTypes` and an empty egress list
- **THEN** the rule reports no problem

#### Scenario: The product base
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on each NetworkPolicy of `k8s/devops/`
- **THEN** the rule reports no problem

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
