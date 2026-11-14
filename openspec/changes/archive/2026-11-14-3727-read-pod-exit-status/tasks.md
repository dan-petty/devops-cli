# Tasks

## 1. Read the pod exit status

Reads: `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/roadmap/implement/implement_submit.py`. Changes: the same files and `tests/roadmap/implement/test_roadmap_implement_submit.py`.

- [x] 1.1 Add `ClusterJobs.exit_status(name)` that reads the first pod of the Job label and the terminated exit status of its container, from `state` and then `lastState`.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_cluster_job_api.py` passes
- [x] 1.2 Pass the status through `_report` and `_failure_of` to `FailureEvidence.exit_status`, and keep 143 for a stall.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py` passes
- [x] 1.3 Add the tests: exit 137 with an empty log stops the item as `oom`, `lastState` 137 gives `oom`, and a pod with no terminated state keeps the class of the log.
  - Verification: the same test command passes
