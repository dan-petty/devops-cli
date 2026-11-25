# roadmap-project-review Specification

## Purpose
How `devops roadmap review run` resolves a version range or a period to a half-open window of first-parent commits and UTC times, reads the git facts of that window from the local checkout and the facts of its catalog through their readers, and writes them with their sources to `data.json`.

## Requirements

### Requirement: A review window is half-open on first-parent commits and UTC times
`devops roadmap review run` SHALL take one window: `--version A..B`, `--since` with `--until`, `--week` or `--last`. A tag SHALL become its commit and commit time. A time SHALL become an aware UTC value, UTC when it has no offset, and the last first-parent commit of the default branch at or before it. The base commit and the start time SHALL be out of the window, and the head commit and the end time SHALL be in.

#### Scenario: Tags in two time zones compare by the instant
- **WHEN** `v1.1.0` is created at +02:00 and `v1.1.1` at -07:00, and the review resolves the week `2026-W40`
- **THEN** the tags of the week are `v1.1.0` only, by the UTC instant of each tag

#### Scenario: The base tag is out of a version window
- **WHEN** the review resolves `--version v1.0.0..v1.1.1`
- **THEN** the window starts at the commit time of `v1.0.0`, which is out, and its release tags are `v1.1.0` and `v1.1.1`

#### Scenario: A period takes the last first-parent commit at or before each time
- **WHEN** the review resolves `--since 2026-10-03T10:00:00Z --until 2026-10-05T06:30:00Z`
- **THEN** the base and head commits are the commits of `v1.1.0` and `v1.1.1`, and the previous window is `20261001T1330Z..20261003T1000Z`

#### Scenario: Two windows are refused before any read
- **WHEN** a person gives `--version v1.0.0..v1.1.1` and `--last 7d`
- **THEN** the command exits 1 with a message that asks for one window, and it starts no program

### Requirement: The review writes each git fact of the window with its source
The review SHALL write `data.json` and its JSON Schema `data.schema.json`. Each fact SHALL hold an id, a section, a value, a unit, `n`, a source, the exact query, a definition, `read_at` and a status of `ok`, `expired`, `skipped` or `error`; a fact that is not `ok` SHALL give a reason.

#### Scenario: A run writes data.json under the data directory
- **WHEN** a person runs `devops roadmap review run --version v1.0.0..v1.1.1 --json` in a checkout of `example/project`
- **THEN** the command writes `project-review/example/project/v1.0.0..v1.1.1/data.json` and `data.schema.json` under the data directory, and prints the same data

#### Scenario: A review with no lizard skips the complexity and says why
- **WHEN** lizard is not installed
- **THEN** the fact `lizard.complexity` has no value, the status `skipped`, and a reason that names the extra `review`

#### Scenario: A fact that is not ok must say why
- **WHEN** a fact has the status `error` and no reason
- **THEN** the model refuses the fact

### Requirement: The review writes the facts in a fixed order with the disagreements and the read counts
The facts in `data.json` SHALL be the commits, their types, the net change and the churn with generated paths apart, the release tags, the hot files and the complexity, the `functional.change` fact when the catalog result holds no `ok` fact whose id starts with `openspec.`, then each fact of the catalog in the catalog order. `data.json` SHALL also hold the disagreements, and the count of the reads of each reader kind with the seconds of the collection.

#### Scenario: The facts of a fixture catalog follow the git facts
- **WHEN** the review runs with a fixture catalog of two facts in the section `service` and no `ok` OpenSpec fact
- **THEN** `data.json` holds the git facts with section `changes`, then `functional.change` with section `changes`, then the two facts with section `service`, and the count of the reads of each reader kind

### Requirement: Hot files follow renames
The hot-file fact SHALL count a commit at an old path of a renamed file for the row of the path at the head, SHALL name each old path in the row, and SHALL leave out the paths that `.gitattributes` of the head marks `linguist-generated`.

#### Scenario: A commit at an old name counts for the path at the head
- **WHEN** `a.py` becomes `b.py` and then `c.py` in the window, and four commits touch the file
- **THEN** the row of `c.py` counts 4 commits and names `b.py` and `a.py`

### Requirement: A dry run of the review starts no program
With a window option, `devops roadmap review run --dry-run` SHALL print the ordered git commands, shared reads, and catalog facts with read placeholders. With no window option, it SHALL list each `service.repos` repository with section titles, fact IDs, unset settings, and condition text. It SHALL start no program, send no request, open no connection, and write no file.

#### Scenario: A dry run lists the git commands
- **WHEN** a person runs `devops roadmap review run --version v1.0.0..v1.1.1 --dry-run`
- **THEN** the output lists the `git log` command of each tag and the first-parent log of `<base commit>..<head commit>`, and no program starts

#### Scenario: A dry run lists the catalog queries and sends no request
- **WHEN** a person runs `devops roadmap review run --last 7d --dry-run` with fakes of GitHub, Prometheus, Loki and the processes that record each call
- **THEN** the output lists each fact id of the catalog with its rendered query, and each fake records 0 calls

#### Scenario: A dry run with no window lists each repository of service.repos
- **WHEN** a person runs `devops roadmap review run --dry-run` with no window option while `service.repos` names 7 repositories and `prometheus.url` is unset, with fakes of GitHub, Prometheus, Loki and the processes recording each call
- **THEN** the output holds one block for each of the 7 repositories containing every catalog section title and fact id, `The setting prometheus.url has no value.` on `prometheus.*` facts, `the base and the head commits hold openspec/specs` on `openspec.*` facts, and zero calls on any fake

### Requirement: The review refuses a repository that is not the origin of the checkout
When `--repo` names a repository that is not the origin of the checkout, the command SHALL exit 1 with a message that names both, and SHALL write no file.

#### Scenario: Another repository is refused
- **WHEN** a person runs the review with `--repo example/other` in a checkout of `example/project`
- **THEN** the command exits 1, the message names `example/project`, and no folder is written

### Requirement: The catalog defines each fact and a JSON Schema validates it
The project review SHALL read the facts that are not git facts from `catalog.yaml`, and SHALL validate the catalog against its JSON Schema before any read. Each fact SHALL have an id, a reader kind, a section, a query template, a unit and a definition. A refusal SHALL raise `RoadmapReviewError` with a message that names the fact and the field.

#### Scenario: A fact with no id is refused
- **WHEN** a fixture catalog holds one fact with no `id` field and the loader reads it
- **THEN** the loader raises `RoadmapReviewError`, and the message names the index of the fact and the field `id`

#### Scenario: A fact with no section is refused
- **WHEN** a fixture catalog holds the fact `prometheus.example` with no `section` field
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.example` and the field `section`

### Requirement: The catalog refuses unknown references and placeholders
The loader SHALL refuse a section that the catalog does not list, two facts with one id, a disagreement that names an unknown fact, and a placeholder other than `{start}`, `{end}`, `{range}`, `{base}`, `{head}`, `{repo}`, `{name_slug}` and `{namespaces}`. A refusal SHALL raise `RoadmapReviewError` with a message that names the fact.

#### Scenario: A section that the catalog does not list is refused
- **WHEN** the fact `prometheus.example` names the section `unknown`, and `sections` does not list it
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.example` and `unknown`

#### Scenario: An unknown placeholder is refused
- **WHEN** the query of the fact `github.example` holds `{owner}`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `github.example` and the field `query`

### Requirement: A Service metric query names its repository
The catalog schema SHALL refuse a `prometheus` fact whose query names a metric that starts with `devops_cli_service_` and holds no `{repo}` placeholder. The loader SHALL also refuse each selector of such a metric, in the query or in the `base` metric of a fact, whose own braces hold no matcher `repo="{repo}"`.

#### Scenario: A Service metric with no repository is refused
- **WHEN** the query of the `prometheus` fact `prometheus.stage_runs` is `sum(increase(devops_cli_service_jobs_total{row="stage"}[{range}]))`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.stage_runs`

#### Scenario: A ratio whose numerator has no repository is refused
- **WHEN** the query of the fact `prometheus.service_slo1` is `sum(increase(devops_cli_service_jobs_total{row="stage", result="success"}[{range}])) / sum(increase(devops_cli_service_jobs_total{repo="{repo}", row="stage"}[{range}]))`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.service_slo1` and `devops_cli_service_jobs_total`

### Requirement: A review query gives no host name
The catalog schema SHALL refuse a `prometheus` or `loki` fact whose query groups by `node` or `instance`.

#### Scenario: A query by node is refused
- **WHEN** the query of the fact `prometheus.memory_requests` is `sum by (node) (kube_pod_container_resource_requests{resource="memory"})`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.memory_requests`

### Requirement: The dispatcher fills the placeholders of the window
Before it sends a query, the dispatcher SHALL replace each placeholder: `{start}` and `{end}` with the UTC times of the window (`YYYY-MM-DDTHH:MM:SSZ`), `{range}` with the window length in whole seconds and the unit `s`, `{base}` and `{head}` with the two commits, `{repo}` with `owner/name`, `{name_slug}` with `RepoRef.name_slug` of the repository, and `{namespaces}` with the names of `roadmap.project_review.namespaces` joined with `|`. It SHALL keep every other brace.

#### Scenario: The placeholders of a PromQL query
- **WHEN** the window is the 7 days to `2026-11-11T14:51:23Z` of `example/project`, and a fact query is `sum(increase(devops_cli_service_jobs_total{repo="{repo}"}[{range}]))`
- **THEN** the sent query is `sum(increase(devops_cli_service_jobs_total{repo="example/project"}[604800s]))`

#### Scenario: The name slug of a Job name
- **WHEN** the repository is `Example/My.Project`, and a fact query is `kube_job_status_start_time{job_name=~"devops-cli-implement-{name_slug}-.+"}`
- **THEN** the sent query is `kube_job_status_start_time{job_name=~"devops-cli-implement-my-project-.+"}`

#### Scenario: The project namespaces of a workload query
- **WHEN** `roadmap.project_review.namespaces` is `devops` and `llm`, and the query of a `rows` fact is `max by (namespace, pod) (redis_memory_max_bytes{namespace=~"{namespaces}"} == 0)`
- **THEN** the dispatcher sends `max by (namespace, pod) (redis_memory_max_bytes{namespace=~"devops|llm"} == 0)` to the fixture Prometheus

### Requirement: A Service SLI is the value of one repository
A fact on a Service metric SHALL give the value of the repository of the review, and SHALL NOT add the values of the repositories together.

#### Scenario: Seven repositories
- **WHEN** a fixture Prometheus gives the SLO 1 of the Service 0.372 for `example/project` and 0.555 for each of six other repositories, and gives 0.927 for a query with no `repo` matcher
- **THEN** the fact `prometheus.service_slo1` of `example/project` has the value 0.372

### Requirement: Prometheus and Loki facts are read at the end of the window
The `prometheus` and `loki` readers SHALL send each query as an instant query with the `time` parameter set to the end of the window.

#### Scenario: A past window
- **WHEN** the review reads a `prometheus` fact and a `loki` fact for the window that ends at `2026-11-11T14:51:23Z`
- **THEN** each recorded request to `/api/v1/query` and to `/loki/api/v1/query` holds `time` with that instant

### Requirement: A source past its retention marks its facts expired
When the start of the window is more than 1 hour older than the retention limit of a reader kind, or of a fact, the dispatcher SHALL give each fact of it the status `expired`, a null value and a reason that names the retention, and SHALL send no request for it. The command SHALL give one time now to the window and to the retention test.

#### Scenario: A window that ended 40 days ago
- **WHEN** the window ended 40 days ago and the retention of the `prometheus` reader kind is `30d`
- **THEN** each `prometheus` fact has the status `expired`, the value null and a reason that is not empty, and the fake Prometheus records 0 requests

#### Scenario: A window as long as the retention
- **WHEN** the window is the 30 days to the whole minute before the time now, and the retention of the `prometheus` reader kind is `30d`
- **THEN** the `prometheus` fact has the status `ok` and the value of the fixture Prometheus

### Requirement: A missing value is never zero
The dispatcher SHALL give a fact the status `skipped` with a reason when a `requires` condition is false or when a query matches no series. It SHALL give a fact the status `error` with the first line of the error when its read raises a project error, and SHALL read the other facts. Each fact that is not `ok` SHALL have a null value.

#### Scenario: An unset address
- **WHEN** the setting `prometheus.url` has no value
- **THEN** each `prometheus` fact has the status `skipped`, a null value and a reason that names `prometheus.url`, and no request is sent

#### Scenario: A scalar query with no series
- **WHEN** a fixture Prometheus answers a `scalar` fact with an empty vector
- **THEN** the fact has the status `skipped`, a null value and a reason that says that no series matched

#### Scenario: A failed read
- **WHEN** the fixture Loki answers HTTP 500 to each attempt, and the catalog also holds a `prometheus` fact
- **THEN** the `loki` fact has the status `error` and a reason, and the `prometheus` fact has the status `ok`

#### Scenario: A Loki address that answers a web page
- **WHEN** the fixture Loki answers HTTP 200 with `text/html`, and the catalog also holds a `prometheus` fact
- **THEN** the `loki` fact has the status `error` and a reason that names `loki.url`, and the `prometheus` fact has the status `ok`

#### Scenario: A rows query with no series
- **WHEN** a fixture Prometheus answers a `rows` fact with no `base` metric with an empty vector
- **THEN** the fact has the status `skipped`, a null value and a reason that says that no series matched

### Requirement: An empty answer is none only when its base metric has a series
A `prometheus` fact can name a `base` metric. When its query matches no series and the base metric has a series, the fact SHALL have the status `ok` with no rows, or 0 for a `scalar` fact; else `skipped` with a reason that names the base metric. The probe SHALL have the time scope of the query: `group(last_over_time(<base>[<range>]))` when the query holds `{range}`, else `group(<base>)` at the window end.

#### Scenario: An empty answer of a fact with a base metric
- **WHEN** a fixture Prometheus answers the query `sum by (row) (increase(x_total[{range}])) > 0` of a fact with the base metric `x_total{repo="{repo}"}` with an empty vector, and answers `group(last_over_time(x_total{repo="example/project"}[604800s]))` with one series
- **THEN** a `rows` fact has the status `ok`, the value `[]` and `n` 0, and a `scalar` fact has the status `ok` and the value 0

#### Scenario: An empty answer and no base series
- **WHEN** the fixture Prometheus also answers the read of the base metric with an empty vector
- **THEN** the fact has the status `skipped`, a null value and a reason that names the base metric

#### Scenario: An end-instant fact whose base has no series at the end
- **WHEN** a fact with the base `x_total{repo="{repo}"}` has the query `sum by (state) (x_total)` with no `{range}`, and the fixture Prometheus answers it with an empty vector, answers `group(last_over_time(x_total{repo="example/project"}[604800s]))` with one series, and answers `group(x_total{repo="example/project"})` with an empty vector
- **THEN** the fact has the status `skipped`, a null value and a reason that names the base metric and the window end, and the sent queries are the query and `group(x_total{repo="example/project"})`

### Requirement: An address that does not answer ends the reads of its reader kind
After a read that gets no answer from the network, a `ServiceRequestError` with no HTTP status, each later fact of that reader kind SHALL have the status `error` with the same reason, and the dispatcher SHALL send no request for it.

#### Scenario: An address that does not answer
- **WHEN** the fixture Prometheus refuses each connection, and the catalog holds three `prometheus` facts with three queries
- **THEN** the fake records the attempts of the first query only, and each fact has the status `error` with one reason

### Requirement: The listing reader fills the gap after the snapshot watermark
The `listing` reader SHALL read the review snapshot of the release schema, else the intake snapshot. It SHALL read the issues and pull requests changed from the later of the watermark and the window start. It SHALL read from the window start when no snapshot fits or the window starts before the first window that the review snapshot covers. It SHALL keep the merged records only in the review store. A read that starts after the watermark SHALL keep a snapshot of only the time from its start.

#### Scenario: An issue after the watermark
- **WHEN** the review snapshot watermark is 2026-11-11T14:28:04Z, the window ends at 2026-11-11T14:51:23Z, and the fake GitHub gives one issue opened at 2026-11-11T14:40:00Z in the listing changed since the watermark
- **THEN** the fact of the issues opened in the window counts that issue once, the sent listing names since=2026-11-11T14:28:04Z, and the review snapshot holds that issue

#### Scenario: An old snapshot
- **WHEN** the review keeps no snapshot and the last full read of the intake snapshot is 3 days old
- **THEN** the fake GitHub records only the listing changed since its watermark, the intake snapshot file is byte-identical after the run, and the review snapshot holds the merged records

#### Scenario: No snapshot of this schema
- **WHEN** neither store holds a snapshot of this schema and the window starts at 2026-11-04T14:51:23Z
- **THEN** the fake GitHub records only the listing changed since 2026-11-04T14:51:23Z, and the review store holds a snapshot with the schema key of the release

#### Scenario: A watermark before the window start
- **WHEN** the review snapshot watermark is 3 weeks before the window start
- **THEN** each listing request names a since at or after the window start, and the listing count equals the listing count of a run with an empty review store

#### Scenario: A window wider than the review snapshot
- **WHEN** the window starts before the first window that the review snapshot covers
- **THEN** the fake GitHub records only the listing changed since the window start, and the review store holds a snapshot that covers the new window

#### Scenario: A second review over a new window
- **WHEN** a second review reads a window one day after the window of the first review, and the new window holds the watermark that the first review kept
- **THEN** the fake GitHub records only the listing changed since that watermark: one page, where a review of the new window with an empty review store reads three

#### Scenario: A read that starts after the watermark
- **WHEN** review A keeps the watermark 2026-09-14T23:59:00Z, an issue closes on 2026-10-06, review B reads a window that starts on 2026-10-14, and review C reads a window that starts on 2026-09-21
- **THEN** review C sends the listing changed since 2026-09-21T00:00:00Z and gives the closed record of that issue

### Requirement: The listing gives the merged pull requests
An issue record of a pull request SHALL hold `merged_at` from `pull_request.merged_at` of the issue listing, or null when the pull request did not merge.

#### Scenario: A merged and a closed pull request
- **WHEN** the issue listing holds pull request 7 with `pull_request.merged_at` `2026-11-11T10:00:00Z` and pull request 8 closed with `pull_request.merged_at` null
- **THEN** the record of pull request 7 has `merged_at` `2026-11-11T10:00:00Z`, and the record of pull request 8 has `merged_at` null

### Requirement: A newest-first listing stops at the window start
A `github` fact that names a `newest_first` field SHALL read no page after the first page that holds an item with that field at or before the start of the window.

#### Scenario: Releases of one week
- **WHEN** the fake GitHub gives three pages of releases, newest first, and the second page holds a release created before the window start
- **THEN** the reader requests pages 1 and 2 only

### Requirement: Facts on one answer share one read
The dispatcher SHALL send each distinct rendered query once, and SHALL give the answer to each fact that names that query.

#### Scenario: Two facts on the releases
- **WHEN** two `github` facts name the same query `repos/{repo}/releases` with two different `value` programs
- **THEN** the fake GitHub records one request for each page, and each fact has the value of its own program

### Requirement: The OpenSpec reader counts the deltas of the window
The `openspec` reader SHALL copy the files of each change that the window archived, at the head, into a temporary root, SHALL read each change that the window archived with `openspec show --json --deltas-only`, and SHALL count the requirements at the base and at the head with `git grep -c`. A change that `openspec show` refuses SHALL be listed with the reason of the tool, and the reader SHALL read the other changes. It SHALL change no file of the checkout.

#### Scenario: One archived change
- **WHEN** a fixture repository archives one change with one ADDED and one MODIFIED requirement in the window, and its specs hold 1 requirement at the base and 2 at the head
- **THEN** the reader gives 1 ADDED and 1 MODIFIED delta, and the totals 1 at the base and 2 at the head

#### Scenario: A change that openspec cannot show
- **WHEN** `openspec show` exits 1 for the archived change of the fixture repository with the message "Change must have a Why section"
- **THEN** the reader lists the change with that message, gives no delta for it, and still gives the totals 1 at the base and 2 at the head

### Requirement: The OpenSpec reader reads the archived files line by line
The `openspec` reader SHALL read the text of the archived files with one `git grep` of their lines, so that no byte count must match the text that the git seam gives.

#### Scenario: A file with CRLF line ends and a byte that is not UTF-8
- **WHEN** the archived change also holds `design.md` with CRLF line ends, a lone carriage return and a byte that is not UTF-8
- **THEN** the temporary root holds `design.md` with one line end in place of each, U+FFFD in place of the byte, and `specs/cap/spec.md` with its own text

### Requirement: The review lists the disagreements of the catalog
For each pair of facts that the catalog says must agree, the review SHALL list a disagreement when both facts are `ok` numbers and their relative difference is more than the tolerance of the pair. Each row SHALL hold the id of the pair, the two fact ids and the two values.

#### Scenario: Three disagreements
- **WHEN** fixture facts give 48.8 and 0 for the implement counters, 12 and 30 for the Service counter and kube-state-metrics, 77.22 and 118.74 for the CLI spend and the gateway spend, and 10 and 10.5 for a fourth pair with the tolerance 0.1
- **THEN** the review lists three disagreements, each with its two values, and does not list the fourth pair

### Requirement: The shipped catalog covers the review facts
The shipped `catalog.yaml` SHALL hold a fact for each SRE query Q1 to Q16 and each Kubernetes query Q2 to Q22 that the `prometheus` reader kind can read. It SHALL also hold the alert, notification, silence and Argo CD facts, the activity, release, Actions run, code-scanning and OpenSpec facts, the Service SLIs, the agentic job counters, the Renovate facts, and the gateway and CLI spend.

#### Scenario: The dry run lists the alert facts
- **WHEN** a person runs `uv run devops roadmap review run --last 7d --dry-run` in this repository
- **THEN** the output lists `ALERTS`, `alertmanager_notifications_total`, `alertmanager_silences` and `argocd_app_info` as `prometheus` facts, and the command sends 0 requests

### Requirement: The shipped catalog cites its query lists
The header of the shipped `catalog.yaml` SHALL cite the permalink of the Queries of `docs/SRE.md` at commit 6eae498088b2ff86a06883638e50b1a4fe3ad11a (SRE Q1 to Q16) and of `docs/K8S_PERFORMANCE.md` of PR #5492 at commit d0f6e42d117badb5f5b68d47eb25a74e33f01609 (Kubernetes Q2 to Q22).

#### Scenario: The header names both query lists
- **WHEN** a person reads the comment lines at the top of `catalog.yaml`
- **THEN** they hold both permalinks

### Requirement: The shipped catalog holds no usage-error row
The shipped `catalog.yaml` SHALL hold no fact on `devops_cli_usage_error_total`, because that counter has 0 series, and no LogQL fact of the CLI usage errors, which #4840 adds.

#### Scenario: The dry run lists no usage-error fact
- **WHEN** a person runs `uv run devops roadmap review run --last 7d --dry-run` in this repository
- **THEN** the output holds no `devops_cli_usage_error_total` and no `cli_usage_error`

### Requirement: A rows fact names only the workloads of the project namespaces
The loader SHALL refuse a `rows` fact whose query names `namespace` or `pod` in a `by` or `on` clause when the query, or its `base`, holds no positive namespace matcher, `namespace="…"` or `namespace=~"…"`. A refusal SHALL raise `RoadmapReviewError` with a message that names the fact, the field (`query` or `base`) and the label. A `scalar` fact SHALL NOT be refused for its grouping, because its answer has no label.

#### Scenario: A grouping by namespace with no matcher is refused
- **WHEN** a fixture catalog holds the `rows` fact `prometheus.valkey_pods` with the query `max by (namespace, pod) (redis_memory_max_bytes == 0)`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.valkey_pods`, the field `query` and the label `namespace`

#### Scenario: A join on pod with no matcher is refused
- **WHEN** a fixture catalog holds the `rows` fact `prometheus.requests` with the query `sum by (resource) (kube_pod_container_resource_requests * on (pod) group_left() kube_pod_status_ready)`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.requests` and the label `pod`

#### Scenario: A negative namespace matcher does not scope a fact
- **WHEN** a fixture catalog holds the `rows` fact `prometheus.valkey_pods` with the query `max by (namespace, pod) (redis_memory_max_bytes{namespace!="kube-system"} == 0)`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.valkey_pods`

#### Scenario: A base of all namespaces is refused
- **WHEN** a fixture catalog holds the `rows` fact `prometheus.valkey_pods` with the query `max by (namespace, pod) (redis_memory_max_bytes{namespace=~"{namespaces}"} == 0)` and the base `redis_memory_max_bytes`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.valkey_pods`, the field `base` and the label `namespace`

#### Scenario: A base in the project namespaces loads
- **WHEN** the same fact has the base `redis_memory_max_bytes{namespace=~"{namespaces}"}`
- **THEN** the loader gives the catalog with that fact and that base

#### Scenario: A grouping in the project namespaces loads
- **WHEN** a fixture catalog holds the `rows` fact `prometheus.valkey_pods` with the query `max by (namespace, pod) (redis_memory_max_bytes{namespace=~"{namespaces}"} == 0)`
- **THEN** the loader gives the catalog with that fact

#### Scenario: A scalar fact by namespace loads
- **WHEN** a fixture catalog holds the `scalar` fact `prometheus.pods` with the query `count(count by (namespace, pod) (kube_pod_info))`
- **THEN** the loader gives the catalog with that fact

#### Scenario: The shipped catalog scopes its workload rows
- **WHEN** the loader reads the shipped `catalog.yaml`, and each query is filled with the window placeholders and the namespace `devops`
- **THEN** the loader raises no error, each `rows` fact whose query names `namespace` or `pod` in a `by` or `on` clause holds a positive namespace matcher in its query and in its `base` after the fill, and no filled query holds `{namespaces}`

### Requirement: The dispatcher keeps no row of a workload outside the project namespaces
When a series of the answer of a `rows` fact of Prometheus or Loki holds a namespace label (`namespace`, `exported_namespace` or `dest_namespace`) outside `roadmap.project_review.namespaces`, or a workload label of the dispatcher list (for example `pod`, `container` or `service`) and no `namespace`, the fact SHALL have the status `error` and a null value. The reason SHALL name the fact and the label, and SHALL hold no label value. The dispatcher SHALL check only the labels of its lists.

#### Scenario: A row of another namespace
- **WHEN** `roadmap.project_review.namespaces` is `devops`, the query of the `rows` fact `prometheus.valkey_rows` is `sort_desc(sum without (instance) (redis_memory_used_bytes))`, and the fixture Prometheus answers a series with `namespace` `devops` and `pod` `valkey-0` and a series with `namespace` `other-project` and `pod` `database-0`
- **THEN** the fact has the status `error` and a null value, and the reason names `prometheus.valkey_rows` and `namespace`, and holds none of `other-project`, `database-0` and `valkey-0`

#### Scenario: A row with a workload label and no namespace
- **WHEN** the fixture Prometheus answers the same fact with a series with `pod` `database-0` and no `namespace`, or with `container` `database` and no `namespace`
- **THEN** the fact has the status `error`, and the reason names `pod` or `container` and holds no label value

#### Scenario: A row of another namespace in a label of the scrape or of Traefik
- **WHEN** the fixture Prometheus answers the same fact with a series with `namespace` `devops`, `exported_namespace` `other-project` and `exported_pod` `db-0`, or with a series with `service` `other-project-database-5432@kubernetes` and no `namespace`
- **THEN** the fact has the status `error`, and the reason names `exported_namespace` or `service` and holds no label value

#### Scenario: A Loki row of another namespace
- **WHEN** the fixture Loki answers the `rows` fact `loki.lines` with a series with `namespace` `other-project` and `container` `app`
- **THEN** the fact has the status `error`, and the reason names `loki.lines` and holds no `other-project`

#### Scenario: A row with no workload label
- **WHEN** the fixture Prometheus answers the `rows` fact with one series with only the label `resource`, or with only `namespace` `devops` and `pod` `valkey-0`, or with no label
- **THEN** the fact has the status `ok`, and its value is that one row

### Requirement: The project namespaces are a setting
The setting `roadmap.project_review.namespaces` SHALL list the project namespaces whose workloads the review can name. The settings load SHALL refuse an empty list, and each name that is not an RFC 1123 label. The review and its dry run SHALL fill `{namespaces}` from this setting.

#### Scenario: An empty list is refused
- **WHEN** the settings of the project review are loaded with `namespaces` set to an empty list
- **THEN** the load raises a validation error at `namespaces`

#### Scenario: A name that is not an RFC 1123 label is refused
- **WHEN** the settings of the project review are loaded with `namespaces` set to `["devops|.*"]`, `["Devops"]` or `["-devops"]`
- **THEN** the load raises a validation error at `namespaces`

#### Scenario: A dry run prints the project namespaces and sends no request
- **WHEN** a person runs `devops roadmap review run --last 7d --repo example/project --dry-run` with `roadmap.project_review.namespaces` set to `devops` and `agents`, with fakes that record each request and each process
- **THEN** the output holds `namespace=~"devops|agents"`, the output holds no `{namespaces}`, and each fake records 0 calls

### Requirement: The base metric of a fact is a metric of its query
The loader SHALL refuse a fact whose `base` metric name does not occur as a whole metric name in its query, unless the fact gives `base_reason`, a text that says why its base is another metric. The refusal SHALL raise `RoadmapReviewError` with a message that names the fact, the base metric and `base_reason`. The schema SHALL refuse `base_reason` in a fact with no `base`.

#### Scenario: A base of another metric is refused
- **WHEN** a fixture catalog holds the fact `prometheus.cuts` with the query `sum(increase(x_cuts_total[{range}]))` and the base `x_calls_total`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.cuts`, `x_calls_total` and `base_reason`

#### Scenario: A base of another metric with a reason loads
- **WHEN** the same fact also gives `base_reason` with a text
- **THEN** the loader gives the catalog with that fact

#### Scenario: A metric name inside a longer name does not count
- **WHEN** the query of the fact is `sum(increase(x_calls_total_bucket[{range}]))` and the base is `x_calls_total`
- **THEN** the loader raises `RoadmapReviewError`

#### Scenario: A reason with no base is refused
- **WHEN** a fixture fact gives `base_reason` and no `base`
- **THEN** the loader raises `RoadmapReviewError`, and the message names the fact and `base_reason`

#### Scenario: The shipped catalog loads
- **WHEN** the loader reads the shipped `catalog.yaml`
- **THEN** it raises no error

### Requirement: A fact can name the first time of its series
A fact MAY give `not_before`, a UTC time `YYYY-MM-DDTHH:MM:SSZ`. When the window starts before it, the dispatcher SHALL give the fact the status `skipped` with a reason that names that time, and SHALL send no request for it. The dry run SHALL show the condition.

#### Scenario: A window across the first time of a series
- **WHEN** a fixture catalog holds `prometheus.left` and `prometheus.right` with `not_before` `2026-11-14T22:29:00Z` and the pair of both with the tolerance 0.1, the window is the 7 days to `2026-11-16T00:00:00Z`, and the fixture Prometheus answers 48.43 for each query
- **THEN** `prometheus.left` is `ok` with 48.43, `prometheus.right` is `skipped` with a reason that names `2026-11-14T22:29:00Z`, the query of `prometheus.right` is not sent, and the review lists no disagreement

#### Scenario: A window after the first time of a series
- **WHEN** the window is the 1 day to `2026-11-16T00:00:00Z`, and the fixture Prometheus answers 48.43 for the left query and 15 for the right query
- **THEN** both facts are `ok`, and the review lists the disagreement of the pair

#### Scenario: The dry run shows the first time
- **WHEN** the plan of a dry run holds the fixture fact `prometheus.right`
- **THEN** the condition of its read says that the window starts at or after `2026-11-14T22:29:00Z`

#### Scenario: A time that is not UTC is refused
- **WHEN** a fixture fact gives `not_before` `2026-11-14T22:29:00+01:00`
- **THEN** the loader raises `RoadmapReviewError`, and the message names the fact and `not_before`

### Requirement: The runner Job count reads the Jobs that start in the window
The shipped fact `prometheus.runner_jobs_started` SHALL count the implement Jobs of the repository of the review whose start time is at or after the window start. It SHALL NOT count a Job that started before the window, also when kube-state-metrics keeps the series of that Job in the window.

#### Scenario: A Job that started before the window and a Job that started in it
- **WHEN** promtool evaluates the query of the shipped `prometheus.runner_jobs_started`, filled for `example/project` and the window from `1970-01-01T01:00:00Z` to `1970-01-01T02:00:00Z`, over fixture series of `kube_job_status_start_time` of an implement Job of `example/project` that started before the window and has a series in it, an implement Job of `example/project` that started in the window, and an implement Job of another repository that started in the window
- **THEN** the value is 1

#### Scenario: Only a Job that started before the window
- **WHEN** the fixture series hold only the implement Job of `example/project` that started before the window
- **THEN** the query gives no series

### Requirement: A path condition holds at the commits of the window
A `path:<path>` condition SHALL hold when the base and the head commits of the window hold the path, as `git ls-tree --name-only <commit> -- <path>` gives it, not the working tree. Else the fact SHALL be `skipped` with a reason that names the path and the commit. The dispatcher SHALL check each path once for each review. A git failure SHALL stop the review. The dry run SHALL list the two git commands.

#### Scenario: A base commit with no specs
- **WHEN** the window of a fixture repository has a base commit with no `openspec/specs` and a head commit with it, and the working tree holds `openspec/specs`
- **THEN** each `openspec` fact has the status `skipped`, a null value and a reason that names `openspec/specs` and the base commit, and the review starts no other git command for it

#### Scenario: The dry run lists the path checks
- **WHEN** a person runs `devops roadmap review run --last 7d --dry-run`
- **THEN** the output lists the git command `ls-tree --name-only` of `<base commit>` and of `<head commit>`, each with the path `openspec/specs`, and no program starts

### Requirement: A fact can give the reason of a missing series
A fact with no `base` MAY give `no_series_reason`, a text. When its query matches no series, the fact SHALL have the status `skipped` and that text as its reason. The schema SHALL refuse `no_series_reason` in a fact with a `base`.

#### Scenario: A gauge that no code emits yet
- **WHEN** a fixture fact with no `base` gives the `no_series_reason` "No code emits this gauge before #4911." and the fixture Prometheus answers its query with an empty vector
- **THEN** the fact has the status `skipped`, a null value and the reason "No code emits this gauge before #4911."

#### Scenario: A reason of a missing series with a base is refused
- **WHEN** a fixture fact gives `no_series_reason` and `base`
- **THEN** the loader raises `RoadmapReviewError`, and the message names the fact

### Requirement: The stage SLI counts the outcomes of the stage items
The shipped fact `prometheus.stage_sli` SHALL be the share of the stage items of the repository of the review that ended `staged` or `needs_split`, over the items of `devops_cli_roadmap_stage_total` that ended with a result other than `skipped`. It SHALL be 0 when no item ended well, and have no value when no item ended. Its definition SHALL name the owner decision of 2026-11-21 on #4692.

#### Scenario: Good and bad outcomes of one repository
- **WHEN** promtool evaluates the query of the shipped `prometheus.stage_sli`, filled for `example/project` and a window of 1 hour, over fixture series that add 6 `staged`, 2 `needs_split`, 1 `failed`, 1 `degenerate` and 5 `skipped` items of `example/project` and 10 `failed` items of `example/other` in the window
- **THEN** the value is 0.8

#### Scenario: Only bad outcomes
- **WHEN** the fixture series add only 3 `failed` items of `example/project`
- **THEN** the value is 0

#### Scenario: Only skipped items
- **WHEN** the fixture series add only 5 `skipped` items of `example/project`
- **THEN** the query gives no series

### Requirement: The review keeps its own listing snapshot
The project review SHALL write its listing snapshot to its own store under `review-listing` in the roadmap state directory, and SHALL NOT write the snapshot that intake keeps.

#### Scenario: A review writes the review snapshot
- **WHEN** a test runs one review over a 7-day window with an empty review store and an empty intake store
- **THEN** the review store holds one snapshot of the repository with the schema key of the release, and the intake store holds no file

#### Scenario: A review leaves the intake snapshot unchanged
- **WHEN** a test runs a review with an intake snapshot that holds a record of an older schema key
- **THEN** the intake snapshot file is byte-identical after the review, and the review store holds a new snapshot

### Requirement: The runs reader counts the runs of each status
The `github_runs` reader SHALL count the Actions runs created after the window start, in whole seconds, up to the window end. It SHALL read the total of each slice first. It SHALL split a slice at the GitHub cap of 2,500 in two halves by created time. For each slice under the cap, it SHALL add the total and the count of each status: success, failure, cancelled and in progress. It SHALL raise an error for a page with no total, a one-second slice at the cap and status counts above a total.

#### Scenario: A window under the count cap
- **WHEN** the fake GitHub gives 1,927 successful, 29 failed, 104 cancelled and 12 in-progress runs in a 7-day window, 2,072 runs in all
- **THEN** the fact's value holds the four counts, its n is 2,072, and the review counts 5 reads of the `github_runs` reader

#### Scenario: A window above the count cap
- **WHEN** the window holds 4,500 runs and the fake GitHub stops each total at 2,500, as GitHub does
- **THEN** the reader splits the window in two halves, the counts of the halves add up to the counts of the 4,500 runs, and the reader sends 11 requests

#### Scenario: A one-second slice at the count cap
- **WHEN** one second holds 2,500 runs
- **THEN** the reader raises an error that names the cap of 2,500

#### Scenario: Status counts above the total
- **WHEN** the four status counts of a slice add up to 16 and its total is 10
- **THEN** the reader raises an error that names the sum 16

#### Scenario: A runs page with no total
- **WHEN** the fake GitHub gives a runs page with no `total_count`
- **THEN** the runs fact has the status `error` and no count of 0

#### Scenario: A run in the start second
- **WHEN** one run is created in the start second of the window and one run in its end second
- **THEN** the window counts only the run of its end second, and the window that ends at that start counts the other run

#### Scenario: A run of another status
- **WHEN** the window holds 3 skipped runs
- **THEN** the total includes those 3 runs and the value holds no skipped key

### Requirement: A 7-day review sends at most 45 GitHub requests
A project review over a 7-day window MUST send at most 45 GitHub requests when it starts with no snapshot of any kind, and MUST send at most 45 when it starts with the review snapshot of an earlier review and no intake snapshot.

#### Scenario: A first 7-day review
- **WHEN** a test runs a review over a 7-day window with an empty review store and an empty intake store
- **THEN** the sum of the counts of the reads is at most 45

#### Scenario: A second 7-day review
- **WHEN** a test runs the review with the review snapshot of the previous review and no intake snapshot
- **THEN** the sum of the counts of the reads is at most 45 and the listing count is lower than the listing count of the first review

### Requirement: A version window needs a tag that matches the tag pattern
The project review SHALL read the review tag pattern from `[review] tag_pattern` of `.devops/roadmap.toml` in the checkout, SHALL use `v*` when the file or key is absent, SHALL reject invalid patterns (`ConfigurationError`), and SHALL refuse a version window when no tag of the repository matches the pattern with an error that names `tag_pattern` and the pattern before any commit lookup.

#### Scenario: A repository with no tag that matches the tag pattern
- **WHEN** a fixture checkout holds tags that do not match the configured `[review] tag_pattern` (for example empty tags for `release-*`)
- **THEN** `resolve_window` raises `RoadmapReviewError` whose message names `tag_pattern` and the pattern, and starts no git command

#### Scenario: A checkout with no review table
- **WHEN** a fixture checkout has no `[review]` table in `.devops/roadmap.toml` and holds `v1.0.0..v1.1.1` tags
- **THEN** the default pattern `v*` matches those tags and accepts the version window

### Requirement: The functional change comes from the CHANGELOG without openspec
The project review SHALL record `functional.change` from bullet items under the `### Features` and `### Bug Fixes` headings of the first release (`## ...`) of `CHANGELOG.md` when the catalog result holds no `ok` fact whose id starts with `openspec.`, and the fact MUST name `changelog` as its `source`.

#### Scenario: A repository without openspec
- **WHEN** a fixture checkout holds a `CHANGELOG.md` with Features or Bug Fixes items and the catalog result holds no `ok` OpenSpec fact
- **THEN** `functional.change` holds those items and names `changelog` as its `source`

### Requirement: The functional change falls back to the commit subjects
The project review SHALL record `functional.change` from the `feat` and `fix` commit subjects of its window when `CHANGELOG.md` gives no section items, and the fact MUST name `subjects` as its `source`.

#### Scenario: A repository with neither openspec nor changelog
- **WHEN** a fixture checkout holds no `ok` OpenSpec fact and no `CHANGELOG.md` section items, and its window holds `feat` and `fix` commits
- **THEN** `functional.change` holds those commit subjects and names `subjects` as its `source`

### Requirement: The functional change falls back to the merged pull request titles
The project review SHALL record `functional.change` from the titles of `listing.merged_titles` when no CHANGELOG section item and no `feat` or `fix` commit subject exists, and the fact MUST name `pull_requests` as its `source`, or record status `skipped` with `source` `functional` and a reason when all sources are empty.

#### Scenario: A repository with only pull request titles
- **WHEN** a fixture window holds no CHANGELOG section item and no `feat` or `fix` commit subject, and `listing.merged_titles` gives two merged pull request titles
- **THEN** `functional.change` holds the two titles and names `pull_requests` as its `source`

#### Scenario: All functional change sources are empty
- **WHEN** a fixture window holds no CHANGELOG section item, no `feat` or `fix` commit subject, and no merged pull request title
- **THEN** `functional.change` has status `skipped`, `source` `functional`, and a non-empty reason

### Requirement: The complexity rank is skipped when lizard reads no hot file
The project review SHALL keep churn order on `git.hotspots` and MUST record `lizard.complexity` as `skipped` with a reason when the window has hot files and lizard reads none of them, while empty hot files stay `ok` with `[]`, and `render_review` MUST show that skipped reason.

#### Scenario: A Shell-only repository
- **WHEN** a fixture window holds only Shell hot files
- **THEN** `complexity_fact` gives `status` `skipped` with a reason stating no hot file is readable by lizard, `git.hotspots` keeps the churn rank, and `render_review` includes that reason

### Requirement: No spend disagreement pair
The project review catalog SHALL define no disagreement pair named `spend`.

#### Scenario: Shipped catalog omits the spend pair
- **WHEN** `load_catalog()` reads `src/devops_cli/roadmap/project_review/catalog.yaml`
- **THEN** no entry in `catalog.disagreements` has `id == "spend"`

### Requirement: Both spend facts stay separate
The project review catalog MUST keep `prometheus.cli_spend` and `prometheus.gateway_spend` as separate facts.

#### Scenario: Dry run lists both spend facts
- **WHEN** a person runs `uv run devops roadmap review run --since 2026-11-16T12:00Z --until 2026-11-17T12:00Z --dry-run`
- **THEN** the command exits 0 and prints a line for `prometheus.cli_spend` and a line for `prometheus.gateway_spend`

### Requirement: The map covers the guideline rows
The row-check map MUST hold exactly one entry for each row id of `docs/guidelines/production-readiness.md`, with that row's Level and Scope.

#### Scenario: A missing or an unknown row id
- **WHEN** A test parses the row ids, Level cells and Scope cells of `docs/guidelines/production-readiness.md` and compares them with the row-check map.
- **THEN** Each row id has one entry with the same level and scope, and a missing or unknown row id fails the test with its id.

### Requirement: The map check matches the Measured by cell
Each row-check map entry MUST name the same tool checks and commands as the Measured by cell of its guideline row.

#### Scenario: A changed Measured by cell
- **WHEN** A test parses each Measured by cell of `docs/guidelines/production-readiness.md` and compares its tool checks and commands with the entry of the same row id.
- **THEN** Each cell matches its entry, and a changed cell fails the test with the row id.

### Requirement: The map holds no issue number and no gap table
The row-check map MUST hold no issue number and no gap table.

#### Scenario: An issue number in the map
- **WHEN** A test scans each row-check map entry for an issue reference or a gap table field.
- **THEN** No entry holds an issue reference or a gap table field.

### Requirement: Scorecard JSON maps to row states
The readiness reader MUST map each Scorecard check in a recorded JSON result to the row that it measures and to that row's state.

#### Scenario: A recorded Scorecard JSON result
- **WHEN** A test gives the reader a recorded Scorecard JSON result of one repository.
- **THEN** The report gives each row that a Scorecard check measures a state of met, partly met or not met, and the check name as its source.

### Requirement: The Scorecard reader runs the pinned binary
The Scorecard reader MUST run the pinned OpenSSF Scorecard binary with `--format json` once for each repository of the live setting `service.repos` and once for each infra repository of the setting `infra.repos`.

#### Scenario: Two repositories in settings
- **WHEN** A test runs the Scorecard reader with two repositories in `service.repos`, one repository in `infra.repos` and a process edge that records the argv.
- **THEN** The recorded argv holds one Scorecard run with `--format json` for each of the two repositories and for the infra repository.

### Requirement: File rows use the GitHub contents query
The report MUST read a row whose check is a file on the default branch with the GitHub reader of #4692 and a contents query at the ref.

#### Scenario: A file row
- **WHEN** A test runs the report with a fake GitHub reader for a row whose check is `AGENTS.md`, `CODEOWNERS` or `openspec/config.yaml`.
- **THEN** The fake reader receives a contents query for that path at the ref, and the row holds the reader's state, source and read time.

### Requirement: Command rows run the devops command
The report MUST run a row whose check is a `devops` command with its JSON output at the ref and map the JSON result to the row state.

#### Scenario: A command row
- **WHEN** A test runs the report for a row whose check is `devops repos onboard --plan` and a process edge that records the argv and returns a JSON result.
- **THEN** The recorded argv holds that command with its JSON output, and the row holds the state of the JSON result, with the command as its source.

### Requirement: A manual row gets no request
The report MUST give a row whose check is `manual` the state `not readable` and MUST send no request for it.

#### Scenario: A manual row
- **WHEN** A test runs the report for a repository that has a row whose check is `manual` and a reader that counts requests.
- **THEN** The row holds the state `not readable` and the counter shows no request for it.

### Requirement: Each row gives its state, source and read time
The report MUST give each row one state, the source of the value and the time of the read.

#### Scenario: A readable row
- **WHEN** A test runs the readiness report for one repository.
- **THEN** Each row holds one state, the source of the value and the read time.

### Requirement: The ref option reads the branch
The `--ref` option MUST read the repository rows at the named branch.

#### Scenario: A branch differs from the default branch
- **WHEN** A test runs the readiness report with `--ref` at a branch whose files differ from the default branch.
- **THEN** The report gives the states of the branch files and not the states of the default branch.

### Requirement: Private repository rows stay out of the shared report
The report MUST keep the rows of a private repository out of the shared report.

#### Scenario: A private repository
- **WHEN** A test gives the report a repository that the GitHub API reports as private.
- **THEN** The shared report holds no row of that repository.

### Requirement: A private repository falls back to the GitHub API
When the pinned Scorecard binary cannot read a private repository, the report MUST read that repository's practice rows with the GitHub API reader of #4692 and name that reader as their source.

#### Scenario: Scorecard refuses a private repository
- **WHEN** A test makes the Scorecard reader fail for a repository that the GitHub API reports as private.
- **THEN** The report reads the practice rows with the GitHub API reader and each row names the GitHub reader as its source.

### Requirement: The dry run sends no request
The `--dry-run` option MUST send no request.

#### Scenario: A dry run with a request counter
- **WHEN** A test runs the readiness report with `--dry-run` and a reader that counts requests.
- **THEN** The counter stays at zero and the report lists the planned reads.

### Requirement: The report reads the repository names from settings
The report MUST take the repository names from the live setting `service.repos` at run time.

#### Scenario: A changed repository list
- **WHEN** A test sets `service.repos` to a list and runs the report.
- **THEN** The report reads exactly the repositories of that list, and no committed file of the change holds a repository name of the setting.

### Requirement: The guideline states the record use
`docs/guidelines/production-readiness.md` MUST say that the readiness report holds the record of a running service and, with `--ref`, of a launch.

#### Scenario: The readiness record section
- **WHEN** A test reads the readiness record section of `docs/guidelines/production-readiness.md`.
- **THEN** It holds a sentence that the readiness report is the record of a running service and, with `--ref`, of a launch.
