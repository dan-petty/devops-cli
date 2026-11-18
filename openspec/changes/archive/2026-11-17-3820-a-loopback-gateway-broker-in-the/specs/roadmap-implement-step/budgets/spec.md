## ADDED Requirements

### Requirement: A shell call through the broker counts as a model call of the step
A request that the broker forwards SHALL count against the step budget as a model call of the agent: `StepBudget.add` SHALL take the new tokens of its gateway usage. The step SHALL record its requests, input tokens, cache-read tokens and output tokens in `StepOutcome.tier_spend` under the tier of the attempt that made the call, and SHALL stop at its budget before its next model request.

#### Scenario: The budget and the tier record hold the shell call
- **WHEN** A shell call through the broker returns a gateway answer with usage on the tier of the current attempt
- **THEN** The step budget counts the new tokens of that usage and the tier record of that tier holds the same requests and tokens as a model call of the agent
