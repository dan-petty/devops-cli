# Tasks

## 1. Per-Job instance id in `stage_job_env` (behavior)

- [x] 1.1 Write failing tests for `stage_job_env` setting `OTEL_RESOURCE_ATTRIBUTES=service.instance.id=<name>` as plain `value` without `valueFrom`, distinct across two built stage Jobs, and submitted Jobs carrying it.
  - Verification: `$ uv run pytest -n 0 tests/k8s/test_k8s_cluster_job.py tests/roadmap/stage/test_roadmap_stage_submit.py -k "instance_id or created_job"`
- [x] 1.2 Implement `OTEL_RESOURCE_ATTRIBUTES` in `stage_job_env` (`src/devops_cli/k8s/cluster_job.py`) and verify admission policy check passes.
  - Verification: `$ uv run pytest -n 0 tests/k8s/test_k8s_cluster_job.py tests/roadmap/stage/test_roadmap_stage_submit.py && uv run devops ci --check --only k8s`

## 2. Stage alert rules and dashboard query coverage (behavior)

- [x] 2.1 Add failing multi-instance promtool cases for `RoadmapStageGitHubRequestsHigh` (`tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`) and `devops-cli.json` (`tests/fixtures/dashboard_queries/devops-cli.yaml`).
  - Verification: `$ uv run pytest -n 0 tests/prometheus/test_k8s_monitoring_alerting.py tests/prometheus/test_dashboard_queries.py`
- [x] 2.2 Update `RoadmapStageGitHubRequestsHigh` in `k8s/devops/monitoring/prometheus-rules-values.yaml` to group by `instance` (`sum by (instance)`) and update the comment in `k8s/devops/cronjob-stage.yaml`.
  - Verification: `$ uv run pytest -n 0 tests/prometheus/test_k8s_monitoring_alerting.py tests/prometheus/test_dashboard_queries.py`

## 3. Settings rationale and documentation (behavior)

- [x] 3.1 Write failing test asserting `RoadmapStageConfig.model_fields["jobs"].description` and `stage_submit.__doc__` reference per-Job `service.instance.id` and omit `"one model tier"`.
  - Verification: `$ uv run pytest -n 0 tests/roadmap/stage/test_roadmap_stage_submit.py`
- [x] 3.2 Update `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/stage/stage_submit.py`, `tests/roadmap/stage/test_roadmap_stage_submit.py`, and `docs/CLUSTER.md`, regenerate `docs/ENV_VARS.md` with `devops docs generate`, and verify all checks.
  - Verification: `$ uv run devops ci docs && ! git grep -n "one model tier" src/ docs/ tests/`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
