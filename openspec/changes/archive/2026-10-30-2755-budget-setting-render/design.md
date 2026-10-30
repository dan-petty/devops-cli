# Design

## Decisions

- **Render only a value that a source set.** `render_active_devops_configmap` passes `github_requests_per_hour` when `"github_requests_per_hour"` is in `settings.service.model_fields_set`, and `None` otherwise. A config file, a variable and code all put the key in that set, so the owner's `devops config set` reaches the ConfigMap. With no value set, the ConfigMap holds none and the Service uses its default. The ConfigMap does not copy a default into the cluster, so a later change of the default reaches the Service.
- **One parameter, like its neighbours.** `_service_block` and `render_devops_configmap_content` get `github_requests_per_hour: int | None`, as they hold `drain_timeout_seconds` and `poll_interval_seconds`. No new abstraction.
- **Declare the field like its neighbours.** `Annotated[int, Variable()]` and `Field(description=...)`. The variable name follows the rule of the spec `config-commands` (`DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR`). The documents come from the declaration, so `devops docs generate --sync-readme` writes them.
- **Alert from the reported limit.** The rule is `sum(<window count>) > on() 0.9 * max(devops_cli_service_budget_limit_requests{job="roadmap-service"})`. The window count stays as #2505 made it. `max` picks the one series of the running pod. `on()` joins the sum and the limit, which carry different `instance` labels. The comparison keeps the left value, so the summary still gives the request count.
- **No fallback to 500 in the rule.** `or vector(500)` would put the default into the rule again, and it would be wrong after the owner changes the budget. While the Service reports no limit, it is down, and `RoadmapServiceUnavailable` and `RoadmapServiceLaneStalled` cover that case.
- **The description names no number.** An annotation cannot read the right side of a comparison. The text says "90% of its hourly budget" and the runbook row says where the limit shows.

## Rejected alternatives

- **Raise the literal to 1800.** The owner can change the budget again, and the rule would be wrong again. A rule that follows the reported limit stays right.
- **Template the rule from `settings`.** The values file is static YAML that Argo CD applies. A render step would need a second source of the budget. The Service already reports it.
- **Render the value always, with the default.** The ConfigMap would copy a code default into the cluster. A later change of the default would not reach the Service. Evidence: `ServiceConfig.drain_timeout_seconds` does so today, and the Service then ignores its own default.
- **Match with `ignoring(instance, pod, ...)`.** The label sets of the two series share no key except `job` and `cluster`. A list of labels to ignore breaks when a label is added. `on()` names the empty join and cannot break that way.
- **Fix #2505 here.** It is closed, and the rule already counts the first value of a series.
