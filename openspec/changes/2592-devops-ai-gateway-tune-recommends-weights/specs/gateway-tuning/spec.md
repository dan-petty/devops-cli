## ADDED Requirements

### Requirement: tune-report-excludes-weight-columns
The tune command report table SHALL NOT include columns for current weight, recommended weight, or max parallel requests.

#### Scenario: table headers exclude weight columns
- **WHEN** the tune command renders its report table
- **THEN** the table headers do not contain Weight, Recommended, or Max Parallel

### Requirement: tune-footer-omits-weight-instruction
The tune command footer SHALL NOT instruct the user to set litellm_params.weight on any deployment.

#### Scenario: footer omits weight instruction
- **WHEN** the tune command prints its footer after the table
- **THEN** the footer text does not contain the string litellm_params.weight

### Requirement: tune-docstring-names-least-busy
The module docstring of gateway_tune.py SHALL describe the least-busy routing strategy and SHALL NOT describe simple-shuffle as the gateway routing method.

#### Scenario: docstring reflects actual routing
- **WHEN** the module docstring of src/devops_cli/ai/gateway_tune.py is read
- **THEN** it contains least-busy and does not contain simple-shuffle as the routing strategy

### Requirement: tune-help-describes-measurement
The tune command help text SHALL describe measuring and reporting per-deployment capacity, and SHALL NOT say it recommends routing weights.

#### Scenario: help text omits weight recommendation
- **WHEN** devops ai gateway tune --help is run
- **THEN** the help text does not contain the phrase recommend routing weights

### Requirement: settings-model-has-no-weight-fields
The settings model SHALL NOT define gateway_weights or gateway_concurrency fields under the ai section.

#### Scenario: settings model has no weight fields
- **WHEN** the settings model is loaded and inspected
- **THEN** the ai section has no gateway_weights field and no gateway_concurrency field

### Requirement: module-exports-exclude-weight-functions
The module gateway_tune.py SHALL NOT define or export recommend_weights, calculate_hardware_weights, or calculate_hardware_concurrency.

#### Scenario: module exports exclude weight functions
- **WHEN** src/devops_cli/ai/gateway_tune.py is imported
- **THEN** the module __all__ does not contain recommend_weights, calculate_hardware_weights, or calculate_hardware_concurrency
