# Design

#6612 has no refine design. The coordinator of the delivery decided the six points with the best-practice answer (owner rule: decide open design questions and report them). This design records each decision.

## Decisions

### 1. The base metric is a metric of the query

- The base metric of a fact is the leading metric name of its `base` selector. The schema pattern of `base` already makes the selector start with a metric name.
- The loader refuses a fact whose base metric does not occur in its query as a whole metric name (no letter, digit, `_` or `:` before or after it), unless the fact gives `base_reason`. The refusal names the fact, the base metric and the field `base_reason`, and quotes no query text. The function `unqueried_base` goes beside `unscoped_service_metric` and `unscoped_workload_metric` in `catalog.py` (#6615).
- `base_reason` is a text that says why the base is another metric. A text, not a boolean, because the reader of the catalog must see the reason next to the fact. The schema refuses `base_reason` with no `base`.
- Three shipped facts need `base_reason`, so the field is not unused code:
  - `prometheus.colon_rules`: the query selects metrics by a name pattern and names no metric. `prometheus_rule_group_rules` shows that Prometheus loads its rules.
  - `prometheus.alerts_firing_hours`: `ALERTS` has a series only while an alert is pending or firing. `prometheus_rule_group_rules` shows that Prometheus evaluates the alert rules, so an empty answer is "no alert fired".
  - `prometheus.oom_kills_devops`: kube-state-metrics gives `kube_pod_container_status_last_terminated_reason` only for a container that ended. `kube_pod_container_info` shows that it reads the namespace.
- `prometheus.tool_limit_hits` takes the base `devops_cli_roadmap_tool_cuts_total`. The counter has no label `repo` (`docs/TELEMETRY.md`), so the fact stays the value of all repositories, as today.
- `prometheus.stage_gate_refusals` takes the base `devops_cli_roadmap_stage_gate_refusals_total{repo="{repo}"}`, and its query reads `{repo="{repo}"}`. The counter has the label `repo` (`docs/TELEMETRY.md`), and the review is the review of one repository. The line changes for the base, so the scope comes in the same change.

### 2. The probe has the time scope of the query

- A query that holds the placeholder `{range}` reads the window, so its probe stays `group(last_over_time(<base>[<range>]))`. This covers the range vectors `[{range}]` and the subqueries `[{range}:5m]` of 4 shipped facts, which read the window too.
- A query with no `{range}` reads only the window end, so its probe is `group(<base>)`, an instant query at the window end, as the query is. The prometheus reader already sends each read at the window end.
- When the probe at the end gives no series, the fact is `skipped` with a reason that names the base metric and the end of the window. The dry run lists the probe of the time scope of each fact, through the same `_probe`.

### 3. The first time of a series

- The optional fact field `not_before` is a UTC time `YYYY-MM-DDTHH:MM:SSZ`, quoted in YAML so that it stays a string for the schema. When the window starts before it, the fact is `skipped` with a reason that names the window start and that time, and the dispatcher sends no request for the fact. A window that starts at that time or later reads the fact.
- The dispatcher tests `not_before` after the `requires` conditions and before the retention.
- `prometheus.runner_jobs_started` takes `not_before: "2026-11-14T22:29:00Z"`, the "Live since 2026-11-14 22:29 UTC" comment of the release v0.144.0 on #4558, the issue of PR #5739. Before that time, the Service named the Jobs of all repositories `devops-cli-runner-<time>-<hex>`.
- `disagreements` already skips a pair when a side is not an `ok` number, so the pair `runner_jobs` is not listed for a window that starts before that time. No code of the pair changes. A test proves it.
- The dry run shows the condition "the window starts at or after <time>" for such a fact.

### 4. A path condition at the commits of the window

- `path:<path>` holds when the base and the head commits of the window hold the path. The git reader `git ls-tree --name-only <commit> -- <path>` (a new argument builder in `git_read.py`) gives the path when it is there, and no output when it is not.
- The check runs through `run_git` of the review (#4686), which uses `run_subprocess` as ARCHITECTURE.md requires. A non-zero exit, for example a commit that the checkout does not have, raises `RoadmapReviewError` and stops the review, as each other git read of the review does. No error becomes "the path is not there".
- The dispatcher checks each distinct path once for each review: at most two git commands. It checks the base first, and the head only when the base holds the path.
- A path that is not at a commit gives `skipped` with a reason that names the path and the commit.
- The dry run lists the two `git ls-tree` commands with the placeholders of the base and the head commits, before the shared reads of the OpenSpec reader, and the condition text of `path:` says "the base and the head commits hold <path>".

### 5. The reason of a missing series

- The optional fact field `no_series_reason` is the reason of `skipped` when the query of a fact matches no series and the fact has no `base`. It replaces "No series matched the query.". A fact with a `base` keeps the reason that names its base metric, so the schema refuses `no_series_reason` together with `base`.
- `prometheus.oldest_pending_update` says: no code emits the gauge before #4911 adds it. One fact, one source: the text is in the catalog (ADR 0025, section 2), not in `messages.py`.

### 6. The stage SLI by item outcomes

- `prometheus.stage_sli` reads `devops_cli_roadmap_stage_total` of the repository:

  ```promql
  (sum(increase(devops_cli_roadmap_stage_total{repo="{repo}", result=~"staged|needs_split"}[{range}])) or vector(0))
  / sum(increase(devops_cli_roadmap_stage_total{repo="{repo}", result!="skipped"}[{range}]))
  ```

- Good outcomes are `staged` and `needs_split`: `needs_split` is a correct stage judgment that an item is too big for one pull request, not a failure. Bad outcomes are `failed` and `degenerate`. `skipped` is an item that the job left out with a reason, so it is not an outcome of a plan, and the SLI does not count it.
- `or vector(0)` gives a numerator of 0 when the window has bad outcomes and no good one, so the value is 0, not a missing value. With no outcome at all, the denominator has no series, the answer is empty, and the fact is `skipped`: a window with no item has no SLI. The fact has no `base`, because a base would turn that empty answer into `ok` with 0.
- The definition names the owner decision of 2026-11-21 (comment on #4692) and says that the quality of a plan (the plans that build) is #5603.
- The counter has the label `repo`, so both selectors read `repo="{repo}"`.
- The spec scenarios that use the fixture fact id `prometheus.stage_sli` for a ratio of Service rounds take the id `prometheus.service_slo1`, the shipped fact on that metric.

### Tests

- Each point has a test that fails on the base commit, with fixtures: fixture catalogs and the web fake for the dispatcher, a recorded git scenario for the path condition (ADR 0007: tests double only the process edge), and promtool over fixture series for the query of the stage SLI.
- No test asserts a value of the shipped catalog. The shipped catalog test loads it, so the base rule checks each shipped fact. The promtool test evaluates the shipped query of the stage SLI, which is the behavior of the fact.

### Verification before the pull request

- Read only, from the worktree: `devops roadmap review run --since 2026-11-06T00:00:00Z --until 2026-11-07T00:00:00Z` gives `prometheus.tool_limit_hits` and `prometheus.stage_gate_refusals` `skipped`, and `--since 2026-11-16T12:00:00Z --until 2026-11-17T12:00:00Z` (a window that ends at `2026-11-17T12:00:00Z`) gives `prometheus.alertmanager_alerts` and `prometheus.silences_active` `skipped`. Prometheus keeps 30 days, so both windows are in the retention on 2026-11-21.

## Rejected alternatives

- **Remove the `base` of the three facts that read another metric.** Rejected: `ALERTS` and the last end reason have no series in a quiet window, so each quiet window would give `skipped` in place of "none". That loses a true 0.
- **A boolean field in place of `base_reason`.** Rejected: a reader of the catalog sees the flag but not why the other metric is correct.
- **Parse the PromQL with promql-parser.** Rejected: its PyPI release states no license (alternatives check of 2026-11-21), and the rule needs only the leading name of the `base` selector and a whole-name search of the query.
- **Choose the probe by the text `[{range}]`.** Rejected: 4 shipped facts read the window with the subquery `[{range}:5m]`, so the text test would give them an end-instant probe for a query that reads the whole window.
- **Remove the pair `runner_jobs` for a window across the rename.** Rejected: it needs window code in `disagreements`, and `prometheus.runner_jobs_started` alone still gives a low count for that window. `not_before` corrects the fact and the pair with data only.
- **`git cat-file -e <commit>:<path>`.** Rejected: it exits 128 both for a path that is not there and for a commit that does not exist, so the check could not tell an absent path from a git failure. `git ls-tree --name-only` exits 0 with no output for an absent path.
- **`try_git` for the path check.** Rejected: it turns each git failure into "the path is not there", a swallowed error.
- **The text of #4911 in `messages.py`.** Rejected: the text is about one fact, so it belongs to the fact in the catalog.
- **Count `needs_split` as a bad outcome.** Rejected: the stage job stops an item that is too big for one pull request on purpose, and the owner decision counts item outcomes of the stage, not the plans that build (#5603).
- **Give `prometheus.stage_sli` the base `devops_cli_roadmap_stage_total{repo="{repo}"}` and no `or vector(0)`.** Rejected: a window with only `skipped` items gives an empty ratio, and the base would make it `ok` with 0, a value that the review did not measure.
