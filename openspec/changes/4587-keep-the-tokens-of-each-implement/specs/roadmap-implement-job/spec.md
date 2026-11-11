## ADDED Requirements

### Requirement: The record keeps the tokens of each step
The implement job SHALL record in `implement.spend`, under `steps`, for each step: its model requests, its input tokens, its output tokens, its repair rounds and the input tokens of its largest model request, from the usage of the replies of the step. The job SHALL write these figures apart from the trace, so the limit of the trace never drops them.

#### Scenario: A step whose requests grow
- **WHEN** the requests of a step report an input that grows with the conversation
- **THEN** the entry of the step holds the count of the `model` events of the step, the sums of their `tokens_in` and `tokens_out`, and their largest `tokens_in`, which is above the first request of the step

#### Scenario: A step with a repair round
- **WHEN** the lint check of group 1 fails once and one repair turn fixes it
- **THEN** the entry of group 1 holds 1 repair round and the 4 requests of both turns
