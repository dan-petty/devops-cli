## MODIFIED Requirements

### Requirement: The dispatcher keeps no row of a workload outside the project namespaces
When a Prometheus or Loki `rows` series holds a namespace label outside `roadmap.project_review.namespaces`, or holds no namespace label and any non-`__name__` label outside `_SAFE_ROW_LABELS`, the fact SHALL have status `error` and null value. The reason SHALL name the fact and the first sorted offending label with no label value. Each shipped `rows` fact in `catalog.yaml` SHALL pass, and `dispatch.py`, `catalog.yaml`, and `docs/ROADMAP_WORKFLOW.md` SHALL state this default refusal.

#### Scenario: A row of another namespace
- **WHEN** `roadmap.project_review.namespaces` is `devops`, the query of the `rows` fact `prometheus.valkey_rows` is `sort_desc(sum without (instance) (redis_memory_used_bytes))`, and the fixture Prometheus answers a series with `namespace` `devops` and `pod` `valkey-0` and a series with `namespace` `other-project` and `pod` `database-0`
- **THEN** the fact has the status `error` and a null value, and the reason names `prometheus.valkey_rows` and `namespace`, and holds none of `other-project`, `database-0` and `valkey-0`

#### Scenario: A row with a workload label and no namespace
- **WHEN** the fixture Prometheus answers the same fact with a series with `pod` `database-0` and no `namespace`, or with `container` `database` and no `namespace`
- **THEN** the fact has the status `error`, and the reason names `pod` or `container` and holds no label value

#### Scenario: A row with an unknown label and no namespace
- **WHEN** the fixture Prometheus answers the same fact with a series with `name` `other-app` and no `namespace`
- **THEN** the fact has the status `error`, and the reason names `prometheus.valkey_rows` and `name` and holds no label value

#### Scenario: A row of another namespace in a label of the scrape or of Traefik
- **WHEN** the fixture Prometheus answers the same fact with a series with `namespace` `devops`, `exported_namespace` `other-project` and `exported_pod` `db-0`, or with a series with `service` `other-project-database-5432@kubernetes` and no `namespace`
- **THEN** the fact has the status `error`, and the reason names `exported_namespace` or `service` and holds no label value

#### Scenario: A Loki row of another namespace
- **WHEN** the fixture Loki answers the `rows` fact `loki.lines` with a series with `namespace` `other-project` and `container` `app`
- **THEN** the fact has the status `error`, and the reason names `loki.lines` and holds no `other-project`

#### Scenario: A row with no workload label
- **WHEN** the fixture Prometheus answers the `rows` fact with one series with only the label `resource`, or with only `namespace` `devops` and `pod` `valkey-0`, or with no label
- **THEN** the fact has the status `ok`, and its value is that one row

#### Scenario: A row with safe labels or a project namespace
- **WHEN** the fixture Prometheus answers a `rows` fact with one series holding only labels from `_SAFE_ROW_LABELS` (`resource`, `le`), or holding `namespace` `devops` with `name` `app`, or holding no label
- **THEN** the fact has the status `ok`, and its value is that row

#### Scenario: Shipped catalog rows pass the guard
- **WHEN** a test loads `catalog.yaml` and runs the guard on synthetic rows holding the kept labels of each `shape: rows` fact
- **THEN** every shipped `rows` fact passes the guard
