## MODIFIED Requirements

### Requirement: The gateway sends the 48 GiB and 64 GiB tiers one model
Every gateway deployment that calls a Service which selects `ollama-48gib` or `ollama-64gib` SHALL name `ollama_chat/qwen3.8:27b`. No embedding deployment SHALL call either tier. A tier rendered from a template above the `embedding_only` threshold SHALL get no embedding deployment, and the 48 GiB template SHALL keep one model loaded.

#### Scenario: A second model on a tier
- **WHEN** a gateway deployment sends `qwen3-coder:30b`, `gemma4:31b` or an embedding model to `ollama-48gib-fast` or `ollama-64gib-standard`
- **THEN** the check that reads the gateway config fails

#### Scenario: A chat tier from a template
- **WHEN** a tier template is rendered above the `embedding_only` threshold
- **THEN** the render writes no embedding deployment for it

#### Scenario: Embeddings keep their tiers
- **WHEN** the gateway config is loaded
- **THEN** `qwen3-embedding:0.6b` has deployments on `ollama-24gib-embed-gpu0` and `-gpu1` at order 1, and on no other tier

## ADDED Requirements

### Requirement: The gateway sends the 16 GiB tier nothing
The GPU placement table of `k8s/README.md` SHALL mark `ollama-16gib` as not serving. No gateway deployment, review slot, route of the GPU matrix or devcontainer setting SHALL name a Service that selects that tier. The DaemonSet `ollama-16gib` and its Services SHALL stay in the profiles.

#### Scenario: The consumers of the tier
- **WHEN** the gateway config, `DEFAULT_GATEWAY_REVIEW_SLOTS`, the routes of the GPU matrix and the devcontainer are read
- **THEN** none names `ollama-16gib` or `ollama-16gib-fast`, and the DaemonSet and the Services are in the profiles

#### Scenario: The review pool
- **WHEN** the gateway config and the defaults are read
- **THEN** `DEFAULT_GATEWAY_REVIEW_CONCURRENCY` is 2, and each deployment of `devops-review` and `devops-background` has the window 262144

#### Scenario: A tier that stops serving
- **WHEN** the check runs with a tier that consumers reach marked as not serving
- **THEN** the check names each consumer that reaches that tier alone
