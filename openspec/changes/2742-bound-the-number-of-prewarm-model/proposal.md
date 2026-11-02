# Proposal

## Why

Issue #2742 reports that the MCP tool `ai_prewarm` lets a caller set any `model` text. The text becomes a metric label and a span attribute, so many names make many series and an unbounded span value.

## What Changes

- Add `bounded_model_label` in `src/devops_cli/telemetry/instruments.py`.
- Use the helper for the `model` label of `devops_cli_ai_prewarms_total` and the `ai.model` attribute of the `ai.prewarm` span in `src/devops_cli/commands/ai.py`.
- Build the allowed set from `settings.ai.model` and `client.list_models()`, and fall back to the configured model when the call raises.
- Add offline tests in `tests/test_ai_prewarm_cardinality.py`.
- Add spec requirements to `ai-prewarm` for the bounded label and span attribute.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-prewarm`: Bounded model label cardinality, Bounded prewarm span model attribute

## Impact

- Code: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/commands/ai.py`
- Tests: `tests/test_ai_prewarm_cardinality.py`

## Feasibility

- The inputs show the raw span attribute in the `trace_span("ai.prewarm", ...)` call and the length-bounded metric label in the `emit(AI_PREWARMS_TOTAL, ...)` call in `src/devops_cli/commands/ai.py`.
- The inputs show `bounded_label` in `src/devops_cli/telemetry/instruments.py`; the change reuses it for character and length bounds.
- The inputs show the archived design of #2676 in `openspec/changes/archive/2026-10-30-2676-prewarm-output-server-labels/design.md`; it rejected a fixed model list and a hash.
- The issue can be built as written. No block is present.
- First check: `uv run devops ci test tests/test_ai_prewarm_cardinality.py` runs the offline tests.
- First real-system check: `uv run devops ai prewarm --model <model> --json` with `ai.provider=ollama` and a loopback listener exercises the command path.
- Second real-system check: `uv run devops telemetry test` sends a test metric to the collector.

## Existing Tool Considered

OpenTelemetry Python SDK (Apache-2.0) carries the counter and the span. It does not bound the number of label values. The change adds a project-specific `bounded_model_label` of about 300 tokens to write, keep and fix, and under one hour of elapsed time. The change deletes no internal code.
