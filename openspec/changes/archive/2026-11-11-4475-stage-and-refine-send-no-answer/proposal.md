# Proposal: #4475

## Why
Since #4237, the stage, refine and alternatives runs add nothing to `devops_cli_ai_model_answers_total`. The last sample of job `roadmap-service` is at 2026-11-09T17:32:53Z. #4237 removed the `record_run_spend` call from `investigate`, and the hook that `build_agent` adds writes one spend record for each request but no answer count. The hook also gives the ledger no cached prompt tokens, so a stage or refine request costs the full input rate for the tokens that the provider read from its cache, while an implement step costs the cached rate (#4403). And no AI series names the job row that sent a request, so no query splits the tokens of stage from those of refine. Closes #4475.

## What Changes
- The spend hook of `build_agent` adds one count to `devops_cli_ai_model_answers_total` for each reply that names its model, and gives `track_request_spend` the cached prompt tokens of the reply.
- `model_answer_labels` in `devops_cli.ai.spend.ledger` gives the labels of one answer count: asked, answered, fallback and row. The hook and `record_run_spend` both use it, so the fallback rule has one place.
- `track_request_spend` adds the label `row` to `devops_cli_ai_requests_total`, `devops_cli_ai_tokens_total` and `devops_cli_ai_spend_usd_total`. The value is the job row of the `request_scope` context variable, which the Service sets for each row, or `other`.
- `devops roadmap implement --confirm` applies its plan in the scope of the row `implement`, so the runner Job names that row on its AI and GitHub series.

## Capabilities
- Modified: `ai-spend-pricing`.

## Impact
- `src/devops_cli/ai/client/factory.py`, `src/devops_cli/ai/spend/ledger.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`.
- Series: a series of the Service splits into at most one series for each row that uses its model and `other`, 6 of them. In the 7 days to 2026-11-11, roadmap-service sent 53 series of the four (tokens 32, spend 8, requests 11, answers 2), so at most 318 with the row. A runner Job and a command line send one row.
- The ledger keeps one row for each request. No request counts two times: the implement step builds its agent without the hook of `build_agent` and records through `record_run_spend` only.

## Feasibility
- `git log -S record_run_spend --oneline` names 5edd7a54 (#4237). Its diff removes `record_run_spend(model, messages, ..., stage="analysis")` from `src/devops_cli/roadmap/refine/refine_investigation.py` and adds the `after_model_request` hook to `build_agent`.
- Prometheus: `max by (job) (max_over_time(timestamp(devops_cli_ai_model_answers_total)[2d:5m]))` gives 2026-11-09T17:32:53Z for `roadmap-service` and 2026-11-10T20:36:29Z for `devops-cli-job` (the runner Jobs).
- Prometheus: the `reasoning` tokens of `roadmap-service`, which only the hook sends, grew from about 72K to about 1.4M in 6 hours after 17:32Z. So the spend records did not stop: the premise of a lost spend record is false, and only the answer count, the cached tokens and the row are missing.
- The cached input rate: a request on the DeepSeek group with 900,000 of 1,000,000 prompt tokens from the cache costs 0.10192 USD through the hook and 0.033477 USD through `record_run_spend`.
- `request_scope` (`src/devops_cli/github/request_scope.py`) holds the row of each Service row (`run.py`, `_execute_due_rows`) and `other` outside a row, so its values are bounded by the due table.

## Existing Tool Considered
- pydantic-ai `Hooks(after_model_request=...)`, the seam that #4237 added, sends the count; the OpenTelemetry counters of `devops_cli.telemetry.instruments` carry the label. No new tool or library is needed.
