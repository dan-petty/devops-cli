# Proposal

## Why

The Service continues a runner Job that ended with no result. It skips the continuation for the class `oom`, because a second run on the same memory limit ends the same way. The Service finds `oom` only from the log of the Job. A kernel kill of the runner process can leave no text in the log, so the class becomes `ci_infra` and the Service makes two more Jobs with the same limit (#3727).

## What Changes

- `ClusterJobs.exit_status` reads the terminated exit status of the container of the Job's pod, from `state` and then `lastState`.
- The report of an ended Job passes that status to `classify_failure` through `FailureEvidence.exit_status`, so exit status 137 gives the class `oom`.
- A stall still passes 143 and keeps the class `timeout`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/stops`: The report of an ended Job reads the pod status before it classifies the failure.

## Impact

- Code: `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/roadmap/implement/implement_submit.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_submit.py`

## Feasibility

- `ClusterJobs.log_tail` already lists the pod of the Job, and the Kubernetes client gives the container status.
- `classify_failure` already maps exit status 137 to `oom` and 143 to `timeout`.
- Verification commands: `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py tests/k8s/test_k8s_cluster_job_api.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The Kubernetes API through the `kubernetes` client gives the container status, and the Service already holds a client and lists pods. No new library.
