## ADDED Requirements

### Requirement: The record keeps the size of the first request of each step
The implement job SHALL record in `implement.spend`, under `steps`, the input tokens of the first model request of each step, from the usage of the first reply of the step. The job SHALL write the figure apart from the trace, so the limit of the trace never drops it.

#### Scenario: A step records its first request
- **WHEN** a step makes two model requests
- **THEN** `implement.spend` holds for that step the input tokens of the first request, and they equal `tokens_in` of the first `model` event of the step.

#### Scenario: A trace over its limit keeps the figure
- **WHEN** a run has more events than `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` allows
- **THEN** the trace has a `dropped` count above 0, and `implement.spend` still holds the first-request figure of each step.
