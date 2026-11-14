## ADDED Requirements

### Requirement: The Service reads its own gateway key
The roadmap Service Deployment SHALL read `DEVOPS_CLI_AI_API_KEY` from key `api-key` of Secret `roadmap-service-llm-key`. Its pod template SHALL NOT hold an `envFrom` entry for Secret `devops-cli`, and each other variable of that Secret SHALL have an explicit `secretKeyRef`, with `optional: true` on the four optional keys.

#### Scenario: The rendered Deployment
- **WHEN** `kustomize build k8s/devops/roadmap-service/` renders the Deployment
- **THEN** `DEVOPS_CLI_AI_API_KEY` has one `secretKeyRef` to `roadmap-service-llm-key` with key `api-key`, the pod template has no `envFrom`, and each other variable names its key of `devops-cli`
