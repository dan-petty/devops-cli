# Proposal: #5165

## Why

Closes #5165, the first item of the tracker #5164. The owner asked on 2026-11-12 for a grade of each agentic workflow from its measured success, with one action for each grade. Each roadmap job already logs one result line for each attempt to Loki (`docs/roadmap/job-success.md`), but no command reads the lines and says how each workflow performs. A person or an agent must write LogQL to see a ratio, and the dashboard row `Roadmap Job Success` shows only the line at 0.80.

## What Changes

- Add `devops roadmap eval grades` (`--repo`, `--window 6h|24h|7d`, `--loki-url`, `--format`/`--json`, `--dry-run`). For each workflow and repository it prints the attempts with `infra=false`, the successes, `p`, the Wilson 95% interval, the grade, the point grade and the range of the interval, the first-pass ratio, the all-attempts ratio, the infrastructure share, the top 3 failure classes, the owner action of the grade, the efficiency measures (tokens and seconds: median, p90 and max for each attempt, and for each success), each version with 10 attempts or more, and the attempts of 24 h and 6 h with the signals `broken` and `infra`.
- Add `roadmap/job_grade.py` with the grade table (floor, rule, name, action, efficiency work), the grade rules and the Wilson interval (statsmodels).
- Add `roadmap/job_grade_report.py`: the planned LogQL metric queries, the report and its text form.
- Add `FIRST_PASS_LIMITS` next to `SUCCESS_RESULTS` in `roadmap/job_result.py`: the first-pass rule of `stage`, `implement` and `fix_plan`, the jobs whose line holds the counts of their fix rounds.
- Add `query_loki_metrics` to `k8s/logql.py`: LogQL instant queries through the private egress client.
- `devops docs generate` writes the grade table into `docs/roadmap/job-success.md` between markers. The section "The 80% rule" goes under the new section "The job grades". CONTEXT.md gets the term "job grade".
- The command, its options and messages are observable behavior, so the change carries a spec delta: the new capability `roadmap-job-grades`.

## Capabilities

- New: `roadmap-job-grades`.

## Impact

- A new read-only command. It sends 13 LogQL metric queries with the 7-day window (12 with the 24-hour or 6-hour window) to Loki and writes nothing.
- `docs/roadmap/job-success.md` is still a hand-written page. Its grade table is generated, as the command matrix of `README.md` is.
- The grade `100` needs first-pass counts. Only the lines of `stage`, `implement` and `fix_plan` hold them today. The other jobs get `n/a` for the first pass and cannot get `100` until their lines get the counts (#5168).
- The change fits one pull request.

## Feasibility

Confirmed against the cluster Loki 3.7.9 (revision `d3b4a2f7`) on 2026-11-12 through a port-forward of `svc/loki` in the namespace `logging`:

- The instant query `sum by (roadmap_job, repo, version, success, infra) (count_over_time(<base> [7d]))` returned 25 series of the 7 jobs. All 107 result lines of 7 days are in the stream `app_kubernetes_io_name="roadmap-service"`, so the base selector of `job-success.md` is correct for now.
- `quantile_over_time(0.9, <base> |~ " tokens=[0-9]+ " | regexp ` tokens=(?P<tokens>[0-9]+) ` | unwrap tokens [7d]) by (roadmap_job, repo)` returned the p90 of each job with tokens.
- A `regexp` stage that does not match a line keeps the line and adds no label, with no `__error__`. So one query grouped by the counts `plan_calls`, `gate_returns`, `verify_rounds`, `repair_rounds` and `after` gives the first-pass counts of every job, and the code applies the rule of each job.
- statsmodels 0.15.0 `proportion_confint(22, 25, alpha=0.05, method="wilson")` gives (0.70044, 0.95833), so the acceptance example holds. With 0 attempts it gives NaN, so the report gives no interval there.
- The acceptance criteria say both "22 of 25 give grade 80" and "29 attempts give too few". The two hold together as the point grade (`80`) and the grade (`too few`), which the issue also names ("the point grade and the grade range").

## Existing Tool Considered

Grafana Explore and the dashboard row `Roadmap Job Success` show a 7-day ratio and the line at 0.80. They give no grade, no interval, no action and no efficiency, and an agent cannot read them as JSON. statsmodels, a current dependency, gives the Wilson interval. Loki gives the counts and the quantiles. The custom code is the grade table, the queries and the report. Cost: about 300,000 tokens to build and 6 hours elapsed; about 20,000 tokens a month to keep the tests and the documents current. The change deletes no internal code.
