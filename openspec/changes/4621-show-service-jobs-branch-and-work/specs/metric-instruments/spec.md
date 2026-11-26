## ADDED Requirements

### Requirement: The item, branch and worktree values stay off the Service series
No series of the Service metrics SHALL carry a label named item, branch or worktree.

#### Scenario: The Service series of the metrics registry
- **WHEN** `uv run devops ci test tests/telemetry/test_service_counter_series.py` runs.
- **THEN** The case `test_no_service_series_carries_an_item_branch_or_worktree_label` primes the Service counters, walks each sample of the metrics registry, and finds no label named item, branch or worktree on any of them.
