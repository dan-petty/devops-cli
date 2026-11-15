## ADDED Requirements

### Requirement: The example ConfigMap names the decision model
`k8s/devops/configmap.example.yaml` SHALL set `ai.decision_model` to `typesafe/jev-1.14` once the Service, runner and MCP server images know the key, so a render of the stack keeps the setting.

#### Scenario: A render of the stack names the decision model
- **WHEN** `devops k8s deploy-stack` renders the devops ConfigMap from the example template
- **THEN** the settings hold `ai.decision_model` as `typesafe/jev-1.14` and no error

#### Scenario: The three images know the key
- **WHEN** a person asks `devops config get ai.decision_model` in the Service, in a runner Job and in the MCP server
- **THEN** each prints an empty value and no error, so the key is safe to set
