# Design: AI Runs, Cost, and Cache Dry-Run Behavior

## Architecture Overview
Dry-run behavior enforces zero outbound network, socket, subprocess, Kubernetes, or Valkey operations when previewing external requests.

### Request Plan Builders (`src/devops_cli/ai/ai_plans.py`)
Add pure request planning functions:
- `plan_ai_cost_update_pricing(source: str | None = None, reset: bool = False, timeout: float = 15.0) -> list[PlannedRequest]`: Plans HTTP GET to the source URL or genai-prices upstream catalog endpoint. If reset is requested, returns empty list as it resets local snapshot.
- `plan_ai_runs_reindex(mechanism: str | None = None) -> list[PlannedRequest]`: Plans Valkey pipeline SET and ZADD commands for stored local runs.
- `plan_ai_runs_connect(context: str | None = None, namespace: str = "devops-llm", service: str = "valkey-runs", secret_name: str = "valkey-runs-auth") -> list[PlannedRequest]`: Plans kubectl service and secret lookups, followed by Valkey connection and pipeline operations.
- `plan_ai_runs_show(run_id: str) -> list[PlannedRequest]`: Plans Valkey GET for the run record if not found in local files.
- `plan_ai_runs_compare(run_a: str, run_b: str | None = None) -> list[PlannedRequest]`: Plans Valkey GET for base and comparison run records.
- `plan_ai_runs_baseline_set(run_id: str) -> list[PlannedRequest]`: Plans Valkey SET for the designated subject baseline.
- `plan_ai_runs_baseline_show(subject_or_run: str, mechanism: str | None = None) -> list[PlannedRequest]`: Plans Valkey GET for the subject baseline.
- `plan_ai_runs_check(run_id: str, baseline_id: str | None = None) -> list[PlannedRequest]`: Plans Valkey GET for the baseline and comparison run records.

### Command Implementations
- `src/devops_cli/commands/ai_cache.py`:
  - Decorate `cache_status` with `@dry_run_class("no-external-request")`.
  - Remove `dry_run` parameter and `render_dry_run_result` call from `cache_clear`.
  - Decorate `cache_clear` with `@dry_run_class("no-external-request")`.
- `src/devops_cli/commands/ai_cost.py`:
  - Decorate `cost_default`, `cost_report`, `cost_roi`, `cost_payoff`, `cost_payback`, `cost_prometheus`, and `cost_list_pricing` with `@dry_run_class("no-external-request")`.
  - Add `--dry-run` option to `cost_set_price` and decorate with `@dry_run_class("no-external-request")`. In dry run, display preview message without mutating custom pricing store.
  - Add `--dry-run` option to `cost_reset` and decorate with `@dry_run_class("no-external-request")`. In dry run, display preview message without resetting ledger.
  - Add `--dry-run` option to `cost_update_pricing` and decorate with `@dry_run_class("request-plan")`. In dry run, render request plan.
- `src/devops_cli/commands/ai_runs.py`:
  - Decorate `list_cmd` and `baseline_list_cmd` with `@dry_run_class("no-external-request")`.
  - Add `--dry-run` option to `reindex_cmd`, `connect_cmd`, `show_cmd`, `compare_cmd`, `baseline_set_cmd`, `baseline_show_cmd`, and `check_cmd`.
  - Decorate all seven with `@dry_run_class("request-plan")`.
  - In dry run, render planned requests; for json formats, emit structured output with `dry_run=True`.

### Ratchet Inventory Update
Remove all 21 commands from `tests/fixtures/dry_run_gaps.json`.
