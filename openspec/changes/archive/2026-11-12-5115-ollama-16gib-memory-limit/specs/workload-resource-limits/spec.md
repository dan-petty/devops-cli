## ADDED Requirements

### Requirement: The 16 GiB Ollama tier limits its memory to its request
The container `ollama` of the DaemonSet `ollama-16gib` (`k8s/llm/profiles/ollama-profiles.yaml`) SHALL have a memory request of `8Gi` and a memory limit of `8Gi`. Its CPU request SHALL stay `3000m`, with no CPU limit.

#### Scenario: The profiles manifest is read
- **WHEN** `k8s/llm/profiles/ollama-profiles.yaml` is read
- **THEN** the container `ollama` of `ollama-16gib` requests `8Gi` of memory and limits its memory to `8Gi`
