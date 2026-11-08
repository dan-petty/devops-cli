# Tasks

## 1. Send the seconds of each stage step and count the refusing gates

Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/core/clock.py`. Changes: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/telemetry/test_roadmap_stage_steps.py`, `tests/roadmap/test_roadmap_failure.py`. Creates: `src/devops_cli/roadmap/step_metrics.py`.

- [x] 1.1 Add `tests/telemetry/test_roadmap_stage_steps.py` with the cases of the spec, and extend the `StepName` test in `tests/roadmap/test_roadmap_failure.py`. Run them and see them fail on the base
  - Verification: `$ uv run devops ci test tests/telemetry/test_roadmap_stage_steps.py` fails on the base
- [x] 1.2 Add `SELECT`, `GATE` and `REVIEW` to `StepName` in `src/devops_cli/roadmap/failure.py`. Declare `ROADMAP_STEP_SECONDS` (histogram, unit `s`) and `ROADMAP_STAGE_GATE_REFUSALS_TOTAL` (counter, unit `1`) in `src/devops_cli/telemetry/instruments.py`, with the series counts in their texts, and add both to `INSTRUMENTS` and `__all__`. Add `observe_step(repo, row, step)` in `src/devops_cli/roadmap/step_metrics.py`
  - Verification: `$ uv run devops ci test tests/telemetry/test_roadmap_stage_steps.py tests/roadmap/test_roadmap_failure.py tests/telemetry/test_telemetry_instruments.py` passes
- [x] 1.3 In `src/devops_cli/roadmap/stage/stage.py`, time `read_stage_selection` in `plan_stage`, `_Planner._ask`, `_Planner._problems`, `_Planner._review` and `StageWriter._stage` with `observe_step`, and send nothing when the planner has no repository. In `_Planner._problems`, call `check_gates`, add 1 to the refusal counter for each gate with a problem, and join the lists in the order that `check_proposal` uses
  - Verification: `$ uv run devops ci test tests/telemetry/test_roadmap_stage_steps.py tests/roadmap/stage` passes

## 2. Document the series

Reads: `docs/TELEMETRY.md`, `src/devops_cli/docs/generator.py`. Changes: `docs/TELEMETRY.md`.

- [x] 2.1 Run `uv run devops docs generate --sync-readme` so that `docs/TELEMETRY.md` lists both instruments with their labels and series counts
  - Verification: `$ grep -q devops_cli_roadmap_step_seconds docs/TELEMETRY.md && grep -q devops_cli_roadmap_stage_gate_refusals_total docs/TELEMETRY.md` exits 0

## Criteria

- Group 1: A stage round emits a step sample for `select`, `plan`, `gate`, `review` and `apply` under `repo`, `row` and `result`.
- Group 1: A refused plan adds 1 to the counter of its gate and to no other gate.
- Group 1: Every `step` value is a member of `StepName`.
- Group 2: `docs/TELEMETRY.md` lists `devops_cli_roadmap_step_seconds` and `devops_cli_roadmap_stage_gate_refusals_total`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
