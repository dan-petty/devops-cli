# Design

## Decisions

1. **ISO-week cohorts with `unlabeled` cancellation**: Parse `--since` as UTC (`datetime.fromisoformat`, treating naive dates as `00:00:00Z`). Inspect each issue's timeline chronologically. Record `status/ready` on `labeled`. An `unlabeled` `status/ready` event cancels an earlier `ready_at` unless a forward workflow label (`status/planned`, `status/in-progress`, `status/in-review`, `status/blocked`) is labeled within 60 seconds without an intervening `status/new` label (matching atomic `write_status` transitions observed on `#4416` and `#5516`). Keep items whose latest `ready_at >= since` in cohort `YYYY-Www`. Only timeline events and pull requests belonging to the current pass (after any canceled `status/ready`) count toward that pass's steps.

2. **Path split (`G1` vs `continue`) and step timestamps**:
   - Classify cross-referenced pull requests via `pull_kind(title)` (`PLAN_TITLE_PREFIX` `"docs(openspec): plan #"` in `src/devops_cli/roadmap/pr_verdict.py`).
   - Use `head.ref` directly if present in a timeline payload; otherwise resolve missing branch names from `GET /repos/{owner}/{name}/pulls?state=all&sort=updated&direction=desc&per_page=100` (with `/pulls/{n}` fallback if older).
   - Resolve delivery PR `ready_for_review` from the delivery PR's timeline when non-draft and missing inline `ready_for_review`, falling back to PR `created_at` when created non-draft without a `convert_to_draft` event.
   - Same non-empty `head.ref` between plan PR and delivery PR selects path `continue` (`plan PR open to ready delivery PR`, `ready delivery PR to merge`). Distinct head branches (or merged plan PR before delivery PR opens) select path `G1` (`plan PR merged to ready delivery PR`, `ready delivery PR to merge`). Both share `New (placed) to Ready` and `Ready to plan PR open`.

3. **Window-wide `p90` cutoff, Wilson interval, and smallest change**:
   - Compute step `median` and `p90` with linear interpolation (`rank = q * (len - 1)`) over completed pass durations.
   - Compute window-wide step `p90` across all cohorts in the `--since` window. Any item still open in a step whose age (`now - step_started_at`) is strictly below that window `p90` (or when `p90` is `None` for that step) counts in `in_progress` outside `n` and `share`.
   - Reuse `wilson_interval(successes, n)` (`src/devops_cli/roadmap/job_grade.py`). Smallest detectable change equals half the Wilson 95% interval width `(upper - lower) / 2`.

4. **Loki result-line queries and missing lines**:
   - Reuse `RESULT_LINES`, `_ITEM_FIELDS`, `_count_label`, and `query_loki_metrics` to query `/loki/api/v1/query` with `count_over_time` and `sum_over_time` (`tokens` and `cost_usd_micros`) grouped by `(repo, roadmap_job, item)`.
   - An item in a cohort with 0 Loki result lines increments `missing_result_lines` and contributes `0` tokens and `0` micro-USD cost while staying in `n`.
   - Each step's `tokens_per_success` and `cost_usd_micros_per_success` equal the cohort's summed `tokens` and `cost_usd_micros` divided by that step's pass count (`None` when `0` passes). Each item reports `new_to_staged_tokens`, summing pre-delivery jobs (`intake`, `refine`, `refine_judge`, `alternatives`, `stage`, `retitle`).

5. **CLI validation and `--dry-run`**:
   - Validate `--since`, `--repo` (`RepoRef`), and non-empty `service.repos` (when `--repo` is omitted) before any HTTP request.
   - `@dry_run_class("request-plan")` prints the GitHub REST listing/timeline requests and Loki metric queries and sends 0 requests.
   - Output supports human-readable tables and `--json`.

## Rejected alternatives

- **Use first `status/ready` event or job record time instead of latest `status/ready` after `unlabeled` cancellation**: Rejected because returning an item to `status/new` (`docs/ROADMAP_WORKFLOW.md:57`) restarts its funnel pass; `src/devops_cli/github/metrics.py:535-546` already cancels earlier `labeled` timestamps on `unlabeled`.
- **Infer path from plan PR merge state alone instead of comparing head branches**: Rejected because a `continue` delivery reuses the plan branch even if commit/PR states vary, whereas comparing head branches directly captures branch reuse vs new branch (`docs/ROADMAP_WORKFLOW.md:25`).
- **Use per-cohort `p90` as the `in progress` threshold**: Rejected because cohorts with fewer than 30 items produce noisy cutoffs and cause an item to alter its own step cutoff (`docs/guidelines/agentic-jobs.md:81,113,153`).
- **Exclude items with no Loki result line from `n`**: Rejected because omitting items without result lines inflates pass shares and conceals missing telemetry from `src/devops_cli/roadmap/job_result.py:214`.
- **Add `--format` alongside `--json` (`roadmap_eval_grades.py:57-62`)**: Rejected because `eval funnel` has only text and JSON outputs via `--json`.
