# Design: Dry-Run Classification for AI Model and Gateway Commands

## Context
Under issue #886 and sub-issue #2241, commands that communicate with external inference models, gateway proxies, Kubernetes, Prometheus, or Valkey must support `--dry-run` by outputting an ordered sequence of planned external requests without initiating network or process calls.

## Architecture & Module Organization
- Create `src/devops_cli/ai/ai_plans.py`:
  - Contains deterministic plan functions returning `list[PlannedRequest]`:
    - `plan_ai_agents(repo, template)`
    - `plan_ai_benchmark(models, servers, benchmark_type)`
    - `plan_ai_chaos_model(mode, primary_provider, primary_model, fallback_provider, fallback_model)`
    - `plan_ai_chat(persona, model)`
    - `plan_ai_gateway_connect(context, namespace, service)`
    - `plan_ai_gateway_load(window)`
    - `plan_ai_gateway_probe_backend(backend, backend_url)`
    - `plan_ai_gateway_routes(gateway_url)`
    - `plan_ai_gateway_status(gateway_url)`
    - `plan_ai_gateway_tune(model, gateway_url)`
    - `plan_ai_models()`
    - `plan_ai_pipeline(prompt, personas)`
    - `plan_ai_preload()`
    - `plan_ai_prewarm(model, evict, urls)`
    - `plan_ai_prompt_eval(producer, dataset)`
    - `plan_ai_test(prompt, url)`
  - Mask secrets and API keys: use `<api-key>` or `<token>` placeholders.
- Update `src/devops_cli/commands/ai_gateway.py`:
  - Decorate `status_cmd`, `routes_cmd`, `connect_cmd`, `probe_backend_cmd`, `tune_cmd`, `load_cmd` with `@dry_run_class("request-plan")`.
  - Add `--dry-run` to all commands missing it.
  - In each command, intercept `if dry_run or is_dry_run():` to emit request plan and return early.
  - Decorate `failover_cmd` with `@dry_run_class("no-external-request")`, add `--dry-run`, simulate failover without writing state.
  - Decorate `render_cmd` with `@dry_run_class("no-external-request")`.
- Update `src/devops_cli/commands/ai.py`:
  - Decorate `agents`, `chat`, `models`, `pipeline`, `preload`, `prewarm`, `prompt_eval_cmd`, `test` with `@dry_run_class("request-plan")`.
  - Add `--dry-run` where missing.
  - Remove echo-only `render_dry_run_result`.
- Update `src/devops_cli/commands/benchmark.py`:
  - Decorate `run_benchmark` with `@dry_run_class("request-plan")`.
  - In `run_benchmark`, return early on dry run with planned requests.
- Update `src/devops_cli/commands/ai_chaos.py`:
  - Decorate `run_chaos_model_cmd` with `@dry_run_class("request-plan")`.
  - In `run_chaos_model_cmd`, return early on dry run with planned requests.
- Update `tests/fixtures/dry_run_gaps.json`:
  - Remove the eighteen commands.

## Invariant and Safety Considerations
- Conftest guards: Network, socket, and subprocess connections are forbidden in dry run.
- No swallowed exceptions: Specific error types only; no unhandled `try-except-pass`.
- Return real result types on JSON output: Ensure models support `dry_run` and `requests`.
