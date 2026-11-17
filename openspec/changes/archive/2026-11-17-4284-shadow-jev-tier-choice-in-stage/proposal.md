# Proposal

## Why

The stage job picks one model tier for every item and never records which tier Jev would pick. A person who wants to compare the Jev tier choice with the tier that the job used has no data. The refine job recorded that `route_with_jev` in `src/devops_cli/ai/jev.py` already gives the tier choice, the complexity score and the high-risk probability, and that the intake job already runs Jev in a shadow mode (`src/devops_cli/roadmap/intake/intake_jev_shadow.py`, #4395). The stage job has no such record (#4284).

## What Changes

- A new switch `roadmap.stage.jev_shadow`, default off, beside `roadmap.stage.jev_completeness`.
- With the switch on, the stage job makes one shadow Jev routing call for each item before the first plan call of that item, when the item has no kept plan, and logs one line with the item, the choice, the complexity, `high_risk` and the concrete-files probability.
- The job counts the choice in the counter `devops_cli_roadmap_stage_jev_total`, with the single label `choice` and the values `deepseek`, `sonnet` and `error` (3 series).
- The call is a record only: it changes no plan, no model and no item list. A Jev error is logged, counts `choice=error` and never stops the item.
- `route_with_jev` in `src/devops_cli/ai/jev.py` gains an optional `extra_questions` parameter and a `extra_probabilities` field on `JevRouteDecision`, so the shadow call adds the question "the item names concrete files and criteria" to the same request.
- The docs `docs/TELEMETRY.md`, `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` name the new counter and the new setting.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-stage/jev-shadow`: The shadow Jev tier choice of the stage job

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/jev.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/telemetry/instruments.py`
- Docs: `docs/TELEMETRY.md`, `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`
- Tests: `tests/roadmap/stage/test_stage_jev_shadow.py` (new)

## Feasibility

- The premise holds in the code at the staging commit. `route_with_jev` in `src/devops_cli/ai/jev.py:219` returns a `JevRouteDecision` with `picked_model`, `complexity_score` and `high_risk_probability`, and `decide_with_jev` runs each request on one anyio blocking portal, so the call works from any thread. The stage job has no call site for it.
- The switch follows `roadmap.stage.jev_completeness` in `src/devops_cli/config/settings.py:1392`.
- The counter follows `ROADMAP_STAGE_PLAN_RECORD_TOTAL` in `src/devops_cli/telemetry/instruments.py:388` and the `emit` call of `src/devops_cli/roadmap/stage/stage.py:1638`.
- The seam for the test is a new `jev_route` parameter of `_Planner`, which defaults to `route_with_jev`. The test injects a fake Jev that records its calls, so the module makes no network call.
- The first check is `uv run devops ci test tests/roadmap/stage/test_stage_jev_shadow.py`, which runs the new cases.
- The second check is `uv run devops docs generate` followed by `uv run devops ci --check --only docs`, which regenerates and validates the metric and setting docs.
- The third check is `uv run devops openspec check`, which validates the added requirements and their scenarios.

## Existing Tool Considered

`route_with_jev` in `src/devops_cli/ai/jev.py` (TypeSafe Jev) covers the tier choice, the complexity score and the `high_risk` probability, and this work reuses it. It lacks the question "the item names concrete files and criteria", so the change adds one optional parameter to it. The counter reuses `Instrument` and `emit` in `src/devops_cli/telemetry/instruments.py`, and the shadow call reuses the pattern of `src/devops_cli/roadmap/intake/intake_jev_shadow.py`. No new library is needed. The written cost is about 6,000 tokens and about 2 hours. The run cost is about 0.0001 USD for each item that a person turns the switch on for.

## Dependencies

#4289 (closed): the gateway route for the Jev Decisions API, which the shadow call needs.
