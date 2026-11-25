# Proposal: #6364

## Why
Every stage pod inherits `OTEL_RESOURCE_ATTRIBUTES=service.instance.id=roadmap-stage` from `k8s/devops/cronjob-stage.yaml` (#6364). Running more than one stage Job at once writes concurrent samples into one OTLP series, causing counter resets and preventing `roadmap.stage.jobs` from scaling past `1`. In addition, the `DEFAULT_ROADMAP_STAGE_JOBS` comment (`defaults.py`), `RoadmapStageConfig.jobs` description (`settings.py`), `stage_submit.py` docstring, and `docs/CLUSTER.md` still cite `"one model tier"`, which no longer applies.

## What Changes
- **Code**: `src/devops_cli/k8s/cluster_job.py` (`stage_job_env`) sets `OTEL_RESOURCE_ATTRIBUTES` to `service.instance.id=<name>` as a plain environment value (no `valueFrom`), overriding CronJob `roadmap-stage` per created Job.
- **Configuration & Docstrings**: `src/devops_cli/config/defaults.py` (`DEFAULT_ROADMAP_STAGE_JOBS`), `src/devops_cli/config/settings.py` (`RoadmapStageConfig.jobs`), `src/devops_cli/roadmap/stage/stage_submit.py`, `docs/CLUSTER.md`, and `docs/ENV_VARS.md` replace `"one model tier"` with the per-Job `service.instance.id` reason and the 2026-11-19 owner-decision prerequisites (`#6319`, `#4563`, and per-Job instance id).
- **Observability**: `k8s/devops/monitoring/prometheus-rules-values.yaml` updates `RoadmapStageGitHubRequestsHigh` to sum by `instance` (`sum by (instance) (...) > on() group_left() ...`) so concurrent stage Jobs compare individually against one Job budget; `k8s/devops/cronjob-stage.yaml` updates its comment; Prometheus alert and dashboard fixture suites cover multi-instance stage series in `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` and `tests/fixtures/dashboard_queries/devops-cli.yaml`.

This change is observable in Job specs, configuration help text, and Prometheus rules, and fits cleanly in one pull request.

## Capabilities
- Modified: `roadmap-stage/job`

## Impact
- Stage Job manifests created by the Service carry distinct plain `service.instance.id` values without requiring any change to ValidatingAdmissionPolicy `roadmap-service-jobs`.
- `RoadmapStageGitHubRequestsHigh` no longer false-fires when concurrent stage Jobs each stay within 90% of `roadmap.stage.github_requests_per_hour`.
- Configuration reference (`docs/ENV_VARS.md`) and cluster documentation (`docs/CLUSTER.md`) reflect current prerequisites.

## Feasibility
Confirmed against the live codebase:
- `stage_job_env` (`src/devops_cli/k8s/cluster_job.py:167-178`) returns plain env vars and `_with_env` (`cluster_job.py:194-200`) replaces existing template env entries by name.
- `k8s/devops/roadmap-service/admissionpolicy.yaml:206-210` already permits plain `OTEL_RESOURCE_ATTRIBUTES` on stage Jobs while refusing `valueFrom.fieldRef`.
- Note on alerts path: `k8s/devops/alerts/` contains only `inbox.yaml` (`RoadmapPersonCauseInflowHigh` on `roadmap-service`); the live stage alert rules reside in `k8s/devops/monitoring/prometheus-rules-values.yaml:182-198`, whose comment explicitly notes `A limit over 1 needs an instance for each Job before this sum compares with one budget`. `k8s/devops/dashboards/devops-cli.json` panel queries (`sum by (job)` / `sum(...)`) already aggregate across `instance`.
- `defaults.py:1055-1057`, `settings.py:1507-1511`, `stage_submit.py:39-43`, `docs/CLUSTER.md:99,104`, and `docs/ENV_VARS.md:290` all contain the outdated `"one model tier"` / shared instance text.

## Existing Tool Considered
No external maintained tool can mint deterministic per-Job `OTEL_RESOURCE_ATTRIBUTES` values inside `stage_job_env`, update project PromQL alerting rules, or revise internal Pydantic field descriptions and cluster docs; OpenTelemetry Collector/Operator was evaluated in `#6364` and only pipelines telemetry after emission. Building this change directly costs ~15,000 output tokens (~2 hours elapsed) and ~1 hour/quarter maintenance; it deletes the obsolete `"one model tier"` wording from defaults, settings, docstrings, and cluster documentation.
