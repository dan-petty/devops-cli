# Proposal: #6615

## Why

The fact catalog of the project review (`src/devops_cli/roadmap/project_review/catalog.yaml`) has seven `rows` facts that group or join by `namespace` or `pod` over all namespaces of the shared cluster: `prometheus.requests_over_allocatable`, `prometheus.working_set_over_limit`, `prometheus.cpu_throttling`, `prometheus.restarting_containers`, `prometheus.valkey_memory`, `prometheus.valkey_no_maxmemory` and `prometheus.database_memory`. The dispatcher keeps each label of a series, so the `data.json` of the review of one repository can hold the namespace and pod names of the workloads of other projects (#6615). On 2026-11-21, a 7-day read-only review gave 15 rows for `prometheus.database_memory`, and one row named the namespace and the database pod of another project. #4733 publishes the review data, so these names would go into a published report.

The header rule of the catalog says only "A query gives no host name: no grouping by node or instance". The loader rule `unscoped_service_metric` covers only the Service metrics. No rule stops a new fact that leaks workload names.

## What Changes

- Add the setting `roadmap.project_review.namespaces`: the project namespaces whose workloads the review can name. Its default is the namespaces that the manifests of this repository define. The settings load refuses an empty list and each name that is not an RFC 1123 label. Thus a value never means "all namespaces", and a name cannot change the regular expression of the matcher.
- Add the placeholder `{namespaces}` to the catalog. The dispatcher and the dry run replace it with the names of the setting, joined with `|`, for the matcher `namespace=~"{namespaces}"`.
- Add the loader rule `unscoped_workload_metric` beside `unscoped_service_metric`. The loader refuses a `rows` fact whose query names `namespace` or `pod` in a `by` or `on` clause and holds no positive namespace matcher (`namespace="…"` or `namespace=~"…"`). The refusal names the fact, the field `query` and the label.
- Add `namespace=~"{namespaces}"` to each selector of the seven facts whose metric has a `namespace` label. Their definitions name the project namespaces. The `base` metrics and the probe do not change.
- Extend the header rule of the catalog: no name of a workload outside the project namespaces.
- `devops roadmap review run --dry-run` prints the queries with the namespaces filled, and still sends 0 requests.
- The command output, its `data.json` and the settings change, so the change modifies the capability `roadmap-project-review`.

## Capabilities

- `roadmap-project-review` (modified): the setting of the project namespaces, the placeholder `{namespaces}`, and the loader rule that refuses an unscoped workload grouping.

## Impact

- `data.json` and the summary of a review hold only the workloads of the project namespaces for the seven facts. `prometheus.requests_over_allocatable` now gives the requests of the project namespaces over the allocatable resources of the Ready nodes, not the requests of all namespaces.
- A catalog fact that a person adds later with a `namespace` or `pod` grouping and no namespace matcher stops the load with `RoadmapReviewError`.
- One new setting with a default: no config file and no ConfigMap must change. `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` are generated again.
- No new dependency.
- The change fits one pull request. #6612 changes other facts of the same file: there is no merge order, and the second pull request rebases on the first.

## Feasibility

- The defect exists on origin/main c6395d856: `catalog.yaml` lines 484 to 694 hold the seven facts with no namespace matcher. `catalog.py` line 226 checks only `devops_cli_service_` metrics, and `catalog.schema.json` refuses only `by (node)` and `by (instance)`.
- Census of the shipped catalog (a probe of the plan run that parses `catalog.yaml` and reads each `by (…)` and `on (…)` clause): 24 `rows` facts. 8 `rows` facts name `namespace` or `pod` in a `by` or `on` clause. 7 of them hold no namespace matcher: the seven facts of the issue. The eighth, `loki.error_lines_top`, holds `namespace=~"devops|llm"`, two project namespaces, so the rule keeps it as it is. 5 `scalar` facts also group by `namespace` or `pod` (`prometheus.no_memory_limit`, `prometheus.no_memory_request`, `prometheus.pending_pods`, `prometheus.runner_memory_p90`, `prometheus.service_pods`). A scalar answer is one number with no label, so it names no workload, and the rule does not apply to it.
- The manifests define 14 namespaces: `git grep -l "kind: Namespace" k8s/` gives `k8s/namespaces.yaml` with `agents`, `argo-workflows`, `argocd`, `cert-manager`, `cloudflared`, `cnpg-system`, `devops`, `gitea`, `llm`, `logging`, `mattermost`, `mattermost-operator`, `monitoring` and `otel`. The `namespace:` of the kustomizations are `cloudflared` and `monitoring`, which the list already holds.
- Prometheus applies a regular-expression matcher to the full label value (anchored RE2), so `namespace=~"devops|llm"` matches only these two names. An RFC 1123 label holds only `a-z`, `0-9` and `-`, so a name of the setting holds no character that a regular expression or a PromQL string reads as special.
- `CONST_K8S_LABEL_RE` (`src/devops_cli/config/constants.py`) already holds the RFC 1123 label pattern.

## Existing Tool Considered

- The alternatives check of 2026-11-21 gives the verdict `none`. cloudflare/pint (Apache-2.0, maintained) lints the `expr` of Prometheus rule files. It is a Go program and does not read the catalog form. A run of pint for each catalog load would add a second runtime to the CLI for one check.
- promql-parser 0.12.0 (PyPI, the Python binding of a Rust PromQL parser) gives a PromQL syntax tree. Its package metadata states no license (PyPI JSON, 2026-11-21), and it cannot parse the LogQL query of `loki.error_lines_top`. So the change does not add it.
- The change builds the rule as one function beside `unscoped_service_metric`, with the same technique: a regular expression over the query text, as the schema already does for `by (node)`. It reuses `CONST_K8S_LABEL_RE` and pydantic for the setting. Cost: about 100,000 model tokens to build, test and keep, and about 3 hours elapsed. The cost to keep is small, because the rule is about 20 lines and the namespaces are one setting.
- The change deletes no internal code.
