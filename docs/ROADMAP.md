# Project Roadmap — devops-cli

> **Vision:** A secure, privacy-first DevOps CLI designed to run natively inside Dev Containers on developer workstations. Combines infrastructure automation (Git, Kubernetes, ArgoCD, Grafana, SSH) with multi-persona Agentic LLM code reviews, OS keyring secret isolation, and strict verification loops.

---

## Strategic Goals

1. **DevOps Engineering Workstation Native**: Zero bare-metal sprawl. All operations run deterministically inside dev containers with verified binary dependencies and isolated configuration layers.
2. **Privacy & SSRF-Defended AI Integrations**: Multi-provider LLM client (Ollama, Claude, Copilot, OpenAI-compatible) with mandatory private-network egress guards (`DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true`).
3. **Auditable & Verifiable AI Code Reviews**: Automated multi-persona reviews (`devsecops`, `architect`, `pm`, `auditor`, `qa`) with automated LLM verification, human invalidation feedback loops, and structured audit logs.

---

## Phased Milestones

### Phase 1: Core Foundation & Modernization (Completed)
- [x] Python 3.14+ runtime with `uv` dependency management.
- [x] OS Keyring integration (`keyring`) for zero-plaintext secret storage.
- [x] Multi-persona code review engine with diff pagination (`devops review branch|pr|path`).
- [x] Infrastructure commands: `repos`, `ssh`, `k8s`, `argo`, `grafana`, `prometheus`, `docker`.
- [x] `devops ci` unified quality gate (pytest, ruff check, ruff format, mypy strict).

### Phase 2: Finding Verification & Human Feedback Loop (Current)
- [x] Structured finding schema with verification status (`UNVERIFIED`, `VERIFIED`, `INVALIDATED`, `MITIGATED`).
- [x] Finding inspection & human invalidation CLI (`devops review findings`, `devops review verify`).
- [x] Review accuracy metrics & false-positive analytics (`devops review stats`).
- [x] Robust RFC 1123 label sanitization and path traversal guards across all subcommands.

### Phase 3: Enhanced PR Collaboration & Customization (Short-Term: Q3 2026)
- [ ] **GitHub PR Inline Line-Level Comments**: Post persona review findings directly to specific lines on GitHub PRs via PyGithub REST/GraphQL APIs.
- [ ] **Custom Persona Prompting**: Project-level `.devops/personas/` prompt overrides allowing teams to define domain-specific reviewer personas.
- [ ] **Prompt Fine-Tuning Pipeline**: Export human-invalidated findings (`status="INVALIDATED"`) as benchmark datasets for prompt tuning.

### Phase 4: Enterprise Infrastructure & Governance (Mid-Term: Q4 2026)
- [ ] **Multi-Cluster Kubeconfig Management**: Seamless context switching with namespace access control policies.
- [ ] **SIEM Audit Log Streaming**: Optional JSON audit trail output to Syslog / CloudWatch / Datadog for compliance reporting (PCI-DSS, SOC 2).
- [ ] **ArgoCD Multi-App Batch Sync**: Parallel sync operations with health dependency checks.

### Phase 5: Autonomous Remediation & Offline Bundling (Long-Term: 2027+)
- [ ] **Automated Code Patch Application**: Apply suggested LLM fixes (`finding.fix`) directly to source files with interactive git staging.
- [ ] **Air-Gapped Container Bundles**: Pre-packaged devcontainers with local Ollama models and pre-verified CLI binaries for offline environments.

---

## Strategic Prioritization Matrix (Value vs. Effort)

| Category | Milestone / Feature | Value | Effort | Rationale & Impact |
|---|---|---|---|---|
| **Quick Wins** | Finding Invalidation CLI & Stats | **High** | **Low** | Enables human verification loops and false-positive tracking with minimal code footprint. |
| | RFC 1123 & Path Traversal Guards | **High** | **Low** | Hardens input validation against injection and path traversal with low implementation overhead. |
| | Pydantic Schema Model Unification | **High** | **Low** | Replaces complex dict parsing with type-checked models, improving IDE auto-complete and maintainability. |
| **Strategic Investments** | Line-Level GitHub PR Inline Comments | **High** | **High** | High developer UX impact; requires diff position mapping and PyGithub GraphQL API integration. |
| | Custom Persona Prompt Overrides | **High** | **Medium** | Enables team-specific governance rules (`.devops/personas/`) without altering core codebase. |
| | Human Invalidation Dataset Exporter | **High** | **Medium** | High long-term value for automated LLM prompt tuning and benchmark creation. |
| **Fill-ins** | Multi-Cluster Kubeconfig Management | **Medium** | **Medium** | Useful for multi-environment cluster management; standard `kubectl` context switching mitigates urgency. |
| | SIEM Audit Log Streaming | **Medium** | **Low** | Structured JSON logging meets compliance audit needs; simple handler addition. |
| | Headless Keyring Fallback Auth | **Medium** | **Medium** | Unblocks headless CI containers where DBus / SecretService is unavailable. |
| **De-prioritized** | Bare-Metal OS Installers | **Low** | **High** | Direct conflict with workstation DevContainer design policy; adds maintenance debt without adding value. |

