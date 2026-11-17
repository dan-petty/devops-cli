# Tasks

## 1. Add the shadow Jev tier choice

Reads: `src/devops_cli/ai/jev.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/ai/jev.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_stage_jev_shadow.py` (new), `docs/TELEMETRY.md`, `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`.

- [x] 1.1 Write `tests/roadmap/stage/test_stage_jev_shadow.py`: a case for the switch off, a case for the switch on that reads the log line and the counter, a case that the plan result is equal with the switch on and off, a case for a Jev error, and a case that the metric has three series
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_stage_jev_shadow.py` fails on the base
- [x] 1.2 Add the optional `extra_questions` parameter to `route_with_jev` and the `extra_probabilities` field to `JevRouteDecision` in `src/devops_cli/ai/jev.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_stage_jev_shadow.py` passes
- [x] 1.3 Add the `jev_shadow` setting, the `ROADMAP_STAGE_JEV_TOTAL` instrument, the two messages, and the `_shadow_choice` helper with its call in `_Planner.plan`, and the `jev_route` seam
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_stage_jev_shadow.py` passes
- [x] 1.4 Regenerate the docs with `uv run devops docs generate` and check them with `uv run devops ci --check --only docs`
  - Verification: `$ uv run devops docs generate` leaves `docs/TELEMETRY.md`, `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` with the new counter and setting

## Criteria

- Group 1: The stage job SHALL make no Jev call when `roadmap.stage.jev_shadow` is off.
- Group 1: With the switch on, the stage job SHALL log one line for each item and SHALL count the choice once, before the first plan call.
- Group 1: The stage job SHALL produce the same plan result, model and item list with the switch on as with the switch off.
- Group 1: A Jev error MUST be logged, MUST count `choice=error` and MUST NOT stop the item.
- Group 1: The metric SHALL hold the single label `choice` with only `deepseek`, `sonnet` and `error` (3 series).

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
