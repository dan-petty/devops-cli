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
The facts in `data.json` SHALL be the commits, their types, the net change and the churn with generated paths apart, the release tags, the hot files and the complexity, then each fact of the catalog in the catalog order. `data.json` SHALL also hold the disagreements, and the count of the reads of each reader kind with the seconds of the collection.

#### Scenario: The facts of a fixture catalog follow the git facts
- **WHEN** the review runs with a fixture catalog of two facts in the section `service`
- **THEN** `data.json` holds the git facts with the section `changes`, then the two facts with the section `service`, and the count of the reads of each reader kind

### Requirement: Hot files follow renames
The hot-file fact SHALL count a commit at an old path of a renamed file for the row of the path at the head, SHALL name each old path in the row, and SHALL leave out the paths that `.gitattributes` of the head marks `linguist-generated`.

#### Scenario: A commit at an old name counts for the path at the head
- **WHEN** `a.py` becomes `b.py` and then `c.py` in the window, and four commits touch the file
- **THEN** the row of `c.py` counts 4 commits and names `b.py` and `a.py`

### Requirement: A dry run of the review starts no program
`devops roadmap review run --dry-run` SHALL print the git commands that a run starts, in order, then the shared reads, then each fact of the catalog with its id, its reader kind and its rendered query, with a placeholder for each value that a read gives. It SHALL start no program, send no request, open no connection and write no file.

#### Scenario: A dry run lists the git commands
- **WHEN** a person runs `devops roadmap review run --version v1.0.0..v1.1.1 --dry-run`
- **THEN** the output lists the `git log` command of each tag and the first-parent log of `<base commit>..<head commit>`, and no program starts

#### Scenario: A dry run lists the catalog queries and sends no request
- **WHEN** a person runs `devops roadmap review run --last 7d --dry-run` with fakes of GitHub, Prometheus, Loki and the processes that record each call
- **THEN** the output lists each fact id of the catalog with its rendered query, and each fake records 0 calls

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
The loader SHALL refuse a section that the catalog does not list, two facts with one id, a disagreement that names an unknown fact, and a placeholder other than `{start}`, `{end}`, `{range}`, `{base}`, `{head}`, `{repo}` and `{name_slug}`. A refusal SHALL raise `RoadmapReviewError` with a message that names the fact.

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
- **WHEN** the query of the fact `prometheus.stage_sli` is `sum(increase(devops_cli_service_jobs_total{row="stage", result="success"}[{range}])) / sum(increase(devops_cli_service_jobs_total{repo="{repo}", row="stage"}[{range}]))`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.stage_sli` and `devops_cli_service_jobs_total`

### Requirement: A review query gives no host name
The catalog schema SHALL refuse a `prometheus` or `loki` fact whose query groups by `node` or `instance`.

#### Scenario: A query by node is refused
- **WHEN** the query of the fact `prometheus.memory_requests` is `sum by (node) (kube_pod_container_resource_requests{resource="memory"})`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.memory_requests`

### Requirement: The dispatcher fills the placeholders of the window
Before it sends a query, the dispatcher SHALL replace `{start}` and `{end}` with the UTC times of the window in the form `YYYY-MM-DDTHH:MM:SSZ`, `{range}` with the length of the window in whole seconds and the unit `s`, `{base}` and `{head}` with the two commits, `{repo}` with the repository as `owner/name`, and `{name_slug}` with the slug of the repository name that the Job names of the Service hold (`RepoRef.name_slug`). It SHALL keep every other brace of the query.

#### Scenario: The placeholders of a PromQL query
- **WHEN** the window is the 7 days to `2026-11-11T14:51:23Z` of `example/project`, and a fact query is `sum(increase(devops_cli_service_jobs_total{repo="{repo}"}[{range}]))`
- **THEN** the sent query is `sum(increase(devops_cli_service_jobs_total{repo="example/project"}[604800s]))`

#### Scenario: The name slug of a Job name
- **WHEN** the repository is `Example/My.Project`, and a fact query is `kube_job_status_start_time{job_name=~"devops-cli-implement-{name_slug}-.+"}`
- **THEN** the sent query is `kube_job_status_start_time{job_name=~"devops-cli-implement-my-project-.+"}`

### Requirement: A Service SLI is the value of one repository
A fact on a Service metric SHALL give the value of the repository of the review, and SHALL NOT add the values of the repositories together.

#### Scenario: Seven repositories
- **WHEN** a fixture Prometheus gives the stage SLI 0.372 for `example/project` and 0.555 for each of six other repositories, and gives 0.927 for a query with no `repo` matcher
- **THEN** the stage SLI fact of `example/project` has the value 0.372

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
A `prometheus` fact can name a `base` metric. When its query matches no series and the base metric has a series in the window, the fact SHALL have the status `ok` with no rows, or 0 for a `scalar` fact. When the base metric has no series either, the fact SHALL have the status `skipped` with a reason that names the base metric.

#### Scenario: An empty answer of a fact with a base metric
- **WHEN** a fixture Prometheus answers the query of a fact with the base metric `x_total{repo="{repo}"}` with an empty vector, and answers `group(last_over_time(x_total{repo="example/project"}[604800s]))` with one series
- **THEN** a `rows` fact has the status `ok`, the value `[]` and `n` 0, and a `scalar` fact has the status `ok` and the value 0

#### Scenario: An empty answer and no base series
- **WHEN** the fixture Prometheus also answers the read of the base metric with an empty vector
- **THEN** the fact has the status `skipped`, a null value and a reason that names the base metric

### Requirement: An address that does not answer ends the reads of its reader kind
After a read that gets no answer from the network, a `ServiceRequestError` with no HTTP status, each later fact of that reader kind SHALL have the status `error` with the same reason, and the dispatcher SHALL send no request for it.

#### Scenario: An address that does not answer
- **WHEN** the fixture Prometheus refuses each connection, and the catalog holds three `prometheus` facts with three queries
- **THEN** the fake records the attempts of the first query only, and each fact has the status `error` with one reason

### Requirement: The listing reader fills the gap after the snapshot watermark
The `listing` reader SHALL read the kept listing snapshot of the repository when its records have the schema of the release, whatever the age of its last full read, SHALL send the listing of the issues and pull requests changed at or after its watermark, and SHALL merge the answer with the snapshot. When no such snapshot is kept, it SHALL send only the listing of the issues and pull requests changed at or after the window start. It SHALL NOT write a snapshot.

#### Scenario: An issue after the watermark
- **WHEN** the snapshot watermark is `2026-11-11T14:28:04Z`, the window ends at `2026-11-11T14:51:23Z`, and the fake GitHub gives one issue opened at `2026-11-11T14:40:00Z` in the listing changed since the watermark
- **THEN** the fact of the issues opened in the window counts that issue once, and the snapshot file is the same as before the run

#### Scenario: An old snapshot
- **WHEN** the last full read of the snapshot is 3 days old
- **THEN** the fake GitHub records only the listing changed since the watermark, and the snapshot file is the same as before the run

#### Scenario: No snapshot of this schema
- **WHEN** no snapshot is kept, or the snapshot has another schema key, and the window starts at `2026-11-04T14:51:23Z`
- **THEN** the fake GitHub records only the listing changed since `2026-11-04T14:51:23Z`, and no snapshot file changes

### Requirement: The listing gives the merged pull requests
An issue record of a pull request SHALL hold `merged_at` from `pull_request.merged_at` of the issue listing, or null when the pull request did not merge.

#### Scenario: A merged and a closed pull request
- **WHEN** the issue listing holds pull request 7 with `pull_request.merged_at` `2026-11-11T10:00:00Z` and pull request 8 closed with `pull_request.merged_at` null
- **THEN** the record of pull request 7 has `merged_at` `2026-11-11T10:00:00Z`, and the record of pull request 8 has `merged_at` null

### Requirement: The runs reader splits a slice that reaches the result cap
The `github_runs` reader SHALL read the runs of a query by created time. When a slice gives a `total_count` of 1,000 or more, it SHALL split the slice in two halves by created time and read each half. It SHALL give each run once.

#### Scenario: Two thousand runs
- **WHEN** a fake session holds 2,000 runs in the window and answers each `created` slice as GitHub does, with at most 1,000 runs and the real `total_count`
- **THEN** the reader gives all 2,000 run ids, each id once, and each slice that it reads to the end holds fewer than 1,000 runs

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
