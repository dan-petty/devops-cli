# Proposal: #3491

## Why

A stage plan that changes only a tool setting in `pyproject.toml` and a workflow needs no spec delta. Case 2163 changes only a coverage setting and a CI workflow. But `_needs_no_spec` treats `pyproject.toml` as a path that always needs a spec delta. The stage check cannot tell a tool setting from a dependency or an entry point. The replay records this gap as an unjudged defect for case 2163. Closes #3491.

## What Changes

- Add a diff-aware classifier for `pyproject.toml` changes using `unidiff` and TOML table paths.
- Treat `pyproject.toml` as needing no spec delta when every changed key is under `[tool.*]`.
- Keep requiring a spec delta when a dependency or an entry point changes.
- Update `CaseFacts` and `PlanUnderTest` to carry `pyproject_diff`.
- Update case 2163 in `tests/fixtures/roadmap_eval/stage/2163-coverage-measures-branches-and-ci-keeps/`: add `pyproject_diff` in `facts.json`, set gate `paths`, and remove `reason` in `case.json`.
- Add test coverage in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.

## Capabilities

### Modified Capabilities

- `roadmap-stage/spec-delta`: Refuse a spec delta that the changed paths do not need.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`
- Fixtures: `tests/fixtures/roadmap_eval/stage/2163-coverage-measures-branches-and-ci-keeps/case.json`, `facts.json`

## Feasibility

- `pyproject.toml` has table headers such as `[tool.*]`, `[project]`, and `[project.scripts]`.
- Case 2163 in `tests/fixtures/roadmap_eval/stage/2163-coverage-measures-branches-and-ci-keeps/case.json` has `spec_delta_wrong` with gate `none` and reason citing `pyproject.toml`.
- Verification command `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` runs the replay.

## Existing Tool Considered

`unidiff` (already a pinned dependency) parses unified diffs. Python standard `tomllib` parses TOML documents but cannot map diff hunks to tables. The project implements the table path resolver. Token cost: about 4,000 tokens to build and test; time: about 1 hour.
