## ADDED Requirements

### Requirement: A rows fact names only the workloads of the project namespaces
The loader SHALL refuse a `rows` fact whose query names `namespace` or `pod` in a `by` or `on` clause and holds no positive namespace matcher, `namespace="…"` or `namespace=~"…"`. A refusal SHALL raise `RoadmapReviewError` with a message that names the fact, the field `query` and the label. A `scalar` fact SHALL NOT be refused for its grouping, because its answer has no label.

#### Scenario: A grouping by namespace with no matcher is refused
- **WHEN** a fixture catalog holds the `rows` fact `prometheus.valkey_pods` with the query `max by (namespace, pod) (redis_memory_max_bytes == 0)`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.valkey_pods`, the field `query` and the label `namespace`

#### Scenario: A join on pod with no matcher is refused
- **WHEN** a fixture catalog holds the `rows` fact `prometheus.requests` with the query `sum by (resource) (kube_pod_container_resource_requests * on (pod) group_left() kube_pod_status_ready)`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.requests` and the label `pod`

#### Scenario: A negative namespace matcher does not scope a fact
- **WHEN** a fixture catalog holds the `rows` fact `prometheus.valkey_pods` with the query `max by (namespace, pod) (redis_memory_max_bytes{namespace!="kube-system"} == 0)`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.valkey_pods`

#### Scenario: A grouping in the project namespaces loads
- **WHEN** a fixture catalog holds the `rows` fact `prometheus.valkey_pods` with the query `max by (namespace, pod) (redis_memory_max_bytes{namespace=~"{namespaces}"} == 0)`
- **THEN** the loader gives the catalog with that fact

#### Scenario: A scalar fact by namespace loads
- **WHEN** a fixture catalog holds the `scalar` fact `prometheus.pods` with the query `count(count by (namespace, pod) (kube_pod_info))`
- **THEN** the loader gives the catalog with that fact

#### Scenario: The shipped catalog scopes its workload rows
- **WHEN** the loader reads the shipped `catalog.yaml`, and each query is filled with the window placeholders and the namespace `devops`
- **THEN** the loader raises no error, each `rows` fact whose query names `namespace` or `pod` in a `by` or `on` clause holds a positive namespace matcher after the fill, and no filled query holds `{namespaces}`

### Requirement: The project namespaces are a setting
The setting `roadmap.project_review.namespaces` SHALL list the project namespaces whose workloads the review can name. The settings load SHALL refuse an empty list, and each name that is not an RFC 1123 label. The review and its dry run SHALL fill `{namespaces}` from this setting.

#### Scenario: An empty list is refused
- **WHEN** the settings of the project review are loaded with `namespaces` set to an empty list
- **THEN** the load raises a validation error at `namespaces`

#### Scenario: A name that is not an RFC 1123 label is refused
- **WHEN** the settings of the project review are loaded with `namespaces` set to `["devops|.*"]`, `["Devops"]` or `["-devops"]`
- **THEN** the load raises a validation error at `namespaces`

#### Scenario: A dry run prints the project namespaces and sends no request
- **WHEN** a person runs `devops roadmap review run --last 7d --repo example/project --dry-run` with `roadmap.project_review.namespaces` set to `devops` and `llm`, with fakes that record each request and each process
- **THEN** the output holds `namespace=~"devops|llm"`, the output holds no `{namespaces}`, and each fake records 0 calls

## MODIFIED Requirements

### Requirement: The catalog refuses unknown references and placeholders
The loader SHALL refuse a section that the catalog does not list, two facts with one id, a disagreement that names an unknown fact, and a placeholder other than `{start}`, `{end}`, `{range}`, `{base}`, `{head}`, `{repo}`, `{name_slug}` and `{namespaces}`. A refusal SHALL raise `RoadmapReviewError` with a message that names the fact.

#### Scenario: A section that the catalog does not list is refused
- **WHEN** the fact `prometheus.example` names the section `unknown`, and `sections` does not list it
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.example` and `unknown`

#### Scenario: An unknown placeholder is refused
- **WHEN** the query of the fact `github.example` holds `{owner}`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `github.example` and the field `query`

### Requirement: The dispatcher fills the placeholders of the window
Before it sends a query, the dispatcher SHALL replace `{start}` and `{end}` with the UTC times of the window in the form `YYYY-MM-DDTHH:MM:SSZ`, `{range}` with the length of the window in whole seconds and the unit `s`, `{base}` and `{head}` with the two commits, `{repo}` with the repository as `owner/name`, `{name_slug}` with the slug of the repository name that the Job names of the Service hold (`RepoRef.name_slug`), and `{namespaces}` with the names of `roadmap.project_review.namespaces` joined with `|`. It SHALL keep every other brace of the query.

#### Scenario: The placeholders of a PromQL query
- **WHEN** the window is the 7 days to `2026-11-11T14:51:23Z` of `example/project`, and a fact query is `sum(increase(devops_cli_service_jobs_total{repo="{repo}"}[{range}]))`
- **THEN** the sent query is `sum(increase(devops_cli_service_jobs_total{repo="example/project"}[604800s]))`

#### Scenario: The name slug of a Job name
- **WHEN** the repository is `Example/My.Project`, and a fact query is `kube_job_status_start_time{job_name=~"devops-cli-implement-{name_slug}-.+"}`
- **THEN** the sent query is `kube_job_status_start_time{job_name=~"devops-cli-implement-my-project-.+"}`

#### Scenario: The project namespaces of a workload query
- **WHEN** `roadmap.project_review.namespaces` is `devops` and `llm`, and the query of a `rows` fact is `max by (namespace, pod) (redis_memory_max_bytes{namespace=~"{namespaces}"} == 0)`
- **THEN** the dispatcher sends `max by (namespace, pod) (redis_memory_max_bytes{namespace=~"devops|llm"} == 0)` to the fixture Prometheus
