# Proposal: #4690

## Why

The metrics row of the Service sends the project snapshot of each managed repository from one process, but the `devops_cli_project_*` series carry no `repo` label. So all repositories write to one series and overwrite each other. In 24 h, `devops_cli_project_stars` changed 265 times and `devops_cli_project_releases` 234 times, and the stars panel shows the value of the repository that wrote last. `_sent_item_series` is one set for the process, so the snapshot of each repository sends 0 for the item label sets of the repository before it. `devops gh metrics --emit-telemetry --milestone X` or `--limit 5` also writes a filtered snapshot to the same series, and that snapshot stays in the 30-day range of the dashboard. Closes #4690.

## What Changes

- `emit_project_metrics_telemetry` adds `repo`, the casefolded `owner/name` of the report (`RepoRef.key`, ADR 0022), to each point of each `devops_cli_project_*` instrument: the release, star, fork, traffic, commit, pull request, release interval, CI run and item series. The age gauges of the oldest item and the oldest claim take the same value, in place of the spelling of the report.
- `_sent_item_series` becomes a dict keyed by `repo`. A snapshot sends 0 once for a label set that the last snapshot of its own repository sent and this one lacks, and no 0 for a label set of another repository.
- `devops gh metrics --emit-telemetry` refuses `--milestone`, and a `--limit` other than the default of 10, with an error that names the option. It refuses before it reads the repository, so it makes no request and sends no point. `--limit 10` is accepted. The default is one named value, `DEFAULT_PROJECT_METRICS_RELEASE_LIMIT`, that the option and `collect_project_metrics_report` share.
- The description of each `devops_cli_project_*` instrument names `repo`, and `docs/TELEMETRY.md` says what the label holds and that the command refuses a filtered snapshot.
- The dashboard queries stay as they are. They aggregate over the new label until the project-metrics dashboard item adds the `repo` filter.

The change alters the labels of a metric and the result of a command option, which a consumer observes, so it has a spec delta.

## Capabilities

- `project-metrics-dashboard` (modified): the project series carry `repo`, the 0 for a label set that goes away is kept per repository, and the command sends no filtered snapshot.

## Impact

- Each `devops_cli_project_*` series splits into one series for each repository. The panels of `project-metrics.json` show a `max` or a `sum` over the repositories until the dashboard item adds the filter.
- A run of `devops gh metrics --emit-telemetry` with `--milestone` or another `--limit` now exits with an error. A run with no filter sends its snapshot as before, with the `repo` label.
- No setting, manifest or dependency changes. The change fits one pull request.

## Feasibility

- Prometheus, read on 2026-11-11 through the Grafana data source: `changes(devops_cli_project_stars{job="roadmap-service"}[24h])` is 265 and `changes(devops_cli_project_releases{job="roadmap-service"}[24h])` is 234 for one series each. `count(count by (repo) (last_over_time(devops_cli_project_items{job="roadmap-service"}[1h])))` is 1, so the items series hold no `repo` label.
- Source: `emit_project_metrics_telemetry`, `_emit_traffic` and `_emit_item_counts` in `src/devops_cli/github/metrics.py` send the project series with no `repo` attribute, and `_sent_item_series` is one set for the process.
- Source: `project_metrics_cmd` in `src/devops_cli/commands/gh.py` passes `--milestone` and `--limit` to `collect_project_metrics_report` and then emits the report when `--emit-telemetry` is set.
- Source: `RepoRef.key` in `src/devops_cli/github/repo_ref.py` is the casefolded `owner/name`, and ADR 0022 says telemetry uses `key`.
- Test run: the new tests of `tests/github/test_github_metrics.py` and `tests/telemetry/test_telemetry_instruments.py` fail on `origin/main` and pass with the change.

## Existing Tool Considered

The OpenTelemetry Python SDK, already a direct dependency, records and exports the gauges, and each attribute of a point becomes a Prometheus label through the collector. It covers the `repo` label. It does not cover which label sets a repository sent before, or the refusal of a filtered snapshot. The change adds a dict key in `_sent_item_series` and a guard of about 10 lines in the command. Cost: about 2,000 tokens to build, about 100 tokens a quarter to keep and about 1,000 tokens to fix, with about half a day of elapsed time and one CI run. The change deletes the process-wide set of item label sets and the repeated literal `10` of the option and the collector.
