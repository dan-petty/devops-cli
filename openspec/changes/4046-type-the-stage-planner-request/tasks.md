# Tasks

## 1. Type the planner request and read the gates from it

Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_overlap.py`, `tests/support/roadmap_stage.py`. Changes: `tests/roadmap/stage/test_roadmap_stage_request.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/stage/stage.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_request.py`, write the tests: the JSON of the model is the golden JSON (for a full request, a request with no optional key, a run through the planner and a returned reply), the gate-only fields are not in it, the gates give the same problems from a `StageRequest` alone, the gates read the whole issue body, the request round-trips through JSON, and an unknown key raises a validation error
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main` shows the new tests failing on the base
- [x] 1.2 In the new module `src/devops_cli/roadmap/stage/stage_request.py`, define `StageRequest` with `extra="forbid"`, `GATE_ONLY_FIELDS`, `StageRequest.for_model` and `gate_arguments`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_request.py` passes
- [x] 1.3 In `src/devops_cli/roadmap/stage/stage.py`, make `_Planner._request` return a `StageRequest` with the gate inputs, send `request.for_model()` from `_ask`, `_gated`, `_verified` and `_repaired`, and make `_problems` call `gate_arguments`. Delete the planner fields that the request replaces and the untyped dictionary
  - Verification: `$ uv run devops ci test tests/roadmap/stage` passes
  - Verification: `$ ! grep -n 'request: dict\[str, Any\]' src/devops_cli/roadmap/stage/stage.py`

## 2. Document the new module

Reads: `docs/roadmap/package-layout.md`. Changes: `docs/roadmap/package-layout.md`.

- [x] 2.1 Add `stage_request` to the module list of `stage/` in `docs/roadmap/package-layout.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: `uv run pytest tests/roadmap/stage/test_roadmap_stage_request.py -k model_json_unchanged` - for a fixed item, the JSON sent to the model equals the golden dict of today. The gate-only fields are not in it.
- Group 1: `uv run pytest tests/roadmap/stage/test_roadmap_stage_request.py -k gates_from_request` - `check_proposal` gives the same problems when its arguments come from a `StageRequest` alone, with no `_Planner` object.
- Group 1: `uv run pytest tests/roadmap/stage/test_roadmap_stage_request.py -k forbid_extra` - an unknown key in `StageRequest` raises a validation error.
- Group 1: `! grep -n 'request: dict\[str, Any\]' src/devops_cli/roadmap/stage/stage.py` - the untyped request is gone.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
