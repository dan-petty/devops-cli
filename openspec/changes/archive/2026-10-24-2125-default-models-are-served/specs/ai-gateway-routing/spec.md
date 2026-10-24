# Spec Delta

## ADDED Requirements

### Requirement: Each default model of the CLI is a model that the default Ollama tier and the gateway serve
The default of `ai.model`, each model of `devops ai bundle-models`, and the model that a task benchmark runs when it gets no candidate SHALL be a model that a deployment of the gateway config sends to a serving tier that the default Ollama Service selects. Each SHALL also be a model group of the gateway config with a deployment on a serving tier.

#### Scenario: The defaults with no configuration
- **WHEN** the CLI runs with no `ai.model` set, `devops ai bundle-models` runs, and a task benchmark gets no candidate
- **THEN** each names a model that the gateway config sends to a serving tier of the default Ollama Service, and a gateway group with a deployment on a serving tier

#### Scenario: The benchmark with no candidate
- **WHEN** a task benchmark gets an empty list of candidates
- **THEN** it runs the configured `ai.model`

### Requirement: Each virtual model of the GPU matrix is a group that the gateway serves
The virtual model of each hardware profile and of each Service alias that `devops k8s gpu-matrix` shows SHALL be a model group of the gateway config with a deployment on a serving tier.

#### Scenario: The GPU matrix
- **WHEN** `devops k8s gpu-matrix` reads its profiles and Service aliases
- **THEN** each virtual model is a gateway group with a deployment on a serving tier, and a 70B profile names `deepseek-r1:70b`
