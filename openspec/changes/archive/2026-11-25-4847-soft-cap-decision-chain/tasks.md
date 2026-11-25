# Tasks

## 1. Tests First & OpenSpec Contract

- [x] 1.1 Write failing tests for ordered guards, `Mode.RULE`, fit bar (`>= 30` cases, `>= 10` per label, passing halves), `5.0 s` timeout/error fallback, `DecisionRecord` fields (`rule_band`, `model_band`, `guard`), sync-safe invocation, `implement.extension` registration, `ToolCallLog` loop counters (`4` identical call+answer, `3` identical failing), and `110` series bound
  - Verification: `$ uv run pytest -n 0 tests/roadmap/test_roadmap_decision_point.py tests/roadmap/test_roadmap_decision_table.py tests/config/test_decision_point_settings.py tests/roadmap/implement/test_roadmap_implement_limits.py tests/roadmap/test_roadmap_limit_classes.py`

## 2. Decision Chain, Fit Bar, Mode Rule, and Telemetry

- [x] 2.1 Add `Guard`, `Mode.RULE`, ordered guard execution, `rule_band`/`model_band`/`guard` fields on `DecisionRecord`, fit-bar checks in `decision_fit.py`/`decision_step.py`/`decision_table.py`, and `5.0 s` rule fallback in `src/devops_cli/roadmap/decision_point.py`
  - Verification: `$ uv run pytest -n 0 tests/roadmap/test_roadmap_decision_point.py tests/roadmap/test_roadmap_decision_table.py tests/config/test_decision_point_settings.py`
- [x] 2.2 Register `implement.extension` (`IMPLEMENT_EXTENSION`) in `src/devops_cli/roadmap/decision_registry.py` and `POINT_CUTS`, update constants (`CONST_ROADMAP_DECISION_POINT_MAX_SERIES = 110`, fit bar, timeout, margin, loop bounds), `LIMITS` entries, `DECISION_POINT_TOTAL`, and `StepBudget`/`ToolCallLog` loop/outer-limit integration
  - Verification: `$ uv run pytest -n 0 tests/roadmap/implement/test_roadmap_implement_limits.py tests/roadmap/implement/test_roadmap_implement_extension.py tests/roadmap/test_roadmap_limit_classes.py tests/telemetry/test_telemetry_instruments.py`

## 3. Docs, ADR Status History, and Gate

- [x] 3.1 Regenerate docs (`docs/TELEMETRY.md`, `docs/CONFIGURATION.md`), update `docs/ROADMAP_WORKFLOW.md`, append the Status History amendment to ADR 0020 without altering body hash, and run full checks
  - Verification: `$ uv run devops docs check && uv run devops openspec check && uv run devops ci --check`
