## MODIFIED Requirements

### Requirement: Every Ollama tier runs one Ollama release that runs multimodal embedding models on Linux
Each container and each init container of each DaemonSet in `k8s/llm/profiles/ollama-profiles.yaml` SHALL name one image. The image repository SHALL be `ollama/ollama`, and its tag SHALL be 0.40.4 or later, the first release that runs a multimodal embedding model through `llama-server`.

#### Scenario: Two containers name different images
- **WHEN** a person runs `kubectl -n llm get daemonset -o jsonpath='{..image}'` on the cluster
- **THEN** all of the Ollama containers name the same image

#### Scenario: The tiers name a release below the first that runs multimodal embedding models on Linux
- **WHEN** a person runs `kubectl -n llm get daemonset -o jsonpath='{..image}'` on the cluster
- **THEN** the image repository is `ollama/ollama`
- **AND** the image tag, read as a version, is 0.40.4 or later
