## ADDED Requirements

### Requirement: Every Ollama tier sets one KV cache type
Each DaemonSet in `k8s/llm/profiles/ollama-profiles.yaml` SHALL set `OLLAMA_KV_CACHE_TYPE` to `q8_0`. The KV cache type changes the vectors of an embedding model, so every tier that the gateway sends embeddings to SHALL make the same vector for the same input.

#### Scenario: The KV cache type of the nine tiers
- **WHEN** a check reads the `OLLAMA_KV_CACHE_TYPE` value of every container of every DaemonSet in `k8s/llm/profiles/ollama-profiles.yaml`
- **THEN** it finds nine values, and each of them is `q8_0`
