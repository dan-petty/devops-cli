# Proposal

## Why

Staging a plan cannot see the registries and ratchet tests that a new constant, setting, metric or job write needs, so the entries are missed and the suite fails later (#3254). Evidence: the limit-class ratchet in `tests/roadmap/test_roadmap_limit_classes.py` (#3174), the job-write registries of #3169, and the `INSTRUMENTS` registry whose documented test path is stale (#3173).

## What Changes

- Add `src/devops_cli/roadmap/stage_registry.py`: an `ast` reader of module-level `REGISTRY_COUNTS` declarations, a table builder that returns each entry with its `path:line`, a matcher of a plan against the table, and a scanner for test paths in docstrings and specs.
- Add `REGISTRY_COUNTS` declarations to `tests/roadmap/test_roadmap_limit_classes.py`, `tests/roadmap_faults.py`, `tests/telemetry/test_telemetry_instruments.py` and `tests/roadmap/test_roadmap_dry_runs.py`, each naming the counted prefix, enum or table and the path that must carry the entry.
- List the matching registry entries with `path:line` in the plan context that the stage job gives the model.
- Refuse in `check_proposal` a plan that adds a counted item and has no task naming the listed place.
- Refuse in `check_proposal` a plan whose changed Python docstrings or specs name a test file that the commit does not hold.
- Correct the stale root-level telemetry test path in the `docs/TELEMETRY.md` sentence that names it, so it names the mirrored module.
- Add two requirements to the `roadmap-stage` capability and no other spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The plan lists the registry and ratchet places that its changes need, A test path in a docstring or a spec names a file of the commit

## Impact

- Code: `src/devops_cli/roadmap/stage_registry.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_change.py`
- Documents: `docs/TELEMETRY.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_stage_registry.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/roadmap_faults.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_form.py`

## Feasibility

- `probes` shows the premise holds: "The path `tests/roadmap/test_roadmap_limit_classes.py` is a file of the staging commit." and "The path `tests/roadmap_faults.py` is a file of the staging commit." and "The path `tests/roadmap/test_roadmap_store_contract.py` is a file of the staging commit." The ratchet and registry tests that the issue cites are present.
- `probes` shows the stale-path evidence of the issue is real: "The path `tests/test_telemetry_instruments.py` is no file of the staging commit. Commit 513bb31f 2026-10-30 test(cli): tests mirror package directories and trim root conftest (#2830) deleted or renamed it." while "The path `tests/telemetry/test_telemetry_instruments.py` is a file of the staging commit."
- `probes` shows the example name of the new path check is a name that no commit ever held, so it is a fixture name to create and no false premise: "The path `tests/test_missing_example.py` is no file of the staging commit. No commit in the history deleted or renamed it."
- The context shows the declaration sites that the table reads: the `LIMITS` table of `tests/roadmap/test_roadmap_limit_classes.py`, the `WRITES` frozenset of `tests/roadmap_faults.py`, and `INSTRUMENTS` of `src/devops_cli/telemetry/instruments.py` with its test in `tests/telemetry/test_telemetry_instruments.py`.
- The context shows `check_proposal` lives in `src/devops_cli/roadmap/stage_change.py` and is called by `src/devops_cli/roadmap/stage.py`, and that `tests/roadmap/test_roadmap_stage_plan.py` and `tests/roadmap/test_roadmap_stage_form.py` test it.
- The context shows `docs/TELEMETRY.md` names the stale path in the sentence "`tests/test_telemetry_instruments.py` fails on a metric that a module writes by name."
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_registry.py`, then `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`, then `uv run devops openspec check`, then `uv run devops ci lint`.

## Existing Tool Considered

No open, maintained tool or library covers a repository-specific table of test declarations. The need is the declaration in this repository's own test modules, read without importing pytest. Build in-house in `src/devops_cli/roadmap/stage_registry.py`: about 20,000 tokens to build, about 8,000 tokens a year to keep, about 4,000 tokens for each fix, and about 2 engineer-days. It deletes no internal code: the declaration reader is new, and `check_proposal` in `src/devops_cli/roadmap/stage_change.py` gains two calls to it.
