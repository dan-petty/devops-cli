# Design

## Decisions

- **Set the value in the example; do not remove the line.** The comment above `roadmap.stage` names `step_tokens`, and a reader of the example sees the budget. The value is the default, so it needs a change only when the default changes. A test that compares the example with the default would pin it again, so none is added.
- **Remove the tests that pin tuned values.** The filter, the limit, the step tokens, the models, the window and the telemetry endpoint are the owner's to tune. A test of them states no requirement.
- **Keep the tests that state a requirement or a safety property.** The retry count is a requirement (`roadmap-service-deployment`). The example must validate as settings, call the model through the gateway in the cluster, and hold no credential.

## Rejected alternatives

- **Remove `step_tokens` from the example so the default applies.** The example then hides the setting that its comment names, and a later change of the default would be silent for a reader.
- **Replace the pins with a test that the example equals the default.** It pins the value again and fails at each tuning, which is the cost this change removes.
