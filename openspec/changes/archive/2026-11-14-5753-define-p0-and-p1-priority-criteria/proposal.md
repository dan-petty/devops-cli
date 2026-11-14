# Proposal: #5753

## Why

Issue #5753: Roadmap intake and triage currently restrict the model and Jev from proposing P0 priorities directly. The code in `src/devops_cli/roadmap/intake/intake.py` caps model proposals at `P1-High` and permits `P0-Critical` only when verified evidence (GHSA advisory, failed Actions run, or regression commit) is cited.
The project requires standardized criteria for labeling `P0-Critical` and `P1-High` priorities during issue triage and intake.

## What Changes

- Update `CONST_ROADMAP_MODEL_PRIORITIES` in `src/devops_cli/config/constants.py` to include `CONST_ROADMAP_CRITICAL_PRIORITY` (`P0-Critical`).
- Update `CONST_ROADMAP_JEV_PRIORITY_CRITERIA` in `src/devops_cli/config/constants.py` with criteria for `P0-Critical` and `P1-High`.
- Update `_priority_choice` in `src/devops_cli/roadmap/intake/intake.py` so that `P0-Critical` is accepted directly rather than capped at `P1-High`. Normalize `"P0"` to `"P0-Critical"`.
- Update the intake system prompt (`src/devops_cli/ai/tasks/roadmap_intake_system.md`) to define the explicit criteria for `P0-Critical` and `P1-High`.
- Update `openspec/specs/roadmap-intake-reply-schema/spec.md` so that the proposal schema requires `priority` as an enum of `P0-Critical`, `P1-High`, `P2-Medium`, and `P3-Low`.
- Update `docs/roadmap/intake.md` to document the P0 and P1 priority criteria and updated priority options.
- Update tests and prompt snapshot in `tests/roadmap/intake/`.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-intake-reply-schema`: The proposal schema lists the values of each fixed field (MODIFIED)

## Impact

- `src/devops_cli/config/constants.py`
- `src/devops_cli/roadmap/intake/intake.py`
- `src/devops_cli/ai/tasks/roadmap_intake_system.md`
- `docs/roadmap/intake.md`
- `tests/roadmap/intake/test_roadmap_intake_model_reply.py`
- `tests/roadmap/intake/__snapshots__/test_roadmap_intake_duplicates.ambr`
- `tests/roadmap/intake/test_roadmap_intake_checks.py`

## Feasibility

Premise confirmed against source code and command output:
- `CONST_ROADMAP_MODEL_PRIORITIES` currently defines `("P1-High", "P2-Medium", "P3-Low")` in `src/devops_cli/config/constants.py`.
- `_priority_choice` in `src/devops_cli/roadmap/intake/intake.py` caps `CONST_ROADMAP_P0_PRIORITIES` to `CONST_ROADMAP_MODEL_PRIORITIES[0]`.
- `test_the_reply_schema_lists_the_values_of_each_fixed_field` in `tests/roadmap/intake/test_roadmap_intake_model_reply.py` asserts the enum values `["P1-High", "P2-Medium", "P3-Low"]`.
- `uv run pytest -n 0 tests/roadmap/intake/` passed 191 tests.

## Existing Tool Considered

Roadmap intake is devops-cli's native single entry point for labeling candidates into items. No external tool defines these project-specific criteria.
Cost: 50,000 tokens, 0.25 day.
Deleted code: the capping logic in `_priority_choice`.
