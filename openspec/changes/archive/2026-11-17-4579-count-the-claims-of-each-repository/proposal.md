# Proposal

## Why

No metric counts the open roadmap items of each repository by claimant kind, and the pipeline dashboard (#3655) needs the count. Prometheus cannot count GitHub labels by itself. The metrics row already reads the items of the store for the item ages, so the count comes from the same snapshot (#4579). The approved pipeline split (tracker #5482) moved the item count to #5495, which owns `devops_cli_roadmap_items{repo, phase}`, so this change adds only the claims gauge.

## What Changes

- A new gauge `devops_cli_roadmap_claims` with the labels `repo` and `claimant`, and the claimant kinds `service`, `agent` and `human`.
- Each metrics snapshot sends one sample for each claimant kind, with 0 for a kind that holds no open item, from the items that the item-age read already holds.
- `get_item_age_metrics` in `src/devops_cli/github/metrics.py` returns the claim counts beside the ages, so one read gives both and a failed read sends neither.
- The report `ProjectMetricsReport` gains a `claims` field, and `_emit_item_ages` sends the gauge.
- The docs `docs/TELEMETRY.md` name the new gauge.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `metric-instruments`: The claims gauge and its snapshot

## Impact

- Code: `src/devops_cli/github/metrics.py`, `src/devops_cli/telemetry/instruments.py`
- Docs: `docs/TELEMETRY.md`
- Tests: `tests/github/test_github_metrics.py`, `tests/github/test_github_metrics_request_budget.py`, `tests/roadmap/stores/test_roadmap_store_tool_issues.py`

## Feasibility

- The premise holds in the code at the staging commit. `get_item_age_metrics` in `src/devops_cli/github/metrics.py:592` reads the open items once and already computes the oldest claim from the `owner` field. No gauge counts them by claimant kind.
- The gauge follows `ROADMAP_ITEM_AGE` and `ROADMAP_ITEMS` in `src/devops_cli/telemetry/instruments.py:486`, and the emission follows `_emit_item_ages` in `src/devops_cli/github/metrics.py:1022`.
- The claimant kinds are the three owner values of `CONST_ROADMAP_OWNER_SERVICE`, `CONST_ROADMAP_OWNER_AGENT` and `CONST_ROADMAP_OWNER_HUMAN` (`src/devops_cli/config/constants.py:3915`).
- The first check is `uv run devops ci test tests/github/test_github_metrics.py`, which runs the new cases beside the existing ones.
- The second check is `uv run devops docs generate`, which regenerates the metric table of `docs/TELEMETRY.md`.
- The third check is `uv run devops openspec check`, which validates the added requirements and their scenarios.

## Existing Tool Considered

The OpenTelemetry Python SDK (`open-telemetry/opentelemetry-python`, Apache-2.0, maintained, the in-use tool of the alternatives check of 2026-11-13) covers the gauge export through `Instrument` and `emit`, as `ROADMAP_ITEM_AGE` uses it. The SDK cannot count GitHub labels, so the counts come from the store snapshot that `get_item_age_metrics` already reads. This change adds no dependency. The written cost is about 4,000 tokens and about 1 hour.

## Dependencies

None. #5495 owns `devops_cli_roadmap_items{repo, phase}` and this change adds no items gauge.
