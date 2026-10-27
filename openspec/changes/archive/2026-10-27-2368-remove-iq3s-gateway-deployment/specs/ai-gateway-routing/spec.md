# Spec Delta

## ADDED Requirements

### Requirement: The gateway routes qwen3.8:27b and devops-chat only to 48gib and 64gib tiers
The gateway configuration SHALL NOT deploy `qwen3.8:27b` or `devops-chat` to the 16gib serving tier. Deployments for `qwen3.8:27b` and `devops-chat` SHALL only target serving tiers with at least 48 GiB total VRAM.

#### Scenario: Gateway deployments for qwen3.8:27b and devops-chat
- **WHEN** the gateway configuration is loaded
- **THEN** every deployment for `qwen3.8:27b` and `devops-chat` targets `ollama-48gib-fast` or `ollama-64gib-standard`, and no deployment targets `ollama-16gib-fast`
