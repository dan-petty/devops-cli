# Release Notes — devops-cli v0.2.18

Workstation-native DevOps CLI for managing repositories, SSH keys, Kubernetes clusters, Kustomize, ArgoCD, Grafana, Prometheus, Docker, workspace files, vector embedding benchmarks, TLS certificate automation, OpenTelemetry observability, Valkey distributed caching, and multi-persona AI code reviews.

---

## 🚀 Highlights of v0.2 Series (v0.2.4 – v0.2.18 - Completed)

- **Distributed Observability & Telemetry Triad**: Prometheus client metrics, Jaeger distributed tracing waterfalls, Loki LogQL terminal log streaming, and OpenTelemetry traceparent propagation.
- **PydanticAI Standardized Agent Framework**: 18 modernized agent subsystems, multi-turn reasoning buffers, prompt mutation testing, and human-in-the-loop feedback dataset export.
- **Valkey Workstation Management & High-Performance Distributed Caching**: Pure-Python RESP3 wire protocol client, token-bucket rate limiter, and vector cache slashing LLM latency.
- **Tree-Sitter Multilingual AST Graph & Polyglot Code Intelligence**: CST parsing across Python, TypeScript, Go, Rust, Java, and HCL with S-expression query resolution.
- **Ephemeral Workload Sandboxing & Dynamic Probing**: Rootless container test harness, cgroup v2 metrics, protocol-agnostic health probing, and OpenAPI dynamic API fuzzing.
- **BaseSecurityScanner Declarative Framework**: Standardized 11 static security scanners with pre-flight binary verification, bounded timeouts, and normalized finding models.

---


## 🚀 Highlights of v0.1 Series (v0.1.0 – v0.1.13 - Completed)

- **Vector Embedding Benchmarks (`devops ai benchmark --type embedding`)**: Dense vector embedding evaluation measuring Recall@1, Recall@3, MRR, Cosine Margin, single-query latency, and batch throughput across local Ollama and remote embedding models.
- **Local & Homelab TLS Certificate Automation (`devops tls`)**: Native X.509 CA and server/client TLS certificate issuance with SAN extensions, cert-manager ClusterIssuer integration, and Kubernetes secret injection (`devops k8s enable-tls`).
- **OpenTelemetry Distributed Tracing & Observability (`devops telemetry`)**: Distributed tracing across CLI commands and multi-agent pipeline stages with OTLP export, Jaeger manifests, and Prometheus client metrics.
- **OpenTofu Multi-Cloud Infrastructure as Code (`devops tf`)**: Production OpenTofu IaC modules for AWS (EKS), Azure (AKS), and GCP (GKE), with FastMCP agent tools (`tf_plan`, `tf_apply`, `tf_output`).
- **Automated Release Management & Documentation (`devops release`, `devops docs`)**: Version bumping, changelog maintenance, pre-release checks, and dynamic Typer/Click markdown documentation generation with CI freshness gating.
- **Native DevContainer Lifecycle Hooks (`devops devcontainer run-lifecycle`)**: Pure Python lifecycle execution (`--post-create`, `--post-start`) replacing shell scripts, with pre-built GHCR workstation containers.
- **Static SecOps & Kubernetes Auditing**: Embedded Aqua Trivy vulnerability scanning, Red Hat Kube-linter static manifest analysis, Derailed Popeye cluster health audits, Fairwinds Pluto API deprecation checks, and Kubernetes RBAC audits.
- **Minikube Auto-Configuration & Gated CI**: Automated NodePort discovery (`configure-urls`), 18 core FastMCP tools, and Gated CI validation suite (`test`, `coverage`, `lint`, `format`, `typecheck`, `audit`, `security`).
- **AI Scratchpad & Prompt Defense**: Structured multi-turn reasoning buffers (`ScratchpadBuffer`), XML prompt boundary isolation, and human invalidation feedback dataset exporter (`export-feedback`).

---

## 🛠️ Environment & Requirements
- **Runtime**: Python >=3.14 (managed by `uv`)
- **Container**: VS Code Dev Container / Local workstation environment (`python:3.14-trixie`)
- **Tool Dependencies**: `kubectl`, `helm`, `minikube`, `kustomize`, `docker`, `gh`, `trivy`, `kube-linter`, `popeye`, `pluto`
