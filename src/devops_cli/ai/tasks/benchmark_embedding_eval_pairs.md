# Embedding Evaluation Pairs Dataset

## sec-ssrf-filter
- **Category:** security
- **Query:** Prevent Server-Side Request Forgery and block private IP address egress
- **Target Passage:** To mitigate SSRF vulnerabilities, resolve all destination hostnames and validate that the resulting IP address is globally routable using ipaddress.is_global before dispatching HTTP webhook requests. Explicitly drop RFC 1918, RFC 3927 loopback, and cloud metadata addresses (169.254.169.254).

## sec-tls-cert-manager
- **Category:** security
- **Query:** Automate TLS certificate issuance and secret generation in Kubernetes with cert-manager
- **Target Passage:** Deploy cert-manager ClusterIssuer using Let's Encrypt ACME challenge solver. Annotate Ingress resources with cert-manager.io/cluster-issuer to automatically provision, rotate, and mount X.509 TLS Secret certificates in target namespaces.

## sec-keyring-secrets
- **Category:** security
- **Query:** Secure secret storage using OS Keyring instead of plaintext files or environment variables
- **Target Passage:** The devops_cli.config.keyring module interfaces directly with Linux SecretService, macOS Keychain, and Windows Credential Manager to persist AI API keys and SSH passphrases securely, preventing accidental credential leaks.

## sec-cve-osv-lookup
- **Category:** security
- **Query:** Scan dependencies for CVE security advisories using OSV.dev database
- **Target Passage:** The vulnerability intelligence lookup queries Open Source Vulnerabilities (OSV.dev) with package names and versions from pyproject.toml or package.json, identifying vulnerable ranges, CVSS severity ratings, and fix recommendations.

## k8s-pod-security
- **Category:** kubernetes
- **Query:** Enforce restricted pod security standards with non-root user and read-only root filesystem
- **Target Passage:** Configure securityContext at both Pod and Container levels with runAsNonRoot: true, readOnlyRootFilesystem: true, allowPrivilegeEscalation: false, and drop: [ALL]. Mount emptyDir scratch volumes for temporary file writes at /tmp and /data.

## k8s-ingress-routing
- **Category:** kubernetes
- **Query:** Configure Traefik ingress route with TLS termination and path prefix stripping
- **Target Passage:** Define an IngressRoute custom resource in traefik.io/v1alpha1 specifying entryPoints [websecure], match Rule PathPrefix('/api/v1'), and attach a stripPrefix middleware to rewrite request paths before forwarding traffic to the backend Service.

## k8s-helm-bootstrap
- **Category:** kubernetes
- **Query:** Bootstrap local development cluster with Helm chart releases and wait for ready pods
- **Target Passage:** Execute devops k8s bootstrap --context homelab-k3s to reconcile CRDs, install Prometheus and Grafana Helm charts, apply Kustomize overlays, and poll Deployment rollout status until all pods pass readiness probes.

## k8s-netpol-isolation
- **Category:** kubernetes
- **Query:** Isolate pod network traffic with default-deny ingress and egress NetworkPolicy
- **Target Passage:** Apply a Kubernetes NetworkPolicy with policyTypes [Ingress, Egress] and empty podSelector to block cross-namespace traffic by default, whitelisting DNS port 53 and backend service CIDR blocks.

## arch-pydantic-v2
- **Category:** architecture
- **Query:** Migrate data models to Pydantic v2 with field validators and model_dump_json
- **Target Passage:** Replace legacy v1 @validator with @field_validator(mode='before'), update Config class to ConfigDict(frozen=True, populate_by_name=True), and serialize objects using model.model_dump_json() for high-performance Rust-backed serialization.

## arch-fastmcp-tools
- **Category:** architecture
- **Query:** Register structured FastMCP tools for AI agent pair programming workflows
- **Target Passage:** FastMCP decorators (@mcp.tool()) expose DevOps CLI operations directly to IDE coding assistants. All MCP tools define type annotations, docstrings, and Pydantic schemas to enable reliable tool invocation and contextual reasoning.

## arch-ast-analyzer
- **Category:** architecture
- **Query:** Static code analysis with Python AST visitor and type annotation extraction
- **Target Passage:** The AST CodeScanner parses Python source trees using ast.parse(), traversing FunctionDef, AsyncFunctionDef, and ClassDef nodes to compute cyclomatic complexity, symbol dependencies, and signature type hints without executing arbitrary code.

## arch-polyglot-chunker
- **Category:** architecture
- **Query:** Chunk source code files along class and function boundaries for RAG indexing
- **Target Passage:** The PolyglotChunker parses syntactic grammar definitions for Python, Go, Rust, and TypeScript, segmenting source modules along AST function boundaries while attaching symbol metadata and import dependencies to each vector chunk.

## ci-concurrency-cancel
- **Category:** ci_cd
- **Query:** Cancel in-progress GitHub Actions workflow runs on branch push with concurrency groups
- **Target Passage:** Add concurrency: group: ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress: true at the workflow root to terminate redundant pending runs when rapid successive commits are pushed to pull request topic branches.

## ci-docker-multi-stage
- **Category:** ci_cd
- **Query:** Optimize Docker build caching with multi-stage layers and non-root distroless runtime
- **Target Passage:** Stage 1 compiles dependencies into a virtual environment with uv sync. Stage 2 copies runtime artifacts into gcr.io/distroless/python3-debian12, setting USER nonroot:nonroot to minimize image vulnerability attack surface.

## ci-actionlint-gate
- **Category:** ci_cd
- **Query:** Lint GitHub Actions workflows for syntax errors and unpinned actions in pre-commit
- **Target Passage:** The devops ci quality gate invokes actionlint on all .github/workflows/*.yml manifests, verifying shellcheck compliance inside run scripts and flagging untagged third-party action SHA references.

## ci-uv-cache-matrix
- **Category:** ci_cd
- **Query:** Accelerate CI test matrix runs using uv cache and lockfile hash keys
- **Target Passage:** Use astral-sh/setup-uv with enable-cache: true and cache-dependency-glob: 'uv.lock' to restore pre-built Python wheels across Ubuntu, macOS, and Windows matrix jobs, reducing dependency sync duration from minutes to under 5 seconds.

## infra-terraform-state
- **Category:** infrastructure
- **Query:** Remote Terraform state backend with S3 bucket and DynamoDB locking
- **Target Passage:** Configure terraform backend 's3' with bucket = 'org-tf-state-prod', key = 'vpc/terraform.tfstate', region = 'us-east-1', and dynamodb_table = 'terraform-locks' to prevent concurrent conflicting state mutations during automated CI runs.

## infra-qdrant-vector-db
- **Category:** infrastructure
- **Query:** Index code chunks and execute cosine similarity vector search in Qdrant database
- **Target Passage:** Initialize Qdrant client connection at port 6333, create collection with Distance.COSINE and vector dimension 768, and query nearest neighbor points matching embedding vectors using client.search_points(collection_name, query_vector=vec).

## infra-prometheus-metrics
- **Category:** infrastructure
- **Query:** Query Prometheus PromQL metrics endpoint for p99 request latency and CPU usage
- **Target Passage:** Execute PromQL instant and range queries against Prometheus /api/v1/query_range using histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) to monitor microservice tail latency SLA breaches.

## infra-jaeger-tracing
- **Category:** infrastructure
- **Query:** Collect distributed trace spans with OpenTelemetry Collector and Jaeger UI
- **Target Passage:** Deploy OpenTelemetry Collector DaemonSet receiving OTLP gRPC spans at port 4317 and exporting traces to Jaeger backend storage, visualizing request call graphs and latency bottlenecks across microservices.
