# Release Notes — devops-cli v1.0.0

Workstation-native DevOps CLI for managing repositories, SSH keys, Kubernetes clusters, Kustomize, ArgoCD, Grafana, Prometheus, Docker, workspace files, and multi-persona AI code reviews.

---

## Highlights

### 🤖 Multi-Persona AI Code Reviews & Prompt Guardrails
- **Specialized Personas**: Multi-persona reviews (`devsecops`, `architect`, `pm`, `auditor`, `qa`).
- **Prompt Isolation Guardrails**: Boundary tag sanitization (`_sanitize_prompt_boundary_tags`) and XML tag framing (`<untrusted_code_diff>`, `<target_code_to_review>`) isolate untrusted reviewed code from LLM instructions.
- **Fast Deterministic Metadata**: Static analysis (`SegmentMeta`) extracts segment metadata upfront in <5ms with 100% consistency.
- **Verification & Analytics**: Inspect findings (`devops review findings`), validate/invalidate entries (`devops review verify`), and track persona accuracy metrics (`devops review stats`).

### 🛡️ Security Hardening & Zero-Plaintext Secret Storage
- **OS Keyring Integration**: All tokens (`github.token`, `grafana.token`, `argocd.token`, `ai.api_key`) stored exclusively in OS keyring via `keyring`.
- **SSRF Defenses**: `validate_service_url` blocks non-public IPs unless `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` is set.
- **Path Traversal Guards**: Strict workspace boundary checks (`_is_safe_workspace_path`) enforce path isolation.
- **Binary Checksum Verification**: `devops install-tools` verifies SHA-256 checksums before installing binaries.

### ⚙️ Complete DevOps Subcommand Suite
- **Comprehensive Commands**: `ai`, `review`, `repos`, `ssh`, `k8s`, `kustomize`, `argo`, `grafana`, `prometheus`, `docker`, `workspace`, `install-tools`, `config`, `ci`, `branches`, `devcontainer`, `uv`.
- **Environment Output Command**: `devops config output` (aliases `env`, `env-vars`) displays metadata for all 30 environment variables with Rich Table, `--export`, and `--json` formats.

---

## Environment & Requirements
- **Runtime**: Python >=3.14 (managed by `uv`)
- **Container**: VS Code Dev Container / Local workstation environment
- **Tool Dependencies**: `kubectl`, `helm`, `minikube`, `kustomize`, `docker`, `gh`
