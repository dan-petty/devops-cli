# FastMCP Tool Catalog

The `devops-cli` FastMCP server exposes DevOps automation and AI review capabilities to Model Context Protocol (MCP) clients and AI agents.

## Available Tools

| Tool Name | Description |
|---|---|
| [`ai_architecture`](#ai-architecture) | Analyze architectural module boundaries, dependency graphs, and cyclic imports. |
| [`ai_ast_graph`](#ai-ast-graph) | Synthesize whole-repository code symbol and reference graph across polyglot languages. |
| [`ai_ast_parse`](#ai-ast-parse) | Parse a polyglot source file (Python, TypeScript, Go, Rust, Java, HCL) into syntax symbols or execute S-expression query. |
| [`ai_chaos_model`](#ai-chaos-model) | Execute model dependency chaos fault injection and verify automated fallback recovery. |
| [`ai_constellation_status`](#ai-constellation-status) | Display constellation fleet status, active fallback routes, and suspended tasks. |
| [`ai_diagram`](#ai-diagram) | Generate visual Mermaid architecture or threat modeling diagram. |
| [`ai_failover`](#ai-failover) | Emergency failover controller re-routing tasks to designated fallback endpoints. |
| [`ai_harness_status`](#ai-harness-status) | Inspect AI agent harness slot configuration, active models, skills, and sandbox state. |
| [`ai_ingest_library`](#ai-ingest-library) | Introspect an installed Python package and extract its public API contract into .data/libraries/. |
| [`ai_inspect_symbol`](#ai-inspect-symbol) | Inspect exact symbol signature, parameter types, return type, and docstrings from library contracts. |
| [`ai_pack_context`](#ai-pack-context) | Pack and prune source code context to fit token budget while preserving signatures and types. |
| [`ai_query_library`](#ai-query-library) | Search library contracts and documentation via semantic search or exact symbol lookup. |
| [`ai_quiesce`](#ai-quiesce) | Centralized emergency quiesce cleanly suspending active agent loops and background tasks. |
| [`ai_repomap`](#ai-repomap) | Generate a compact whole-repository AST symbol map for AI context. |
| [`ai_resume`](#ai-resume) | Gracefully resume suspended constellation agent loops and task runners. |
| [`ai_subagent_offload`](#ai-subagent-offload) | Offload AST exploration, symbol cataloging, or file scouting to local sub-agent slot. |
| [`ai_test_gen`](#ai-test-gen) | Synthesize isolated pytest unit test suite for a target Python file. |
| [`argo_list`](#argo-list) | List ArgoCD applications. |
| [`argo_status`](#argo-status) | Check ArgoCD application health and sync status. |
| [`benchmark_embeddings`](#benchmark-embeddings) | Benchmark embedding model inference latency, dimensions, and retrieval accuracy. |
| [`benchmark_suite`](#benchmark-suite) | Benchmark candidate models against feedback dataset for precision, recall, and hallucination scoring. |
| [`branches_list`](#branches-list) | List git branches across repositories with tracking status and stale detection. |
| [`ci_run`](#ci-run) | Run devops-cli complete quality gate (pytest, ruff check, ruff format, mypy). |
| [`config_audit_keys`](#config-audit-keys) | Audit OS Keyring health, token state, and zero-plaintext secret compliance. |
| [`config_output`](#config-output) | Output environment variables available for configuration (text or json). |
| [`config_show`](#config-show) | Display configuration settings with masked secret tokens. |
| [`docker_sandbox`](#docker-sandbox) | Execute command inside an isolated Docker container sandbox. |
| [`docker_stats`](#docker-stats) | List local Docker images and display container information. |
| [`gh_issue_create`](#gh-issue-create) | Create a new GitHub issue linking milestone and taxonomy labels. |
| [`gh_issue_list`](#gh-issue-list) | List repository issues with milestone, taxonomy labels, and status. |
| [`gh_issue_status`](#gh-issue-status) | Display aggregated issue counts by priority, type, and milestone. |
| [`gh_issue_triage`](#gh-issue-triage) | Audit open issues for mandatory taxonomy labels and milestone linkage. |
| [`gh_label_list`](#gh-label-list) | List declarative repository labels and descriptions. |
| [`gh_label_sync`](#gh-label-sync) | Synchronize repository labels against .github/labels.yml schema. |
| [`gh_milestone_close`](#gh-milestone-close) | Close a repository milestone matching the given version or title. |
| [`gh_milestone_list`](#gh-milestone-list) | List repository milestones and progress rates. |
| [`gh_milestone_sync`](#gh-milestone-sync) | Synchronize repository milestones from docs/ROADMAP.md. |
| [`gh_pages_build`](#gh-pages-build) | Trigger a new deployment build for GitHub Pages. |
| [`gh_pages_status`](#gh-pages-status) | Inspect GitHub Pages site deployment status, URL, branch, and HTTPS enforcement. |
| [`gh_pages_verify`](#gh-pages-verify) | Verify local repository readiness for GitHub Pages publishing. |
| [`gh_project_audit`](#gh-project-audit) | Audit project board health and alignment against standardized template. |
| [`gh_project_list`](#gh-project-list) | List available GitHub Projects v2 boards for user or organization. |
| [`gh_project_reconcile`](#gh-project-reconcile) | Reconcile custom fields (Status, Priority, Category, Value, Effort) on GitHub Projects v2 items. |
| [`gh_project_status`](#gh-project-status) | Inspect GitHub Projects v2 template configuration, fields, and view definitions. |
| [`gh_project_sync`](#gh-project-sync) | Synchronize task items from task.md into GitHub Projects v2 status. |
| [`gh_view_spec`](#gh-view-spec) | Return JSON specification for GitHub Projects v2 views. |
| [`gh_views_audit`](#gh-views-audit) | Audit remote project views against standardized view template specifications. |
| [`gh_views_sync`](#gh-views-sync) | Synchronize standardized GitHub Projects v2 views with the remote repository project. |
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
| [`k8s_logs_query`](#k8s-logs-query) | Execute LogQL query across Kubernetes and cluster log streams (e.g. {app="web"} |= "error"). |
| [`k8s_logs_tail`](#k8s-logs-tail) | Tail recent log lines matching LogQL stream selector (e.g. {app="web"}). |
| [`k8s_pods`](#k8s-pods) | List Kubernetes pod status for the specified namespace. |
| [`k8s_status`](#k8s-status) | Display pod status across infrastructure namespaces. |
| [`k8s_teardown_stack`](#k8s-teardown-stack) | Uninstall Kubernetes infrastructure or LLM stack and delete namespaces. |
| [`k8s_validate`](#k8s-validate) | Validate Kubernetes manifest syntax and schemas against OpenAPI specifications. |
| [`pr_checks`](#pr-checks) | Inspect detailed status of GitHub Actions CI checks for a pull request. |
| [`pr_list`](#pr-list) | List GitHub pull requests with review approval state and CI check summaries. |
| [`pr_thread_reply`](#pr-thread-reply) | Post an in-thread reply directly to a pull request review discussion thread. |
| [`pr_thread_resolve`](#pr-thread-resolve) | Programmatically mark a pull request review discussion thread as resolved. |
| [`pr_threads_list`](#pr-threads-list) | List review discussion threads, file locations, and comments on a pull request. |
| [`prometheus_query`](#prometheus-query) | Execute PromQL instant query against Prometheus endpoint. |
| [`rag_drift`](#rag-drift) | Detect staleness and drift between the working tree and the Qdrant vector index. |
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
| [`telemetry_logfire_status`](#telemetry-logfire-status) | Check Logfire structured observability bridge status, token configuration, and recorded metrics. |
| [`telemetry_profile`](#telemetry-profile) | Display terminal waterfall latency breakdown of OpenTelemetry trace spans. |
| [`telemetry_status`](#telemetry-status) | Check OpenTelemetry collector connectivity, Jaeger UI URL, and active telemetry settings. |
| [`telemetry_test_span`](#telemetry-test-span) | Emit a test OpenTelemetry trace span and metric to verify collector pipeline health. |
| [`tf_apply`](#tf-apply) | Apply OpenTofu / Terraform Infrastructure-as-Code changes. |
| [`tf_cost_estimate`](#tf-cost-estimate) | Estimate cloud infrastructure cost with Infracost FinOps engine. |
| [`tf_notify_plan`](#tf-notify-plan) | Format structured OpenTofu/Terraform plan summary for PR comments. |
| [`tf_output`](#tf-output) | Retrieve OpenTofu / Terraform outputs from state. |
| [`tf_plan`](#tf-plan) | Generate and inspect an OpenTofu / Terraform execution plan. |
| [`tls_generate_ca`](#tls-generate-ca) | Generate an X.509 Root CA key pair for local or homelab infrastructure. |
| [`tls_generate_cert`](#tls-generate-cert) | Generate an X.509 TLS certificate with Subject Alternative Names signed by local CA. |
| [`tls_inspect_cert`](#tls-inspect-cert) | Inspect and display metadata, validity, SANs, and expiration of a TLS certificate. |
| [`valkey_flush`](#valkey-flush) | Flush and purge keys from current or all Valkey databases. |
| [`valkey_get`](#valkey-get) | Retrieve string value stored at Valkey key. |
| [`valkey_info`](#valkey-info) | Inspect Valkey server configuration, memory allocation, and operational metrics. |
| [`valkey_ping`](#valkey-ping) | Test connection and measure latency to the workstation Valkey server. |
| [`valkey_set`](#valkey-set) | Set string value of Valkey key with optional expiration TTL in seconds. |
| [`valkey_stats`](#valkey-stats) | Display quick diagnostic summary of Valkey server health, memory, and keys. |
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

### `ai_ast_graph`

Synthesize whole-repository code symbol and reference graph across polyglot languages.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_dir` | `string` | No | `.` | - |
| `max_files` | `integer` | No | `50` | - |

### `ai_ast_parse`

Parse a polyglot source file (Python, TypeScript, Go, Rust, Java, HCL) into syntax symbols or execute S-expression query.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `file_path` | `string` | Yes | - | - |
| `query` | `string` | No | `` | - |

### `ai_chaos_model`

Execute model dependency chaos fault injection and verify automated fallback recovery.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `mode` | `string` | No | `all` | - |
| `fallback_model` | `string` | No | `qwen2.5-coder:7b` | - |
| `dry_run` | `boolean` | No | `False` | - |

### `ai_constellation_status`

Display constellation fleet status, active fallback routes, and suspended tasks.

*No parameters required.*

### `ai_diagram`

Generate visual Mermaid architecture or threat modeling diagram.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `diagram_type` | `string` | No | `arch` | - |
| `target_dir` | `string` | No | `.` | - |

### `ai_failover`

Emergency failover controller re-routing tasks to designated fallback endpoints.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_provider` | `string` | No | `ollama` | - |
| `target_model` | `string` | No | `qwen2.5-coder:7b` | - |
| `dry_run` | `boolean` | No | `False` | - |

### `ai_harness_status`

Inspect AI agent harness slot configuration, active models, skills, and sandbox state.

*No parameters required.*

### `ai_ingest_library`

Introspect an installed Python package and extract its public API contract into .data/libraries/.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `package` | `string` | Yes | - | - |
| `max_depth` | `integer` | No | `1` | - |

### `ai_inspect_symbol`

Inspect exact symbol signature, parameter types, return type, and docstrings from library contracts.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `symbol` | `string` | Yes | - | - |
| `package` | `string` | No | `` | - |

### `ai_pack_context`

Pack and prune source code context to fit token budget while preserving signatures and types.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `file_path` | `string` | Yes | - | - |
| `referenced` | `string` | No | `` | - |
| `max_tokens` | `integer` | No | `1500` | - |
| `strip_private` | `boolean` | No | `True` | - |
| `skeletonize` | `boolean` | No | `True` | - |

### `ai_query_library`

Search library contracts and documentation via semantic search or exact symbol lookup.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `string` | Yes | - | - |
| `package` | `string` | No | `` | - |
| `exact` | `boolean` | No | `False` | - |
| `top_k` | `integer` | No | `5` | - |

### `ai_quiesce`

Centralized emergency quiesce cleanly suspending active agent loops and background tasks.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `reason` | `string` | No | `Operator requested emergency quiesce` | - |
| `dry_run` | `boolean` | No | `False` | - |

### `ai_repomap`

Generate a compact whole-repository AST symbol map for AI context.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_dir` | `string` | No | `.` | - |

### `ai_resume`

Gracefully resume suspended constellation agent loops and task runners.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `dry_run` | `boolean` | No | `False` | - |

### `ai_subagent_offload`

Offload AST exploration, symbol cataloging, or file scouting to local sub-agent slot.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | `.` | - |
| `symbol` | `string` | No | - | - |
| `pattern` | `string` | No | - | - |

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

### `benchmark_suite`

Benchmark candidate models against feedback dataset for precision, recall, and hallucination scoring.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `models` | `string` | No | `qwen2.5-coder:7b` | - |
| `dataset` | `string` | No | `` | - |
| `provider` | `string` | No | `ollama` | - |
| `dry_run` | `boolean` | No | `True` | - |

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

### `gh_issue_create`

Create a new GitHub issue linking milestone and taxonomy labels.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `title` | `string` | Yes | - | - |
| `body` | `string` | No | `` | - |
| `milestone` | `string` | No | - | - |
| `labels` | `string` | No | - | - |
| `repo` | `string` | No | - | - |

### `gh_issue_list`

List repository issues with milestone, taxonomy labels, and status.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |
| `state` | `string` | No | `open` | - |
| `milestone` | `string` | No | - | - |
| `label` | `string` | No | - | - |
| `limit` | `integer` | No | `30` | - |

### `gh_issue_status`

Display aggregated issue counts by priority, type, and milestone.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_issue_triage`

Audit open issues for mandatory taxonomy labels and milestone linkage.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_label_list`

List declarative repository labels and descriptions.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_label_sync`

Synchronize repository labels against .github/labels.yml schema.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |
| `dry_run` | `boolean` | No | `True` | - |

### `gh_milestone_close`

Close a repository milestone matching the given version or title.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `version` | `string` | Yes | - | - |
| `repo` | `string` | No | - | - |

### `gh_milestone_list`

List repository milestones and progress rates.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_milestone_sync`

Synchronize repository milestones from docs/ROADMAP.md.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |
| `dry_run` | `boolean` | No | `True` | - |

### `gh_pages_build`

Trigger a new deployment build for GitHub Pages.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_pages_status`

Inspect GitHub Pages site deployment status, URL, branch, and HTTPS enforcement.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_pages_verify`

Verify local repository readiness for GitHub Pages publishing.

*No parameters required.*

### `gh_project_audit`

Audit project board health and alignment against standardized template.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_project_list`

List available GitHub Projects v2 boards for user or organization.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `owner` | `string` | No | - | - |

### `gh_project_reconcile`

Reconcile custom fields (Status, Priority, Category, Value, Effort) on GitHub Projects v2 items.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `project_number` | `integer` | No | - | - |
| `repo` | `string` | No | - | - |
| `dry_run` | `boolean` | No | `False` | - |

### `gh_project_status`

Inspect GitHub Projects v2 template configuration, fields, and view definitions.

*No parameters required.*

### `gh_project_sync`

Synchronize task items from task.md into GitHub Projects v2 status.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |
| `dry_run` | `boolean` | No | `True` | - |

### `gh_view_spec`

Return JSON specification for GitHub Projects v2 views.

*No parameters required.*

### `gh_views_audit`

Audit remote project views against standardized view template specifications.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_views_sync`

Synchronize standardized GitHub Projects v2 views with the remote repository project.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | `` | - |

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

### `k8s_logs_query`

Execute LogQL query across Kubernetes and cluster log streams (e.g. {app="web"} |= "error").

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `string` | Yes | - | - |
| `limit` | `integer` | No | `100` | - |
| `since` | `string` | No | `1h` | - |
| `namespace` | `string` | No | - | - |

### `k8s_logs_tail`

Tail recent log lines matching LogQL stream selector (e.g. {app="web"}).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `string` | Yes | - | - |
| `lines` | `integer` | No | `50` | - |
| `namespace` | `string` | No | - | - |

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

### `pr_thread_reply`

Post an in-thread reply directly to a pull request review discussion thread.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `thread_id` | `string` | Yes | - | - |
| `body` | `string` | Yes | - | - |

### `pr_thread_resolve`

Programmatically mark a pull request review discussion thread as resolved.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `thread_id` | `string` | Yes | - | - |

### `pr_threads_list`

List review discussion threads, file locations, and comments on a pull request.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `pr_number` | `integer` | Yes | - | - |
| `unresolved_only` | `boolean` | No | `True` | - |

### `prometheus_query`

Execute PromQL instant query against Prometheus endpoint.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `promql` | `string` | No | `up` | - |

### `rag_drift`

Detect staleness and drift between the working tree and the Qdrant vector index.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | `string` | No | `.` | - |
| `auto_sync` | `boolean` | No | `False` | - |

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

### `telemetry_logfire_status`

Check Logfire structured observability bridge status, token configuration, and recorded metrics.

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

### `tf_cost_estimate`

Estimate cloud infrastructure cost with Infracost FinOps engine.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `mock` | `boolean` | No | `False` | - |
| `max_monthly_cost` | `number` | No | - | - |

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

### `valkey_flush`

Flush and purge keys from current or all Valkey databases.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `all_databases` | `boolean` | No | `False` | - |

### `valkey_get`

Retrieve string value stored at Valkey key.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `key` | `string` | Yes | - | - |

### `valkey_info`

Inspect Valkey server configuration, memory allocation, and operational metrics.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `section` | `string` | No | - | - |

### `valkey_ping`

Test connection and measure latency to the workstation Valkey server.

*No parameters required.*

### `valkey_set`

Set string value of Valkey key with optional expiration TTL in seconds.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `key` | `string` | Yes | - | - |
| `value` | `string` | Yes | - | - |
| `ex` | `integer` | No | - | - |

### `valkey_stats`

Display quick diagnostic summary of Valkey server health, memory, and keys.

*No parameters required.*

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
| `keys` | `array` | No | - | - |

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
