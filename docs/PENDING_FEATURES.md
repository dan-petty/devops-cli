# Pending Features & Design Proposals — devops-cli

Tracks active feature proposals, architectural spikes, and planned functionality.

---

## 1. Line-Level GitHub Pull Request Inline Comments
- **Overview**: Map `Finding.location` (e.g. `src/config.py:72-85`) to GitHub PR diff Hunk position offsets via PyGithub/GraphQL to post findings directly inline on PR Files Changed views.
- **Deduplication**: Prevent re-posting duplicate inline comments across re-runs on the same commit SHA.

---

## 2. Human Invalidation Feedback Loop for Prompt Tuning
- **Overview**: Export invalidated findings (`status="INVALIDATED"`) recorded via `devops review verify` into benchmark datasets (`devops review export-feedback`) to refine persona prompt instructions and few-shot examples.

---

## 3. Custom Team Persona Definitions
- **Overview**: Support repository-level persona definitions under `.devops/personas/<name>.md`, dynamically loaded during `devops review path|branch|pr --persona <custom_name>`.

---

## 4. Keyring Fallback & Headless Environment Auth
- **Overview**: Provide `devops config auth-headless` to securely load session tokens into ephemeral memory for headless Linux CI runners lacking DBus / SecretService.

---

## 5. Observability & K8s Telemetry Stack (OpenTelemetry, Prometheus, Grafana, Jaeger & Minikube)
- **Overview**: Native telemetry instrumentation for `devops-cli` commands, FastMCP server tools, and multi-agent persona pipelines. Includes automated local Minikube cluster provisioning inside DevContainer for zero-dependency local testing of OpenTelemetry collector, Prometheus metrics, Grafana dashboards, and Jaeger distributed tracing.

---

## 6. SecOps & K8s Security Integrations (Trivy, Kube-linter, Popeye, Pluto)
- **Overview**: Integration of 4 open-source SRE/security static engines:
  1. `devops scan [repo|image|iac]`: Aqua Trivy vulnerability & secret scanning with finding injection into `devsecops` persona reviews.
  2. `devops k8s lint`: Red Hat Kube-linter static K8s manifest & Helm chart security analysis.
  3. `devops k8s audit`: Derailed Popeye live Minikube/K8s cluster health sanitizer.
  4. `devops k8s check-deprecated`: Fairwinds Pluto deprecated K8s API version scanner.

---

## 7. DevContainer Shell Script Replacement Engine
- **Overview**: Implement native CLI commands (`devops devcontainer run-lifecycle --post-create|--post-start`) to replace `.devcontainer/postCreate.sh` and `.devcontainer/postStart.sh` shell scripts with type-safe, cross-platform Python execution.

---

## 8. Feature Prioritization & Implementation ROI

| Feature Proposal | Priority Tier | Value | Effort | ROI & Sequencing |
|---|---|---|---|---|
| **1. SecOps & K8s Security (v0.1.6)** | **Completed** | High | Low | **High Impact**: Embeds Trivy, Kube-linter, Popeye & Pluto static analysis. |
| **2. DevContainer Script Replacement (v0.1.7)** | **P1 (Highest)** | High | Medium | **High Impact**: Replaces shell scripts with cross-platform `devops devcontainer` lifecycle commands. |
| **3. Line-Level PR Inline Comments** | **P1 (Highest)** | High | High | **High Impact**: Anchors persona findings directly to PR diff lines via PyGithub. |
| **4. Invalidation Feedback Exporter** | **P1 (High)** | High | Medium | **High Impact**: Exports false-positive datasets for continuous prompt tuning. |
| **5. Custom Team Persona Prompts** | **P2 (Medium)** | High | Medium | **Medium Impact**: Enables team-specific governance overlays (`.devops/personas/`). |
| **6. Observability & K8s Telemetry** | **P2 (Medium)** | High | High | **High Impact**: Full OpenTelemetry, Prometheus, Grafana & Jaeger tracing via Minikube. |
| **7. Headless Keyring Auth Fallback** | **P3 (Lower)** | Medium | Medium | **Niche Impact**: Unlocks headless CI runners without DBus. |
