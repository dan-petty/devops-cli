# FastMCP Tool Catalog

The `devops-cli` FastMCP server exposes DevOps automation and AI review capabilities to Model Context Protocol (MCP) clients and AI agents.

## Available Tools

| Tool Name | Description |
|---|---|
| [`ai_architecture`](#ai-architecture) | Analyze architectural module boundaries, dependency graphs, and cyclic imports. |
| [`ai_diagram`](#ai-diagram) | Generate visual Mermaid architecture or threat modeling diagram. |
| [`ai_repomap`](#ai-repomap) | Generate a compact whole-repository AST symbol map for AI context. |
| [`ai_test_gen`](#ai-test-gen) | Synthesize isolated pytest unit test suite for a target Python file. |
| [`argo_list`](#argo-list) | List ArgoCD applications. |
| [`argo_status`](#argo-status) | Check ArgoCD application health and sync status. |
| [`benchmark_embeddings`](#benchmark-embeddings) | Benchmark embedding model inference latency, dimensions, and retrieval accuracy. |
| [`branches_list`](#branches-list) | List git branches across repositories with tracking status and stale detection. |
| [`ci_run`](#ci-run) | Run devops-cli complete quality gate (pytest, ruff check, ruff format, mypy). |
| [`config_audit_keys`](#config-audit-keys) | Audit OS Keyring health, token state, and zero-plaintext secret compliance. |
| [`config_output`](#config-output) | Output environment variables available for configuration (text or json). |
| [`config_show`](#config-show) | Display configuration settings with masked secret tokens. |
| [`docker_sandbox`](#docker-sandbox) | Execute command inside an isolated Docker container sandbox. |
| [`docker_stats`](#docker-stats) | List local Docker images and display container information. |
| [`grafana_dashboards`](#grafana-dashboards) | List Grafana dashboards, optionally filtered by search query. |
| [`k8s_audit`](#k8s-audit) | Audit Kubernetes cluster security posture, RBAC policies, and CIS benchmarks. |
| [`k8s_bootstrap`](#k8s-bootstrap) | Bootstrap minikube Kubernetes cluster and deploy infrastructure stack. |
| [`k8s_chaos`](#k8s-chaos) | Inject or validate Kubernetes chaos engineering experiments and cluster resilience. |
| [`k8s_create_tls_secret`](#k8s-create-tls-secret) | Create or update a kubernetes.io/tls secret in a target namespace. |
| [`k8s_deploy_stack`](#k8s-deploy-stack) | Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to Kubernetes cluster. |
| [`k8s_diff_helm`](#k8s-diff-helm) | Compare local Helm values or charts against deployed cluster releases. |
| [`k8s_enable_tls`](#k8s-enable-tls) | Apply TLS secrets across Kubernetes cluster namespaces (argocd, monitoring, llm, otel). |
| [`k8s_jaeger_info`](#k8s-jaeger-info) | Retrieve Jaeger distributed tracing Query UI URL and OTLP trace endpoints. |
| [`k8s_lint`](#k8s-lint) | Lint Kubernetes manifests against security best practices and deprecated APIs. |
| [`k8s_pods`](#k8s-pods) | List Kubernetes pod status for the specified namespace. |
| [`k8s_status`](#k8s-status) | Display pod status across infrastructure namespaces. |
| [`k8s_teardown_stack`](#k8s-teardown-stack) | Uninstall Kubernetes infrastructure or LLM stack and delete namespaces. |
| [`k8s_validate`](#k8s-validate) | Validate Kubernetes manifest syntax and schemas against OpenAPI specifications. |
| [`pr_checks`](#pr-checks) | Inspect detailed status of GitHub Actions CI checks for a pull request. |
| [`pr_list`](#pr-list) | List GitHub pull requests with review approval state and CI check summaries. |
| [`prometheus_query`](#prometheus-query) | Execute PromQL instant query against Prometheus endpoint. |
| [`rag_index`](#rag-index) | Index workspace files into Qdrant vector database for semantic retrieval. |
| [`rag_search`](#rag-search) | Perform semantic vector search across indexed workspace codebase and architecture docs. |
| [`release_status`](#release-status) | Check devops-cli release status, version consistency, tags, and docs state. |
| [`repos_list`](#repos-list) | List local workspace repositories and active git branches. |
| [`repos_status`](#repos-status) | Display uncommitted changes and branch drift across workspace repositories. |
| [`repos_sync`](#repos-sync) | Fetch and pull tracking branches across workspace repositories. |
| [`review_branch`](#review-branch) | Run an AI code review on git branch diff against base branch. |
| [`review_export_feedback`](#review-export-feedback) | Export review findings into JSONL feedback dataset for LLM alignment. |
| [`review_findings`](#review-findings) | Inspect structured review findings for a session by verification status. |
| [`review_path`](#review-path) | Run an AI code review on local files matching pattern using specified persona. |
| [`review_pr`](#review-pr) | Fetch GitHub PR diff and review using specified persona; optionally post comment. |
| [`review_stats`](#review-stats) | View accuracy metrics and false-positive rates per reviewer persona. |
| [`scan_aibom`](#scan-aibom) | Generate an AI Bill of Materials (AIBOM) cataloging models, datasets, and licenses. |
| [`scan_checkov`](#scan-checkov) | Scan Infrastructure-as-Code (Terraform, Helm, Kubernetes, Dockerfile) via Checkov. |
| [`scan_complexity`](#scan-complexity) | Inspect Python codebase for cyclomatic complexity and excessive indentation depth. |
| [`scan_fix`](#scan-fix) | Remediate vulnerable dependencies via lockfile upgrades and optional git branch creation. |
| [`scan_gitleaks`](#scan-gitleaks) | Scan git repository or directory for hardcoded secrets, tokens, and private keys. |
| [`scan_sbom`](#scan-sbom) | Generate CycloneDX or SPDX Software Bill of Materials for target workspace. |
| [`scan_semgrep`](#scan-semgrep) | Perform AST-based static code security analysis and rule enforcement via Semgrep. |
| [`scan_trivy`](#scan-trivy) | Run container, filesystem, or repository vulnerability scanning via Trivy. |
| [`scan_uv_audit`](#scan-uv-audit) | Run uv dependency audit / pip-audit to check workspace Python dependencies for known CVEs. |
| [`security_intel_network`](#security-intel-network) | Check IP or domain threat intelligence via Shodan and Cloudflare Radar. |
| [`security_intel_package`](#security-intel-package) | Query OSV.dev and NVD vulnerability databases for package CVE intelligence. |
| [`ssh_audit`](#ssh-audit) | Audit SSH key expiration dates and key file permissions. |
| [`ssh_status`](#ssh-status) | Inspect age and rotation status of managed SSH keys in ~/.ssh. |
| [`telemetry_profile`](#telemetry-profile) | Display terminal waterfall latency breakdown of OpenTelemetry trace spans. |
| [`telemetry_status`](#telemetry-status) | Check OpenTelemetry collector connectivity, Jaeger UI URL, and active telemetry settings. |
| [`telemetry_test_span`](#telemetry-test-span) | Emit a test OpenTelemetry trace span and metric to verify collector pipeline health. |
| [`tf_apply`](#tf-apply) | Apply OpenTofu / Terraform Infrastructure-as-Code changes. |
| [`tf_notify_plan`](#tf-notify-plan) | Format structured OpenTofu/Terraform plan summary for PR comments. |
| [`tf_output`](#tf-output) | Retrieve OpenTofu / Terraform outputs from state. |
| [`tf_plan`](#tf-plan) | Generate and inspect an OpenTofu / Terraform execution plan. |
| [`tls_generate_ca`](#tls-generate-ca) | Generate an X.509 Root CA key pair for local or homelab infrastructure. |
| [`tls_generate_cert`](#tls-generate-cert) | Generate an X.509 TLS certificate with Subject Alternative Names signed by local CA. |
| [`tls_inspect_cert`](#tls-inspect-cert) | Inspect and display metadata, validity, SANs, and expiration of a TLS certificate. |
| [`vault_get`](#vault-get) | Fetch secret from HashiCorp Vault or OS Keyring fallback. |
| [`vault_set`](#vault-set) | Store secret key-value pairs in HashiCorp Vault KV-v2 engine. |
| [`vault_status`](#vault-status) | Check HashiCorp Vault cluster health and sealing status. |
| [`vault_sync`](#vault-sync) | Synchronize secrets from HashiCorp Vault into the local OS Keyring. |
| [`verify_finding`](#verify-finding) | Validate or invalidate a finding and record human feedback. |
| [`workspace_list`](#workspace-list) | Show the active VS Code workspace file and configured repository directories. |

---

### `ai_architecture`

Analyze architectural module boundaries, dependency graphs, and cyclic imports.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `src` | - |
| `max_depth` | `integer` | No | `4` | - |

### `ai_diagram`

Generate visual Mermaid architecture or threat modeling diagram.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `diagram_type` | `string` | No | `arch` | - |
| `target_dir` | `string` | No | `.` | - |

### `ai_repomap`

Generate a compact whole-repository AST symbol map for AI context.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_dir` | `string` | No | `.` | - |

### `ai_test_gen`

Synthesize isolated pytest unit test suite for a target Python file.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_file` | `string` | Yes | - | - |

### `argo_list`

List ArgoCD applications.

*No parameters required.*

### `argo_status`

Check ArgoCD application health and sync status.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `app` | `string` | No | `argocd` | - |

### `benchmark_embeddings`

Benchmark embedding model inference latency, dimensions, and retrieval accuracy.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `provider` | `string` | No | `ollama` | - |
| `model` | `string` | No | `bge-m3` | - |
| `samples` | `integer` | No | `10` | - |

### `branches_list`

List git branches across repositories with tracking status and stale detection.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `remote` | `boolean` | No | `True` | - |

### `ci_run`

Run devops-cli complete quality gate (pytest, ruff check, ruff format, mypy).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `check` | `string` | No | `all` | - |

### `config_audit_keys`

Audit OS Keyring health, token state, and zero-plaintext secret compliance.

*No parameters required.*

### `config_output`

Output environment variables available for configuration (text or json).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `output_format` | `string` | No | `json` | - |

### `config_show`

Display configuration settings with masked secret tokens.

*No parameters required.*

### `docker_sandbox`

Execute command inside an isolated Docker container sandbox.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `command` | `array` | Yes | - | - |
| `image` | `string` | No | `python:3.14-slim` | - |
| `workspace` | `string` | No | `.` | - |
| `memory` | `string` | No | `2g` | - |
| `network` | `string` | No | `bridge` | - |
| `read_only` | `boolean` | No | `False` | - |

### `docker_stats`

List local Docker images and display container information.

*No parameters required.*

### `grafana_dashboards`

List Grafana dashboards, optionally filtered by search query.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `string` | No | `` | - |

### `k8s_audit`

Audit Kubernetes cluster security posture, RBAC policies, and CIS benchmarks.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `namespace` | `string` | No | `default` | - |

### `k8s_bootstrap`

Bootstrap minikube Kubernetes cluster and deploy infrastructure stack.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `auto_start` | `boolean` | No | `True` | - |

### `k8s_chaos`

Inject or validate Kubernetes chaos engineering experiments and cluster resilience.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `action` | `string` | No | `validate` | - |
| `experiment` | `string` | No | `pod-failure` | - |
| `namespace` | `string` | No | `default` | - |

### `k8s_create_tls_secret`

Create or update a kubernetes.io/tls secret in a target namespace.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `secret_name` | `string` | Yes | - | - |
| `namespace` | `string` | No | `default` | - |
| `cert_path` | `string` | No | `` | - |
| `key_path` | `string` | No | `` | - |

### `k8s_deploy_stack`

Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to Kubernetes cluster.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `stack` | `string` | No | `infra` | - |
| `context` | `string` | No | - | - |

### `k8s_diff_helm`

Compare local Helm values or charts against deployed cluster releases.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `release_name` | `string` | Yes | - | - |
| `chart` | `string` | Yes | - | - |
| `namespace` | `string` | No | `default` | - |

### `k8s_enable_tls`

Apply TLS secrets across Kubernetes cluster namespaces (argocd, monitoring, llm, otel).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `stack` | `string` | No | `all` | - |
| `secret_name` | `string` | No | `homelab-tls` | - |
| `context` | `string` | No | `` | - |

### `k8s_jaeger_info`

Retrieve Jaeger distributed tracing Query UI URL and OTLP trace endpoints.

*No parameters required.*

### `k8s_lint`

Lint Kubernetes manifests against security best practices and deprecated APIs.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `manifest_path` | `string` | No | `.` | - |

### `k8s_pods`

List Kubernetes pod status for the specified namespace.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `namespace` | `string` | No | `default` | - |

### `k8s_status`

Display pod status across infrastructure namespaces.

*No parameters required.*

### `k8s_teardown_stack`

Uninstall Kubernetes infrastructure or LLM stack and delete namespaces.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `stack` | `string` | No | `infra` | - |
| `context` | `string` | No | - | - |

### `k8s_validate`

Validate Kubernetes manifest syntax and schemas against OpenAPI specifications.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `manifest_path` | `string` | No | `.` | - |

### `pr_checks`

Inspect detailed status of GitHub Actions CI checks for a pull request.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `pr_number` | `integer` | Yes | - | - |

### `pr_list`

List GitHub pull requests with review approval state and CI check summaries.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `limit` | `integer` | No | `10` | - |
| `state` | `string` | No | `open` | - |

### `prometheus_query`

Execute PromQL instant query against Prometheus endpoint.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `promql` | `string` | No | `up` | - |

### `rag_index`

Index workspace files into Qdrant vector database for semantic retrieval.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | `string` | No | `.` | - |
| `project` | `string` | No | - | - |
| `force` | `boolean` | No | `False` | - |

### `rag_search`

Perform semantic vector search across indexed workspace codebase and architecture docs.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `string` | Yes | - | - |
| `top_k` | `integer` | No | `5` | - |
| `min_score` | `number` | No | `0.35` | - |
| `project` | `string` | No | - | - |
| `language` | `string` | No | - | - |
| `category` | `string` | No | - | - |

### `release_status`

Check devops-cli release status, version consistency, tags, and docs state.

*No parameters required.*

### `repos_list`

List local workspace repositories and active git branches.

*No parameters required.*

### `repos_status`

Display uncommitted changes and branch drift across workspace repositories.

*No parameters required.*

### `repos_sync`

Fetch and pull tracking branches across workspace repositories.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `all_repos` | `boolean` | No | `False` | - |

### `review_branch`

Run an AI code review on git branch diff against base branch.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `branch` | `string` | No | `` | - |
| `base` | `string` | No | `main` | - |
| `persona` | `string` | No | `devsecops` | - |

### `review_export_feedback`

Export review findings into JSONL feedback dataset for LLM alignment.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `status` | `string` | No | `ALL` | - |
| `output_path` | `string` | No | `` | - |

### `review_findings`

Inspect structured review findings for a session by verification status.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `session_id` | `string` | No | `` | - |
| `status` | `string` | No | `` | - |

### `review_path`

Run an AI code review on local files matching pattern using specified persona.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | - |
| `pattern` | `string` | No | `*` | - |
| `persona` | `string` | No | `devsecops` | - |

### `review_pr`

Fetch GitHub PR diff and review using specified persona; optionally post comment.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | Yes | - | - |
| `post` | `boolean` | No | `False` | - |
| `persona` | `string` | No | `devsecops` | - |

### `review_stats`

View accuracy metrics and false-positive rates per reviewer persona.

*No parameters required.*

### `scan_aibom`

Generate an AI Bill of Materials (AIBOM) cataloging models, datasets, and licenses.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | - |

### `scan_checkov`

Scan Infrastructure-as-Code (Terraform, Helm, Kubernetes, Dockerfile) via Checkov.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | - |

### `scan_complexity`

Inspect Python codebase for cyclomatic complexity and excessive indentation depth.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `src` | - |
| `max_complexity` | `integer` | No | `10` | - |
| `max_nesting_depth` | `integer` | No | `5` | - |

### `scan_fix`

Remediate vulnerable dependencies via lockfile upgrades and optional git branch creation.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_path` | `string` | No | `.` | - |
| `package` | `string` | No | - | - |
| `min_severity` | `string` | No | `HIGH` | - |
| `apply` | `boolean` | No | `False` | - |
| `create_branch` | `boolean` | No | `False` | - |

### `scan_gitleaks`

Scan git repository or directory for hardcoded secrets, tokens, and private keys.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | - |

### `scan_sbom`

Generate CycloneDX or SPDX Software Bill of Materials for target workspace.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | - |
| `format` | `string` | No | `cyclonedx` | - |

### `scan_semgrep`

Perform AST-based static code security analysis and rule enforcement via Semgrep.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | - |
| `config` | `string` | No | `auto` | - |

### `scan_trivy`

Run container, filesystem, or repository vulnerability scanning via Trivy.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | - |
| `scan_type` | `string` | No | `fs` | - |
| `severity` | `string` | No | `HIGH,CRITICAL` | - |

### `scan_uv_audit`

Run uv dependency audit / pip-audit to check workspace Python dependencies for known CVEs.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `requirements_file` | `string` | No | `` | - |

### `security_intel_network`

Check IP or domain threat intelligence via Shodan and Cloudflare Radar.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | Yes | - | - |

### `security_intel_package`

Query OSV.dev and NVD vulnerability databases for package CVE intelligence.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `package_name` | `string` | Yes | - | - |
| `version` | `string` | No | `` | - |
| `ecosystem` | `string` | No | `PyPI` | - |

### `ssh_audit`

Audit SSH key expiration dates and key file permissions.

*No parameters required.*

### `ssh_status`

Inspect age and rotation status of managed SSH keys in ~/.ssh.

*No parameters required.*

### `telemetry_profile`

Display terminal waterfall latency breakdown of OpenTelemetry trace spans.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `command` | `string` | No | `` | - |

### `telemetry_status`

Check OpenTelemetry collector connectivity, Jaeger UI URL, and active telemetry settings.

*No parameters required.*

### `telemetry_test_span`

Emit a test OpenTelemetry trace span and metric to verify collector pipeline health.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | `string` | No | `mcp_test_span` | - |

### `tf_apply`

Apply OpenTofu / Terraform Infrastructure-as-Code changes.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `var_file` | `string` | No | `` | - |
| `auto_approve` | `boolean` | No | `True` | - |

### `tf_notify_plan`

Format structured OpenTofu/Terraform plan summary for PR comments.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `plan_file` | `string` | No | `tfplan.json` | - |

### `tf_output`

Retrieve OpenTofu / Terraform outputs from state.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `json_format` | `boolean` | No | `True` | - |

### `tf_plan`

Generate and inspect an OpenTofu / Terraform execution plan.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `var_file` | `string` | No | `` | - |

### `tls_generate_ca`

Generate an X.509 Root CA key pair for local or homelab infrastructure.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `output_dir` | `string` | No | `` | - |
| `common_name` | `string` | No | `Homelab Root CA` | - |
| `validity_days` | `integer` | No | `3650` | - |

### `tls_generate_cert`

Generate an X.509 TLS certificate with Subject Alternative Names signed by local CA.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `common_name` | `string` | No | `localhost` | - |
| `sans` | `string` | No | `localhost,127.0.0.1,*.homelab.local` | - |
| `output_dir` | `string` | No | `` | - |
| `validity_days` | `integer` | No | `365` | - |

### `tls_inspect_cert`

Inspect and display metadata, validity, SANs, and expiration of a TLS certificate.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `cert_path` | `string` | Yes | - | - |

### `vault_get`

Fetch secret from HashiCorp Vault or OS Keyring fallback.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | `string` | Yes | - | - |
| `key` | `string` | No | - | - |

### `vault_set`

Store secret key-value pairs in HashiCorp Vault KV-v2 engine.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | `string` | Yes | - | - |
| `key_values` | `array` | Yes | - | - |

### `vault_status`

Check HashiCorp Vault cluster health and sealing status.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `vault_addr` | `string` | No | - | - |

### `vault_sync`

Synchronize secrets from HashiCorp Vault into the local OS Keyring.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | `string` | Yes | - | - |
| `keys` | `string` | No | - | - |

### `verify_finding`

Validate or invalidate a finding and record human feedback.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `session_id` | `string` | Yes | - | - |
| `index` | `integer` | Yes | - | - |
| `status` | `string` | Yes | - | - |
| `reason` | `string` | No | `` | - |

### `workspace_list`

Show the active VS Code workspace file and configured repository directories.

*No parameters required.*
