# Tasks

## 1. Spend ledger date range and period grouping

Reads: `src/devops_cli/ai/spend/models.py`, `src/devops_cli/ai/spend/ledger.py`, `tests/ai/spend/test_ai_spend_ledger.py`.
Changes: `src/devops_cli/ai/spend/models.py`, `src/devops_cli/ai/spend/ledger.py`, `tests/ai/spend/test_ai_spend_ledger.py`.

- [x] 1.1 In `tests/ai/spend/test_ai_spend_ledger.py`, add failing tests asserting `since` and `until` range filtering and `get_period_report` output for day and week grouping
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_ledger.py`
- [x] 1.2 Add `PeriodSpendSummary` in `src/devops_cli/ai/spend/models.py`, and implement `since`, `until`, and `get_period_report` in `src/devops_cli/ai/spend/ledger.py`
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_ledger.py`

## 2. CLI commands for cost report and ROI

Reads: `src/devops_cli/commands/ai_cost.py`, `tests/ai/spend/test_ai_spend_cli.py`.
Changes: `src/devops_cli/commands/ai_cost.py`, `tests/ai/spend/test_ai_spend_cli.py`.

- [x] 2.1 In `tests/ai/spend/test_ai_spend_cli.py`, add failing tests for `devops ai cost report` and `devops ai cost roi` with `--since`, `--until`, `--by week`, and `--days`
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_cli.py`
- [x] 2.2 Update `cost_report`, `cost_roi`, and `cost_default` in `src/devops_cli/commands/ai_cost.py` to accept `--since`, `--until`, and `--by day|week`
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_cli.py`

## 3. FastMCP tool ai_cost_report arguments and snapshot

Reads: `tests/ai/mcp/test_mcp_tool_argv.py`, `tests/ai/mcp/test_mcp_tool_listing.py`.
Changes: `tests/ai/mcp/test_mcp_tool_argv.py`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`.

- [x] 3.1 In `tests/ai/mcp/test_mcp_tool_argv.py`, add a test verifying `ai_cost_report` passes `since`, `until`, and `by`
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_tool_argv.py`
- [x] 3.2 Update tool listing snapshot in `tests/ai/mcp/test_mcp_tool_listing.py`
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_tool_listing.py`

## 4. Documentation updates

Reads: `docs/MCP_TOOLS.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ai.md`.
Changes: `docs/MCP_TOOLS.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ai.md`.

- [x] 4.1 Run `uv run devops docs generate --sync-readme` to regenerate documentation manuals
  - Verification: `$ uv run devops ci docs`

## Criteria

- Criterion 1 (Weekly grouping column sums): group 2
- Criterion 2 (Weekly grouping ROI output): group 2
- Criterion 3 (--days short form equivalence): group 2
- Criterion 4 (FastMCP tool ai_cost_report): group 3

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r <base>..HEAD`).
