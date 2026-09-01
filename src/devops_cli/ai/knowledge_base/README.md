# DevOps CLI — Knowledge Base & Engineering Reference

The **DevOps CLI Knowledge Base** is a comprehensive, centralized technical manual and operational guide covering all core tools, subsystems, automation workflows, architectural concepts, and engineering tasks leveraged across the `devops-cli` ecosystem.

The Knowledge Base is divided into two primary structural divisions:
1. [**DevOps CLI Information**](#-division-1-devops-cli-information-devops_cli): Architecture, settings hierarchy, CLI command references, and operational task workflows specific to `devops-cli`.
2. [**Information Technology Domain-Specific Information**](#-division-2-information-technology-domain-specific-information-it_domains): Industry architectural topic guides and standard tool reference manuals across cloud-native, observability, security, and developer infrastructure.

---

## 🌐 Official Project Repositories & Published Artifacts

| Resource | Description | Endpoint / URL |
| :--- | :--- | :--- |
| **Project Repository** | Primary open-source source repository | [github.com/dan-petty/devops-cli](https://github.com/dan-petty/devops-cli) |
| **Published Container (GHCR)** | Pre-baked DevContainer package | [`ghcr.io/dan-petty/devops-cli/devcontainer:latest`](https://github.com/dan-petty/devops-cli/pkgs/container/devops-cli%2Fdevcontainer) |
| **Container Package Registry** | GitHub Container Registry package view | [GHCR Package Catalog](https://github.com/dan-petty/devops-cli/pkgs/container/devops-cli%2Fdevcontainer) |
| **Release Artifacts & Tarballs** | Official GitHub release assets and changelogs | [GitHub Releases](https://github.com/dan-petty/devops-cli/releases) |
| **Pull Requests & Code Reviews** | Active development pull requests | [GitHub Pull Requests](https://github.com/dan-petty/devops-cli/pulls) |
| **GitHub Actions CI/CD** | Automated continuous integration and builds | [GitHub Actions](https://github.com/dan-petty/devops-cli/actions) |

---

## 💻 Division 1: DevOps CLI Information (`devops_cli/`)

### Core Architecture & Configuration Reference

| Article | Summary | Guide |
| :--- | :--- | :--- |
| **DevOps CLI Architecture** | Subsystem breakdown, multi-persona AI review engine, prompt isolation, dry-run protocol, and language catalogs. | [architecture.md](devops_cli/architecture.md) |
| **Configuration & Settings** | Pydantic settings schema hierarchy, resolution priority, OS Keyring secrets storage, and dotted config commands. | [configuration_and_settings.md](devops_cli/configuration_and_settings.md) |
| **CLI Command Reference** | Complete command surface reference across all 19 command groups, subcommands, arguments, and flags. | [cli_command_reference.md](devops_cli/cli_command_reference.md) |
| **Python Packages & Code Libraries** | Technical manual and dedicated guides for all 22 production runtime dependencies and 11 development quality tools. | [python_packages.md](devops_cli/python_packages.md) |

### Code Library Guides (`devops_cli/libraries/`)

| Library / Tool | Category | Summary | Guide |
| :--- | :--- | :--- | :--- |
| **Typer & Click** | CLI Framework | Type-annotated CLI routing, parameter parsing, and centralized help. | [typer.md](devops_cli/libraries/typer.md) |
| **Rich** | Terminal UI | Beautiful ANSI tables, animated status spinners, and code diff highlighting. | [rich.md](devops_cli/libraries/rich.md) |
| **Pydantic v2 & Settings** | Data Validation | Rust-core data validation, schemas, and layered configuration resolution. | [pydantic.md](devops_cli/libraries/pydantic.md) |
| **PydanticAI** | Multi-Agent AI | Type-safe multi-agent framework, persona reviews, and MCP client toolsets. | [pydantic_ai.md](devops_cli/libraries/pydantic_ai.md) |
| **HTTPX2** | HTTP/2 Client | Modern async/sync HTTP/2 client for streaming LLM provider requests. | [httpx2.md](devops_cli/libraries/httpx2.md) |
| **FastMCP** | MCP Server | Model Context Protocol server exposing CLI tools to AI IDEs and assistants. | [fastmcp.md](devops_cli/libraries/fastmcp.md) |
| **Keyring** | Secret Storage | Zero-trust OS Keyring storage for tokens and credentials. | [keyring.md](devops_cli/libraries/keyring.md) |
| **Tiktoken** | Tokenizer | Fast BPE token counting and LLM context window budgeting. | [tiktoken.md](devops_cli/libraries/tiktoken.md) |
| **JSON Repair** | LLM Resilience | Resilient parser repairing malformed and truncated JSON payloads from LLMs. | [json_repair.md](devops_cli/libraries/json_repair.md) |
| **Qdrant Client** | Vector Search | Local and remote vector database for RAG context indexing and search. | [qdrant_client.md](devops_cli/libraries/qdrant_client.md) |
| **GitPython** | Git VCS | Object-oriented Git inspection, diff generation, and branch operations. | [gitpython.md](devops_cli/libraries/gitpython.md) |
| **PyGithub** | GitHub API | GitHub REST/GraphQL client for PR reviews, checks, and release automation. | [pygithub.md](devops_cli/libraries/pygithub.md) |
| **Cryptography** | X.509 & TLS | Rust-backed X.509 Certificate Authority, TLS leaf cert, and Ed25519 engine. | [cryptography.md](devops_cli/libraries/cryptography.md) |
| **Kubernetes Client** | K8s SDK | Official Python client for Kubernetes cluster management and diagnostics. | [kubernetes.md](devops_cli/libraries/kubernetes.md) |
| **Docker SDK** | Containers | Python client for Docker Engine daemon, real-time stats, and lifecycle. | [docker.md](devops_cli/libraries/docker.md) |
| **FastAPI & Uvicorn** | REST & ASGI | Asynchronous REST service engine and OpenAPI server backing `devops serve`. | [fastapi_uvicorn.md](devops_cli/libraries/fastapi_uvicorn.md) |
| **OpenTelemetry** | Observability | Distributed tracing, OTLP gRPC export to Jaeger, and Prometheus metrics. | [opentelemetry.md](devops_cli/libraries/opentelemetry.md) |
| **Pathspec** | Gitignore Matcher | Pure Python pattern matching based on `.gitignore` wildcards and rules. | [pathspec.md](devops_cli/libraries/pathspec.md) |
| **TLDExtract** | Egress Safety | Public Suffix List domain parsing and SSRF egress safety validation. | [tldextract.md](devops_cli/libraries/tldextract.md) |
| **Packaging** | SemVer & Specs | PyPA core specifications, SemVer 2.0.0 validation, and version bumping. | [packaging.md](devops_cli/libraries/packaging.md) |
| **PyYAML & Jinja2** | Manifests & Templates | YAML parsing and Jinja2 templating for DevContainers and K8s manifests. | [pyyaml_jinja2.md](devops_cli/libraries/pyyaml_jinja2.md) |
| **Ruff, Mypy & Pytest** | Quality Suite | 100x fast linter, strict static typing, and parallel test runner ($\ge 90\%$ cov). | [ruff_mypy_pytest.md](devops_cli/libraries/ruff_mypy_pytest.md) |
| **Bandit & Actionlint** | Security Analysis | Python AST security analysis (CWE) and GitHub Actions workflow linting. | [bandit_actionlint.md](devops_cli/libraries/bandit_actionlint.md) |

### CLI Operational Task References (`devops_cli/tasks/`)

| Operational Task | Domain | Summary | Article |
| :--- | :--- | :--- | :--- |
| **AI Code Review** | AI & Quality | Multi-persona code review (Architect, DevSecOps, Auditor, QA, PM) with calibrated feedback. | [ai_code_review.md](devops_cli/tasks/ai_code_review.md) |
| **Security Audit & Scanning** | Security & Compliance | Comprehensive workstation audits, SSH key permission hardening, secret scanning, and CVE lookups. | [security_audit_and_scanning.md](devops_cli/tasks/security_audit_and_scanning.md) |
| **K8s Stack Deployment** | Kubernetes & Cloud | Automated bootstrap and teardown of local Kubernetes observability and GitOps stacks. | [k8s_stack_deployment.md](devops_cli/tasks/k8s_stack_deployment.md) |
| **Repo & Workspace Management** | Workstation & Git | Multi-org repository cloning, automated `.code-workspace` synchronization, and branch hygiene. | [repo_and_workspace_management.md](devops_cli/tasks/repo_and_workspace_management.md) |
| **Infrastructure Provisioning** | Infrastructure as Code | Declarative IaC workflows (init, plan, apply, output, state inspect) with OpenTofu/Terraform. | [infrastructure_provisioning.md](devops_cli/tasks/infrastructure_provisioning.md) |
| **CI Quality Gate** | Continuous Integration | 10-point local quality gate execution (`devops ci`) and pre-commit verification. | [ci_quality_gate.md](devops_cli/tasks/ci_quality_gate.md) |
| **Release Management** | Release Engineering | Semantic version bumping, release quality verification, changelog updates, and release branch PRs. | [release_management.md](devops_cli/tasks/release_management.md) |
| **Agent Instructions Scaffolding** | Agentic AI | Automatic generation and synchronization of canonical `AGENTS.md`, `CLAUDE.md`, and Copilot stubs. | [agent_instructions_scaffolding.md](devops_cli/tasks/agent_instructions_scaffolding.md) |
| **RAG Context Indexing** | Semantic Search & AI | Local vector embedding store, document chunking, and grounded context retrieval. | [rag_context_indexing.md](devops_cli/tasks/rag_context_indexing.md) |
| **Telemetry & Observability** | Observability | OpenTelemetry span tracing, Prometheus client metric scraping, and latency profiling. | [telemetry_and_observability.md](devops_cli/tasks/telemetry_and_observability.md) |
| **REST API Service Engine** | Workstation API | Running the background REST and OpenAPI service engine (`devops serve`) for tool inspection. | [rest_api_service.md](devops_cli/tasks/rest_api_service.md) |
| **DevContainer Lifecycle** | Dev Environments | Containerized workstation scaffolding, SSH commit signing, and MCP server synchronization. | [devcontainer_lifecycle.md](devops_cli/tasks/devcontainer_lifecycle.md) |

---

## 🌐 Division 2: Information Technology Domain-Specific Information (`it_domains/`)

### Core IT Topic Guides (`it_domains/topics/`)

| Core Topic | Domain | Summary | Topic Guide |
| :--- | :--- | :--- | :--- |
| **Agentic AI & Code Reviews** | AI & Multi-Persona Reviews | Architecture for multi-persona code reviews, prompt isolation, and calibrated findings. | [agentic_ai_and_code_reviews.md](it_domains/topics/agentic_ai_and_code_reviews.md) |
| **Cloud-Native K8s & GitOps** | Kubernetes & Cloud Delivery | Declarative GitOps delivery with ArgoCD, Helm charts, and local Minikube orchestration. | [cloud_native_kubernetes_and_gitops.md](it_domains/topics/cloud_native_kubernetes_and_gitops.md) |
| **Zero-Trust Security & Compliance** | Security Engineering | Credential isolation with OS Keyring, vulnerability scanning, and SSH key hardening. | [zero_trust_security_and_compliance.md](it_domains/topics/zero_trust_security_and_compliance.md) |
| **Observability & Distributed Tracing** | APM & Monitoring | OpenTelemetry distributed trace spans, Prometheus metrics series, and Jaeger UI. | [observability_and_distributed_tracing.md](it_domains/topics/observability_and_distributed_tracing.md) |
| **Reproducible DevContainers** | Developer Workstations | Containerized developer environments, Docker-in-Docker, persistent history, and MCP sync. | [developer_workstations_and_devcontainers.md](it_domains/topics/developer_workstations_and_devcontainers.md) |
| **Infrastructure as Code & Cloud Automation** | Cloud IaC | Declarative cloud provisioning with OpenTofu & Terraform, state locking, and drift checks. | [infrastructure_as_code_and_cloud_automation.md](it_domains/topics/infrastructure_as_code_and_cloud_automation.md) |
| **CI & Progressive Verification** | Continuous Integration | 10-point local quality gate (`devops ci`), progressive testing, and workflow validation. | [continuous_integration_and_progressive_verification.md](it_domains/topics/continuous_integration_and_progressive_verification.md) |
| **Modern Python 3.14+ Ecosystem** | Python Runtime & Tooling | Strict Mypy typing, Astral `uv` packaging, Ruff formatting, and dynamic standard parsers. | [modern_python_runtime_and_ecosystem.md](it_domains/topics/modern_python_runtime_and_ecosystem.md) |
| **REST API Architecture & Services** | Workstation REST API | Asynchronous FastAPI service engine (`devops serve`), OpenAPI schemas, and status probes. | [rest_api_architecture_and_service_engineering.md](it_domains/topics/rest_api_architecture_and_service_engineering.md) |
| **Release Engineering & SemVer** | Release Governance | Semantic versioning 2.0.0, release verification gates, and automated PR governance. | [release_engineering_and_semver_governance.md](it_domains/topics/release_engineering_and_semver_governance.md) |
| **Model Governance, Routing & Curation** | AI Governance & Routing | Adaptive 2-axis LLM routing, open-weight model curation, AIBOM generation, sub-agent local offloading, and model dependency chaos engineering. | [model_governance_routing_and_curation.md](it_domains/topics/model_governance_routing_and_curation.md) |

### Integrated IT Tool References (`it_domains/tools/`)

| Tool | Category | Public Git Repository | Published Artifact / Container | Article |
| :--- | :--- | :--- | :--- | :--- |
| **uv** | Python Runtime & Packaging | [astral-sh/uv](https://github.com/astral-sh/uv) | [PyPI uv](https://pypi.org/project/uv/) / [Binary Releases](https://github.com/astral-sh/uv/releases) | [uv.md](it_domains/tools/uv.md) |
| **Docker** | Containerization | [moby/moby](https://github.com/moby/moby) | [ghcr.io devcontainer](https://github.com/dan-petty/devops-cli/pkgs/container/devops-cli%2Fdevcontainer) | [docker.md](it_domains/tools/docker.md) |
| **kubectl** | Kubernetes Orchestration | [kubernetes/kubectl](https://github.com/kubernetes/kubectl) | [dl.k8s.io Binaries](https://dl.k8s.io/release/) | [kubectl.md](it_domains/tools/kubectl.md) |
| **Helm** | Kubernetes Packaging | [helm/helm](https://github.com/helm/helm) | [Artifact Hub Charts](https://artifacthub.io) | [helm.md](it_domains/tools/helm.md) |
| **Kustomize** | Declarative Config | [kubernetes-sigs/kustomize](https://github.com/kubernetes-sigs/kustomize) | [Kubernetes Releases](https://github.com/kubernetes-sigs/kustomize/releases) | [kustomize.md](it_domains/tools/kustomize.md) |
| **Minikube** | Local Kubernetes | [kubernetes/minikube](https://github.com/kubernetes/minikube) | [minikube Releases](https://github.com/kubernetes/minikube/releases) | [minikube.md](it_domains/tools/minikube.md) |
| **OpenTofu & Terraform** | Infrastructure as Code | [opentofu/opentofu](https://github.com/opentofu/opentofu) | [OpenTofu Registry](https://search.opentofu.org) | [opentofu_terraform.md](it_domains/tools/opentofu_terraform.md) |
| **ArgoCD** | GitOps & Delivery | [argoproj/argo-cd](https://github.com/argoproj/argo-cd) | [quay.io/argoproj/argocd](https://quay.io/repository/argoproj/argocd) | [argocd.md](it_domains/tools/argocd.md) |
| **Grafana** | Observability Visualization | [grafana/grafana](https://github.com/grafana/grafana) | [docker.io/grafana/grafana](https://hub.docker.com/r/grafana/grafana) | [grafana.md](it_domains/tools/grafana.md) |
| **Prometheus** | Metrics & Alerting | [prometheus/prometheus](https://github.com/prometheus/prometheus) | [docker.io/prom/prometheus](https://hub.docker.com/r/prom/prometheus) | [prometheus.md](it_domains/tools/prometheus.md) |
| **OpenTelemetry & Jaeger** | Distributed Tracing | [open-telemetry/opentelemetry-python](https://github.com/open-telemetry/opentelemetry-python) | [jaegertracing/all-in-one](https://hub.docker.com/r/jaegertracing/all-in-one) | [opentelemetry_jaeger.md](it_domains/tools/opentelemetry_jaeger.md) |
| **Ollama** | Local LLM Inference | [ollama/ollama](https://github.com/ollama/ollama) | [Ollama Model Library](https://ollama.com/library) | [ollama.md](it_domains/tools/ollama.md) |
| **GitHub CLI (gh)** | VCS & CI Platform | [cli/cli](https://github.com/cli/cli) | [GitHub CLI Releases](https://github.com/cli/cli/releases) | [github_cli.md](it_domains/tools/github_cli.md) |
| **Trivy** | Vulnerability Scanner | [aquasecurity/trivy](https://github.com/aquasecurity/trivy) | [docker.io/aquasec/trivy](https://hub.docker.com/r/aquasec/trivy) | [trivy.md](it_domains/tools/trivy.md) |
| **Bandit** | Static Security Analysis | [PyCQA/bandit](https://github.com/PyCQA/bandit) | [PyPI bandit](https://pypi.org/project/bandit/) | [bandit.md](it_domains/tools/bandit.md) |
| **KubeLinter / Popeye / Pluto** | K8s Quality & Safety | [stackrox/kube-linter](https://github.com/stackrox/kube-linter) | [Fairwinds Pluto](https://github.com/FairwindsOps/pluto) | [kubelinter_popeye_pluto.md](it_domains/tools/kubelinter_popeye_pluto.md) |
| **FastAPI & Uvicorn** | REST & OpenAPI Service | [fastapi/fastapi](https://github.com/fastapi/fastapi) | [PyPI fastapi](https://pypi.org/project/fastapi/) | [fastapi_uvicorn.md](it_domains/tools/fastapi_uvicorn.md) |
| **Keyring** | Secure Secrets Store | [jaraco/keyring](https://github.com/jaraco/keyring) | [PyPI keyring](https://pypi.org/project/keyring/) | [keyring.md](it_domains/tools/keyring.md) |
| **actionlint** | GitHub Actions Linter | [rhysd/actionlint](https://github.com/rhysd/actionlint) | [actionlint Releases](https://github.com/rhysd/actionlint/releases) | [actionlint.md](it_domains/tools/actionlint.md) |
| **Ruff, Mypy & Pytest** | Python Quality Engine | [astral-sh/ruff](https://github.com/astral-sh/ruff) | [PyPI ruff](https://pypi.org/project/ruff/) | [ruff_mypy_pytest.md](it_domains/tools/ruff_mypy_pytest.md) |
| **Gitleaks** | Sub-Millisecond Secret Scanner | [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks) | [Gitleaks Releases](https://github.com/gitleaks/gitleaks/releases) | [gitleaks.md](it_domains/tools/gitleaks.md) |
| **Semgrep** | Polyglot Static AST Matcher | [semgrep/semgrep](https://github.com/semgrep/semgrep) | [PyPI semgrep](https://pypi.org/project/semgrep/) | [semgrep.md](it_domains/tools/semgrep.md) |
| **tiktoken** | Fast BPE Tokenizer | [openai/tiktoken](https://github.com/openai/tiktoken) | [PyPI tiktoken](https://pypi.org/project/tiktoken/) | [tiktoken.md](it_domains/tools/tiktoken.md) |
| **PydanticAI** | Typed Agent Framework | [pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai) | [PyPI pydantic-ai](https://pypi.org/project/pydantic-ai/) | [pydantic_ai.md](it_domains/tools/pydantic_ai.md) |
| **Checkov** | IaC Policy & Compliance | [bridgecrewio/checkov](https://github.com/bridgecrewio/checkov) | [PyPI checkov](https://pypi.org/project/checkov/) | [checkov.md](it_domains/tools/checkov.md) |
| **TFLint** | Cloud Provider Terraform Linter | [terraform-linters/tflint](https://github.com/terraform-linters/tflint) | [TFLint Releases](https://github.com/terraform-linters/tflint/releases) | [tflint.md](it_domains/tools/tflint.md) |
| **Dive** | Container Layer Efficiency | [wagoodman/dive](https://github.com/wagoodman/dive) | [Dive Releases](https://github.com/wagoodman/dive/releases) | [dive.md](it_domains/tools/dive.md) |
| **Kubeconform** | OpenAPI Manifest Validator | [yannh/kubeconform](https://github.com/yannh/kubeconform) | [Kubeconform Releases](https://github.com/yannh/kubeconform/releases) | [kubeconform.md](it_domains/tools/kubeconform.md) |
