# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests of the readers and the builder for both templates
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_cluster_job.py tests/k8s/test_k8s_cluster_job_api.py`
- [x] 1.2 Read each container by name, and build each phase container
  - Verification: `$ uv run devops ci test tests/k8s tests/roadmap/test_roadmap_fix_checks_row.py tests/roadmap/implement/test_roadmap_implement_deadline.py tests/roadmap/implement/test_roadmap_implement_submit.py tests/roadmap/test_roadmap_follow_live.py`
- [x] 1.3 Follow each phase container in run-job
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_run_job.py`

- [x] 1.4 Run a fix-checks phase with no `--confirm` as a plan, and list the phase reads in the dry run
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_step_fix_checks.py tests/commands/k8s/test_k8s_run_job.py`

## 2. Documents

- [x] 2.1 Add the requirements to the `roadmap-implement-runner` and `roadmap-fix-checks` specs
  - Verification: `$ uv run devops openspec check`
