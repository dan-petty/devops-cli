# Design

## Decisions

- **Remove all three weight functions and their helpers rather than keeping them behind a flag**: The gateway uses least-busy and reads no weight. No other code path calls these functions. The pre-1.0 policy is to delete dead code.
- **Remove recommended_weight and recommended_concurrency from DeploymentTune**: No function computes them after the change. Keeping unset fields in the model misleads the reader.
- **Keep current_weight in DeploymentTune**: It is read from the gateway model info and is informational data. The table does not show it, but JSON output can carry it.
- **Remove ai.gateway_weights and ai.gateway_concurrency settings**: No code reads them after the change. The gateway reads no weight. Keeping dead settings misleads the user.

## Rejected alternatives

- **Keep weight columns but mark them informational**: The user cannot apply the value. Keeping it adds noise and implies an action that does not exist. The gateway uses least-busy and reads no weight.
- **Keep the settings for a future routing strategy**: Speculative. The project is pre-1.0 and the pre-1.0 policy is to delete, not keep behind flags.
- **Keep the functions for reuse**: No other code path uses them. Keeping unused functions adds maintenance cost.
