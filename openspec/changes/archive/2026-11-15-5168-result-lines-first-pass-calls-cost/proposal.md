# Proposal: #5168 feat(roadmap): result lines state first-pass, model calls and cost

## Why
Closes #5168.
The owner grades a workflow by success with no fix rounds and by cost, time, and token efficiency.
The result line of `roadmap/job_result.py` gives neither for most jobs:
- No line states whether the attempt succeeded with no fix round.
- `tokens` and `seconds` exist only for `stage`, `implement`, and `fix_plan`. No line gives model calls, cost in money, or GitHub requests.
- `retitle` makes one model call for each item and writes no line.
- The spend ledger (`ai/spend/ledger.py`) keeps `cost_usd` for each request, but no attempt adds it up.
- The `row` label of `devops_cli_ai_tokens_total` and `devops_cli_ai_spend_usd_total` had no row label in Job pods.

## What Changes
1. Add `first_pass=<true|false>` to each result line right after `infra=<true|false>`. Add the `FIRST_PASS` table mapping each job to its first-pass count limits.
2. Add an attempt context (`attempt_context`, `AttemptContext`) that tallies `model_calls`, `tokens`, `seconds`, `cost_usd_micros` (integer micro-dollars), and `gh_requests`. The spend ledger adds AI model calls, tokens, and cost. The paced GitHub session adds GitHub requests. The writer adds these counts to every result line.
3. Add the counts needed by the first-pass rules: `tries` (refine), `round` (refine_judge), `returns` (alternatives), and `fallbacks` (intake).
4. Add `RoadmapJob.RETITLE` with results `retitled`, `kept`, and `failed`, and intended results `retitled` and `kept`. Retitle logs one result line for each item attempt.
5. Set `request_scope` in Job pods so `devops_cli_ai_tokens_total` and `devops_cli_ai_spend_usd_total` carry the `row` label of the job.
6. Update `docs/roadmap/job-success.md` and spec `openspec/specs/roadmap-service-logs/spec.md`.

## Capabilities
- `roadmap.job_result`: `first_pass` field on each result line and `FIRST_PASS` table.
- `roadmap.job_result`: `attempt_context` tracking model calls, tokens, seconds, micro-dollars cost, and GitHub requests.
- `roadmap.retitle`: logs one result line for each attempt.
- `roadmap.telemetry`: Job pods set `request_scope` with their job row.

## Impact
- Loki result lines provide first-pass success ratios, efficiency metrics (tokens, seconds, model calls, cost), and request counts across all roadmap workflows.
- Downstream funnel and grade queries can read first-pass and cost metrics directly.

## Feasibility
- Verified on `origin/main`:
  - `job_result.py` defines `SUCCESS_RESULTS` and `FIRST_PASS_LIMITS`.
  - `ledger.py` records requests and prices in `track_request_spend`.
  - `rate_limiter.py` counts GitHub requests in `count_request`.
  - `job-success.md` and `roadmap-service-logs` specify the result line contract.

## Existing Tool Considered
OpenTelemetry spans carry similar counts, but Loki holds the result lines and spans keep no prompt text by privacy defaults. LiteLLM spend logs keep request cost but do not know the roadmap attempt context. Custom code: attempt context and table.
