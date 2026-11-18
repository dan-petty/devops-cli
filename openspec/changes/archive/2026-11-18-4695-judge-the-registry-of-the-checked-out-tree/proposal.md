# Proposal: #4695

## Why

The stage change gates and replays read the registry table from the process working directory via `registry_table(Path.cwd())`. When `check_gates`, `check_proposal`, `replay_all`, or `replay_case` operated in another directory or against another checkout (such as during evaluation replays or when running tests from an arbitrary working folder), they read counts from the wrong folder or failed to find the project root.

## What Changes

- Make `registry: Sequence[RegistryCount]` a required keyword-only argument in `check_gates` and `check_proposal`.
- Make `registry: Sequence[RegistryCount]` a required keyword-only argument in `replay_all` and `replay_case`.
- Add an ast-grep rule `stage-registry-cwd-read` forbidding `registry_table(Path.cwd())` in `src/**`.
- Build `registry_table` once per stage run in `_Planner.__init__` and reuse it across all items, requests, and gate checks.
- Build `registry_table` once in `_Judge._registry` via `@cached_property` in the implement job.
- Build `registry_table` once in `_replay` of `commands/roadmap_eval_stage.py` and pass it to `replay_all`.
- Build `registry_table` once in `run_cases` of `stage_eval_run.py` and pass it down.
- Update the `report` fixture in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` to use a session-scoped `registry` fixture.

## Capabilities

None: this changes internal gate parameterization and evaluation replays, not external product capabilities. `skip_specs` is set.

## Impact

- Gate checks evaluate the passed registry table rather than the process working directory.
- `registry_table` is built once per stage run instead of once per item or request.

## Feasibility

- The ast-grep scan verifies no caller in `src/**` calls `registry_table(Path.cwd())`.
- All 134 evaluation replay test cases and all unit tests pass with the session fixture and required keyword arguments.

## Existing Tool Considered

No external tool is applicable. The changes standardize existing internal registry validation APIs and eliminate process working directory dependencies.
