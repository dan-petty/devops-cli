## ADDED Requirements

### Requirement: A local gateway group counts as local
`is_local` SHALL count a gateway reply as local when it names a local group of `k8s/llm/gateway/config.yaml` or a model with the `ollama/`, `ollama_chat/` or `ollama:` prefix, and it SHALL keep a hosted group hosted.

#### Scenario: A local fallback
- **WHEN** a gateway reply names `ollama_chat/qwen3.8:27b`
- **THEN** `is_local` is true and the record holds the source `local`

#### Scenario: A local group outside the virtual models
- **WHEN** a gateway reply names `devops-review`, `devops-background`, `devops-triage`
- **THEN** `is_local` is true

#### Scenario: A hosted group
- **WHEN** a gateway reply names `claude-sonnet-5-5`
- **THEN** `is_local` is false
