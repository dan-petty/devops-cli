## MODIFIED Requirements

### Requirement: The devops stack includes the role-scoped MCP server and disables workload telemetry banners
`k8s/devops/kustomization.yaml` and `MANIFESTS_BY_STACK["devops"]` SHALL include `k8s/devops/mcp-server/` (`deployment.yaml`, `service.yaml`, `networkpolicy.yaml`, `networkpolicy-client.yaml`), and `mcp-server`, `cronjob-runner`, and `roadmap-service` SHALL set `DO_NOT_TRACK=1`, `OPENSPEC_TELEMETRY=0`, `OPENSPEC_NO_UPDATE_CHECK=1`, and `PYDANTIC_AI_NO_BANNER=1`.

#### Scenario: The devops kustomization and workload manifests are read
- **WHEN** `uv run devops ci --check --only k8s` renders Application `devops`, and a person reads the render
- **THEN** `mcp-server` is listed in `k8s/devops/kustomization.yaml` and `MANIFESTS_BY_STACK["devops"]`
- **AND** `mcp-server`, `cronjob-runner`, and `roadmap-service` set the four telemetry and banner opt-out variables

### Requirement: The Service reads its own gateway key
The roadmap Service Deployment SHALL read `DEVOPS_CLI_AI_API_KEY` from key `api-key` of Secret `roadmap-service-llm-key`. Its pod template SHALL NOT hold an `envFrom` entry for Secret `devops-cli`, and each other variable of that Secret SHALL have an explicit `secretKeyRef`, with `optional: true` on the four optional keys.

#### Scenario: The rendered Deployment
- **WHEN** a person runs `kubectl -n devops get deployment roadmap-service -o yaml` on the cluster
- **THEN** `DEVOPS_CLI_AI_API_KEY` has one `secretKeyRef` to `roadmap-service-llm-key` with key `api-key`, the pod template has no `envFrom`, and each other variable names its key of `devops-cli`

## ADDED Requirements

### Requirement: The ConfigMap render refuses a key that no setting declares
The render of ConfigMap `devops-cli-config` from `k8s/devops/configmap.example.yaml` SHALL refuse a template whose config holds a key that no settings model declares, and SHALL name each such key by its dotted path. The settings models ignore an unknown key, so without the refusal a key that a change removed from the settings stays in the template with no error.

#### Scenario: A template holds an unknown key
- **WHEN** the render reads a template whose config holds `telemetry.not_a_setting` and the section `not_a_section`
- **THEN** it raises `KubernetesContextError`, and the message names `not_a_section` and `telemetry.not_a_setting`

#### Scenario: The committed template renders
- **WHEN** `uv run devops k8s deploy-stack --stack devops --dry-run` renders the ConfigMap from `k8s/devops/configmap.example.yaml`
- **THEN** the render names no unknown key
