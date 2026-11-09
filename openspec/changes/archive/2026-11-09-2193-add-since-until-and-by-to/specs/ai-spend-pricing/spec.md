## ADDED Requirements

### Requirement: Spend report and ROI accept time range and period grouping
The `devops ai cost report` and `devops ai cost roi` commands SHALL accept `--since` and `--until` for ISO dates or datetimes (UTC unless an offset is specified), and SHALL accept `--by day` and `--by week` to return spend, token and savings summaries grouped by period. The `--days N` flag SHALL remain as a short form equivalent to `--since` set to `N` days before the current time.

#### Scenario: Cost report grouped by week across a date range
- **WHEN** `devops ai cost report --since 2026-10-01 --until 2026-10-22 --by week --json` runs against a ledger
- **THEN** it outputs three period rows whose column sums equal the ungrouped report for the same date range

#### Scenario: Cost ROI grouped by week
- **WHEN** `devops ai cost roi --since 2026-10-01 --until 2026-10-22 --by week --json` runs against a ledger
- **THEN** each period row contains requests, local tokens, actual spend, local cost equivalent, and cloud spend avoided

#### Scenario: The MCP tool ai_cost_report accepts date range and grouping
- **WHEN** the MCP tool `ai_cost_report` is called with `since`, `until`, and `by`
- **THEN** it passes the options to the command line and returns the matching report
