# Enterprise DevOps & Agentic Infrastructure Architecture

## 1. Zero-Trust Security, Secret Storage & Network Egress
Modern cloud-native workstations and CI/CD automation systems must operate under zero-trust.
Plaintext API tokens and cloud keys must never be stored in files, env vars, or logs.
The devops_cli.config.keyring subsystem interfaces directly with native OS secret stores:
- Linux: SecretService / D-Bus Secret Service API (freedesktop secret storage)
- macOS: Apple Keychain Services API
- Windows: Windows Credential Manager
All outbound HTTP requests dispatched by AI agents must pass rigorous SSRF validation.
Destination hostnames must resolve to publicly routable IP addresses verified via ipaddress.
Requests reaching RFC 1918 private subnets, link-local, loopback, or metadata endpoints are blocked.

## 2. Kubernetes Cluster Orchestration & Pod Security Standards
Kubernetes deployments in local, homelab, and edge environments enforce Pod Security Standards.
Every container manifest must declare explicit security contexts at Pod and Container scopes:
- runAsNonRoot: true with explicit non-root UID/GID (e.g., 65532:65532)
- readOnlyRootFilesystem: true to prevent runtime binary alteration
- allowPrivilegeEscalation: false
- capabilities.drop: [ALL] to strip unnecessary Linux capabilities
Temporary scratch storage must be mounted via in-memory emptyDir volumes at /tmp and /data.
Ingress routing is managed via Traefik IngressRoute with Let's Encrypt TLS certificates.
NetworkPolicies enforce default-deny ingress and egress isolation across namespaces.

## 3. High-Performance Asynchronous Python Architecture & Type Safety
The DevOps CLI codebase is built upon Python 3.14+ runtime features, adhering to mypy --strict.
Data structures and configuration schemas are declared as immutable Pydantic v2 models.
Field validation uses @field_validator and serialization is via model.model_dump_json().
Static code analysis is performed using Python's native ast module.
The AST CodeScanner parses Python source trees into syntax trees without executing arbitrary code,
extracting FunctionDef, AsyncFunctionDef, and ClassDef nodes to compute McCabe complexity.
For HTTP communication, httpx2 clients enforce strict request timeouts and connection pooling.

## 4. CI/CD Pipeline Optimization, Distroless Containers & Quality Gates
Continuous integration pipelines running on GitHub Actions must maximize speed and determinism.
Dependency resolution is accelerated using uv sync and astral-sh/setup-uv caching.
Multi-stage Docker builds separate build toolchains from runtime containers:
- Stage 1: Build virtual environment and compile native extensions using uv
- Stage 2: Copy virtual environment into distroless with nonroot user privileges
Workflow concurrency groups terminate obsolete runs upon rapid commit pushes.
The devops ci quality gate enforces pre-commit verification including actionlint and ruff.

## 5. Cloud Infrastructure, OpenTofu State Locking & Observability
Infrastructure as Code (IaC) is provisioned using OpenTofu and Terraform configurations:
- S3 backend storage with AES-256 server-side encryption
- DynamoDB state locking tables to prevent conflicting concurrent terraform apply executions
Observability telemetry is collected via OpenTelemetry Collector DaemonSets forwarding OTLP spans.
Prometheus scrapes operational metrics at 15-second intervals for SLA monitoring.
Vector similarity search for code intelligence is indexed into Qdrant vector databases.
