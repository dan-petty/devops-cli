# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests for runner Job labels, repository annotations, runner Job naming, and dry run output
  - Verification: `$ uv run pytest tests/k8s/test_k8s_cluster_job.py tests/commands/k8s/test_k8s_run_job.py`
- [x] 1.2 Implement repository labels, repository annotations, and runner Job helpers in `src/devops_cli/k8s/cluster_job.py`
  - Verification: `$ uv run pytest tests/k8s/test_k8s_cluster_job.py`
- [x] 1.3 Update `src/devops_cli/commands/k8s/cluster_jobs.py` for runner Job naming and dry run labels
  - Verification: `$ uv run pytest tests/commands/k8s/test_k8s_run_job.py`
- [x] 1.4 Update `src/devops_cli/k8s/cluster_job_api.py` and `src/devops_cli/roadmap/implement/implement_submit.py`
  - Verification: `$ uv run pytest tests/roadmap/implement/test_roadmap_implement_submit.py`
- [x] 1.5 Update telemetry service name in `k8s/devops/cronjob-runner.yaml` and dashboard descriptions
  - Verification: `$ uv run pytest tests/gate/k8s_checks/telemetry_resource.py tests/prometheus/test_k8s_monitoring_dashboards.py`

## 2. Documents

- [x] 2.1 Validate OpenSpec change and run CI quality checks
  - Verification: `$ uv run openspec validate 4558-label-service-jobs-by-repository-and-item && uv run devops ci`
