# Proposal: #7181

## Why

`tests/roadmap/stage/test_roadmap_stage_github_snapshot.py::test_agent_phase_offers_stock_tools_only_without_read_issue_or_find_issues` prepares `inputs` with `now=NOW` (`2026-11-25T09:00:00Z`), which sets `inputs.deadline` in the past once the real wall clock passes `13:00Z` on `2026-11-25`. `run_stage_agent` runs without freezing the clock, so `within_budget` raises `RoadmapTimeBudgetError` before any model call and leaves `script.tools_offered == []` on `origin/main`.

## What Changes

- Freeze the wall clock around `run_stage_agent` with `time_machine.travel(NOW, tick=False)` in `tests/roadmap/stage/test_roadmap_stage_github_snapshot.py::test_agent_phase_offers_stock_tools_only_without_read_issue_or_find_issues`.

## Capabilities

- `stage-agent-phase`: Snapshot test determinism against frozen stage deadline time (#7181).

## Impact

- Unblocks `Tests & Coverage (shard 2 of 5)` on `origin/main` and open pull requests without altering production code.

## Feasibility

Verified directly against `origin/main` (`0b9c6983f`): running `test_agent_phase_offers_stock_tools_only_without_read_issue_or_find_issues` after `13:00Z` fails consistently with `AssertionError: assert [] == [['edit_file', 'grep', 'list_files', 'read_file', 'shell', 'write_file']]`. Fix is a two-line `time_machine.travel` wrapper in the test.

## Existing Tool Considered

Uses the already-installed `time_machine` pytest dependency (`pyproject.toml`, already used across `tests/roadmap/stage/test_roadmap_stage_plan.py` and `test_roadmap_stage_verify_eval.py`). Cost to fix with `time_machine` is ~5k tokens and ~15 minutes.
