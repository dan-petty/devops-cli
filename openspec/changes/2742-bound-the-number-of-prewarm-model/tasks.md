# Tasks

## 1. Bound the prewarm model label and span attribute

Reads: `src/devops_cli/commands/ai.py`, `src/devops_cli/telemetry/instruments.py`, `openspec/changes/archive/2026-10-30-2676-prewarm-output-server-labels/design.md`. Changes: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/commands/ai.py`, `tests/test_ai_prewarm_cardinality.py` (new).

- [ ] 1.1 Write `tests/test_ai_prewarm_cardinality.py` first. It asserts that `bounded_model_label` returns `other` for an unknown model, the bounded configured model for the configured model, and the bounded server model for a server-reported model. It also runs `prewarm` with a fake client whose `list_models` returns a list or raises, and asserts the `model` label of `AI_PREWARMS_TOTAL` and the `ai.model` attribute of the `ai.prewarm` span, and verify that `uv run devops ci test tests/test_ai_prewarm_cardinality.py` fails on the base
- [ ] 1.2 Add `bounded_model_label(model, allowed_models)` in `src/devops_cli/telemetry/instruments.py`. It returns `bounded_label(model)` when the model is in `allowed_models`, else `other`. In `src/devops_cli/commands/ai.py`, create the client before the span, call `client.list_models()` once, and fall back to the configured model when the call raises. Build the allowed set from `settings.ai.model` and the server list. Use the helper for the `ai.model` span attribute and the `model` counter label, and verify that `uv run devops ci test tests/test_ai_prewarm_cardinality.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
