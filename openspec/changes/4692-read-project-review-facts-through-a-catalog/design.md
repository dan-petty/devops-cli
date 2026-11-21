# Design

## Decisions

### 1. Scope

- The owner comment of 2026-11-19T18:40Z on #4692 moves the row that reads through the reader kind of #4840 (the LogQL row of the CLI usage errors) to #4840. This change adds no such row and does not wait for #4840. The build order is #4692, #4720, #4733, #5219, #4840.
- #5219 waits for these parts: the catalog with the `section` field, the dispatcher, the listing-snapshot reader, the Prometheus and Loki readers that evaluate at the window end with `time`, the state `expired`, and `--dry-run`. This change gives each part.
- The scope comment of 2026-11-12T20:39Z removes the PromQL row on `devops_cli_usage_error_total`, because that counter has 0 series (#5220). The catalog holds no such row.
- The active silences use the `prometheus` reader kind: `sum(alertmanager_silences{state="active"})`. Prometheus has the series (2026-11-21), and the scope comment of 2026-11-13 adds facts "with no new reader where an existing reader kind fits". The match of a silence to an alert, which an incident trigger needs, stays with #4714.

### 2. Files

| File | Role |
| :--- | :--- |
| `src/devops_cli/roadmap/project_review/catalog.yaml` | The facts, the sections, the retention of each reader kind and the pairs that must agree. Data only. |
| `src/devops_cli/roadmap/project_review/catalog.schema.json` | The JSON Schema (Draft 2020-12) of the catalog. It is the one definition of the catalog form. |
| `src/devops_cli/roadmap/project_review/catalog.py` | Load the YAML, validate it with `jsonschema`, check the cross references, give frozen dataclasses, and render the placeholders. |
| `src/devops_cli/roadmap/project_review/dispatch.py` | The dispatcher: `requires`, retention, one read for each distinct query, the value of each fact, the disagreements and the plan of the dry run. |
| `src/devops_cli/roadmap/project_review/readers.py` | The `listing`, `github`, `github_runs`, `prometheus` and `loki` readers. |
| `src/devops_cli/roadmap/project_review/openspec_read.py` | The `openspec` reader. |

### 3. Catalog form

```yaml
# yaml-language-server: $schema=catalog.schema.json
version: 1
sections:
  - {id: activity, title: Activity}
readers:
  prometheus: {retention: 30d, requires: ["setting:prometheus.url"]}
  loki: {retention: 30d, requires: ["setting:loki.url"]}
  github_runs: {retention: 90d}
facts:
  - id: prometheus.stage_successes
    reader: prometheus
    section: service
    query: sum(increase(devops_cli_service_jobs_total{job="roadmap-service", container="service", row="stage", repo="{repo}", result="success"}[{range}]))
    shape: scalar
    unit: runs
    definition: The stage rounds of the repository that ended with success in the window.
disagreements:
  - id: implement_failures
    left: prometheus.implement_failures
    right: prometheus.implement_jobs_failed
    tolerance: 0.1
    definition: The two implement counters count the same failed Jobs.
```

- `id` matches `^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$`. By convention its first part is the reader kind, as the ids of #4686 (`git.commits`) are.
- `reader` is one of `listing`, `github`, `github_runs`, `prometheus`, `loki` and `openspec`.
- `section` names an entry of `sections`. #5219 adds the section `self_improvement` in its own pull request.
- `query` is the template that the reader sends: a REST path with its query string, a PromQL or LogQL expression, or the name of the OpenSpec read.
- `value` is a `jq` program that gives the value from the answer, required for `listing`, `github`, `github_runs` and `openspec`. `n` is an optional `jq` program that gives the sample size. The program gets `$start` and `$end` (Unix seconds) and `$repo`.
- `shape` is `scalar` or `rows`, required for `prometheus` and `loki`. A scalar is the value of the one sample. Rows are `{labels, value}` for each sample, the largest value first.
- `base` is a selector of the metric that a `prometheus` fact reads. When the query gives no series, the dispatcher reads `group(last_over_time(<base>[{range}]))`: a series there makes the fact none (no rows, or 0), and no series makes it `skipped`. A ratio or a quantile names no base, so an empty answer stays `skipped`. Only a `prometheus` fact can name a base.
- `requires` is a list of `setting:<dotted name>` (the setting has a value), `window:<kind>` (the window has that kind) and `path:<path>` (the checkout holds the path). The `openspec` reader kind requires `path:openspec/specs`, so a repository with no OpenSpec gives `skipped`, not 0 requirements. The reader kind and the fact can each give conditions.
- `retention` is a duration in days (`30d`). The fact value overrides the value of its reader kind.
- `tolerance` is the largest relative difference, `|a - b| / max(|a|, |b|)`, that is not a disagreement.

### 4. Schema rules and loader checks

- The schema refuses: a missing required field; a field that it does not name (`additionalProperties: false`); an unknown reader kind; a placeholder other than the six (`\{[a-z_]+\}` that is not one of them; a PromQL label matcher always holds `=` or `~`, so it does not match); a `prometheus` query that names `devops_cli_service_` with no `{repo}` (`if` and `then`); a `prometheus` or `loki` query that groups by `node` or `instance`.
- The loader also refuses: two facts with one id; a section that `sections` does not list; a disagreement that names an unknown fact; and each selector of a `devops_cli_service_` metric, in `query` or in `base`, whose own braces hold no matcher `repo="{repo}"`. The schema sees only one `{repo}` somewhere in the query, so a ratio with no matcher in the numerator passes it, and adds the repositories together (the 0.927 of #4692). JSON Schema cannot compare two values of one document or parse a selector, so these 4 checks are code.
- Each refusal raises `RoadmapReviewError`. The message names the fact id, or the index when the fact has no id, and the field. The text of a `jsonschema` error does not quote the rejected value, as `ai/mcp/argument_contract.py` does.
- No host name goes into a review: the facts can go to a GitHub comment (#4733), and the Kubernetes guideline does not allow a host name in an issue. A query that needs a value for each node uses `max` or `count` over the nodes.

### 5. Placeholders

- The dispatcher replaces only the seven names, with a regular expression, and does not use `str.format`, because PromQL holds braces.
- `{start}` and `{end}` are UTC times in the form `2026-11-11T14:51:23Z`. `{range}` is the length of the window in whole seconds (`604800s`), which PromQL and LogQL take. `{base}` and `{head}` are the commits. `{repo}` is `owner/name`, the form of the `repo` label. `{name_slug}` is `RepoRef.name_slug`, the slug of the repository name that the Job names of the Service hold (`devops-cli-<row>-<name slug>-...`). kube-state-metrics exports no Job label and no pod label (2026-11-21: `kube_pod_labels` has no series), so the name is the only repository scope of a Job. A name longer than the slug budget of a Job name is cut in the Job name, and the fact then finds no Job.

### 6. Readers

- One read for each distinct rendered query: the facts on one answer share the read. So the runs read, the release read and the listing read each happen once.
- `listing`: the reader gives `GitHubRoadmapStore` its own `ListingRead`. It takes the intake snapshot when its records have the schema of this release, whatever the age of its last full read, reads the changes after the watermark and merges them with `merged`. With no such snapshot it reads only the changes at or after the window start (`issues?state=all&since=<start>`), not the whole listing: each listing fact counts issues and pull requests that were opened, closed, merged or written in the window, and each of these moves `updated_at`. The 24-hour full read of intake removes issues that left the repository, which these counts do not need. The review writes no snapshot, so each snapshot file keeps one writer (#4854).
- `IssueRecord.merged_at` comes from `pull_request.merged_at`. The merged pull requests and their lead time come from the listing, with no search request.
- `github`: `GitHubSession.pages(path)`. A fact can name `newest_first: <field>`. The reader then stops after the first page that holds an item with that field at or before the window start. Releases and code-scanning alerts use it.
- `github_runs`: the reader adds `created=<a>..<b>` and reads the first page. When `total_count` is 1,000 or more, it splits the slice in two halves by created time and reads each half. Else it reads the other pages. The reader keeps each run id once. A slice of 1 s with 1,000 runs or more raises `RoadmapReviewError`, so no run is lost without a message.
- `prometheus`: `PrometheusClient(settings.prometheus.url, configured_level(settings.ai)).query(expr, at=end)`.
- `loki`: `query_loki_metrics(expressions, settings.loki.url, at=end)`. `resolve_loki_url` is not used, because it falls back to `http://localhost:3100`, and a client never uses an unconfigured address. An answer that is not JSON, such as the sign-in page of a proxy or a page of Grafana at `loki.url`, raises `KubernetesLoggingError`, which names `loki.url`.
- A read that gets no answer from the network (`ServiceRequestError` with no HTTP status) ends the reads of its reader kind: each later fact of the kind takes the same reason and sends no request. With 65 Prometheus facts, one address that does not answer cost about 9 minutes of retries before. An HTTP status, such as 422 for one bad query, ends only its own read.
- `openspec`: `git diff --name-only -z --diff-filter=A <base> <head> -- openspec/changes/archive/` names the files that the window archived. One `git grep -z -n -I -F --no-column --no-color -e "" <head> -- <change folders>` gives each line with its path and number, and the reader writes each archived change that holds `specs/` to `openspec/changes/` of a temporary root. The git seam reads text: CRLF and a lone carriage return become one line end and a byte that is not UTF-8 becomes U+FFFD, so the reader counts no bytes, and a line with no path continues the line before it. An empty file gives no line, and its text is empty. A test answers the reads from a recorded git transcript; a `git archive` tar stream is binary, and the transcript of the git seam holds text. `isolated_openspec(root)` runs `openspec show <change> --json --deltas-only --no-interactive` for each change that holds `specs/`, in 4 workers. `git grep -c '^### Requirement:' <rev> -- openspec/specs` gives the totals at the base and the head.

### 7. Status of a fact

| Condition | Status | Value | Request |
| :--- | :--- | :--- | :--- |
| A `requires` condition is false | `skipped`, the reason names the setting or the window kind | null | none |
| The window start is more than 1 hour before the retention limit | `expired`, the reason names the retention and the start | null | none |
| An earlier read of the reader kind got no answer from the network | `error`, the reason of that read | null | none |
| The read raises a project error (`DevOpsCLIError`) | `error`, the reason is the first line of the error | null | sent |
| A query gives no series, and the fact names no `base` or the base has no series | `skipped`, the reason says that no series matched | null | sent |
| A query gives no series, and the `base` metric has a series in the window | `ok` | `[]` (n 0) or 0 | sent, and the read of the base |
| Else | `ok` | the value | sent |

- Prometheus and Loki delete a block of samples only when the whole block is past the retention, and `--last 30d` starts at the whole minute before the time now less 30 days. So a start up to 1 hour before the retention limit is read, and the command gives one time now to the window and to the retention test.

- A missing value is never 0. Only these narrow error classes become a fact status. Each other exception stops the run.
- The review exits 0 when it writes `data.json`. The summary shows each fact that is not `ok` with its reason.

### 8. data.json

- `Fact` gets `section`. The git and lizard facts of #4686 take the section `changes`.
- `ReviewData` gets `disagreements` (id, left id, right id, both values and the tolerance) and `collection` (the pages or queries read by each reader kind, and the seconds of the collection). The pages count is the count of requests that the readers ask for. A retry of the GitHub session is not in it.
- A disagreement row appears only when both facts are `ok` numbers and their relative difference is more than the tolerance.

### 9. Dry run

- `--dry-run` prints the git commands of #4686, then the shared reads (the listing read after `<watermark of the snapshot>` when a snapshot of this schema is kept, else after the window start), then one entry for each fact, and the read of its base metric for a fact that names one: its id, its reader and its rendered query. A value that only a read gives is a named placeholder (`<base commit>`, `<start time>`). It sends 0 requests and starts no program.

### 10. Budget

- A 7-day collection sends 45 GitHub requests or fewer and takes 3 min or less. The estimate for the 7 days to 2026-11-11T14:51:23Z: the listing 1 to 2, the runs about 19 (1,633 runs: 1 first page that splits, then 2 halves of about 9 pages), the releases 2, the code-scanning alerts a few pages. The OpenSpec reads take about 20 s in 4 workers (406 changes at 0.2 s).
- The build measures both numbers live and writes them in the pull request. A measure over a limit stops the build with the evidence. The build does not drop facts to pass it.
- Measured 2026-11-21 for `--last 7d` (2,072 push runs): with an intake snapshot of this record schema, 31 GitHub requests (listing 1, github 5, runs 25) in 96 s. With no such snapshot, the listing reads the changes since the window start: 49 requests (listing 19) in 129 s. Each kept snapshot has the old schema key after this change, so a review reads the changes since the window start until `devops roadmap intake` of this release keeps a new snapshot. The runs read grows with the runs: 25 pages for 2,072 runs.

### 11. Live numbers

- The build reproduces the acceptance numbers of #4692 read-only from the worktree, for `--version v0.111.0..v0.112.1` and for `--since 2026-11-04T14:51:23Z --until 2026-11-11T14:51:23Z`. Each number that differs from the body is named with the reason. A source past its retention is `expired`, never 0.
- No source keeps each alternatives check of the version window (20 in the body). `alternatives.checked_at` keeps the latest check only, so `listing.alternatives_last_checked` gives 10 for that window on 2026-11-21. The Service row counts rounds, not checks (`prometheus.alternatives_rounds`, 1). The result line `roadmap job result: job=alternatives` (#4845) counts each check in Loki (`loki.alternatives_checks`), but its first line is of 2026-11-12, after the window. So the review gives no count of 20, and the pull request returns that number to the owner.
- The stage facts of the body (58.3 successes, 98.5 errors, 0.372) are rounds of the stage row (`devops_cli_service_jobs_total{row="stage"}`). Since #5559 (2026-11-13) a round submits and recovers the stage Jobs and plans no item, so the stage row SLI near 1.0 of a later window tells that the round works, not that items were staged. `prometheus.stage_item_results` reads the ended items from `devops_cli_roadmap_stage_total`, which the round counted before #5559 and the stage Job counts since. In the window of the body it gives 156.4 `failed` and 0 `staged`.
- Since #5739 (2026-11-14) the implement Jobs are `devops-cli-implement-<name slug>-<item>-<hex>`. Before it, the Service named the Jobs of all repositories `devops-cli-runner-<time>-<hex>`, the name of a runner Job that a person starts too. So `prometheus.runner_jobs_started` counts the implement Jobs of the repository by the new name, has no series before 2026-11-14, and the pair `runner_jobs` compares later windows only. SLO 2 and the runner memory and CPU read both names.
- `openspec show` refuses the archived change `2026-11-18-4590-trace-gate-judges-reads-that-are-no-run-read`: its proposal has `## Problem` and no `## Why`. Two more archived proposals have no Why section. #5378 (comment of 2026-11-21) holds the fix of the archived proposals and of the gate.

## Rejected alternatives

- **Steampipe (AGPL-3.0).** It reads GitHub and Prometheus through SQL plugins, but it has no Loki or OpenSpec plugin, no catalog with sections and `{repo}` rules, no `expired` mark and no dry run with 0 requests (alternatives check of 2026-11-20, verdict `partly`). A second runtime for two of six readers adds more than it removes.
- **A reader for each fact.** The code grows with each fact, which is the problem of #4692.
- **A pydantic model as the source of the catalog schema.** The rule "a Service metric query needs `{repo}`" would be a validator in code, not in the schema, and editors could not check the YAML. One hand-written JSON Schema keeps every form rule in the file that the YAML names.
- **A new `alertmanager` reader with the setting `alertmanager.url` (the refine design of #4692).** `alertmanager_silences` in Prometheus gives the active silences, and the default `http://localhost:9093` of that design is an unconfigured fallback address, which the owner rule of 2026-10-04 does not allow.
- **The search API for merged pull requests.** It costs a request for each 100 pull requests and has its own 1,000-result cap. The listing already holds each pull request, and `merged_at` is in the same answer.
- **Read page 11 of the runs and later.** GitHub returns 0 runs after 1,000 results. A slice by time keeps each read under the cap.
- **Return 0 or omit a fact past its retention.** 0 states a measured value, and an omitted fact hides that the source cannot answer the window.
- **A recorded-answer test of the live acceptance numbers.** It tests the recorded data, not the code, and the owner rule of 2026-11-16 does not allow a test of a data value. The build measures the numbers live, and the tests use fixture catalogs.
- **A test of the rows of the shipped catalog.** It is a value test of a data file. The dry run loads and validates the shipped catalog, and the build reads it live.
- **`resolve_loki_url` for the Loki address.** It falls back to `http://localhost:3100` when `loki.url` is unset.
- **Write the intake snapshot from the review.** Each snapshot file has one writer (#4854). The review reads it and keeps its gap fill in memory.
- **The 24-hour rule of intake for the review.** The full read of intake removes issues that left the repository; the listing facts do not need it. With the rule, each review with no fresh intake snapshot read the whole listing (66 pages, 92 requests in 215 s).
- **A full read when no snapshot fits.** The changes since the window start hold each record that a listing fact counts, in fewer pages (19 for the last 7 days on 2026-11-21, against 66).
- **`git cat-file --batch` for the archived files.** It gives byte sizes, and the text read of the git seam changes CRLF and bytes that are not UTF-8, so the sizes do not match the text.
- **A join on `kube_pod_labels` for the runner Jobs of a repository.** The metric has no series in the cluster (2026-11-21), so the Job name is the only scope.
- **The ended results of `devops_cli_service_stage_jobs_total` for the stage SLI.** The row counts `succeeded` and `failed` only for a Job that ended with no check-in (1 `succeeded` and 9 `failed` against 165 `created` in the 7 days to 2026-11-21), so it is not the outcome of the items.
