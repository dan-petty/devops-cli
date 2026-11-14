## ADDED Requirements

### Requirement: The roadmap key bootstrap command provisions the virtual key
`devops k8s bootstrap-roadmap-key` SHALL read the gateway master key from Secret `llm-gateway-secrets` in namespace `llm`, call `POST /key/generate` on the LLM gateway, store the generated key in the OS keyring as `roadmap_service.llm_key`, and apply Secret `roadmap-service-llm-key` in namespace `devops` with key `api-key`.

#### Scenario: The command bootstraps the roadmap service key
- **WHEN** `devops k8s bootstrap-roadmap-key` runs without `--dry-run`
- **THEN** it generates a virtual key on the LiteLLM gateway, saves it to the OS keyring, and pushes Secret `roadmap-service-llm-key` to namespace `devops`

#### Scenario: Dry run makes no external modifications
- **WHEN** `devops k8s bootstrap-roadmap-key --dry-run` runs
- **THEN** it lists the planned generation, keyring storage, and Secret push without calling the gateway, writing to the keyring, or modifying the cluster
