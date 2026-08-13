# Pending Features & Design Proposals — devops-cli

Tracks active feature proposals, architectural spikes, and planned functionality for upcoming milestones.

---

## 🎯 Active Proposals & Architectural Spikes (v0.1.8+)

### 1. AI Agent Pipeline Tooling Research & Benchmark
- **Overview**: Conduct architectural evaluation and benchmarking of open-source AI agent frameworks & orchestrators (LangChain/LangGraph, AutoGen, CrewAI, LlamaIndex, DSPy, Haystack).
- **Goal**: Assess integration patterns with `devops-cli` Pydantic models, FastMCP tool registrations, and local LLM node failover mechanisms to enhance multi-agent pipeline orchestration.

### 2. Observability & K8s Telemetry Stack (OpenTelemetry, Prometheus, Grafana, Jaeger & Minikube)
- **Overview**: Native telemetry instrumentation for `devops-cli` commands, FastMCP server tools, and multi-agent persona pipelines.
- **Components**:
  1. OpenTelemetry distributed tracing across agent pipeline stages and FastMCP tool executions.
  2. Prometheus metrics exporter for review latency, token usage, finding counts, and tool throughput.
  3. Pre-configured Grafana telemetry dashboards.
  4. Local Jaeger collector deployment via Minikube.

### 3. Supply Chain Security & Container Provenance (Cosign)
- **Overview**: Keyless image signing and signature verification (`devops docker sign|verify`) integrating Sigstore Cosign with OS Keyring.

### 4. IaC FinOps & Cloud Cost Impact Analysis (Infracost)
- **Overview**: Automated cloud cost estimation (`devops iac cost`) on Terraform diffs to enrich `pm` and `architect` persona review payloads.

### 5. Automated IaC Static Security Policy Guard (Checkov)
- **Overview**: Compliance and security policy scanner (`devops ci iac-security`) across Terraform, CloudFormation, Kubernetes manifests, and Dockerfiles.

---

## ✅ Completed Features Summary

| Feature / Capability | Version | Description |
|---|---|---|
| **DevContainer Lifecycle Engine** | `v0.1.7` | Native Python lifecycle commands (`devops devcontainer run-lifecycle`) replacing legacy shell scripts. |
| **Enhanced AI Scratchpad Buffer** | `v0.1.7` | Structured `ScratchpadBuffer` maintaining multi-turn reasoning context across review stages. |
| **Prompt Token & Latency Optimization** | `v0.1.7` | Compact JSON serialization and streamlined prompt schemas to minimize inference latency. |
| **SecOps Static Security Engine** | `v0.1.6` | Integrated Aqua Trivy (`devops scan`), Red Hat Kube-linter, Derailed Popeye, and Pluto. |
| **Minikube Endpoint Auto-Config** | `v0.1.5` | Automated NodePort detection (`devops k8s configure-urls`) updating `config.yaml`. |
| **7-Gate CI Quality Gate** | `v0.1.5` | Sequential quality gate enforcing tests, coverage, lint, format, typecheck, audit, and security. |
| **Default AI Metadata Analysis** | `v0.1.4` | Default `--enhanced` metadata generation, incremental caching, and submodule imports. |
| **Interactive Patch Staging** | `v0.1.3` | Interactive unified diff rendering and confirmation before applying suggested LLM fixes. |
| **Air-Gapped Ollama Model Bundler** | `v0.1.3` | Export and packaging of local Ollama model weight manifests for offline devcontainers. |
| **Kubernetes RBAC Audit Policy** | `v0.1.3` | Overprivileged RoleBinding and ServiceAccount security audit scanner. |
| **Multi-Cluster Kubeconfig Management** | `v0.1.2` | Context switching and cluster namespace controls (`devops k8s switch-context`). |
| **SIEM Live Audit Streamer** | `v0.1.2` | Structured JSON audit trail logging and syslog/HTTP streaming. |
| **Line-Level PR Inline Comments** | `v0.1.1` | Automated posting of persona findings directly to GitHub PR line hunks. |
| **Human Invalidation Feedback Exporter** | `v0.1.1` | Exporting false-positive review datasets into JSONL for prompt tuning. |
| **Custom Team Persona Overrides** | `v0.1.1` | Repository-level custom persona prompt definitions (`.devops/personas/<name>.md`). |
| **Headless CI Ephemeral Auth** | `v0.1.1` | Memory secret storage fallback for DBus-less headless Linux CI environments. |

---

## 📊 Upcoming Roadmap Prioritization & ROI Matrix

| Feature Proposal | Target Release | Priority Tier | Value | Effort | ROI & Focus |
|---|---|---|---|---|---|
| **1. AI Agent Framework Research & Benchmark** | `v0.1.8` | **P1 (High)** | High | Medium | **High Impact**: Benchmarks open-source agentic orchestrators (LangGraph, CrewAI, AutoGen). |
| **2. OpenTelemetry & Jaeger Tracing** | `v0.1.8` | **P1 (High)** | High | High | **High Impact**: End-to-end distributed tracing across multi-agent pipelines and FastMCP tools. |
| **3. Prometheus & Grafana Telemetry** | `v0.1.8` | **P2 (Medium)** | High | Medium | **High Impact**: Real-time performance dashboards and CLI workload analytics. |
| **4. Infracost IaC FinOps Engine** | `v0.1.9` | **P2 (Medium)** | High | Medium | **High Impact**: Cloud cost impact estimation in `pm` and `architect` persona reviews. |
| **5. Cosign Image Signing & Provenance** | `v0.1.9` | **P2 (Medium)** | High | Low | **High Impact**: Supply chain image verification via OS Keyring. |
| **6. Checkov Static IaC Security Policy** | `v0.1.9` | **P3 (Lower)** | Medium | Low | **Niche Impact**: Automated static compliance policies across Terraform and Dockerfiles. |
