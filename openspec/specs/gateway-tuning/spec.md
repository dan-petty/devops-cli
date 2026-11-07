# gateway-tuning Specification

## Purpose
Measures and estimates AI gateway deployment concurrency capacity and token cost from spend records and hardware bandwidth.

## Requirements

### Requirement: Token cost from spend ledger
The system SHALL read token cost per review request for each backend from the spend ledger when records exist.

#### Scenario: Spend ledger contains tokens for backend
- **WHEN** gateway tuning runs and the spend ledger contains records for a backend
- **THEN** the tuner sets token cost from the ledger without sending synthetic probe requests

### Requirement: Fallback to probe for missing cost records
The system SHALL fall back to a synthetic probe request when the spend ledger contains no records for a backend.

#### Scenario: Spend ledger lacks records for backend
- **WHEN** gateway tuning runs and the spend ledger has no records for a backend
- **THEN** the tuner sends a synthetic probe request to measure token cost

### Requirement: No-load capacity estimation
The system SHALL calculate deployment capacity scaled by GPU memory bandwidth from a prior measured deployment when the estimate option is enabled.

#### Scenario: Estimate option scales capacity by GPU bandwidth
- **WHEN** the user executes gateway tuning with the estimate flag
- **THEN** the system calculates capacity using bandwidth ratio without sending network load to the backend

### Requirement: Persisted run records include estimate mode
The system SHALL record the estimate setting in gateway tuning run records.

#### Scenario: Run record contains estimate attribute
- **WHEN** a gateway tuning execution completes
- **THEN** the persisted run record includes the estimate field

### Requirement: Capability probes execution
The system SHALL run four standardized capability probes (5-field JSON, 10-tool choice, deep recall, and explicit prohibition) using production prompted formats during gateway tuning.

#### Scenario: Capability probes executed for deployment
- **WHEN** gateway tuning executes against active deployments without estimate mode
- **THEN** the system runs all four capability probes and captures response content and completion tokens

### Requirement: Capability scoring and repair tracking
The system SHALL score capability probe responses using deterministic evaluators in pydantic_evals and track whether response repair was required.

#### Scenario: Probes scored and repairs tracked
- **WHEN** capability probe responses are received
- **THEN** deterministic evaluators assess correctness across trials and response repair records repair occurrence

### Requirement: Persist and report measured capabilities
The system SHALL persist probe results per deployment in the run store and report measured capability scores in command outputs.

#### Scenario: Measured capabilities persisted and reported
- **WHEN** gateway tuning completes
- **THEN** run records persist capability probe results per deployment id and reports show measured pass rates or unmeasured status

### Requirement: A refused backend URL keeps its credentials out of the sweep
When the throughput sweep refuses a backend URL that is not an http or https URL with a host, the error text that the sweep records SHALL name no part of the URL.

#### Scenario: A URL with a password and a query token
- **WHEN** `run_level` gets the URL `ftp://user:s3cr3t@example.com/x?token=t0k3n`
- **THEN** the level counts one error, and its `last_error` starts with `ValueError: ` and holds neither `s3cr3t` nor `t0k3n`

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
