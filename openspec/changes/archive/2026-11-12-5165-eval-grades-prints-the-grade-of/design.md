# Design

## Decisions

- **Metric instant queries, not log lines.** The report sends LogQL metric queries to `/loki/api/v1/query`: `count_over_time` for the counts, and `quantile_over_time`, `max_over_time` and `sum_over_time` over `unwrap` for tokens and seconds. A metric query counts every line in the window, so no line limit applies. The existing `execute_loki_query` reads log lines from `query_range` and has a line limit, so `k8s/logql.py` gets `query_loki_metrics`, which uses the same private egress client (`http_client(EgressLevel.PRIVATE)`) and `resolve_loki_url`. The vector reply has the Prometheus form, so `PrometheusQueryResult.from_instant_response` parses it.
- **One query for each measure.** The 7-day report sends 13 queries: the counts by job, repository, version, success and infra; the failure classes; the first-pass counts; 8 efficiency queries; and the counts of 24 h and 6 h. A trend window that is the report window is not queried twice.
- **First pass from the counts.** One query groups the successes by the counts of the fix rounds, and `FIRST_PASS_LIMITS` in `roadmap/job_result.py` applies the rule of each job in code. The table sits next to `SUCCESS_RESULTS`, where #5168 adds the `first_pass` field to the line from the same table.
- **Point grade and grade.** The report gives both: the point grade is the floor of `p` at any count of attempts, and the grade is `too few` under 30 attempts. The range is the grades of the two Wilson bounds; it stops at `90`, because `100` is a rule of first passes, not of a ratio.
- **Infrastructure cuts.** `p` and the grade count only the attempts with `infra=false`. The report shows the all-attempts ratio and the infrastructure share beside them.
- **Rows.** One row for each job and repository with a line in a window, in the order of `RoadmapJob`, and one row with no repository for each job with no line, so a silent job is visible.
- **Tables in one place.** The grade table is `GRADE_POLICIES` in `roadmap/job_grade.py`. The docs generator writes it between markers in `docs/roadmap/job-success.md`, as it writes the command matrix of `README.md`, so `devops docs check` fails when the page and the code differ.
- **The 80% rule stays.** The dashboard descriptions and `docs/ROADMAP_WORKFLOW.md` cite the hold rule of 80% for the tuning of caps. It stays as a subsection of "The job grades" until #5173 makes it the held-grade rule for each floor.

## Rejected alternatives

- **Log-line queries with `execute_loki_query`.** It reads `query_range` with a line limit (default 100) and parses the lines in Python. A 7-day window of intake alone had 72 lines on 2026-11-12, and the count grows with each job, so the report would undercount without a sign.
- **A LogQL numeric filter for the first pass of each job.** `| plan_calls <= 1` on a line with no `plan_calls` label adds a label filter error, and it needs one query for each job. The grouped query with the rule in code needs one query and has no error.
- **A new HTTP client for Loki.** The project has one entry point for httpx2 clients (`http/entry.py`) and one Loki module (`k8s/logql.py`).
- **An "all repositories" row for each job.** Quantiles do not add across repositories, so it needs a second set of 8 efficiency queries. The grade is for each workflow and repository (#5173 keeps one issue for each).
- **Grafana dashboard panels only.** They give no interval, action or JSON for an agent; #3655 adds the gauges after #5172 records the grades in Prometheus.
