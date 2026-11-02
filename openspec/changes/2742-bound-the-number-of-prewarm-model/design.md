# Design

## Decisions

- **Bound the label to the configured model, the server-reported models, and `other`.**: The issue expects this set. It keeps valid server models readable and caps unknown names at one value.
- **Use one helper for the metric label and the span attribute.**: The issue requires the same bounded text in both records. One helper prevents drift.
- **Place `bounded_model_label` in `src/devops_cli/telemetry/instruments.py`.**: `bounded_label` lives there. The function is a telemetry concern and other commands can reuse it.
- **Call `client.list_models()` once before the span and fall back to the configured model on an exception.**: The span attribute needs its value before the span starts. A failed list call must not fail the prewarm.
- **Reuse `bounded_label` for character and length bounds.**: It already bounds the label from #2676. The new helper adds only the cardinality bound.

## Rejected alternatives

- **Bound to the configured model only.**: The issue expects the configured model and the models that the configured servers report. A valid server model would show as `other`.
- **Apply `bounded_label` only.**: The issue reports 10000 series from 10000 model names. A character and length bound does not cap the number of values.
- **Put the mapping inline in `src/devops_cli/commands/ai.py`.**: The archived design of #2676 places `bounded_label` in `src/devops_cli/telemetry/instruments.py`. The mapping is a telemetry concern.
- **Hash the model name.**: The archived design of #2676 rejected a hash because a person cannot read it in a dashboard.
- **Keep a fixed list of model names.**: The archived design of #2676 rejected a fixed list because each new model needs an edit.
