# Design

## Decisions

- **Use half-open intervals `[start, end)` for periods**: Each timestamp belongs to exactly one period. The sum of period columns equals the ungrouped range report.
- **Support `--days N` as short form of `--since`**: Maintains backward compatibility with existing scripts.
- **Normalize dates and datetimes to UTC ISO strings**: Parses ISO date and datetime inputs and sets UTC timezone when no offset is provided.
- **Model period outputs with `PeriodSpendSummary`**: Standardizes fields (`period`, `requests`, `local_tokens`, `actual_spend`, `local_cost_equivalent`, `cloud_spend_avoided`) across CLI JSON, YAML, and tables.
- **Generate FastMCP tool arguments dynamically**: Uses Typer option metadata so `ai_cost_report` automatically exposes `since`, `until`, and `by`.

## Rejected alternatives

- **Closed intervals `[start, end]`**: Boundary records would appear in multiple intervals and invalidate column sum totals.
- **Fixed calendar week boundaries (e.g. Monday-Sunday only)**: Custom arbitrary ranges such as `2026-10-01` to `2026-10-22` would split into partial weeks instead of three equal 7-day periods.
- **Separate CLI commands for grouped reporting**: Adds unnecessary command surface area; extending `--by` aligns with existing grouping parameters.
