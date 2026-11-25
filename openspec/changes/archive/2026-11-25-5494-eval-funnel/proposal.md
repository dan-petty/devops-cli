# Proposal: #5494

## Why

The job grades of `devops roadmap eval grades` rate each job alone. Across multiple hops, per-job ratios hide end-to-end drops, so the pipeline split tracker `#5482` requires an item cohort funnel grouped by ISO week and split by delivery path (`G1` vs `continue`), with Wilson 95% intervals, smallest detectable change, pass durations, `in progress` handling, and Loki `tokens` / `cost_usd_micros` attribution. No command provides this funnel report. Closes #5494.

## What Changes

- Add `devops roadmap eval funnel --since <date> [--repo <owner/name>] [--loki-url <url>] [--json] [--dry-run]`.
- Read issue listings, issue timelines, pull request heads, and delivery `ready_for_review` events through `GitHubSession`.
- Query `RESULT_LINES` in Loki with `query_loki_metrics` to sum `tokens`, `cost_usd_micros`, and result-line presence per `(repo, roadmap_job, item)`.
- Group cohort items by ISO week of their latest active `status/ready` label event, split by path (`G1` vs `continue`), compute per-step conversion, Wilson 95% bounds, smallest detectable change, median/p90 durations, young `in progress` counts, per-success token and micro-USD cost totals, per-item New-to-staged tokens, and missing result-line counts.
- Render human-readable tables and `--json` output, and add a `devops roadmap eval funnel` section to `docs/roadmap/job-success.md`, regenerating CLI docs.

This change adds a new CLI subcommand, options, help messages, and report output observable to users, so it carries a spec delta for `roadmap-eval-funnel`. Fits in one pull request; the post-release live cluster run is tracked separately in `#6256`.

## Capabilities

### New Capabilities

- `roadmap-eval-funnel`: Item-cohort funnel reporting by ISO week and path (`G1` vs `continue`) from GitHub timeline events and Loki result lines.

### Modified Capabilities

None.

## Impact

- Adds `src/devops_cli/roadmap/job_funnel.py` and `src/devops_cli/commands/roadmap_eval_funnel.py`.
- Registers `funnel` in `src/devops_cli/commands/roadmap_eval.py`.
- Adds help and message strings in `src/devops_cli/lang/en/help.py` and `src/devops_cli/lang/en/messages.py`.
- Updates `docs/roadmap/job-success.md` and generated CLI docs (`docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`).
- Adds offline tests under `tests/roadmap/test_job_funnel.py` and `tests/commands/test_roadmap_eval_funnel.py`.

## Feasibility

Confirmed against `origin/main`:

- No funnel subcommand exists in `src/devops_cli/commands/roadmap_eval.py`.
- `wilson_interval` (`src/devops_cli/roadmap/job_grade.py:194-201`) wraps `statsmodels.stats.proportion.proportion_confint` (`0.15.0` locked).
- `RESULT_LINES`, `_ITEM_FIELDS`, and `_count_label` (`src/devops_cli/roadmap/job_grade_report.py:128-142,345-346`) and `query_loki_metrics` (`src/devops_cli/k8s/logql.py:391-417`) already query Loki instant metrics on `tokens` and `cost_usd_micros` logged by `log_job_result` (`src/devops_cli/roadmap/job_result.py:210-309`).
- `GitHubSession` (`src/devops_cli/github/session.py:110-154`) paginates REST listings and issue timelines (`/repos/<owner>/<name>/issues/<n>/timeline`). Real timelines verified on `#5516` and `#4416` via `devops gh api` confirm `labeled`/`unlabeled` and `cross-referenced` events and confirm that `/pulls` and delivery PR `/timeline` supply `head.ref` and `ready_for_review`.

## Existing Tool Considered

- `statsmodels` (`proportion_confint`, in use and locked) provides the Wilson 95% confidence interval for each step's share.
- No open maintained tool joins GitHub REST issue timeline events with this repository's `roadmap job result:` lines in Loki (200,000 to 400,000 agent tokens and 0.5 to 1 day to build in-house; ~10% quarterly upkeep).
- Deletes no existing internal code.
