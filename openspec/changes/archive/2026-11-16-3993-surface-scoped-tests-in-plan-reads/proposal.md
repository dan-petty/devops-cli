# Proposal: #3993 Surface Scoped Tests in Plan Reads

## Why
Stage plans do not show the scoped tests that implement will run. The implement model must discover those tests, and a scoped test that fails on the base commit wastes implement turns and causes budget exhaustion. Closes #3993.

## What Changes
1. When stage plans a task group, run `plan_tests()` against the planned `Changes:` list of each group.
2. For each selected test module that exists in the repository, add it to the group's `Reads:` list once while preserving existing reads.
3. If `plan_tests()` returns a test path that does not exist in the repository, omit the path from `Reads:` and record a warning naming the path in the plan.
4. If `plan_tests()` returns no test modules, leave `Reads:` unchanged.

## Capabilities
- `roadmap-stage/task-groups`: Surface scoped tests in group reads and record warnings for missing scoped test paths.

## Impact
Implement steps have direct context for the scoped tests that will gate their changes without needing discovery turns.

## Feasibility
Confirmed against `plan_tests()` in `src/devops_cli/roadmap/implement/implement_scoped_ci.py` and `StagePlanner` in `src/devops_cli/roadmap/stage/stage.py`.

## Existing Tool Considered
No external tool covers the stage plan `Reads:` integration. The change reuses the existing `plan_tests()` function and adds a small adapter. `pytest-testmon` is an open, maintained library that selects tests affected by code changes, but it lacks stage plan `Reads:` integration and needs coverage instrumentation. The adapter costs one function and its tests; it builds no new selector.
