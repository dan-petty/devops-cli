# Strategic Roadmap — devops-cli

High-density product roadmap for `devops-cli`.

## Core Vision & Design Principles
1. **Workstation-Native DevContainer First**: Native to local Dev Container workstation environments with Python 3.14+ and `uv`.
2. **Zero-Plaintext Secret Isolation**: Mandatory OS Keyring integration (`keyring`) for tokens (`github`, `grafana`, `argocd`, `ai`).
3. **SSRF-Defended AI Integrations**: Multi-provider LLM client (`ollama`, `claude`, `copilot`, `openai`) with private-network egress guards (`DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true`).
4. **Auditable AI Code Reviews**: Multi-persona reviews (`devsecops`, `architect`, `pm`, `auditor`, `qa`) with static metadata extraction (`SegmentMeta`), prompt isolation guardrails, and finding verification loops.

---

## Phased Milestones

### Phase 1: Core Foundation & Modernization (Completed)
- [x] Python 3.14+ runtime with `uv` virtual environment management.
- [x] OS Keyring integration for zero-plaintext secret storage.
- [x] Multi-persona code review engine with diff pagination (`devops review branch|pr|path`).
- [x] Infrastructure subcommands: `repos`, `ssh`, `k8s`, `kustomize`, `argo`, `grafana`, `prometheus`, `docker`, `workspace`, `install-tools`, `config`, `ci`, `branches`, `devcontainer`, `uv`.
- [x] `devops ci` unified quality gate (pytest, ruff check, ruff format, strict mypy).

### Phase 2: Finding Verification & Security Hardening (Completed)
- [x] Structured finding schema with verification status (`UNVERIFIED`, `VERIFIED`, `INVALIDATED`, `MITIGATED`).
- [x] Finding inspection & human invalidation CLI (`devops review findings`, `devops review verify`, `devops review stats`).
- [x] Fast deterministic segment metadata extraction (`SegmentMeta` / `ReviewMeta`) upfront in <5ms.
- [x] Security hardening: Python 2 exception syntax fixes, path traversal boundary checks, and prompt boundary tag sanitization.
- [x] `devops config output` subcommand displaying metadata for all 30 environment variables.

### Phase 3: Enhanced PR Collaboration & Customization (Short-Term: Q3 2026)
- [ ] **Line-Level GitHub PR Inline Comments**: Post persona review findings directly to PR diff line hunks via GitHub API (`devops review pr --post-inline`).
- [ ] **Human Feedback Exporter**: Export invalidated findings (`status="INVALIDATED"`) as benchmark datasets for prompt tuning (`devops review export-feedback`).
- [ ] **Custom Team Personas**: Repository-level `.devops/personas/` prompt overrides allowing custom reviewer personas.

### Phase 4: Enterprise Infrastructure & Governance (Mid-Term: Q4 2026)
- [ ] **Multi-Cluster Kubeconfig Management**: Seamless context switching with namespace access control policies.
- [ ] **SIEM Audit Log Streaming**: Optional JSON audit trail output to Syslog / CloudWatch for compliance reporting.
- [ ] **Headless CI Keyring Fallback Auth**: Memory token loading (`devops config auth-headless`) for headless CI environments lacking DBus.

### Phase 5: Autonomous Remediation & Offline Bundling (Long-Term: 2027+)
- [ ] **Automated Code Patch Application**: Apply suggested LLM fixes (`finding.fix`) directly to source files with interactive git staging.
- [ ] **Air-Gapped Container Bundles**: Pre-packaged devcontainers with local Ollama models for offline environments.

---

## Value vs. Effort Prioritization Matrix

| Priority Category | Feature / Focus | Value | Effort | Status |
|---|---|---|---|---|
| **Quick Wins** | Input Sanitization & Path Traversal Guards | High | Low | ✅ Completed |
| | Human Finding Verification CLI & Accuracy Stats | High | Low | ✅ Completed |
| | Deterministic Static Segment Metadata (`SegmentMeta`) | High | Low | ✅ Completed |
| | Prompt Isolation Guardrails & Tag Sanitization | High | Low | ✅ Completed |
| | `devops config output` Env Var Spec Command | High | Low | ✅ Completed |
| **Strategic Investments** | Line-Level GitHub PR Inline Comments | High | High | 🔄 Short-Term (Q3 2026) |
| | Human Feedback Dataset Exporter | High | Medium | 🔄 Short-Term (Q3 2026) |
| | Custom Team Persona Overrides (`.devops/personas/`) | High | Medium | 🔄 Short-Term (Q3 2026) |
| **Fill-ins** | Non-Interactive GitHub CLI Timeout Config | Medium | Low | ℹ️ Mitigated via Env Var |
| | Ephemeral Headless Keyring Auth | Medium | Medium | 🔄 Mid-Term (Q4 2026) |
| **De-prioritized** | Bare-Metal OS Installers | Low | High | ❌ Rejected (Devcontainer native) |
