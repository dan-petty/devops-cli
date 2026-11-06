# Tasks

## 1. The size table and the memory limit setting

Kind: behavior

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_implement_size.py` for the scenarios of "The Service sizes the runner Job from the plan" (the count and the rows), "The worker count of a runner Job equals its CPU limit", "The size table cites its measurements" and "The memory limit is a setting that holds the largest request"
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_size.py`
- [x] 1.2 Write `src/devops_cli/roadmap/implement_size.py`, the setting `roadmap.implement.max_memory_limit` with its default, and the entry in `tests/security/test_config_declarations.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_size.py tests/security/test_config_declarations.py tests/roadmap/test_roadmap_limit_classes.py`

## 2. The resources in the Job builder

Kind: behavior

- [x] 2.1 Write failing tests in `tests/k8s/test_k8s_cluster_job_api.py` for a Job made with `resources`, and for a Job made with none
  - Verification: `uv run devops ci test tests/k8s/test_k8s_cluster_job_api.py`
- [x] 2.2 Add `resources` to `build_job` and `ClusterJobs.create`
  - Verification: `uv run devops ci test tests/k8s/test_k8s_cluster_job_api.py`

## 3. The size in the round

Kind: behavior

- [x] 3.1 Write failing tests in `tests/roadmap/test_roadmap_implement_submit.py` for the scenarios of a small and a large plan, a Planned item, the storage of the template and the raised memory limit
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_submit.py`
- [x] 3.2 Add `tasks_at` to `src/devops_cli/roadmap/plan_read.py`, and size the Job in `run_implement_round` of `src/devops_cli/roadmap/implement_submit.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_submit.py tests/roadmap/test_roadmap_implement_deadline.py`

## 4. The admission policy

Kind: manifests

- [x] 4.1 Update the checks in `tests/gate/k8s_checks/job_admission_policy.py` for the Job of each row, the grid of sizes, the worker count and the Job with the size of the template, then add the rule to `k8s/devops/roadmap-service/admissionpolicy.yaml`
  - Verification: `uv run devops ci --check --no-cache --only k8s`

## 5. The documents

Kind: documents

- [x] 5.1 Update the runner sections of `k8s/README.md` and `docs/ROUTINE_TASKS.md`, and regenerate the generated documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`
- [x] 5.2 Archive the change
  - Verification: `uv run devops openspec archive 3193-size-the-runner-job-resources`

## Workflow follow-up

- Pending a person: let Argo CD sync the policy `roadmap-service-jobs` with the new Service image. A Service that still runs the old image creates a Job with the size of the template, which the new rule refuses, and the round tries again when the new image runs.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
