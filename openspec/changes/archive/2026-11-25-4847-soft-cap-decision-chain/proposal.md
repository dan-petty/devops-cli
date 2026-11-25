# Proposal: #4847

## Why
The workflow decision layer lacks guard ordering, `rule`-only execution before fitted cuts exist, fit-bar gating before `on`, and shadow answer collection alongside deterministic rules. As a result, new soft-cap points such as `implement.extension` cannot progress safely from deterministic rule -> shadow model observation -> calibrated `on` without risking infinite tool loops, outer budget overruns, or stalled Service shutdowns. Closes #4847.

## What Changes
- **Modes (`off`, `shadow`, `rule`, `on`)**: Add `Mode.RULE = "rule"` (`DecisionMode` in `src/devops_cli/config/defaults.py` and `src/devops_cli/roadmap/decision_point.py`). `check_modes` (`src/devops_cli/roadmap/decision_table.py`) accepts `"off"` and `"rule"` without a cuts file on disk, keeps `"shadow"` and `"on"` gated on an existing cuts file, and refuses `"on"` when a fit-bar-gated point fails the fit bar (`>= 30` labelled outcomes, `>= 10` per label, passing halves check, with no default constant cut).
- **Ordered guards before rule and model**: Add `Guard` evaluation in `ResolverChain` running in fixed order (`service_draining`, `hard_ceiling`, `outer_limits`, `loop_guard`) before `rule` and `model`. The first failing guard stops evaluation with `Resolver.FALLBACK`, `band=None`, `guard="<name>"`, and zero model requests.
- **Rule stands, model logging in `rule` mode, and 5 s fallback**: Record `rule_band`, `model_band`, and `guard` on `DecisionRecord`. Preserve standing rule decisions across `shadow`, `rule`, and `on`. When a point consults a decision model in `rule` mode, query within `CONST_ROADMAP_DECISION_POINT_TIMEOUT_SECONDS` (`5.0` s) inside a sync-safe blocking portal or async loop, store `answers` with `model_band=None`, and fall back to the rule on model errors or timeouts.
- **Register `implement.extension` and loop/outer-limit signals**: Register `IMPLEMENT_EXTENSION` in `decision_registry.py` and `POINT_CUTS`, track identical call+answer repeats (`4`) and failing call repeats (`3`) in `ToolCallLog` (`ProgressDigest`), wire `StepBudget` and `run_step` outer limits (`<= 0.75` context window share, step/item time & token margins), raise `CONST_ROADMAP_DECISION_POINT_MAX_SERIES` from `92` to `110` (`92 + 18`), update `DECISION_POINT_TOTAL`, regenerate `docs/TELEMETRY.md`, update `docs/ROADMAP_WORKFLOW.md`, and add a `Status History` amendment to ADR 0020. The separate `fix-checks` chain remains deferred to its own issue per #4847.

## Capabilities
- `decision-workflows`
- `roadmap-implement-step/budgets`

## Impact
- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/decision_point.py`, `src/devops_cli/roadmap/decision_table.py`, `src/devops_cli/roadmap/decision_registry.py`, `src/devops_cli/roadmap/decision_step.py`, `src/devops_cli/roadmap/decision_fit.py`, `src/devops_cli/roadmap/implement/implement_limits.py`, `src/devops_cli/roadmap/implement/implement_tool_log.py`, `src/devops_cli/roadmap/implement/implement_step.py`.
- Docs: `docs/TELEMETRY.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/CONFIGURATION.md`, `docs/adr/0020-a-decision-point-is-a-unit-of-a-workflow-with-a-resolver-chain-and-a-rule-goes-before-a-decision-model.md`.
- Tests: `tests/roadmap/test_roadmap_decision_point.py`, `tests/roadmap/test_roadmap_decision_table.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/config/test_decision_point_settings.py`, `tests/roadmap/implement/test_roadmap_implement_limits.py`.

## Feasibility
Confirmed against the codebase:
- `src/devops_cli/roadmap/decision_point.py` already defines `Mode` (`off`, `shadow`, `on`), `Resolver` (`rule`, `model`, `fallback`), `DecisionPoint`, `DecisionRecord`, `OutcomeRecord`, `ResolverChain` (`decide`, `adecide`), and `Registry`.
- `src/devops_cli/roadmap/decision_table.py` (`POINT_CUTS`, `check_modes`) and `src/devops_cli/roadmap/decision_registry.py` (`REGISTRY`) manage point modes and registration cleanly.
- `src/devops_cli/roadmap/implement/implement_limits.py` (`StepBudget`, `extends`, `ProgressDigest`), `src/devops_cli/roadmap/implement/implement_tool_log.py` (`ToolCallLog`, `argument_digest`), and `src/devops_cli/roadmap/service_stop.py` (`service_stopping`) already provide the budget, digest, and Service drain primitives.
- `src/devops_cli/telemetry/instruments.py` (`DECISION_POINT_TOTAL`) and `src/devops_cli/config/constants.py` (`CONST_ROADMAP_DECISION_POINT_MAX_SERIES = 92`) define the registry series cap.

## Existing Tool Considered
Reuses the repository's existing `pydantic_ai` decision framework (`DecisionModel`, `NoulQuestion`), `DecisionPoint` / `ResolverChain` / `DECISION_POINT_TOTAL` counter, `decision_fit.halves`, `service_stop.service_stopping`, and `ToolCallLog.argument_digest` rather than building parallel metric instruments or a bespoke loop-detection engine (`0` new dependencies; saves duplicating telemetry and portal lifecycle code).
