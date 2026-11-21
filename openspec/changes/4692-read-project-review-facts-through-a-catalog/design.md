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
- `requires` is a list of `setting:<dotted name>` (the setting has a value) and `window:<kind>` (the window has that kind). The reader kind and the fact can each give conditions.
- `retention` is a duration in days (`30d`). The fact value overrides the value of its reader kind.
- `tolerance` is the largest relative difference, `|a - b| / max(|a|, |b|)`, that is not a disagreement.

### 4. Schema rules and loader checks

- The schema refuses: a missing required field; a field that it does not name (`additionalProperties: false`); an unknown reader kind; a placeholder other than the six (`\{[a-z_]+\}` that is not one of them; a PromQL label matcher always holds `=` or `~`, so it does not match); a `prometheus` query that names `devops_cli_service_` with no `{repo}` (`if` and `then`); a `prometheus` or `loki` query that groups by `node` or `instance`.
- The loader also refuses: two facts with one id; a section that `sections` does not list; a disagreement that names an unknown fact. JSON Schema cannot compare two values of one document, so these 3 checks are code.
- Each refusal raises `RoadmapReviewError`. The message names the fact id, or the index when the fact has no id, and the field. The text of a `jsonschema` error does not quote the rejected value, as `ai/mcp/argument_contract.py` does.
- No host name goes into a review: the facts can go to a GitHub comment (#4733), and the Kubernetes guideline does not allow a host name in an issue. A query that needs a value for each node uses `max` or `count` over the nodes.

### 5. Placeholders

- The dispatcher replaces only the six names, with a regular expression, and does not use `str.format`, because PromQL holds braces.
- `{start}` and `{end}` are UTC times in the form `2026-11-11T14:51:23Z`. `{range}` is the length of the window in whole seconds (`604800s`), which PromQL and LogQL take. `{base}` and `{head}` are the commits. `{repo}` is `owner/name`, the form of the `repo` label.

### 6. Readers

- One read for each distinct rendered query: the facts on one answer share the read. So the runs read, the release read and the listing read each happen once.
- `listing`: `IncrementalListing` gets `keep: bool = True`. The review reads with `keep=False`, so the intake snapshot keeps one writer. The reader uses `GitHubStore` to read the changes after the watermark, merges them with `merged`, and gives each record as JSON. A snapshot that is missing, of another schema, or older than its maximum age gives a full read, as intake does.
- `IssueRecord.merged_at` comes from `pull_request.merged_at`. The merged pull requests and their lead time come from the listing, with no search request.
- `github`: `GitHubSession.pages(path)`. A fact can name `newest_first: <field>`. The reader then stops after the first page that holds an item with that field at or before the window start. Releases and code-scanning alerts use it.
- `github_runs`: the reader adds `created=<a>..<b>` and reads the first page. When `total_count` is 1,000 or more, it splits the slice in two halves by created time and reads each half. Else it reads the other pages. The reader keeps each run id once. A slice of 1 s with 1,000 runs or more raises `RoadmapReviewError`, so no run is lost without a message.
- `prometheus`: `PrometheusClient(settings.prometheus.url, configured_level(settings.ai)).query(expr, at=end)`.
- `loki`: `query_loki_metrics(expressions, settings.loki.url, at=end)`. `resolve_loki_url` is not used, because it falls back to `http://localhost:3100`, and a client never uses an unconfigured address.
- `openspec`: `git archive --format=tar <head> -- openspec` into a temporary root (`tarfile` with `filter="data"`). The change folders that the window adds under `openspec/changes/archive/` (`git diff --name-only --diff-filter=A <base> <head>`) move to `openspec/changes/` in that root. `isolated_openspec(root)` runs `openspec show <change> --json --deltas-only --no-interactive` for each change that holds `specs/`, in 4 workers. `git grep -c '^### Requirement:' <rev> -- openspec/specs` gives the totals at the base and the head.

### 7. Status of a fact

| Condition | Status | Value | Request |
| :--- | :--- | :--- | :--- |
| A `requires` condition is false | `skipped`, the reason names the setting or the window kind | null | none |
| The window start is older than the retention | `expired`, the reason names the retention and the start | null | none |
| The read raises a project error (`DevOpsCLIError`) | `error`, the reason is the first line of the error | null | sent |
| A `scalar` query gives no sample | `skipped`, the reason says that no series matched | null | sent |
| Else | `ok` | the value | sent |

- A missing value is never 0. Only these narrow error classes become a fact status. Each other exception stops the run.
- The review exits 0 when it writes `data.json`. The summary shows each fact that is not `ok` with its reason.

### 8. data.json

- `Fact` gets `section`. The git and lizard facts of #4686 take the section `changes`.
- `ReviewData` gets `disagreements` (id, left id, right id, both values and the tolerance) and `collection` (the pages or queries read by each reader kind, and the seconds of the collection). The pages count is the count of requests that the readers ask for. A retry of the GitHub session is not in it.
- A disagreement row appears only when both facts are `ok` numbers and their relative difference is more than the tolerance.

### 9. Dry run

- `--dry-run` prints the git commands of #4686, then the shared reads (the listing read after `<the watermark of the snapshot>`), then one entry for each fact: its id, its reader and its rendered query. A value that only a read gives is a named placeholder (`<base commit>`, `<start time>`). It sends 0 requests and starts no program.

### 10. Budget

- A 7-day collection sends 45 GitHub requests or fewer and takes 3 min or less. The estimate for the 7 days to 2026-11-11T14:51:23Z: the listing 1 to 2, the runs about 19 (1,633 runs: 1 first page that splits, then 2 halves of about 9 pages), the releases 2, the code-scanning alerts a few pages. The OpenSpec reads take about 20 s in 4 workers (406 changes at 0.2 s).
- The build measures both numbers live and writes them in the pull request. A measure over a limit stops the build with the evidence. The build does not drop facts to pass it.

### 11. Live numbers

- The build reproduces the acceptance numbers of #4692 read-only from the worktree, for `--version v0.111.0..v0.112.1` and for `--since 2026-11-04T14:51:23Z --until 2026-11-11T14:51:23Z`. Each number that differs from the body is named with the reason. A source past its retention is `expired`, never 0.
- The source of the count of alternatives checks (20 in the body) is the source that gives that count live: the `alternatives` row of `devops_cli_service_jobs_total`, or the `alternatives.checked_at` field of the listing records. The build records which one.

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
