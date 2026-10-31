# Proposal

## Why
Commands under `ai runs`, `ai cost` (and alias `ai spend`), and `ai cache` make network, Valkey, or Kubernetes calls during execution or lack clear classification under the dry-run rule (#412, closes #2245).
Under `--dry-run`, commands that make external requests must execute zero requests and output an ordered `PlannedRequest` list, local preview commands must show proposed changes without writing, and local commands that make no external calls must run safely.

## What Changes
- Classify 21 AI commands across `ai runs`, `ai cost`, and `ai cache`:
  - 8 `request-plan` commands: `ai cost update-pricing`, `ai runs baseline set`, `ai runs baseline show`, `ai runs check`, `ai runs compare`, `ai runs connect`, `ai runs reindex`, and `ai runs show`.
  - 2 `no-external-request` local-preview commands: `ai cost reset` and `ai cost set-price`.
  - 11 `no-external-request` mark-only commands: `ai cache clear`, `ai cache status`, `ai cost`, `ai cost list-pricing`, `ai cost payback`, `ai cost payoff`, `ai cost prometheus`, `ai cost report`, `ai cost roi`, `ai runs baseline list`, and `ai runs list`.
- Ensure all 8 `request-plan` commands make zero external requests (HTTP, Valkey, Kubernetes) when `--dry-run` or global `--dry-run` is active.
- Remove echo-only previews with no shim and remove all 21 commands from `tests/fixtures/dry_run_gaps.json`.
- Fits in one pull request.

## Capabilities

### Modified Capabilities
- `command-dry-run-class`: Add dry-run classification, local-preview specifications, and request-plan specifications for AI runs, cost, and cache commands.

## Impact
- Affected files: `src/devops_cli/commands/ai_cache.py`, `src/devops_cli/commands/ai_cost.py`, `src/devops_cli/commands/ai_runs.py`, `src/devops_cli/ai/ai_plans.py`, and `tests/fixtures/dry_run_gaps.json`.
- Zero backward compatibility shim added.
- Public CLI commands remain functional without breaking changes.

## Feasibility
Confirmed against repository source:
- `src/devops_cli/commands/ai_cache.py:20-98`: `cache_status` reads local disk stats; `cache_clear` has an echo-only preview that will be excised.
- `src/devops_cli/commands/ai_cost.py:300-774`: `cost_update_pricing` dispatches HTTP requests via `PricingRegistry.update_from_remote`; `cost_reset` and `cost_set_price` write local data; other cost commands perform local report reads.
- `src/devops_cli/commands/ai_runs.py:98-711`: `reindex`, `connect`, `show`, `compare`, `baseline set`, `baseline show`, and `check` query Valkey via `RunIndex` or access Kubernetes via `NodePortSpec`; `list` and `baseline list` perform local filesystem reads.
- All 21 commands are present in `tests/fixtures/dry_run_gaps.json`.

## Existing Tool Considered
The implementation reuses the existing `devops_cli.dry_run.requests.PlannedRequest` and `render_request_plan` facilities. No third-party library is required.
Internal code deleted: echo-only preview in `src/devops_cli/commands/ai_cache.py`.
