# Proposal: #4707

## Why

The panels of `k8s/monitoring/dashboards/devops-cli.json` for the devops commands and the GitHub API are hard to read (#4707). Panel 22 draws a rolling hour at each 2 min step for all jobs on one linear axis, so core (5,873 an hour) hides code_search (less than 10), and it counts the answers 304 that cost no quota. The rolling-hour bars of panels 23 and 24 add up to 474 throttles in 24 h for 21, and to 765 s of wait for 34.7 s. Panels 2, 11, 12, 18 and 27 draw 14 to 126 lines, and panel 27 repeats 47 to 90 times. Panels 3, 4, 11, 15 and 27 put counts on a seconds axis. The dashboard opens on 1 h with a 10 s refresh, while an OTLP series gets about 4 samples an hour. The owner direction of 2026-11-12 adds the golden signals of the devops commands as the first row, one unit for each panel, at most 3 series and "Other" in a time series, sorted breakdown tables that link to the golden signals, titles that name the signal and the measure, and a description on each panel.

## What Changes

- The first row of `devops-cli.json` is "Golden signals: devops commands", in the order of the SRE book, `w12 h8` each: latency (p50, p95 and p99 of the successful calls, `s`), traffic (calls per hour as bars, `short`), errors (the share of the calls that failed, `percentunit`, y from 0) and saturation (the spend of the Service GitHub budget over its limit, `percentunit`, with a 1 px dashed line at 100 %). Latency, traffic and errors read `devops_cli_subcommand_duration_seconds`, the histogram with the label `status`, and filter on `$job`, `$command` and `$sub_command`.
- The row "Breakdown by command": a sorted bar gauge of the calls of each command in the range, and a table of each command with calls, errors, error share, p50, p95 and p99 in the range. The row "Sub-commands": one table of each sub-command with the same columns. The panels 12 and 27 go, so no panel repeats. Each table is sorted by errors, then by calls, and a row links to this dashboard with `var-command` (and `var-sub_command`) set to the row.
- The GitHub API row: "GitHub quota: core requests per hour" (bars of the requests that cost quota by job, the answers 304 as the series "free (304)", and the Service budget limit as a dashed line), "GitHub quota: requests of the other resources per hour" (graphql, search and "Other"), a stat and a table of the throttles and their wait in the range, and "GitHub quota: GraphQL points per hour" by job with a dashed line at 5,000 points. Bars use a Min interval of 1h and `increase(...[$__interval])`, so the bars add up to the total.
- The panels of reviews, findings and RAG become tables and sorted bar gauges over the range (13 joins 3, and 15 joins 4). The embedding cache hit share reads `[$__rate_interval]` with a Min step of 15m. The error stream shows only the levels error, critical and fatal.
- The dashboard opens on `now-24h` and refreshes each minute.
- `tests/prometheus/test_k8s_monitoring_dashboards.py` checks the chart rules for each panel outside the Service rows: no repeat, a description, a title "Signal: measure", one unit and no second axis in a panel that is not a table, no count on a duration axis, `or vector(0)` only in a stat, and in a time series only the windows `[$__interval]` and `[$__rate_interval]` and no line for each command. #4718 applies the same rules to the Service rows.
- The query harness of #4680 gets the keys `bars` and `total`: a case adds up the bars of its panel over a range and checks the sum within 1 % of the total. `tests/fixtures/dashboard_queries/devops-cli.yaml` gets cases for the golden signals, the command tables, the GitHub requests and the throttles.
- The dashboard is a manifest, so the change has a spec delta. It fits one pull request.

## Capabilities

### New Capabilities

- `devops-cli-dashboard`: the golden signals row, the breakdown tables and the chart rules of `devops-cli.json`.

### Modified Capabilities

- `command-telemetry`: the error stream panel and the sub-command row.
- `github-api-metrics`: the GitHub API row.
- `metric-instruments`: the embedding cache hit share panel.

## Impact

- `k8s/monitoring/dashboards/devops-cli.json`: the rows above "AI Spend & Economics" and the row "GitHub API" change. The Service rows move down and keep their queries (#4718).
- The panel ids 12, 13, 15 and 27 go. A link to one of them opens the dashboard with no panel.
- `k8s/README.md` names the new core requests panel in the action of `RoadmapServiceGitHubRequestsHigh`. `docs/TESTING.md` tells how to add a bars case.
- After the merge, #2703 closes as not planned with a link to this change, because no panel repeats.

## Feasibility

- Live labels (Prometheus, 2026-11-12): `devops_cli_command_duration_seconds` has no label `status`; `devops_cli_subcommand_duration_seconds` has `status` ok or error (`src/devops_cli/telemetry/instruments.py:55`). Calls in 24 h by command: gh 10,491, ci 1,253, openspec 914, pr 680, roadmap 514, docs 234, and 15 more under 100.
- The sub-command histogram has 831 fewer ci calls and 429 fewer gh calls than `devops_cli_command_total` in 24 h: `OTelTyper.callback` (`src/devops_cli/core/cli.py:299`) sends no point for the body of a command group, such as `devops ci`. The golden signals use the histogram as the owner asked, the bar gauge and the command table count every run from `devops_cli_command_total`, and #5192 adds the missing points.
- A sub-command series gets a median of 4 samples an hour, so `$__rate_interval` with a Min step of 15m gives a window of at least 1 h. Through `/api/ds/query` of Grafana 13.3.1, the latency target ran as `[1h0m0s]` with a step of 15m, and the traffic target as `[1h]` with a step of 1h and 25 points over 24 h.
- `{service_name="devops-cli"} | detected_level=~"error|critical|fatal"` gives 13 records in 24 h; the old selector gave 13 errors and 131 warnings.
- The live criterion: at 2026-11-12T19:00Z the hourly core bars of roadmap-service add up to 47,591, and `sum(increase(devops_cli_github_requests_total{job="roadmap-service", resource="core", status!="304"}[24h]))` is 47,796 (0.4 %).
- promtool 3.15.1 evaluates the subquery `sum_over_time((q)[24h:1h])` at steps aligned to the hour, as Grafana aligns a range query. Native histogram quantiles interpolate in the bucket: the p95 of calls in the bucket from 1 to 2 s is 2^0.95 s.
- The preview copy of the dashboard saved in Grafana 13.3.1 with no error, and its schema kept the new fields. The image renderer is not installed (#5185), so no panel image was checked.

## Existing Tool Considered

- The built-in Grafana panel types (time series bars, bar gauge, table, stat) and PromQL do the change. No new code under `src/`.
- grafana/dashboard-linter v0.4.0 has no rule for units, second axes, repeats, `$__range` or `or vector(0)`, and takes no custom rules (#4743). The chart rules are a test of `devops-cli.json` here, and #4743 moves the window, range and zero rules into `devops grafana dashboards lint` for all dashboards.
- Cost of the test code: about 40,000 tokens to build, 1,000 tokens a month to keep, 1 h elapsed.
- No internal code is deleted.
