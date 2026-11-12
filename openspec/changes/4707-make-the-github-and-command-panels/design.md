# Design

## Decisions

- **The golden signals read the sub-command histogram.** It is the only command histogram with the label `status`, so latency can be of the successful calls only and the error share comes from the same calls. With All, each panel shows one series for all commands. A table row link sets `var-command` or `var-sub_command`, so the reader moves from the breakdown to the signals over time.
- **The command bar gauge and the command table count every run.** They read `devops_cli_command_total` and `devops_cli_command_duration_seconds`, so a run of `devops ci` with no sub-command counts. The table says that its quantiles include failed calls. #5192 makes the histogram complete.
- **Bars are hourly increases at a Min interval of 1h.** Each bar is `increase(...[$__interval])` with bar alignment "before", so one bar holds the hour before its time and the bars add up to the total. The rolling `[1h]` at a 2 min step counted each sample in 30 bars.
- **Windows of lines follow the step.** A line reads `[$__rate_interval]` with a Min step of 15m: an OTLP series gets about 4 samples an hour, and the window holds at least 1 h.
- **Reference lines are constant queries.** The budget limit, 100 % and 5,000 points are targets with a 1 px dashed line style `2 2` (docs/DESIGN.md C8, C14). The colors stay the Grafana defaults (#4762).
- **Unstacked bars in the quota panels.** Each job uses its own budget or token, so a stack would compare the sum of the jobs with the limit of one. The bars have a fill of 50 %, so a lower bar stays visible.
- **The chart rules are a test of this dashboard.** `readability_problems` in `tests/prometheus/test_k8s_monitoring_dashboards.py` checks each panel outside the rows that #4718 owns. #4718 removes the list of its rows, and #4743 moves the window, range and zero rules into the linter for all dashboards.
- **Tables merge one instant query for each column.** Each target has the format table, and the transformations merge and organize name the columns. The value columns have their own units, so the one-unit rule does not apply to a table. The last transformation, `sortBy`, sorts by errors, then by calls: in Grafana 13.3.1 it sorts by each field of its list (`sortDataFrames` in `packages/grafana-data/src/transformations/transformers/sortBy.ts`). The option `sortBy` of the table shows the same order in the header.
- **The harness adds up bars with a subquery.** A case with `bars` runs `sum_over_time((q)[<bars>:<__interval>])`, and `total` holds the sum that the series add. The test checks the expected sum within 1 % of the total, and promtool checks the sum.

## Rejected alternatives

- **Latency from `devops_cli_command_duration_seconds`.** It has no label `status` (live labels: command, job, instance, cluster, otel_scope_name), so it cannot give the latency of successful calls.
- **A line for each command.** 21 commands in 24 h, gh with 10,491 calls and 15 commands under 100: the small lines lie on 0. The tables and the bar gauge give each command, and C7 allows 3 series and "Other".
- **The repeat of a latency panel for each sub-command.** 68 sub-commands in 24 h, 132 in 7 d: 47 to 90 panels. #2703 tried to hide the empty ones. A table with a link shows the same values in one panel.
- **Stacked quota bars.** The stack height would mix the App installation of the Service and the Jobs with the token of a person, and the limit line holds for one of them.
- **A threshold line for the reference.** C14 asks for a constant query with a display name, and a threshold step takes a threshold color, which #4762 owns.
- **A sort in PromQL with `sort_desc`.** The merge of the instant queries of a table does not keep the order of a query, and `sort_desc` sorts by one value only.
