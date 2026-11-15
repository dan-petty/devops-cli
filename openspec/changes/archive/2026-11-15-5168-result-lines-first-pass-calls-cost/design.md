# Design: #5168 feat(roadmap): result lines state first-pass, model calls and cost

## Context
Roadmap jobs write one log line for each attempt (`log_job_result`). Issue #5168 adds first-pass indicators and efficiency metrics (model calls, tokens, seconds, cost in micro-dollars, and GitHub requests) across all roadmap jobs.

## Decisions

### 1. `FIRST_PASS` Table and `first_pass` Field Position
- The `first_pass=<true|false>` field is positioned immediately after `infra=<true|false>` in the result line:
  `roadmap job result: job=<job> repo=<owner/repo> item=#<n> result=<result> success=<true|false> class=<class> infra=<true|false> first_pass=<true|false> <count>=<n> ... version=<version>`
- This position preserves backward compatibility with existing Grafana logql queries that parse `result=(?P<result>\S+) success=(?P<success>\S+) class=(?P<failure_class>\S+) infra=(?P<infra>\S+)`.
- `FIRST_PASS` table maps each job to its `CountLimit` tuple:
  - `stage`: `staged`, `plan_calls` <= 1, `gate_returns` == 0, `verify_rounds` <= 1 (missing `plan_calls` fails first-pass)
  - `implement`: `ready`, `repair_rounds` == 0, `extensions` == 0 (missing `extensions` counts as 0)
  - `fix_plan`: `revised` or `cleared`, `gate_returns` == 0, `verify_rounds` <= 1, `after` == 0 (missing `after` counts as 0)
  - `refine`: success (`ready`, `person`, `split`, `blocked`) with `tries` <= 1
  - `refine_judge`: `approved`, `round` <= 1, `findings` == 0
  - `alternatives`: verdict with `returns` == 0
  - `intake`: `placed` or `duplicate`, `fallbacks` == 0
  - `retitle`: `retitled` or `kept`, `model_calls` <= 1

### 2. Attempt Context
- Define `AttemptContext` and `attempt_context()` in `devops_cli.roadmap.job_result`.
- `AttemptContext` holds:
  - `start_time: float` (wall clock via monotonic or perf_counter)
  - `model_calls: int`
  - `tokens: int`
  - `cost_usd_micros: int` (integer micro-dollars, `int(round(cost_usd * 1_000_000))`)
  - `gh_requests: int`
- `track_request_spend` in `ai/spend/ledger.py` calls `record_attempt_ai(tokens, cost_usd)` on the active attempt context. Local model calls add 0 to cost and add their tokens.
- `count_request` in `github/rate_limiter.py` calls `record_attempt_gh()` on the active attempt context.
- When `log_job_result` runs within an active attempt context, it injects `model_calls`, `tokens`, `seconds`, `cost_usd_micros`, and `gh_requests` into the result line counts.

### 3. Counts for Specific Jobs
- `refine`: `_log_attempt` passes `tries` on the item.
- `refine_judge`: `judge` passes `round` on the item.
- `alternatives`: `_log` passes `returns` (number of retry messages triggered by output check).
- `intake`: `_count_candidate` passes `fallbacks` (number of model fallbacks).

### 4. `RoadmapJob.RETITLE`
- Add `RETITLE = "retitle"` to `RoadmapJob`.
- `SUCCESS_RESULTS[RoadmapJob.RETITLE] = frozenset({"retitled", "kept"})`.
- Retitle operations log one result line for each item attempt.

### 5. `request_scope` in Job Pods
- `devops roadmap stage --job-item` and `devops roadmap step fix-plan` run within `request_scope(repo=target, row=job_name)`, ensuring `row` is correctly populated on AI telemetry counters.
