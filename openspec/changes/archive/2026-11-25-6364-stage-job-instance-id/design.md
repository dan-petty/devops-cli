# Design

## Decisions
1. **Derive `service.instance.id` from the stage Job name in `stage_job_env`:**
   `stage_job_env(repo, name, deadline)` (`src/devops_cli/k8s/cluster_job.py:167-178`) already receives `name` (produced by `RepoRef.unit_name` or `RepoRef.adhoc_name`, bounded to 63 chars and unique per item/body). Setting `"OTEL_RESOURCE_ATTRIBUTES": f"service.instance.id={name}"` leverages `_with_env` (`cluster_job.py:194-200`) to replace the template's `OTEL_RESOURCE_ATTRIBUTES` entry with a plain `{name, value}` dictionary entry.
2. **Keep `k8s/devops/cronjob-stage.yaml` default value and update comment:**
   `k8s/devops/cronjob-stage.yaml:123-124` retains `value: service.instance.id=roadmap-stage` for direct template checks (`tests/gate/k8s_checks/stage_job.py:135-146`) and updates lines `118-122` to state that the Service overrides it per Job.
3. **Evaluate `RoadmapStageGitHubRequestsHigh` per `instance`:**
   In `k8s/devops/monitoring/prometheus-rules-values.yaml:186-192`, replace `sum(...)` with `sum by (instance) (...) > on() group_left() (0.9 * max(devops_cli_service_budget_limit_requests{job="roadmap-stage"}))`. Each stage pod holds its own hourly budget (`roadmap.stage.github_requests_per_hour`), so each Job's own requests must compare separately against one Job budget instead of summing concurrent pods. Add fixture coverage in `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` and `tests/fixtures/dashboard_queries/devops-cli.yaml`.
4. **Update `roadmap.stage.jobs` rationale text:**
   Update `DEFAULT_ROADMAP_STAGE_JOBS` (`defaults.py:1055-1057`), `RoadmapStageConfig.jobs` (`settings.py:1507-1511`), `stage_submit.py:39-43`, `test_roadmap_stage_submit.py:332-333`, `docs/CLUSTER.md`, and regenerate `docs/ENV_VARS.md` (`uv run devops docs generate`) so all name the per-Job `service.instance.id` and the 2026-11-19 owner decision prerequisites (`#6319`, `#4563`, and per-Job instance id) with no `"one model tier"`.

## Rejected alternatives
- **Use Downward API `valueFrom.fieldRef` for pod name:** Rejected because ValidatingAdmissionPolicy `roadmap-service-jobs` (`k8s/devops/roadmap-service/admissionpolicy.yaml:175-212`) explicitly refuses `valueFrom.fieldRef` on container env entries.
- **Generate a random UUID in `stage_job_env`:** Rejected because `cluster_job.py:167` already receives the unique Job `name`, which makes `service.instance.id` deterministic across repeated builds and directly traceable to Kubernetes Jobs.
- **Keep cluster-wide `sum(...)` in `RoadmapStageGitHubRequestsHigh`:** Rejected because `src/devops_cli/config/settings.py:1519` defines `roadmap.stage.github_requests_per_hour` per stage Job (`k8s/devops/monitoring/prometheus-rules-values.yaml:184-185`), so summing two concurrent pods at 60% budget would trigger a false positive alert at 120%.
