# Spec Delta

## ADDED Requirements

### Requirement: Gateway routes devops-triage to the standard tier
The LiteLLM gateway configuration SHALL define a `devops-triage` model group with one deployment: `ollama_chat/qwen3.8:27b` on the 64 GiB standard tier.

#### Scenario: The devops-triage route
- **WHEN** the gateway configuration is loaded
- **THEN** `devops-triage` routes to `ollama_chat/qwen3.8:27b` on `http://ollama-64gib-standard.llm.svc.cluster.local:11434`

### Requirement: Gateway fallbacks include triage and background targets
The gateway router settings fallbacks SHALL include `devops-triage: [qwen3.8:27b]` and `devops-background: [qwen3.8:27b]`.

#### Scenario: Fallback routes
- **WHEN** `devops-triage` or `devops-background` fails all retries
- **THEN** the request falls back to `qwen3.8:27b`
