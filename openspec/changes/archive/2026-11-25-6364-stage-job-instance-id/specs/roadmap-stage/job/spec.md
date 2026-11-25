# roadmap-stage/job Specification Delta (#6364)

## ADDED Requirements

### Requirement: Each stage Job carries a distinct plain instance id
`stage_job_env` SHALL set `OTEL_RESOURCE_ATTRIBUTES` to `service.instance.id=<name>` as a plain value without `valueFrom`, so two stage Jobs receive distinct instance ids and pass `roadmap-service-jobs`.

#### Scenario: Two stage Jobs receive distinct plain instance ids
- **WHEN** `build_job` renders two stage Jobs with different names through `stage_job_env`
- **THEN** their `OTEL_RESOURCE_ATTRIBUTES` entries carry different `service.instance.id` values with plain `value` fields and no `valueFrom`

#### Scenario: Admission policy admits plain instance ids and rejects fieldRef
- **WHEN** `uv run devops ci --check --only k8s` validates the stage Job policy
- **THEN** built stage Jobs pass and an env entry using `valueFrom.fieldRef` is refused

### Requirement: Stage dashboards and alerts aggregate concurrent stage pods
Stage queries in `k8s/devops/dashboards/devops-cli.json` SHALL aggregate away `instance` so concurrent stage pods combine into one `roadmap-stage` series, and `RoadmapStageGitHubRequestsHigh` SHALL sum by `instance`.

#### Scenario: Concurrent stage pods show one line in dashboards and alerts evaluate cleanly
- **WHEN** `uv run devops ci --check --only k8s` and `uv run devops ci test tests/prometheus/test_dashboard_queries.py tests/prometheus/test_k8s_monitoring_alerting.py` run on the dashboard and alert fixtures
- **THEN** concurrent `roadmap-stage` instances sum into one `job="roadmap-stage"` dashboard series and promtool passes

### Requirement: Stage Job count rationale drops one model tier
The `DEFAULT_ROADMAP_STAGE_JOBS` comment, `RoadmapStageConfig.jobs` description, `stage_submit.py` docstring, and `docs/CLUSTER.md` SHALL cite the per-Job `service.instance.id` and owner-decision prerequisites (`#6319`, `#4563`), and MUST NOT contain `one model tier`.

#### Scenario: Settings description and stage_submit docstring reflect current reason
- **WHEN** a test reads `RoadmapStageConfig.model_fields["jobs"].description` and `stage_submit.__doc__`
- **THEN** both reference per-Job `service.instance.id` and neither contains `one model tier`

## MODIFIED Requirements

### Requirement: The rules read the series of the stage Jobs
Each rule of the roadmap Service that reads model requests, GitHub writes, GitHub throttles, web searches, or tool calls SHALL select `job=~"roadmap-service|roadmap-stage"`. `RoadmapServiceGitHubRequestsHigh` SHALL read the Service alone, and `RoadmapStageGitHubRequestsHigh` SHALL compare each stage Job `instance` against one stage Job budget.

#### Scenario: A rule reads the series of a stage Job
- **WHEN** the Service sends 300 GitHub requests and a stage Job 300 in an hour, with a Service budget of 500 and a stage budget of 1000
- **THEN** neither request alert fires

#### Scenario: A stage Job near its own budget
- **WHEN** a stage Job sends 960 GitHub requests in an hour with a budget of 1000
- **THEN** `RoadmapStageGitHubRequestsHigh` fires

#### Scenario: Two concurrent stage Jobs below each Job budget
- **WHEN** two stage Job instances each send 600 GitHub requests in an hour with a stage budget of 1000
- **THEN** `RoadmapStageGitHubRequestsHigh` does not fire
