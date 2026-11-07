## ADDED Requirements

### Requirement: The tune report recommends no routing weight and no concurrency
`devops ai gateway tune` SHALL report what it measures for each deployment: the engine, the GPUs, the capacity, the cost and the capabilities. It SHALL NOT recommend a routing weight or a concurrency, and it SHALL NOT tell the reader to set `litellm_params.weight`, because the gateway routes with `least-busy` and reads neither. Its footer SHALL say that the gateway routes with `least-busy` and reads none of the numbers.

#### Scenario: The table shows no weight column and no weight instruction
- **WHEN** `devops ai gateway tune` prints its table for a model group
- **THEN** the table has no column named Weight, Recommended or Max Parallel, the output does not contain `litellm_params.weight`, and the footer says that the gateway routes with `least-busy`

#### Scenario: The JSON report holds no recommendation
- **WHEN** `devops ai gateway tune --format json` runs
- **THEN** no deployment of the report holds `recommended_weight` or `recommended_concurrency`

#### Scenario: The help text says that the command reports
- **WHEN** `devops ai gateway tune --help` runs
- **THEN** the help text does not contain `recommend routing weights`

### Requirement: The setting ai.gateway_weights does not exist
The `ai` section SHALL NOT declare `gateway_weights`, because no command reads it. A config file that still holds `ai.gateway_weights` SHALL stop the load with the error of a refused key, which names the file, the line and the command that removes the key.

#### Scenario: A config file that still holds ai.gateway_weights
- **WHEN** the active config file holds `ai.gateway_weights` on line 2, and a command loads the settings
- **THEN** the message is `Unknown configuration key 'ai.gateway_weights' at <file>:2. Remove it with: devops config unset ai.gateway_weights`
