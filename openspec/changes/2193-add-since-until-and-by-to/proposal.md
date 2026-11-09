# Proposal

## Why

The `devops ai cost report` and `devops ai cost roi` commands accept `--days N` only. A user who needs metrics for a specific date range must copy the ledger database and delete records outside the range. The commands need explicit `--since` and `--until` parameters, and need `--by day` and `--by week` grouping. Closes #2193.

## What Changes

- Add `PeriodSpendSummary` in `src/devops_cli/ai/spend/models.py` to hold spend, token, and savings metrics for a single period.
- Update `SpendLedger` in `src/devops_cli/ai/spend/ledger.py` so queries filter with `since` and `until` timestamps.
- Add `get_period_report` in `SpendLedger` to calculate metrics grouped into day or week intervals.
- Update `devops ai cost report` and `devops ai cost roi` in `src/devops_cli/commands/ai_cost.py` to accept `--since`, `--until`, and `--by`.
- Expose `--since`, `--until`, and `--by` in the generated FastMCP tool `ai_cost_report`.
- Add tests for range filtering, weekly grouping, column sum equivalence, and MCP arguments.
- Regenerate documentation and FastMCP tool snapshots.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-spend-pricing`: Spend report and ROI accept time range and period grouping.

## Impact

- Code: `src/devops_cli/ai/spend/models.py`, `src/devops_cli/ai/spend/ledger.py`, `src/devops_cli/commands/ai_cost.py`
- Documents: `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/ai.md`
- Tests: `tests/ai/spend/test_ai_spend_ledger.py`, `tests/ai/spend/test_ai_spend_cli.py`, `tests/ai/mcp/test_mcp_tool_argv.py`

## Feasibility

- The `ai_spend_records` table indexes `timestamp`.
- The query conditions `WHERE (:since IS NULL OR timestamp >= :since) AND (:until IS NULL OR timestamp < :until)` filter rows in SQLite.
- Half-open intervals `[start, end)` partition the range so the sum of grouped rows equals the ungrouped report.
- The `ai_cost_report` tool generates dynamically from Click parameter metadata.

## Existing Tool Considered

The roadmap check evaluated `ccusage/ccusage`. That tool tracks only Claude and Anthropic usage. It does not read the local SQLite ledger or connect to DevOps CLI workflows. Building this feature in DevOps CLI costs approximately 25,000 tokens and 1 hour.
