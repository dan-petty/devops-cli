# DevOps CLI — Knowledge Base & Engineering Reference

The **DevOps CLI Knowledge Base** is a comprehensive, centralized technical manual and operational guide covering all core tools, subsystems, automation workflows, and engineering tasks leveraged across the `devops-cli` ecosystem.

Each knowledge base article provides detailed usage instructions, common commands, architectural patterns, security recommendations, and engineering standards.

---

## 🛠️ Tool References (`docs/knowledge_base/tools/`)

| Tool | Category | Summary | Article |
| :--- | :--- | :--- | :--- |
| **uv** | Python Runtime & Packaging | Extremely fast Python package manager, lockfile resolver, and tool runner. | [uv.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/uv.md) |
| **Docker** | Containerization | Container runtime, multi-stage builder, Docker-in-Docker (DinD), and GPU passthrough. | [docker.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/docker.md) |
| **kubectl** | Kubernetes Orchestration | Kubernetes cluster management CLI, manifest applier, resource inspector, and context manager. | [kubectl.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/kubectl.md) |
| **Helm** | Kubernetes Packaging | Package manager for Kubernetes charts, atomic releases, rollbacks, and values customization. | [helm.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/helm.md) |
| **Kustomize** | Declarative Config | Template-free Kubernetes configuration customization, overlays, patches, and resource generators. | [kustomize.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/kustomize.md) |
| **Minikube** | Local Kubernetes | Single-node local Kubernetes cluster, driver abstraction, add-on manager, and GPU passthrough. | [minikube.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/minikube.md) |
| **OpenTofu & Terraform** | Infrastructure as Code | Open-source declarative infrastructure provisioning engine, state locking, and provider management. | [opentofu_terraform.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/opentofu_terraform.md) |
| **ArgoCD** | GitOps & Delivery | Declarative GitOps continuous delivery engine for Kubernetes application lifecycle. | [argocd.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/argocd.md) |
| **Grafana** | Observability Visualization | Telemetry dashboard engine, Prometheus/OTel visualization, and metrics exploration. | [grafana.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/grafana.md) |
| **Prometheus** | Metrics & Alerting | Time-series metrics collection, PromQL query engine, and scrape endpoint targets. | [prometheus.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/prometheus.md) |
| **OpenTelemetry & Jaeger** | Distributed Tracing | OTel SDK instrumentation, OTLP collectors, trace context propagation, and Jaeger UI. | [opentelemetry_jaeger.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/opentelemetry_jaeger.md) |
| **Ollama** | Local LLM Inference | Local AI inference engine, model quantization, embedding generation, and model bundling. | [ollama.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/ollama.md) |
| **GitHub CLI (gh)** | VCS & CI Platform | Authenticated GitHub CLI for PR reviews, issue management, and workflow run inspection. | [github_cli.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/github_cli.md) |
| **Trivy** | Vulnerability Scanner | Vulnerability scanner for container images, filesystems, Git repositories, and misconfigurations. | [trivy.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/trivy.md) |
| **Bandit** | Static Security Analysis | Python AST static analyzer for detecting security vulnerabilities and CWE compliance. | [bandit.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/bandit.md) |
| **KubeLinter, Popeye & Pluto** | Kubernetes Quality & Safety | Manifest security linters, live cluster sanitizers, and deprecated API detectors. | [kubelinter_popeye_pluto.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/kubelinter_popeye_pluto.md) |
| **FastAPI & Uvicorn** | REST & OpenAPI Service | Asynchronous REST service engine, OpenAPI specification generation, and Swagger UI. | [fastapi_uvicorn.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/fastapi_uvicorn.md) |
| **Keyring** | Secure Secrets Store | OS Keyring integration for zero-trust token storage and credential isolation. | [keyring.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/keyring.md) |
| **actionlint** | GitHub Actions Linter | Static checker for GitHub Actions workflow files and shell syntax expressions. | [actionlint.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/actionlint.md) |
| **Ruff, Mypy & Pytest** | Python Quality Engine | High-performance linter/formatter (Ruff), strict static typing (Mypy), and parallel test engine (Pytest). | [ruff_mypy_pytest.md](file:///workspaces/devops-cli/docs/knowledge_base/tools/ruff_mypy_pytest.md) |

---

## 📋 Operational Task References (`docs/knowledge_base/tasks/`)

| Operational Task | Domain | Summary | Article |
| :--- | :--- | :--- | :--- |
| **AI Code Review** | AI & Quality | Multi-persona code review (Architect, DevSecOps, Auditor, QA, PM) with calibrated feedback. | [ai_code_review.md](file:///workspaces/devops-cli/docs/knowledge_base/tasks/ai_code_review.md) |
| **Security Audit & Scanning** | Security & Compliance | Comprehensive workstation audits, SSH key permission hardening, secret scanning, and CVE lookups. | [security_audit_and_scanning.md](file:///workspaces/devops-cli/docs/knowledge_base/tasks/security_audit_and_scanning.md) |
| **K8s Stack Deployment** | Kubernetes & Cloud | Automated bootstrap and teardown of local Kubernetes observability and GitOps stacks. | [k8s_stack_deployment.md](file:///workspaces/devops-cli/docs/knowledge_base/tasks/k8s_stack_deployment.md) |
| **Repo & Workspace Management** | Workstation & Git | Multi-org repository cloning, automated `.code-workspace` synchronization, and branch hygiene. | [repo_and_workspace_management.md](file:///workspaces/devops-cli/docs/knowledge_base/tasks/repo_and_workspace_management.md) |
| **Infrastructure Provisioning** | Infrastructure as Code | Declarative IaC workflows (init, plan, apply, output, state inspect) with OpenTofu/Terraform. | [infrastructure_provisioning.md](file:///workspaces/devops-cli/docs/knowledge_base/tasks/infrastructure_provisioning.md) |
| **CI Quality Gate** | Continuous Integration | 10-point local quality gate execution (`devops ci`) and pre-commit verification. | [ci_quality_gate.md](file:///workspaces/devops-cli/docs/knowledge_base/tasks/ci_quality_gate.md) |
| **Release Management** | Release Engineering | Semantic version bumping, release quality verification, changelog updates, and release branch PRs. | [release_management.md](file:///workspaces/devops-cli/docs/knowledge_base/tasks/release_management.md) |
| **Agent Instructions Scaffolding** | Agentic AI | Automatic generation and synchronization of canonical `AGENTS.md`, `CLAUDE.md`, and Copilot stubs. | [agent_instructions_scaffolding.md](file:///workspaces/devops-cli/docs/knowledge_base/tasks/agent_instructions_scaffolding.md) |
| **RAG Context Indexing** | Semantic Search & AI | Local vector embedding store, document chunking, and grounded context retrieval. | [rag_context_indexing.md](file:///workspaces/devops-cli/docs/knowledge_base/tasks/rag_context_indexing.md) |
| **Telemetry & Observability** | Observability | OpenTelemetry span tracing, Prometheus client metric scraping, and latency profiling. | [telemetry_and_observability.md](file:///workspaces/devops-cli/docs/knowledge_base/tasks/telemetry_and_observability.md) |
| **REST API Service Engine** | Workstation API | Running the background REST and OpenAPI service engine (`devops serve`) for tool inspection. | [rest_api_service.md](file:///workspaces/devops-cli/docs/knowledge_base/tasks/rest_api_service.md) |
| **DevContainer Lifecycle** | Dev Environments | Containerized workstation scaffolding, SSH commit signing, and MCP server synchronization. | [devcontainer_lifecycle.md](file:///workspaces/devops-cli/docs/knowledge_base/tasks/devcontainer_lifecycle.md) |
