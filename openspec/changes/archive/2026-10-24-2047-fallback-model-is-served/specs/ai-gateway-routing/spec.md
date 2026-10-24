# Spec Delta

## ADDED Requirements

### Requirement: The default fallback model is a model that the default Ollama tier serves
The default fallback model of `devops ai failover` and `devops ai chaos-model`, and the default model of the harness model slots, SHALL be a model that a deployment of the gateway config sends to a serving tier that the default Ollama Service selects.

#### Scenario: The CLI default and the harness slots
- **WHEN** `devops ai failover` and `devops ai chaos-model` run with no fallback model, and a harness model slot or sub-agent slot is made with no model
- **THEN** each names a model that the gateway config sends to a serving tier of the default Ollama Service

### Requirement: Each Open WebUI default model is a group that the gateway serves
Each model that the `DEFAULT_MODELS` of the Open WebUI values names SHALL be a model group of the gateway config with a deployment on a serving tier. The Open WebUI values SHALL NOT set `MODEL_FILTER_LIST`, which Open WebUI does not read.

#### Scenario: The Open WebUI values
- **WHEN** the Open WebUI values are read
- **THEN** each model of `DEFAULT_MODELS` is a gateway group with a deployment on a serving tier, and the values set no `MODEL_FILTER_LIST`

#### Scenario: A model that the gateway does not serve
- **WHEN** the check reads `qwen2.5-coder:7b`, `devops-flagship` or an Ollama model name that is no group
- **THEN** it names each of them, and it passes `devops-chat` and `qwen3-coder:30b`
