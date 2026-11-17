# Proposal: #6065

## Why
ADR 0018 requires that the planner run Job reaches no network. `networkpolicy-planner-run.yaml` selects `devops-cli-planner-run` with no egress rule. But `devops-default-perimeter` in `k8s/devops/networkpolicy.yaml` selected every pod in namespace `devops` except `crawl4ai`, `searxng`, and `renovate`. Because Kubernetes NetworkPolicies add their rules together, the planner run pod received the egress rules of `devops-default-perimeter` (DNS, the gateway, Valkey, Qdrant, OpenTelemetry, and public HTTPS). Closes #6065.

## What Changes
- Add `devops-cli-planner-run` to the `NotIn` exception list of `devops-default-perimeter` in `k8s/devops/networkpolicy.yaml`.
- Update the comments in `k8s/devops/networkpolicy.yaml` and `k8s/devops/roadmap-service/networkpolicy-planner-run.yaml`.
- Update `k8s/README.md` tree description.
- Update `tests/config/test_k8s_devops_runtime.py` to assert the updated `NotIn` values.
- Update `tests/gate/k8s_checks/job_admission_policy.py` to check that the planner NetworkPolicy is the single policy selecting the planner pod.

## Capabilities
- `k8s-network-policies`: modified requirements for planner run egress denial.

## Impact
The planner run pod reaches no network, DNS included. Other workloads are not affected.

## Feasibility
Verified that `devops-default-perimeter` previously matched the planner run pod, and that excluding it ensures `networkpolicy-planner-run.yaml` is the only selecting policy.

## Existing Tool Considered
Kubernetes NetworkPolicy `podSelector.matchExpressions` `NotIn` operator is the native Kubernetes mechanism.
