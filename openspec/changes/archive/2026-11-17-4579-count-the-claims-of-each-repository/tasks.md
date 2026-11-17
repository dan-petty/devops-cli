# Tasks

## 1. Count the claims of each repository

Reads: `src/devops_cli/github/metrics.py`, `src/devops_cli/telemetry/instruments.py`, `tests/github/test_github_metrics.py`. Changes: `src/devops_cli/github/metrics.py`, `src/devops_cli/telemetry/instruments.py`, `tests/github/test_github_metrics.py`, `tests/github/test_github_metrics_request_budget.py`, `tests/roadmap/stores/test_roadmap_store_tool_issues.py`, `docs/TELEMETRY.md`.

- [x] 1.1 Add cases to `tests/github/test_github_metrics.py`: one sample for each claimant kind with 0 for an empty one, the label names and values, and the claim count of a failed label read
  - Verification: `$ uv run devops ci test tests/github/test_github_metrics.py` fails on the base
- [x] 1.2 Add `claimant_counts` and the `claims` return of `get_item_age_metrics` in `src/devops_cli/github/metrics.py`, the `claims` field of `ProjectMetricsReport`, the emission in `_emit_item_ages`, and the `ROADMAP_CLAIMS` gauge in `src/devops_cli/telemetry/instruments.py`
  - Verification: `$ uv run devops ci test tests/github/test_github_metrics.py` passes
- [x] 1.3 Regenerate the docs with `uv run devops docs generate`
  - Verification: `$ uv run devops docs generate` leaves `docs/TELEMETRY.md` with the new gauge

## Criteria

- Group 1: The telemetry module SHALL define `devops_cli_roadmap_claims` as a gauge with unit `1`.
- Group 1: A snapshot SHALL send one sample for each claimant kind, with 0 for a kind that holds no open item.
- Group 1: The snapshot SHALL read the items of the store once and send no extra GitHub request.
- Group 1: A series of the gauge MUST hold no issue number and no label named `owner`.
- Group 1: A snapshot whose read of the items fails MUST send no sample of the gauge.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
