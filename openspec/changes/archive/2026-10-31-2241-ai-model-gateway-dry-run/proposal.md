# Proposal: Dry-Run Classification for AI Model and Gateway Commands

## Why
Issue #2241 is part of #886. The owner dry-run rule states that a dry run makes no external request and returns the requests that the real run will make. Eighteen AI model and gateway commands in `src/devops_cli/commands/ai.py`, `src/devops_cli/commands/ai_gateway.py`, `src/devops_cli/commands/benchmark.py`, and `src/devops_cli/commands/ai_chaos.py` do not follow this rule:
- Sixteen commands make external requests to inference endpoints, Kubernetes, Prometheus, or Valkey without a request plan.
- One command (`ai gateway failover`) changes local state without a `--dry-run` preview.
- One command (`ai gateway render`) makes no external request, but lacks the `no-external-request` classification.

This change classifies all eighteen commands, adds request plans, adds missing `--dry-run` options, and removes echo-only previews.

## What Changes
- Add the `request-plan` classification and request plan output to:
  `ai agents`, `ai benchmark`, `ai chaos-model`, `ai chat`, `ai gateway connect`, `ai gateway load`, `ai gateway probe-backend`, `ai gateway routes`, `ai gateway status`, `ai gateway tune`, `ai models`, `ai pipeline`, `ai preload`, `ai prewarm`, `ai prompt-eval`, and `ai test`.
- Add `--dry-run` to commands that previously lacked the option:
  `ai agents`, `ai chat`, `ai gateway connect`, `ai gateway failover`, `ai gateway load`, `ai gateway probe-backend`, `ai gateway routes`, `ai gateway status`, `ai gateway tune`, `ai models`, `ai preload`, `ai prewarm`, and `ai test`.
- Add the `no-external-request` classification to local preview and mark-only commands:
  `ai gateway failover` (local preview) and `ai gateway render` (mark only).
- Remove obsolete echo-only previews (`render_dry_run_result`) from `ai benchmark`, `ai chaos-model`, `ai pipeline`, and `ai prompt-eval` with no backwards compatibility shim.
- Zero external requests during dry run.
- Return real result types marked as dry runs when `--format json` or `--json` is supplied.
- Remove all eighteen commands from `tests/fixtures/dry_run_gaps.json`.
- The change fits in one pull request.

## Feasibility
- Verified the eighteen commands in the codebase:
  - `ai.py`: `agents`, `chat`, `models`, `pipeline`, `preload`, `prewarm`, `prompt_eval_cmd`, `test`.
  - `ai_gateway.py`: `status_cmd`, `routes_cmd`, `connect_cmd`, `failover_cmd`, `probe_backend_cmd`, `tune_cmd`, `load_cmd`, `render_cmd`.
  - `benchmark.py`: `run_benchmark`.
  - `ai_chaos.py`: `run_chaos_model_cmd`.
- All eighteen commands are listed in `tests/fixtures/dry_run_gaps.json`.
- External requests are pure HTTP client calls, kubectl invocations, or Prometheus / Valkey queries.

## Existing Tool Considered
The change uses existing internal abstractions:
`devops_cli.dry_run.requests.PlannedRequest`, `render_request_plan`, and `@dry_run_class`.
No third-party library is needed. Obsolete echo-only previews are removed.
