# Proposal

## Why

The stage job accepts plans whose spec delta the changed paths do not need, or that add a requirement the base spec already has. About 14 of 37 recent plans carry such a delta (#3013). The model also gets only the capability names, so it cannot choose the right capability or avoid a duplicate.

## What Changes

- `check_proposal` refuses `skip_specs: false` when every `changes` path is under `tests/`, `.github/workflows/`, `docs/` or `openspec/`.
- `check_proposal` refuses an ADDED requirement whose name already exists in the base spec of that capability.
- The stage model input holds the purpose and the requirement names of each capability.
- The stage prompt tells the model to set `skip_specs` from the changed paths and to avoid a duplicate requirement name.
- Unit tests cover both refusals and assert the problem text.
- The recorded case of #2977 names the `paths` gate for its spec-delta defect, and the replay shows that `check_proposal` refuses it.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Refuse a spec delta that the changed paths do not need, Refuse an added requirement that the base spec already has, The model input holds the purpose and the requirement names of each capability

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_specs.py` (new), `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_specs.py` (new), `tests/roadmap/test_roadmap_stage_eval_gates.py`, and the case `tests/fixtures/roadmap_eval/stage/2116-the-scanner-executor-tests-find-the/case.json`

## Feasibility

- `read_file` of `src/devops_cli/roadmap/stage_change.py` lines 286-299 showed that `check_proposal` checks only `skip_specs` against `specs`, the purpose, the MODIFIED rule, the SHALL keyword and the paths. It never reads the `changes` paths for a spec delta and never compares an ADDED name with the base spec.
- `read_file` of `src/devops_cli/roadmap/stage.py` lines 646-672 showed that `_request` gives the model `sorted(self._known)` only, and that `_settle` calls `check_proposal(proposal, self._known, ...)`.
- `file_symbols` of `src/devops_cli/roadmap/stage.py` showed `capabilities_of`, the function that listed the names of the capabilities under `openspec/specs/`. The change replaces it with `read_base_specs` of `stage_specs.py`.
- `file_symbols` of `src/devops_cli/roadmap/stage_eval_gates.py` showed `_path_gate`, which runs `check_proposal` for the replay, and `PlanUnderTest.of_case`, which takes the capabilities of the case.
- `list_files` of `src/devops_cli/ai/tasks` showed the stage prompt is `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- `list_files` of `tests/roadmap` showed the replay tests are `tests/roadmap/test_roadmap_stage_eval_gates.py` and `tests/roadmap/test_roadmap_stage_eval_cases.py`, and the plan tests are `tests/roadmap/test_roadmap_stage_plan.py`.
- The first checks of the implementation: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` for the two refusals, and `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` for the #2977 case.

## Existing Tool Considered

No open, maintained tool or library covers this need. The check is a rule of this project's own stage job over its own reply schema, and `check_proposal` already holds the other rules of `openspec/config.yaml`. The change adds two rules to that function and reads the base spec with the code that already lists the capabilities. Building it costs about 300 lines of code and tests, a few hours to write, and the upkeep of two rules beside the existing ones. It deletes `capabilities_of` of `stage.py`, which `read_base_specs` replaces.
