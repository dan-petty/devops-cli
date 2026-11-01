## ADDED Requirements

### Requirement: uniform-kv-cache-type
All Ollama tiers that serve the embedding model SHALL set OLLAMA_KV_CACHE_TYPE to the same value.

#### Scenario: all-tiers-share-one-kv-cache-type
- **WHEN** the ollama-profiles.yaml is parsed and every DaemonSet container env block is read
- **THEN** every OLLAMA_KV_CACHE_TYPE value is q8_0
