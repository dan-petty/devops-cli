# Proposal

## Why

The planner reads files and runs no command, so a plan can rest on a premise that only a command run shows. ADR 0018 gives the planner a run tool that runs one read-only command in a separate Kubernetes Job (#3242, #4003). The Job needs its template, its NetworkPolicy, its Role row and its admission rules before any code creates it.

## What Changes

- Add `k8s/devops/roadmap-service/cronjob-planner-run.yaml`: a suspended CronJob with the pod of ADR 0018, two 512 Mi `emptyDir` volumes, ConfigMap `devops-cli-config-sandbox`, the claim `roadmap-service-home` read only at `/repo`, no service account token, UID and GID 1000, a read-only root, no capability, 1 CPU and 2 Gi, and a deadline of 120 s.
- Add `k8s/devops/roadmap-service/networkpolicy-planner-run.yaml`: it selects the pod label `app.kubernetes.io/name: devops-cli-planner-run` and admits no egress.
- Add `get` on CronJob `devops-cli-planner-run` to Role `roadmap-service-jobs`, and list the two files in the kustomization and in `deploy-stack`.
- Add the planner shape to ValidatingAdmissionPolicy `roadmap-service-jobs`: the sandbox ConfigMap, the read-only claim, the security context, the deadline, the resources, and no `envFrom` and no `valueFrom`.
- `build_job` gives a Job from `PLANNER_TEMPLATE` the pod label `devops-cli-planner-run`, so the policy and the NetworkPolicy select it.
- Tests render the Job from the template and refuse an extra volume, a writable claim and a Secret in `envFrom`.

## Capabilities

### New Capabilities

- `k8s-planner-run-job`: the template, the NetworkPolicy, the Role row and the admission rules of the planner run Job.

### Modified Capabilities

- `k8s-network-policies`: a policy that admits no egress of the planner run Job pod.

## Impact

- Manifests: two new files in `k8s/devops/roadmap-service/`, and the kustomization, Role and admission policy there.
- Code: `src/devops_cli/k8s/cluster_job.py` adds `PLANNER_TEMPLATE`; `src/devops_cli/commands/k8s/stack_lifecycle.py` lists the two files.
- Tests: `tests/gate/k8s_checks/job_admission_policy.py`, `runner.py` and `telemetry_resource.py`.
- Documents: `docs/CLUSTER.md` and `k8s/README.md`.

## Feasibility

- Read on `origin/main`, 2026-11-14. `k8s/devops/cronjob-runner.yaml` is the template of the runner Job and `k8s/devops/roadmap-service/admissionpolicy.yaml` holds the policy `roadmap-service-jobs`.
- `src/devops_cli/k8s/cluster_job.py:59:RUNNER_TEMPLATE = JobTemplate(cronjob="devops-cli-runner", container="runner")` shows the template type that `build_job` takes.
- `tests/gate/k8s_checks/job_admission_policy.py:113:def _policy_refusals(` runs the CEL expressions against a rendered Job.
- `docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md` records the seven controls.
- `uv run python -m tests.gate.k8s` passes after the change, and so do `tests/k8s` and `tests/gate`.

## Existing Tool Considered

Kubernetes CronJob, NetworkPolicy and ValidatingAdmissionPolicy cover the pod lifecycle, the egress and the shape of the Job, and the cluster runs them. No other open tool adds a kernel boundary: gVisor or the agent-sandbox controller would, and ADR 0018 accepts that risk for now. The change costs about 12,000 tokens to build and 1,000 tokens a quarter to keep.

## Dependencies

#3242 is closed, and ADR 0018 is on the default branch.
