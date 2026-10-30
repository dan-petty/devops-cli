# Proposal

## Why

Issue #2755. The owner raised the hourly GitHub budget of the roadmap Service from 500 to 2000 on 2026-10-30. The project tools cannot hold that value. Three faults cause this.

1. `_service_block` in `k8s/configmap.py` copies `repos`, `github_app`, `drain_timeout_seconds` and `poll_interval_seconds` into ConfigMap `devops-cli-config`. It does not copy `service.github_requests_per_hour`. Each `devops k8s deploy-stack --stack devops` renders a ConfigMap without the value, and the Service returns to the default of 500.
2. The field `ServiceConfig.github_requests_per_hour` has no `Variable()` marker and no description. No variable names it, and `devops config show`, `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` do not list it.
3. The alert `RoadmapServiceGitHubRequestsHigh` fires above 450 requests in one hour, which is 90% of the default budget. With a budget of 2000 it fires in a normal hour.

## What Changes

- `_service_block` copies `github_requests_per_hour`. `render_active_devops_configmap` passes it when the active settings give it (the key is in `model_fields_set`: a config file, a variable or code set it). With the default, the ConfigMap holds no value, and the Service uses its own default.
- The field gets `Variable()` and a description. The variable is `DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR`. `devops config show`, `devops config env`, `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` list it.
- `RoadmapServiceGitHubRequestsHigh` compares the requests of the hour with 90% of `devops_cli_service_budget_limit_requests`, the limit that the Service reports. The two series carry different `instance` labels, so the rule joins them with `on()`. The rule text, `k8s/README.md` and the promtool tests say so.
- A consumer observes the ConfigMap that a deploy applies and the alert, so the change carries three spec deltas: one MODIFIED requirement in `roadmap-service-alerts` and one ADDED requirement in each of `roadmap-service-deployment` and `roadmap-service-limits`.
- The change fits one pull request.
- The owner sets the value with `devops config set service.github_requests_per_hour 2000`, then runs `devops k8s deploy-stack --stack devops`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-alerts`: MODIFIED `A high request volume warns`. The GitHub alert follows the reported limit.
- `roadmap-service-deployment`: ADDED `A deploy keeps the hourly request budget`.
- `roadmap-service-limits`: ADDED `The hourly budget has a variable and a description`.

## Impact

- `src/devops_cli/k8s/configmap.py`, `src/devops_cli/config/settings.py`, `k8s/monitoring/prometheus-values.yaml`, `k8s/README.md`.
- `tests/test_k8s_configmap.py`, `tests/test_config_declarations.py`, `tests/test_config_field_validation.py`, `tests/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`.
- The documents that `devops docs generate --sync-readme` writes.
- Issue #2505 (the first value of a new series) is closed, and the rule already holds its fix. This change keeps that count and changes only the threshold.

## Feasibility

- The renderer fault is real. On the base, `_service_block` in `src/devops_cli/k8s/configmap.py` has four parameters and no `github_requests_per_hour`. The live ConfigMap holds the value only because of a hand patch.
- The field is settable already. On 2026-10-30, with a scratch config file (`DEVOPS_CLI_CONFIG` set to a file under `.data/agent/scratch/`), `devops config set service.github_requests_per_hour 2000` printed `service.github_requests_per_hour = 2000` and wrote `github_requests_per_hour: 2000` under `service:`. `... 0` was refused with `Input should be greater than 0`. So the owner's command needs no new code. `devops config show` did not list the key, which is fault 2.
- `model_fields_set` shows what the settings give. In a scratch run of `load_settings()`, a config file with `github_requests_per_hour: 2000` gave `['github_requests_per_hour', 'repos']`. A file without it gave `['repos']`, and `DEVOPS_CLI_SERVICE_DRAIN_TIMEOUT_SECONDS=5` added `drain_timeout_seconds`. So a default and a value that a source set are distinct.
- The metric exists. A read-only Prometheus query (Grafana datasource `prometheus`) of `devops_cli_service_budget_limit_requests` on 2026-10-30 gave one series with value 2000 and the labels `job="roadmap-service"`, `namespace="devops"`, `container="service"`, `pod="roadmap-service-<hash>"`, `instance="<pod-ip>:8000"`, `node` and `cluster`. The counter `devops_cli_github_requests_total{job="roadmap-service"}` reaches Prometheus through OTLP and has `instance="roadmap-service"`, plus `repo`, `row`, `resource` and `method`. The `instance` labels differ, so a plain vector match would find no pair. The rule uses `on()` with an empty label list: the sum has no labels, and `max(limit)` has none.
- `Service` code sets the gauge at start (`GLOBAL_METRICS.set_gauge(CONST_SERVICE_METRIC_BUDGET_LIMIT, ...)` in `server/service.py`), so the series stays while a pod runs. While the Service is down the series is stale, the rule gives no result, and `RoadmapServiceUnavailable` covers that case.

## Existing Tool Considered

The existing ConfigMap renderer, the settings declaration (`Variable()` and `Field(description=...)`) and the metric `devops_cli_service_budget_limit_requests` that the Service already exports cover the need. promtool, already pinned, tests the rule. Nothing new is built, and no dependency is added. The change deletes the literal `450` from the rule, from its tests and from the documents.
