# Proposal: #4692

## Why

The project review (#4679) reads only git and lizard today (#4686). It needs facts from five more interfaces: the issue listing, GitHub REST, Prometheus, Loki and OpenSpec (#4692). Code for each fact would grow with no limit. The sources also have these problems:

- A filtered list of Actions runs stops at 1,000 results. On 2026-11-11, page 11 returned 0 runs, and one 12-hour slice held 969 runs. On 2026-11-21, the 7 days to 2026-11-11T14:51:23Z held 1,633 push runs on `main` (`total_count`).
- The listing snapshot lags. Its watermark was 14:28:04Z, the window end was 14:51:23Z, and the review missed 1 issue.
- Prometheus and Loki keep 30 days, and Actions keeps 90 days. A read past the retention gives 0 or an empty answer, which is not a measured value.
- The sources disagree. In the 7 days to 2026-11-11T14:51:23Z, `devops_cli_service_implement_failures_total` grew by 48.8 and `devops_cli_service_implement_jobs_total{result="failed"}` grew by 0. The CLI spend counter grew by 77.22 USD and the gateway spend counter grew by 118.74 USD.
- All three candidate designs added the Service SLIs of 7 repositories together: the stage SLI was 0.927. devops-cli alone gives 0.372 (58.3 successes and 98.5 errors).

## What Changes

- Add `catalog.yaml` and its JSON Schema `catalog.schema.json` in `src/devops_cli/roadmap/project_review/`. The catalog is data: a new fact needs no code. Each fact has an id, a reader kind, a section, a query template, a unit, a definition, and optional `requires` conditions and a retention. The catalog also lists the sections, the retention of each reader kind, and the pairs of facts that must agree.
- The schema refuses a fact with no id or no section, a section that the catalog does not list, an unknown placeholder, a Service metric query (`devops_cli_service_`) that has no `{repo}`, and a PromQL or LogQL query that groups by `node` or `instance`.
- Add one dispatcher. It replaces the placeholders `{start}`, `{end}`, `{range}`, `{base}`, `{head}` and `{repo}`, reads each distinct query once, and gives each fact its value. A `jq` program of the fact gives the value of a listing, GitHub or OpenSpec answer.
- Add thin readers over the existing clients:
  - `listing`: the listing snapshot of intake, with the issues that changed after its watermark (`issues?since=<watermark>`). The review reads the snapshot and does not write it. `IssueRecord` gets `merged_at` from `pull_request.merged_at`, so the listing gives the merged pull requests and their lead time.
  - `github`: a paginated REST read through the GitHub session, for releases and code-scanning alerts. A newest-first listing stops at the first item before the window.
  - `github_runs`: the Actions runs of a query. A slice whose `total_count` is 1,000 or more splits in two halves by created time, until each slice holds fewer than 1,000 runs.
  - `prometheus`: `PrometheusClient` instant queries at the window end (`time`).
  - `loki`: `query_loki_metrics` instant queries at the window end. The function gets an `at` parameter that it sends as `time`. A top-N fact uses `topk` over `count_over_time`, because the patterns API returns 404.
  - `openspec`: a `git archive` copy of the head into a temporary root, `openspec show --json --deltas-only` for each change archived in the window, and the requirement totals at the base and the head from `git grep -c`.
- A reader kind past its retention marks its facts `expired` with a reason and sends no request. A fact is never 0 for missing data: a scalar query with no series is `skipped` with a reason.
- A fact whose reader needs an unset setting (`prometheus.url`, `loki.url`) is `skipped` with a reason that names the setting. A failed read marks its facts `error` with the reason, and the review reads the other facts.
- `data.json` gets the section of each fact, the list of disagreements with both values, and the pages read by each reader kind with the collection time.
- `--dry-run` lists each git command and each rendered query of the catalog, and sends 0 requests.
- The catalog holds the facts of the scope comments of #4692: the activity, releases, Actions and code-scanning facts; the OpenSpec facts; the Service SLIs for each repository; the SRE queries Q1 to Q16 and the Kubernetes queries Q2 to Q22 that an existing reader kind serves; the alert, silence and Argo CD facts; the agentic job counters; the Renovate facts; and the gateway and CLI spend. It holds no fact on `devops_cli_usage_error_total`, which has 0 series, and no LogQL fact of Kubernetes Q9 or Q14 or of the CLI usage errors (#4840 adds that row).
- The command output and `data.json` change, so the change modifies the capability `roadmap-project-review`.

## Capabilities

- `roadmap-project-review` (modified): the fact catalog, its schema and dispatcher, the readers, the `expired` mark, the disagreements and the dry run of the catalog.

## Impact

- `devops roadmap review run` now sends requests to GitHub, Prometheus and Loki, and starts `openspec`. Its dry run still sends 0 requests and starts no program.
- `IssueRecord` gets `merged_at`. The key of the listing schema changes, so each kept listing snapshot is read again in full one time.
- `query_loki_metrics` gets an optional `at` parameter. Its callers keep the current time.
- No new dependency: `jsonschema` 4.26.0, `jq` 1.13.0 and PyYAML 6.0.3 are already direct dependencies.
- No new setting. The review uses `prometheus.url` and `loki.url`, and has no fallback address.
- The change fits one pull request.

## Feasibility

- The package exists on origin/main ddad1a45e with the facts of #4686 (closed 2026-11-11): `src/devops_cli/roadmap/project_review/` holds `data.py`, `facts.py`, `git_read.py`, `review.py` and `window.py`. `FactStatus` already has `expired`.
- `PrometheusClient.query(expr, at=...)` sends `time` (`src/devops_cli/prometheus/client.py:113`). `query_loki_metrics` sends no `time` today (`src/devops_cli/k8s/logql.py:390`).
- GitHub documents that the list of workflow runs gives up to 1,000 results for a search with `branch`, `created`, `event` or `status`. `GET repos/dan-petty/devops-cli/actions/runs?branch=main&event=push&created=2026-11-04T14:51:23Z..2026-11-11T14:51:23Z&per_page=1` gave `total_count` 1,633 on 2026-11-21, so one slice cannot hold the window.
- Prometheus on 2026-11-21 (`/api/v1/status/flags`): `storage.tsdb.retention.time` is `30d`. Instant queries at `time=2026-11-11T14:51:23Z` gave: stage `success` 58.27 and `error` 98.45 for `repo="dan-petty/devops-cli"` (0.372); `litellm_spend_metric_total` 118.74 USD; `devops_cli_ai_spend_usd_total` 77.22 USD; implement failures 48.8 against `result="failed"` 0. The `repo` label has the form `owner/name`.
- `alertmanager_silences{state="active"}` has series in Prometheus, so the active-silences fact uses the `prometheus` reader kind and needs no Alertmanager reader and no new setting.
- `openspec show <change> --json --deltas-only` (OpenSpec 2.1.0) gives each delta with its `operation` in 0.2 s. 406 changes were archived in the 7-day window, so the reader runs the calls in 4 workers.
- The listing snapshot already reads the changes after its watermark (`changed_listing`, `IncrementalListing`). The issue listing of GitHub gives `pull_request.merged_at` for a pull request.

## Existing Tool Considered

- turbot/steampipe (https://github.com/turbot/steampipe, AGPL-3.0, maintained) is the tool of the alternatives check of 2026-11-20 (verdict `partly`). Its plugins read GitHub and Prometheus through SQL. It has no Loki or OpenSpec plugin, no catalog with sections, `requires` and `{repo}` rules, no `expired` mark for each retention, and no dry run that sends 0 requests. A second runtime for two of six readers adds more than it removes, so the change does not adopt it.
- The change uses open tools through their standard interfaces: the GitHub REST API through the `devops gh` session and its pacing, the Prometheus and Loki HTTP APIs through `PrometheusClient` and `query_loki_metrics`, the OpenSpec CLI JSON, `git archive` and `git grep`. `jsonschema` (MIT) validates the catalog against a Draft 2020-12 schema. `jq` (the Python binding of jq, MIT) computes the value of a fact from an answer, as `devops gh api --jq` does.
- The custom code is one catalog loader, one dispatcher and six thin readers, four of which wrap existing clients. Cost: about 900 to 1,200 lines with tests and the catalog, about 250,000 to 400,000 model tokens to build, about 0.50 to 1.00 USD on the DeepSeek implement path, a small cost to keep because a new fact is data, and 2 to 3 days elapsed.
- The change deletes no internal code. No reader of these sources exists for the project review.
