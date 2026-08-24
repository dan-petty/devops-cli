"""Curated evaluation dataset for embedding model semantic retrieval benchmarking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingEvalPair:
    """Query, matching target document passage, and metadata category."""

    id: str
    category: str
    query: str
    target_passage: str


# 20 domain-specific query-passage evaluation pairs across 5 DevOps domains (4 per category)
EMBEDDING_EVAL_PAIRS: list[EmbeddingEvalPair] = [
    # 1. Security
    EmbeddingEvalPair(
        id="sec-ssrf-filter",
        category="security",
        query="Prevent Server-Side Request Forgery and block private IP address egress",
        target_passage=(
            "To mitigate SSRF vulnerabilities, resolve all destination hostnames and validate "
            "that the resulting IP address is globally routable using ipaddress.is_global before "
            "dispatching HTTP webhook requests. Explicitly drop RFC 1918, RFC 3927 loopback, and "
            "cloud metadata addresses (169.254.169.254)."
        ),
    ),
    EmbeddingEvalPair(
        id="sec-tls-cert-manager",
        category="security",
        query=(
            "Automate TLS certificate issuance and secret generation in Kubernetes "
            "with cert-manager"
        ),
        target_passage=(
            "Deploy cert-manager ClusterIssuer using Let's Encrypt ACME challenge solver. "
            "Annotate Ingress resources with cert-manager.io/cluster-issuer to automatically "
            "provision, rotate, and mount X.509 TLS Secret certificates in target namespaces."
        ),
    ),
    EmbeddingEvalPair(
        id="sec-keyring-secrets",
        category="security",
        query=(
            "Secure secret storage using OS Keyring instead of plaintext files or "
            "environment variables"
        ),
        target_passage=(
            "The devops_cli.config.keyring module interfaces directly with Linux SecretService, "
            "macOS Keychain, and Windows Credential Manager to persist AI API keys and SSH "
            "passphrases securely, preventing accidental credential leaks."
        ),
    ),
    EmbeddingEvalPair(
        id="sec-cve-osv-lookup",
        category="security",
        query="Scan dependencies for CVE security advisories using OSV.dev database",
        target_passage=(
            "The vulnerability intelligence lookup queries Open Source Vulnerabilities (OSV.dev) "
            "with package names and versions from pyproject.toml or package.json, "
            "identifying vulnerable ranges, CVSS severity ratings, and fix recommendations."
        ),
    ),
    # 2. Kubernetes
    EmbeddingEvalPair(
        id="k8s-pod-security",
        category="kubernetes",
        query=(
            "Enforce restricted pod security standards with non-root user and "
            "read-only root filesystem"
        ),
        target_passage=(
            "Configure securityContext at both Pod and Container levels with runAsNonRoot: true, "
            "readOnlyRootFilesystem: true, allowPrivilegeEscalation: false, and drop: [ALL]. "
            "Mount emptyDir scratch volumes for temporary file writes at /tmp and /data."
        ),
    ),
    EmbeddingEvalPair(
        id="k8s-ingress-routing",
        category="kubernetes",
        query="Configure Traefik ingress route with TLS termination and path prefix stripping",
        target_passage=(
            "Define an IngressRoute custom resource in traefik.io/v1alpha1 specifying entryPoints "
            "[websecure], match Rule PathPrefix('/api/v1'), and attach a stripPrefix middleware "
            "to rewrite request paths before forwarding traffic to the backend Service."
        ),
    ),
    EmbeddingEvalPair(
        id="k8s-helm-bootstrap",
        category="kubernetes",
        query=(
            "Bootstrap local development cluster with Helm chart releases and wait for ready pods"
        ),
        target_passage=(
            "Execute devops k8s bootstrap --context homelab-k3s to reconcile CRDs, install "
            "Prometheus and Grafana Helm charts, apply Kustomize overlays, and poll Deployment "
            "rollout status until all pods pass readiness probes."
        ),
    ),
    EmbeddingEvalPair(
        id="k8s-netpol-isolation",
        category="kubernetes",
        query="Isolate pod network traffic with default-deny ingress and egress NetworkPolicy",
        target_passage=(
            "Apply a Kubernetes NetworkPolicy with policyTypes [Ingress, Egress] and empty "
            "podSelector to block cross-namespace traffic by default, whitelisting DNS port 53 "
            "and backend service CIDR blocks."
        ),
    ),
    # 3. Architecture & Python
    EmbeddingEvalPair(
        id="arch-pydantic-v2",
        category="architecture",
        query="Migrate data models to Pydantic v2 with field validators and model_dump_json",
        target_passage=(
            "Replace legacy v1 @validator with @field_validator(mode='before'), update Config "
            "class to ConfigDict(frozen=True, populate_by_name=True), and serialize objects using "
            "model.model_dump_json() for high-performance Rust-backed serialization."
        ),
    ),
    EmbeddingEvalPair(
        id="arch-fastmcp-tools",
        category="architecture",
        query="Register structured FastMCP tools for AI agent pair programming workflows",
        target_passage=(
            "FastMCP decorators (@mcp.tool()) expose DevOps CLI operations directly to IDE coding "
            "assistants. All MCP tools define type annotations, docstrings, and Pydantic schemas "
            "to enable reliable tool invocation and contextual reasoning."
        ),
    ),
    EmbeddingEvalPair(
        id="arch-ast-analyzer",
        category="architecture",
        query="Static code analysis with Python AST visitor and type annotation extraction",
        target_passage=(
            "The AST CodeScanner parses Python source trees using ast.parse(), traversing "
            "FunctionDef, AsyncFunctionDef, and ClassDef nodes to compute cyclomatic complexity, "
            "symbol dependencies, and signature type hints without executing arbitrary code."
        ),
    ),
    EmbeddingEvalPair(
        id="arch-polyglot-chunker",
        category="architecture",
        query="Chunk source code files along class and function boundaries for RAG indexing",
        target_passage=(
            "The PolyglotChunker parses syntactic grammar definitions for Python, Go, Rust, and "
            "TypeScript, segmenting source modules along AST function boundaries while attaching "
            "symbol metadata and import dependencies to each vector chunk."
        ),
    ),
    # 4. CI/CD
    EmbeddingEvalPair(
        id="ci-concurrency-cancel",
        category="ci_cd",
        query=(
            "Cancel in-progress GitHub Actions workflow runs on branch push with concurrency groups"
        ),
        target_passage=(
            "Add concurrency: group: ${{ github.workflow }}-${{ github.ref }}, "
            "cancel-in-progress: true at the workflow root to terminate redundant pending runs "
            "when rapid successive commits are pushed to pull request topic branches."
        ),
    ),
    EmbeddingEvalPair(
        id="ci-docker-multi-stage",
        category="ci_cd",
        query=(
            "Optimize Docker build caching with multi-stage layers and non-root distroless runtime"
        ),
        target_passage=(
            "Stage 1 compiles dependencies into a virtual environment with uv sync. Stage 2 copies "
            "runtime artifacts into gcr.io/distroless/python3-debian12, setting USER "
            "nonroot:nonroot to minimize image vulnerability attack surface."
        ),
    ),
    EmbeddingEvalPair(
        id="ci-actionlint-gate",
        category="ci_cd",
        query="Lint GitHub Actions workflows for syntax errors and unpinned actions in pre-commit",
        target_passage=(
            "The devops ci quality gate invokes actionlint on all .github/workflows/*.yml "
            "manifests, verifying shellcheck compliance inside run scripts and flagging untagged "
            "third-party action SHA references."
        ),
    ),
    EmbeddingEvalPair(
        id="ci-uv-cache-matrix",
        category="ci_cd",
        query="Accelerate CI test matrix runs using uv cache and lockfile hash keys",
        target_passage=(
            "Use astral-sh/setup-uv with enable-cache: true and cache-dependency-glob: 'uv.lock' "
            "to restore pre-built Python wheels across Ubuntu, macOS, and Windows matrix jobs, "
            "reducing dependency sync duration from minutes to under 5 seconds."
        ),
    ),
    # 5. Infrastructure & Cloud
    EmbeddingEvalPair(
        id="infra-terraform-state",
        category="infrastructure",
        query="Remote Terraform state backend with S3 bucket and DynamoDB locking",
        target_passage=(
            "Configure terraform backend 's3' with bucket = 'org-tf-state-prod', key = "
            "'vpc/terraform.tfstate', region = 'us-east-1', and dynamodb_table = 'terraform-locks' "
            "to prevent concurrent conflicting state mutations during automated CI runs."
        ),
    ),
    EmbeddingEvalPair(
        id="infra-qdrant-vector-db",
        category="infrastructure",
        query="Index code chunks and execute cosine similarity vector search in Qdrant database",
        target_passage=(
            "Initialize Qdrant client connection at port 6333, create collection with "
            "Distance.COSINE and vector dimension 768, and query nearest neighbor points matching "
            "embedding vectors using client.search_points(collection_name, query_vector=vec)."
        ),
    ),
    EmbeddingEvalPair(
        id="infra-prometheus-metrics",
        category="infrastructure",
        query="Query Prometheus PromQL metrics endpoint for p99 request latency and CPU usage",
        target_passage=(
            "Execute PromQL instant and range queries against Prometheus /api/v1/query_range "
            "using histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) "
            "by (le)) to monitor microservice tail latency SLA breaches."
        ),
    ),
    EmbeddingEvalPair(
        id="infra-jaeger-tracing",
        category="infrastructure",
        query="Collect distributed trace spans with OpenTelemetry Collector and Jaeger UI",
        target_passage=(
            "Deploy OpenTelemetry Collector DaemonSet receiving OTLP gRPC spans at port 4317 and "
            "exporting traces to Jaeger backend storage, visualizing request call graphs and "
            "latency bottlenecks across microservices."
        ),
    ),
]

# Distractor passages to test negative ranking separation and semantic discrimination
EMBEDDING_DISTRACTORS: list[str] = [
    "A standard recipe for chocolate chip cookies requires butter, sugar, and baking soda.",
    "The history of Renaissance painting in Florence flourished during the 15th century.",
    "Planetary astronomy examines orbital resonance and atmospheric composition of exoplanets.",
    "Gardening tips for springtime include pruning perennial roses before planting tomatoes.",
    "Bicycle maintenance requires lubricating the derailleur chain and checking brake pads.",
    "Acoustic guitars produce sound through string vibrations amplified by the wooden chamber.",
    "Modern diesel locomotives utilize internal combustion engines coupled with traction motors.",
    "Sourdough fermentation relies on wild lactobacillus bacteria and ambient yeasts.",
    "The rules of chess dictate that pawns move forward but capture diagonally on adjacent files.",
    "Scuba diving safety rules require monitoring tank pressure and decompression stops.",
    "Espresso brewing requires a water temperature between 90 and 96 degrees Celsius.",
    "Ancient Roman aqueducts transported fresh water using gravity across stone arches.",
    "Vocal warmups for opera singers involve diaphragmatic breathing and arpeggio scales.",
    "Woodworking joinery techniques utilize mortise and tenon or dovetail interlocking joints.",
    "Beekeeping requires inspecting brood frames for queen presence and varroa mite control.",
]


def get_embedding_eval_dataset() -> tuple[list[EmbeddingEvalPair], list[str]]:
    """Return the paired evaluation items and the complete document corpus."""
    corpus: list[str] = [p.target_passage for p in EMBEDDING_EVAL_PAIRS] + list(
        EMBEDDING_DISTRACTORS
    )
    return list(EMBEDDING_EVAL_PAIRS), corpus
