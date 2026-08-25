# FastMCP Tool Catalog

The `devops-cli` FastMCP server exposes DevOps automation and AI review capabilities to Model Context Protocol (MCP) clients and AI agents.

## Available Tools

| Tool Name | Description |
|---|---|
| [`argo_list`](#argo-list) | List ArgoCD applications. |
| [`argo_status`](#argo-status) | Check ArgoCD application health and sync status. |
| [`ci_run`](#ci-run) | Run devops-cli complete quality gate (pytest, ruff check, ruff format, mypy). |
| [`config_output`](#config-output) | Output environment variables available for configuration (text or json). |
| [`config_show`](#config-show) | Display configuration settings with masked secret tokens. |
| [`docker_stats`](#docker-stats) | List local Docker images and display container information. |
| [`grafana_dashboards`](#grafana-dashboards) | List Grafana dashboards, optionally filtered by search query. |
| [`k8s_bootstrap`](#k8s-bootstrap) | Bootstrap minikube Kubernetes cluster and deploy infrastructure stack. |
| [`k8s_create_tls_secret`](#k8s-create-tls-secret) | Create or update a kubernetes.io/tls secret in a target namespace. |
| [`k8s_deploy_stack`](#k8s-deploy-stack) | Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to Kubernetes cluster. |
| [`k8s_enable_tls`](#k8s-enable-tls) | Apply TLS secrets across Kubernetes cluster namespaces (argocd, monitoring, llm, otel). |
| [`k8s_jaeger_info`](#k8s-jaeger-info) | Retrieve Jaeger distributed tracing Query UI URL and OTLP trace endpoints. |
| [`k8s_pods`](#k8s-pods) | List Kubernetes pod status for the specified namespace. |
| [`k8s_status`](#k8s-status) | Display pod status across infrastructure namespaces. |
| [`k8s_teardown_stack`](#k8s-teardown-stack) | Uninstall Kubernetes infrastructure or LLM stack and delete namespaces. |
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
| [`scan_uv_audit`](#scan-uv-audit) | Run uv dependency audit / pip-audit to check workspace Python dependencies for known CVEs. |
| [`security_intel_network`](#security-intel-network) | Check IP or domain threat intelligence via Shodan and Cloudflare Radar. |
| [`security_intel_package`](#security-intel-package) | Query OSV.dev and NVD vulnerability databases for package CVE intelligence. |
| [`ssh_audit`](#ssh-audit) | Audit SSH key expiration dates and key file permissions. |
| [`ssh_status`](#ssh-status) | Inspect age and rotation status of managed SSH keys in ~/.ssh. |
| [`telemetry_status`](#telemetry-status) | Check OpenTelemetry collector connectivity, Jaeger UI URL, and active telemetry settings. |
| [`telemetry_test_span`](#telemetry-test-span) | Emit a test OpenTelemetry trace span and metric to verify collector pipeline health. |
| [`tf_apply`](#tf-apply) | Apply OpenTofu / Terraform Infrastructure-as-Code changes. |
| [`tf_output`](#tf-output) | Retrieve OpenTofu / Terraform outputs from state. |
| [`tf_plan`](#tf-plan) | Generate and inspect an OpenTofu / Terraform execution plan. |
| [`tls_generate_ca`](#tls-generate-ca) | Generate an X.509 Root CA key pair for local or homelab infrastructure. |
| [`tls_generate_cert`](#tls-generate-cert) | Generate an X.509 TLS certificate with Subject Alternative Names signed by local CA. |
| [`tls_inspect_cert`](#tls-inspect-cert) | Inspect and display metadata, validity, SANs, and expiration of a TLS certificate. |
| [`verify_finding`](#verify-finding) | Validate or invalidate a finding and record human feedback. |
| [`workspace_list`](#workspace-list) | Show the active VS Code workspace file and configured repository directories. |

---

### `argo_list`

List ArgoCD applications.

*No parameters required.*

### `argo_status`

Check ArgoCD application health and sync status.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `app` | `string` | No | `argocd` | - |

### `ci_run`

Run devops-cli complete quality gate (pytest, ruff check, ruff format, mypy).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `check` | `string` | No | `all` | - |

### `config_output`

Output environment variables available for configuration (text or json).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `output_format` | `string` | No | `json` | - |

### `config_show`

Display configuration settings with masked secret tokens.

*No parameters required.*

### `docker_stats`

List local Docker images and display container information.

*No parameters required.*

### `grafana_dashboards`

List Grafana dashboards, optionally filtered by search query.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `string` | No | `` | - |

### `k8s_bootstrap`

Bootstrap minikube Kubernetes cluster and deploy infrastructure stack.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `auto_start` | `boolean` | No | `True` | - |

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
