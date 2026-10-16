# FastMCP Tool Catalog

The `devops-cli` FastMCP server exposes DevOps automation and AI review capabilities to Model Context Protocol (MCP) clients and AI agents.

## Available Tools

| Tool Name | `readOnlyHint` | Description |
|---|---|---|
| [`ai_ast_graph`](#ai-ast-graph) | `true` | Synthesize whole-repository code symbol and reference graph across polyglot languages. |
| [`ai_ast_parse`](#ai-ast-parse) | `true` | Parse a polyglot source file (Python, TypeScript, JavaScript, Go, Rust, Java, C#, C, C++, HCL, shell, Markdown) into syntax symbols or execute S-expression query. |
| [`ai_backend_probe`](#ai-backend-probe) | `true` | Directly probe health, latency, and registered models of an inference backend. |
| [`ai_chaos_model`](#ai-chaos-model) | `false` | Execute model dependency chaos fault injection and verify automated fallback recovery. |
| [`ai_constellation_status`](#ai-constellation-status) | `true` | Show the constellation flag: state, reason and recorded fallback route. |
| [`ai_diagram`](#ai-diagram) | `true` | Generate visual Mermaid architecture or threat modeling diagram. |
| [`ai_failover`](#ai-failover) | `false` | Record a fallback route in the constellation flag; ai_gateway_failover reroutes requests. |
| [`ai_gateway_failover`](#ai-gateway-failover) | `false` | Trigger or test circuit-breaker failover of a virtual model to secondary backends. |
| [`ai_gateway_routes`](#ai-gateway-routes) | `true` | List registered virtual models and target backend inference instances. |
| [`ai_gateway_status`](#ai-gateway-status) | `true` | Probe LLM Gateway health, latency, and circuit breaker metrics. |
| [`ai_harness_status`](#ai-harness-status) | `true` | Inspect the AI agent harness slots as configured: provider, model, skills and tools. |
| [`ai_ingest_library`](#ai-ingest-library) | `false` | Introspect an installed Python package and extract its public API contract into the data directory's libraries/. |
| [`ai_inspect_symbol`](#ai-inspect-symbol) | `true` | Inspect exact symbol signature, parameter types, return type, and docstrings from library contracts. |
| [`ai_pack_context`](#ai-pack-context) | `true` | Pack and prune source code context to fit token budget while preserving signatures and types. |
| [`ai_prewarm_models`](#ai-prewarm-models) | `false` | Prewarm local LLM models into GPU VRAM or proactively evict them across candidate cluster nodes. |
| [`ai_query_library`](#ai-query-library) | `true` | Search library contracts and documentation via semantic search or exact symbol lookup. |
| [`ai_quiesce`](#ai-quiesce) | `false` | Set the constellation quiesce flag with a reason; it stops nothing. |
| [`ai_read`](#ai-read) | `true` | Inspect and read source code across 3 multi-scale focal zoom levels (Topology, Structural Outline, Deep Focal Window). |
| [`ai_repomap`](#ai-repomap) | `true` | Generate a compact whole-repository AST symbol map for AI context. |
| [`ai_resume`](#ai-resume) | `false` | Clear the constellation quiesce or failover flag. |
| [`ai_spend_report`](#ai-spend-report) | `true` | Report approximate AI spend per backend service, model, or provider over time. |
| [`ai_subagent_offload`](#ai-subagent-offload) | `true` | Offload AST exploration, symbol cataloging, or file scouting to local sub-agent slot. |
| [`ai_test_gen`](#ai-test-gen) | `true` | Generate failing pytest unit test scaffolds for a target Python file. |
| [`argo_fleet_sync`](#argo-fleet-sync) | `false` | Coordinate multi-cluster ArgoCD fleet synchronization with bounded concurrency. |
| [`argo_list`](#argo-list) | `true` | List ArgoCD applications. |
| [`argo_rollout_analyze`](#argo-rollout-analyze) | `false` | Analyze progressive rollout metric gates and trigger automated rollback on threshold violation. |
| [`argo_status`](#argo-status) | `true` | Check ArgoCD application health and sync status. |
| [`benchmark_embeddings`](#benchmark-embeddings) | `true` | Benchmark embedding latency, dimensions, and retrieval accuracy on the configured servers. |
| [`branches_list`](#branches-list) | `true` | List git branches across repositories with tracking status and stale detection. |
| [`ci_run`](#ci-run) | `true` | Run devops-cli complete quality gate or an individual check in check-only mode without modifying files: python version check (3.14+), pytest & coverage, ruff lint, ruff format, mypy typecheck, uv audit, bandit security scan, actionlint, docs validation, uv check, uv lockfile freshness, outdated package tree, and devcontainer validation. |
| [`config_audit_keys`](#config-audit-keys) | `true` | Audit OS Keyring health, token state, and zero-plaintext secret compliance. |
| [`config_output`](#config-output) | `true` | Output environment variables available for configuration (text or json). |
| [`config_show`](#config-show) | `true` | Display configuration settings with masked secret tokens. |
| [`docker_sandbox`](#docker-sandbox) | `false` | Execute command inside an isolated Docker container sandbox. |
| [`docker_sign`](#docker-sign) | `false` | Sign a container image using Sigstore Cosign (keyless or keyed). |
| [`docker_stats`](#docker-stats) | `true` | List local Docker images and display container information. |
| [`docker_verify`](#docker-verify) | `true` | Verify container image signature or attestation using Sigstore Cosign. |
| [`docs_compact`](#docs-compact) | `false` | Compact historical release series documentation (v0.2.x -> v0.3.x). |
| [`gh_issue_create`](#gh-issue-create) | `false` | Create a new GitHub issue linking milestone and taxonomy labels. |
| [`gh_issue_edit`](#gh-issue-edit) | `false` | Edit an existing GitHub issue title, body, state, or milestone. |
| [`gh_issue_list`](#gh-issue-list) | `true` | List repository issues with milestone, taxonomy labels, and status. |
| [`gh_issue_status`](#gh-issue-status) | `true` | Display aggregated issue counts by priority, type, and milestone. |
| [`gh_issue_triage`](#gh-issue-triage) | `true` | Audit open issues for mandatory taxonomy labels, and report those awaiting intake. |
| [`gh_label_list`](#gh-label-list) | `true` | List declarative repository labels and descriptions. |
| [`gh_label_sync`](#gh-label-sync) | `false` | Synchronize repository labels against .github/labels.yml schema. |
| [`gh_milestone_close`](#gh-milestone-close) | `false` | Close the release milestone of a version, with or without its v. |
| [`gh_milestone_edit`](#gh-milestone-edit) | `false` | Edit a release milestone's title, description, state, or due date; others stay as they are. |
| [`gh_milestone_list`](#gh-milestone-list) | `true` | List repository milestones and progress rates. |
| [`gh_pages_build`](#gh-pages-build) | `false` | Trigger a new deployment build for GitHub Pages. |
| [`gh_pages_status`](#gh-pages-status) | `true` | Inspect GitHub Pages site deployment status, URL, branch, and HTTPS enforcement. |
| [`gh_pages_verify`](#gh-pages-verify) | `true` | Verify local repository readiness for GitHub Pages publishing. |
| [`gh_project_audit`](#gh-project-audit) | `true` | Audit project board health and alignment against standardized template. |
| [`gh_project_list`](#gh-project-list) | `true` | List available GitHub Projects v2 boards for user or organization. |
| [`gh_project_reconcile`](#gh-project-reconcile) | `false` | Reconcile Status and Priority on the cards already on the project board, listing each change and its source.  `mode="plan"`, the default, reads the board and the repository and lists the changes without making them. `mode="dry-run"` makes no request and returns the requests a run makes; `mode="write"` makes the changes. A run that stops early says how many planned changes remain and fails with exit status 1. Reconcile adds no card. |
| [`gh_project_status`](#gh-project-status) | `true` | Inspect GitHub Projects v2 template configuration, fields, and view definitions. |
| [`gh_project_sync`](#gh-project-sync) | `false` | Find or create the project board, link it, create its missing fields, and reconcile Status and Priority on the cards already on it.  Sync adds no issue or pull request to the board: `roadmap_intake` places issues, and a pull request's progress shows on its issue's card. `dry_run`, the default, makes no request. |
| [`gh_rate_limit`](#gh-rate-limit) | `true` | Inspect GitHub REST and GraphQL API rate limits, quotas, and reset countdowns. |
| [`gh_run_view`](#gh-run-view) | `true` | View details and diagnostic failure logs of a specific GitHub Actions workflow run. |
| [`gh_runs_list`](#gh-runs-list) | `true` | List recent GitHub Actions CI/CD workflow runs. |
| [`gh_view_spec`](#gh-view-spec) | `true` | Return JSON specification for GitHub Projects v2 views. |
| [`gh_views_audit`](#gh-views-audit) | `true` | Audit remote project views against standardized view template specifications. |
| [`gh_views_sync`](#gh-views-sync) | `false` | Synchronize standardized GitHub Projects v2 views with the remote repository project. |
| [`grafana_dashboards`](#grafana-dashboards) | `true` | List Grafana dashboards, optionally filtered by search query. |
| [`hydrate_tool_domain`](#hydrate-tool-domain) | `true` | Advertise the tools for one domain, which are withheld from the listing by default.  Call this before browsing a domain's tools. Available lazy domains include `argo`, `benchmark`, `branches`, `ci`, `docker`, `docs`, `gh`, `grafana`, `k8s`, `pr`, `prometheus`, `rag`, `release`, `repos`, `roadmap`, `sandbox`, `scan`, `security`, `ssh`, `telemetry`, `tf`, `tls`, `valkey`, `vault` and `verify`. Pass the domain name alone, for example `k8s`. |
| [`k8s_audit`](#k8s-audit) | `true` | Audit Kubernetes cluster security posture, RBAC policies, and CIS benchmarks. |
| [`k8s_bootstrap`](#k8s-bootstrap) | `false` | Bootstrap minikube Kubernetes cluster and deploy infrastructure stack. |
| [`k8s_chaos`](#k8s-chaos) | `false` | Inject or validate Kubernetes chaos engineering experiments and cluster resilience. |
| [`k8s_create_tls_secret`](#k8s-create-tls-secret) | `false` | Create or update a kubernetes.io/tls secret in a target namespace. |
| [`k8s_deploy_stack`](#k8s-deploy-stack) | `false` | Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to Kubernetes cluster. |
| [`k8s_diff_helm`](#k8s-diff-helm) | `true` | Compare local Helm values or charts against deployed cluster releases. |
| [`k8s_doctor`](#k8s-doctor) | `true` | Diagnose Kubernetes cluster deployment health and correlate symptoms across nodes, pods, and events.  Runs `devops k8s doctor --format json`. When the cluster has findings, the command exits with status 2, so the output begins with `Command exited with status 2:` followed by the JSON report. Status 1 indicates the cluster could not be read or an API call failed. |
| [`k8s_enable_tls`](#k8s-enable-tls) | `false` | Apply TLS secrets across Kubernetes cluster namespaces (argocd, monitoring, llm, otel). |
| [`k8s_lint`](#k8s-lint) | `true` | Lint Kubernetes manifests against security best practices and deprecated APIs. |
| [`k8s_logs_query`](#k8s-logs-query) | `true` | Execute LogQL query across Kubernetes and cluster log streams (e.g. {app="web"} |= "error"). |
| [`k8s_logs_tail`](#k8s-logs-tail) | `true` | Tail recent log lines matching LogQL stream selector (e.g. {app="web"}). |
| [`k8s_pods`](#k8s-pods) | `true` | List the pods of a Kubernetes namespace, or of every namespace when it is empty. |
| [`k8s_security_stream`](#k8s-security-stream) | `true` | Stream runtime security anomaly events and syscall alerts from Kubernetes Falco eBPF probes. |
| [`k8s_status`](#k8s-status) | `true` | Display pod status across infrastructure namespaces. |
| [`k8s_teardown_stack`](#k8s-teardown-stack) | `false` | Uninstall Kubernetes infrastructure or LLM stack and delete namespaces. |
| [`k8s_tempo_info`](#k8s-tempo-info) | `true` | Retrieve Tempo distributed tracing HTTP API URL and OTLP trace endpoints. |
| [`k8s_validate`](#k8s-validate) | `true` | Validate Kubernetes manifest syntax and schemas against OpenAPI specifications. |
| [`pr_check_readiness`](#pr-check-readiness) | `true` | Validate PR merge readiness: verify no unresolved review threads, no conflicts, and clean state. |
| [`pr_checks`](#pr-checks) | `true` | Inspect detailed status of GitHub Actions CI checks for a pull request. |
| [`pr_close`](#pr-close) | `false` | Close a pull request with optional comment and remote branch deletion. |
| [`pr_diff`](#pr-diff) | `true` | View the unified git diff for a pull request. |
| [`pr_edit`](#pr-edit) | `false` | Edit an existing pull request title, body, base branch, or milestone. |
| [`pr_list`](#pr-list) | `true` | List GitHub pull requests with review approval state and CI check summaries. |
| [`pr_monitor`](#pr-monitor) | `true` | Monitor PR CI checks, Copilot reviews, and review threads until ready for merge. |
| [`pr_ready`](#pr-ready) | `false` | Mark a draft pull request as ready for review and optionally begin monitoring. |
| [`pr_thread_reply`](#pr-thread-reply) | `false` | Post an in-thread reply directly to a pull request review discussion thread. |
| [`pr_thread_resolve`](#pr-thread-resolve) | `false` | Programmatically mark a pull request review discussion thread as resolved. |
| [`pr_threads_list`](#pr-threads-list) | `true` | List review discussion threads, file locations, and comments on a pull request. |
| [`pr_update_branch`](#pr-update-branch) | `false` | Update a pull request branch with latest commits from its base branch. |
| [`prometheus_query`](#prometheus-query) | `true` | Execute PromQL instant query against Prometheus endpoint. |
| [`rag_drift`](#rag-drift) | `false` | Detect staleness and drift between the working tree and the Qdrant vector index. |
| [`rag_index`](#rag-index) | `false` | Index workspace files into Qdrant vector database for semantic retrieval. |
| [`rag_search`](#rag-search) | `true` | Perform semantic vector search across indexed workspace codebase and architecture docs. |
| [`release_status`](#release-status) | `true` | Check devops-cli release status, version consistency, tags, and docs state. |
| [`repos_list`](#repos-list) | `true` | List local workspace repositories and active git branches. |
| [`repos_status`](#repos-status) | `true` | Display uncommitted changes and branch drift across workspace repositories. |
| [`repos_sync`](#repos-sync) | `false` | Fetch and pull tracking branches across workspace repositories. |
| [`review_branch`](#review-branch) | `true` | Run an AI code review on git branch diff against base branch. |
| [`review_export_feedback`](#review-export-feedback) | `false` | Append review verdicts the feedback dataset does not hold yet to the JSONL dataset. |
| [`review_findings`](#review-findings) | `true` | List a session's findings, filtered by status, each with the number `review verify` takes. |
| [`review_path`](#review-path) | `true` | Run an AI code review on local files matching pattern using specified persona. |
| [`review_pr`](#review-pr) | `false` | Fetch GitHub PR diff and review using specified persona; optionally post comment. |
| [`review_stats`](#review-stats) | `true` | View accuracy metrics and false-positive rates per reviewer persona. |
| [`roadmap_close`](#roadmap-close) | `true` | Preview closure: each delivered item it would close, with its comment, first in each closed release that still holds an open issue and then in the current release, and the current release's cut it would make or what holds it.  It never writes. `mode="plan"`, the default, reads GitHub and ends with the GraphQL points spent and left once its store has sent a GraphQL request; `mode="dry-run"` makes no request and returns the requests a run makes. A person or the service runs `devops roadmap close --confirm`. |
| [`roadmap_intake`](#roadmap-intake) | `false` | Turn candidates into roadmap items: duplicate check, type, priority, Value, Effort and placement, with the agent filing quota for an agent's new candidate (`title` with `body`, and `source`, the link it came from, which `borrow_reason` needs).  `mode="plan"`, the default, previews: it reads GitHub and calls the model, writes nothing, and reports what it spent. `mode="dry-run"` makes no request and returns the requests a run makes; `mode="confirm"` makes the writes. The body is passed as text, never as a path, so the tool reads no file of the caller's choosing. |
| [`roadmap_migrate`](#roadmap-migrate) | `true` | Preview the one-time move of the roadmap's source to GitHub: its plan and report.  It never writes. `mode="plan"`, the default, reads GitHub and ends with the GraphQL points spent and left; `mode="dry-run"` makes no request and returns the requests a run makes. A person reviews the plan and runs `devops roadmap migrate --confirm`. |
| [`roadmap_refine`](#roadmap-refine) | `true` | Run a dry run of item refinement: returns the refinement plan without making any writes.  It never accepts a confirm argument, ensuring it is strictly read-only. When the model call fails for an item, the tool fails, and its error still carries the plan naming that item. |
| [`roadmap_render`](#roadmap-render) | `false` | Render docs/ROADMAP.md from GitHub's issues, milestones and board.  `mode="plan"`, the default, reads GitHub and prints the file without writing it, ending with the GraphQL points spent and left. `mode="dry-run"` makes no request and returns the requests a run makes; `mode="write"` writes the file. |
| [`roadmap_reprioritize`](#roadmap-reprioritize) | `false` | Hold the current release to its admission rule, size limit and stall window, and start the next release once it ships; prints each change with its reason.  `mode="plan"`, the default, previews: it reads GitHub, writes nothing, and ends with the GraphQL points spent and left. `mode="dry-run"` makes no request and returns the requests a run makes; `mode="confirm"` makes the changes. |
| [`roadmap_run`](#roadmap-run) | `true` | Report the roadmap jobs that are due: runs nothing and returns the due tuple. |
| [`sandbox_deploy`](#sandbox-deploy) | `false` | Deploy an isolated workload container sandbox with security containment and port allocation. |
| [`sandbox_exec`](#sandbox-exec) | `false` | Execute a command inside an active sandbox container. |
| [`sandbox_network_policy`](#sandbox-network-policy) | `true` | Generate declarative Kubernetes NetworkPolicy YAML for workload sandbox isolation.  Each whitelist item opens one TCP port: `host:port`, or 443 for a bare host or IP. `allow_collector` adds one egress rule to the OTel collector's pods on TCP 4317 and 4318, in the sandbox_namespace, public_whitelist and local_whitelist modes. |
| [`sandbox_status`](#sandbox-status) | `true` | Inspect status of deployed sandbox containers. |
| [`sandbox_stop`](#sandbox-stop) | `false` | Gracefully stop and remove a sandbox container. |
| [`scan_aibom`](#scan-aibom) | `true` | Generate an AI Bill of Materials (AIBOM) cataloging models, datasets, and licenses. |
| [`scan_checkov`](#scan-checkov) | `true` | Scan Infrastructure-as-Code (Terraform, Helm, Kubernetes, Dockerfile) via Checkov. |
| [`scan_complexity`](#scan-complexity) | `true` | Inspect Python codebase for cyclomatic complexity and excessive indentation depth. |
| [`scan_fix`](#scan-fix) | `false` | Remediate vulnerable dependencies via lockfile upgrades and optional git branch creation. |
| [`scan_gitleaks`](#scan-gitleaks) | `true` | Scan git repository or directory for hardcoded secrets, tokens, and private keys. |
| [`scan_sbom`](#scan-sbom) | `true` | Generate CycloneDX or SPDX Software Bill of Materials for target workspace. |
| [`scan_semgrep`](#scan-semgrep) | `true` | Perform AST-based static code security analysis and rule enforcement via Semgrep. |
| [`scan_trivy`](#scan-trivy) | `true` | Run container, filesystem, or repository vulnerability scanning via Trivy. |
| [`scan_uv_audit`](#scan-uv-audit) | `true` | Run uv dependency audit / pip-audit to check workspace Python dependencies for known CVEs. |
| [`security_intel_network`](#security-intel-network) | `true` | Check IP or domain threat intelligence via Shodan and Cloudflare Radar. |
| [`security_intel_package`](#security-intel-package) | `true` | Query the OSV.dev vulnerability database for package CVE intelligence. |
| [`ssh_audit`](#ssh-audit) | `true` | Audit SSH key expiration dates and key file permissions. |
| [`ssh_status`](#ssh-status) | `true` | Inspect age and rotation status of managed SSH keys in ~/.ssh. |
| [`telemetry_logfire_status`](#telemetry-logfire-status) | `true` | Check Logfire structured observability bridge status, token configuration, and recorded metrics. |
| [`telemetry_profile`](#telemetry-profile) | `true` | Show the span waterfall Tempo recorded for a trace ID; the tool runs no command. |
| [`telemetry_status`](#telemetry-status) | `true` | Check OpenTelemetry collector connectivity, Tempo HTTP API URL, and active telemetry settings. |
| [`telemetry_test_span`](#telemetry-test-span) | `false` | Emit a test OpenTelemetry trace span and metric to verify collector pipeline health. |
| [`tf_apply`](#tf-apply) | `false` | Apply OpenTofu / Terraform Infrastructure-as-Code changes. |
| [`tf_cost_estimate`](#tf-cost-estimate) | `true` | Estimate cloud infrastructure cost with Infracost FinOps engine. |
| [`tf_notify_plan`](#tf-notify-plan) | `true` | Format structured OpenTofu/Terraform plan summary for PR comments. |
| [`tf_output`](#tf-output) | `true` | Retrieve OpenTofu / Terraform outputs from state. |
| [`tf_plan`](#tf-plan) | `true` | Generate and inspect an OpenTofu / Terraform execution plan. |
| [`tls_generate_ca`](#tls-generate-ca) | `false` | Generate an X.509 Root CA key pair for local or homelab infrastructure. |
| [`tls_generate_cert`](#tls-generate-cert) | `false` | Generate an X.509 TLS certificate with Subject Alternative Names signed by local CA. |
| [`tls_inspect_cert`](#tls-inspect-cert) | `true` | Inspect and display metadata, validity, SANs, and expiration of a TLS certificate. |
| [`valkey_flush`](#valkey-flush) | `false` | Flush and purge keys from current or all Valkey databases. |
| [`valkey_get`](#valkey-get) | `true` | Retrieve string value stored at Valkey key. |
| [`valkey_info`](#valkey-info) | `true` | Inspect Valkey server configuration, memory allocation, and operational metrics. |
| [`valkey_ping`](#valkey-ping) | `true` | Test connection and measure latency to the workstation Valkey server. |
| [`valkey_set`](#valkey-set) | `false` | Set string value of Valkey key with optional expiration TTL in seconds. |
| [`valkey_stats`](#valkey-stats) | `true` | Display quick diagnostic summary of Valkey server health, memory, and keys. |
| [`vault_get`](#vault-get) | `true` | Fetch secret from HashiCorp Vault or OS Keyring fallback. |
| [`vault_set`](#vault-set) | `false` | Store secret key-value pairs in HashiCorp Vault KV-v2 engine. |
| [`vault_status`](#vault-status) | `true` | Check HashiCorp Vault cluster health and sealing status. |
| [`vault_sync`](#vault-sync) | `false` | Synchronize secrets from HashiCorp Vault into the local OS Keyring. |
| [`workspace_list`](#workspace-list) | `true` | Show the active VS Code workspace file and configured repository directories. |

---

### `ai_ast_graph`

Synthesize whole-repository code symbol and reference graph across polyglot languages.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_dir` | `string` | No | `.` | - |
| `max_files` | `integer` | No | `50` | - |

### `ai_ast_parse`

Parse a polyglot source file (Python, TypeScript, JavaScript, Go, Rust, Java, C#, C, C++, HCL, shell, Markdown) into syntax symbols or execute S-expression query.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `file_path` | `string` | Yes | - | - |
| `query` | `string` | No | `` | - |

### `ai_backend_probe`

Directly probe health, latency, and registered models of an inference backend.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `backend` | `string` | Yes | - | - |
| `backend_url` | `string` | No | `` | - |

### `ai_chaos_model`

Execute model dependency chaos fault injection and verify automated fallback recovery.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `mode` | `string` | No | `all` | - |
| `fallback_model` | `string` | No | `qwen2.5-coder:7b` | - |
| `dry_run` | `boolean` | No | `False` | - |

### `ai_constellation_status`

Show the constellation flag: state, reason and recorded fallback route.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `ai_diagram`

Generate visual Mermaid architecture or threat modeling diagram.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `diagram_type` | `string` | No | `arch` | - |
| `target_dir` | `string` | No | `.` | - |

### `ai_failover`

Record a fallback route in the constellation flag; ai_gateway_failover reroutes requests.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_provider` | `string` | No | `ollama` | - |
| `target_model` | `string` | No | `qwen2.5-coder:7b` | - |
| `dry_run` | `boolean` | No | `False` | - |

### `ai_gateway_failover`

Trigger or test circuit-breaker failover of a virtual model to secondary backends.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `virtual_model` | `string` | Yes | - | - |
| `simulate` | `boolean` | No | `True` | - |
| `force` | `boolean` | No | `False` | - |

### `ai_gateway_routes`

List registered virtual models and target backend inference instances.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `gateway_url` | `string` | No | `` | - |
| `provider` | `string` | No | `` | - |

### `ai_gateway_status`

Probe LLM Gateway health, latency, and circuit breaker metrics.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `gateway_url` | `string` | No | `` | - |
| `provider` | `string` | No | `` | - |

### `ai_harness_status`

Inspect the AI agent harness slots as configured: provider, model, skills and tools.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `ai_ingest_library`

Introspect an installed Python package and extract its public API contract into the data directory's libraries/.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `package` | `string` | Yes | - | - |
| `max_depth` | `integer` | No | `1` | - |

### `ai_inspect_symbol`

Inspect exact symbol signature, parameter types, return type, and docstrings from library contracts.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `symbol` | `string` | Yes | - | - |
| `package` | `string` | No | `` | - |

### `ai_pack_context`

Pack and prune source code context to fit token budget while preserving signatures and types.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `file_path` | `string` | Yes | - | - |
| `referenced` | `string` | No | `` | - |
| `max_tokens` | `integer` | No | `1500` | - |
| `strip_private` | `boolean` | No | `True` | - |
| `skeletonize` | `boolean` | No | `True` | - |

### `ai_prewarm_models`

Prewarm local LLM models into GPU VRAM or proactively evict them across candidate cluster nodes.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `model` | `string` | No | `` | - |
| `keep_alive` | `string` | No | `1h` | - |
| `evict` | `boolean` | No | `False` | - |
| `all_nodes` | `boolean` | No | `True` | - |

### `ai_query_library`

Search library contracts and documentation via semantic search or exact symbol lookup.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `string` | Yes | - | - |
| `package` | `string` | No | `` | - |
| `exact` | `boolean` | No | `False` | - |
| `top_k` | `integer` | No | `5` | - |

### `ai_quiesce`

Set the constellation quiesce flag with a reason; it stops nothing.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `reason` | `string` | No | `Operator requested emergency quiesce` | - |
| `dry_run` | `boolean` | No | `False` | - |

### `ai_read`

Inspect and read source code across 3 multi-scale focal zoom levels (Topology, Structural Outline, Deep Focal Window).

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_path` | `string` | Yes | - | - |
| `inspect` | `boolean` | No | `True` | - |
| `level` | `integer` | No | `1` | - |
| `lines` | `string` | No | `` | - |
| `symbol` | `string` | No | `` | - |
| `format` | `string` | No | `markdown` | - |

### `ai_repomap`

Generate a compact whole-repository AST symbol map for AI context.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_dir` | `string` | No | `.` | - |

### `ai_resume`

Clear the constellation quiesce or failover flag.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `dry_run` | `boolean` | No | `False` | - |

### `ai_spend_report`

Report approximate AI spend per backend service, model, or provider over time.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `days` | `integer` | No | - | - |
| `group_by` | `string` | No | `server` | - |
| `reference_model` | `string` | No | - | - |
| `hardware_cost` | `number` | No | - | - |

### `ai_subagent_offload`

Offload AST exploration, symbol cataloging, or file scouting to local sub-agent slot.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | `.` | - |
| `symbol` | `string` | No | - | - |
| `pattern` | `string` | No | - | - |

### `ai_test_gen`

Generate failing pytest unit test scaffolds for a target Python file.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_file` | `string` | Yes | - | - |

### `argo_fleet_sync`

Coordinate multi-cluster ArgoCD fleet synchronization with bounded concurrency.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `app_name` | `string` | Yes | - | - |
| `clusters` | `string` | No | `dev,staging,prod` | - |
| `fleet` | `string` | No | `default-fleet` | - |
| `concurrency` | `integer` | No | `3` | - |

### `argo_list`

List ArgoCD applications.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `argo_rollout_analyze`

Analyze progressive rollout metric gates and trigger automated rollback on threshold violation.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `rollout_name` | `string` | Yes | - | - |
| `namespace` | `string` | No | `default` | - |
| `error_rate_threshold` | `number` | No | `1.0` | - |
| `auto_abort` | `boolean` | No | `True` | - |

### `argo_status`

Check ArgoCD application health and sync status.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `app` | `string` | No | `argocd` | - |

### `benchmark_embeddings`

Benchmark embedding latency, dimensions, and retrieval accuracy on the configured servers.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `provider` | `string` | No | `ollama` | - |
| `model` | `string` | No | `bge-m3` | - |
| `samples` | `integer` | No | `10` | - |

### `branches_list`

List git branches across repositories with tracking status and stale detection.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `remote` | `boolean` | No | `True` | - |

### `ci_run`

Run devops-cli complete quality gate or an individual check in check-only mode without modifying files: python version check (3.14+), pytest & coverage, ruff lint, ruff format, mypy typecheck, uv audit, bandit security scan, actionlint, docs validation, uv check, uv lockfile freshness, outdated package tree, and devcontainer validation.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `check` | `string (all, test, lint, format, typecheck, audit, security, actionlint, docs, uv-check, lockfile, outdated, devcontainer)` | No | `all` | - |

### `config_audit_keys`

Audit OS Keyring health, token state, and zero-plaintext secret compliance.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `config_output`

Output environment variables available for configuration (text or json).

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `output_format` | `string` | No | `json` | - |

### `config_show`

Display configuration settings with masked secret tokens.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `docker_sandbox`

Execute command inside an isolated Docker container sandbox.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `command` | `array[string]` | Yes | - | - |
| `image` | `string` | No | `python:3.14-slim` | - |
| `workspace` | `string` | No | `.` | - |
| `memory` | `string` | No | `2g` | - |
| `network` | `string` | No | `isolated` | - |
| `network_mode` | `string` | No | - | - |
| `public_whitelist` | `array[string]` | No | - | - |
| `local_whitelist` | `array[string]` | No | - | - |
| `read_only` | `boolean` | No | `False` | - |

### `docker_sign`

Sign a container image using Sigstore Cosign (keyless or keyed).

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `image` | `string` | Yes | - | - |
| `key` | `string` | No | - | - |
| `keyless` | `boolean` | No | `True` | - |
| `oidc_token` | `string` | No | - | - |
| `annotations` | `array[string]` | No | - | - |
| `upload` | `boolean` | No | `True` | - |
| `dry_run` | `boolean` | No | `False` | - |

### `docker_stats`

List local Docker images and display container information.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `docker_verify`

Verify container image signature or attestation using Sigstore Cosign.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `image` | `string` | Yes | - | - |
| `key` | `string` | No | - | - |
| `certificate_identity` | `string` | No | - | - |
| `certificate_oidc_issuer` | `string` | No | - | - |
| `attestation` | `boolean` | No | `False` | - |
| `predicate_type` | `string` | No | - | - |
| `insecure_ignore_tlog` | `boolean` | No | `False` | - |
| `dry_run` | `boolean` | No | `False` | - |

### `docs_compact`

Compact historical release series documentation (v0.2.x -> v0.3.x).

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `series` | `string` | No | `v0.2` | - |
| `dry_run` | `boolean` | No | `True` | - |
| `check` | `boolean` | No | `False` | - |
| `roadmap_only` | `boolean` | No | `False` | - |
| `release_notes_only` | `boolean` | No | `False` | - |
| `log_only` | `boolean` | No | `False` | - |

### `gh_issue_create`

Create a new GitHub issue linking milestone and taxonomy labels.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `title` | `string` | Yes | - | - |
| `body` | `string` | No | `` | - |
| `milestone` | `string` | No | - | - |
| `labels` | `string` | No | - | - |
| `repo` | `string` | No | - | - |

### `gh_issue_edit`

Edit an existing GitHub issue title, body, state, or milestone.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `issue_number` | `integer` | Yes | - | - |
| `title` | `string` | No | - | - |
| `body` | `string` | No | - | - |
| `state` | `string` | No | - | - |
| `milestone` | `string` | No | - | - |
| `clear_milestone` | `boolean` | No | `False` | - |
| `repo` | `string` | No | - | - |

### `gh_issue_list`

List repository issues with milestone, taxonomy labels, and status.

**Annotations:** `readOnlyHint: true`

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

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_issue_triage`

Audit open issues for mandatory taxonomy labels, and report those awaiting intake.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_label_list`

List declarative repository labels and descriptions.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_label_sync`

Synchronize repository labels against .github/labels.yml schema.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |
| `dry_run` | `boolean` | No | `True` | - |

### `gh_milestone_close`

Close the release milestone of a version, with or without its v.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `version` | `string` | Yes | - | - |
| `repo` | `string` | No | - | - |

### `gh_milestone_edit`

Edit a release milestone's title, description, state, or due date; others stay as they are.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `version` | `string` | Yes | - | - |
| `title` | `string` | No | - | - |
| `description` | `string` | No | - | - |
| `state` | `string` | No | - | - |
| `due_on` | `string` | No | - | - |
| `repo` | `string` | No | - | - |

### `gh_milestone_list`

List repository milestones and progress rates.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_pages_build`

Trigger a new deployment build for GitHub Pages.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_pages_status`

Inspect GitHub Pages site deployment status, URL, branch, and HTTPS enforcement.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_pages_verify`

Verify local repository readiness for GitHub Pages publishing.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `gh_project_audit`

Audit project board health and alignment against standardized template.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_project_list`

List available GitHub Projects v2 boards for user or organization.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `owner` | `string` | No | - | - |

### `gh_project_reconcile`

Reconcile Status and Priority on the cards already on the project board, listing each change and its source.

`mode="plan"`, the default, reads the board and the repository and lists the changes without
making them. `mode="dry-run"` makes no request and returns the requests a run makes;
`mode="write"` makes the changes. A run that stops early says how many planned changes
remain and fails with exit status 1. Reconcile adds no card.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `project_number` | `integer` | No | - | - |
| `repo` | `string` | No | - | - |
| `mode` | `string (dry-run, plan, write)` | No | `plan` | - |

### `gh_project_status`

Inspect GitHub Projects v2 template configuration, fields, and view definitions.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `gh_project_sync`

Find or create the project board, link it, create its missing fields, and reconcile Status and Priority on the cards already on it.

Sync adds no issue or pull request to the board: `roadmap_intake` places issues, and a pull
request's progress shows on its issue's card. `dry_run`, the default, makes no request.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |
| `dry_run` | `boolean` | No | `True` | - |

### `gh_rate_limit`

Inspect GitHub REST and GraphQL API rate limits, quotas, and reset countdowns.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `format_type` | `string` | No | `table` | - |

### `gh_run_view`

View details and diagnostic failure logs of a specific GitHub Actions workflow run.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `run_id` | `integer` | Yes | - | - |
| `log_failed` | `boolean` | No | `True` | - |
| `repo` | `string` | No | - | - |

### `gh_runs_list`

List recent GitHub Actions CI/CD workflow runs.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `limit` | `integer` | No | `10` | - |
| `branch` | `string` | No | - | - |
| `repo` | `string` | No | - | - |

### `gh_view_spec`

Return JSON specification for GitHub Projects v2 views.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `gh_views_audit`

Audit remote project views against standardized view template specifications.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `gh_views_sync`

Synchronize standardized GitHub Projects v2 views with the remote repository project.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | `` | - |

### `grafana_dashboards`

List Grafana dashboards, optionally filtered by search query.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `string` | No | `` | - |

### `hydrate_tool_domain`

Advertise the tools for one domain, which are withheld from the listing by default.

Call this before browsing a domain's tools. Available lazy domains include `argo`,
`benchmark`, `branches`, `ci`, `docker`, `docs`, `gh`, `grafana`, `k8s`, `pr`,
`prometheus`, `rag`, `release`, `repos`, `roadmap`, `sandbox`, `scan`, `security`, `ssh`,
`telemetry`, `tf`, `tls`, `valkey`, `vault` and `verify`.
Pass the domain name alone, for example `k8s`.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `domain` | `string` | Yes | - | - |

### `k8s_audit`

Audit Kubernetes cluster security posture, RBAC policies, and CIS benchmarks.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `k8s_bootstrap`

Bootstrap minikube Kubernetes cluster and deploy infrastructure stack.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `auto_start` | `boolean` | No | `True` | - |

### `k8s_chaos`

Inject or validate Kubernetes chaos engineering experiments and cluster resilience.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `experiment` | `string` | No | `pod-failure` | - |
| `namespace` | `string` | No | `default` | - |
| `dry_run` | `boolean` | No | `True` | - |

### `k8s_create_tls_secret`

Create or update a kubernetes.io/tls secret in a target namespace.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `secret_name` | `string` | Yes | - | - |
| `namespace` | `string` | No | `default` | - |
| `cert_path` | `string` | No | `` | - |
| `key_path` | `string` | No | `` | - |

### `k8s_deploy_stack`

Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to Kubernetes cluster.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `stack` | `string` | No | `infra` | - |
| `context` | `string` | No | - | - |

### `k8s_diff_helm`

Compare local Helm values or charts against deployed cluster releases.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `release_name` | `string` | Yes | - | - |
| `chart` | `string` | Yes | - | - |
| `namespace` | `string` | No | `default` | - |

### `k8s_doctor`

Diagnose Kubernetes cluster deployment health and correlate symptoms across nodes, pods, and events.

Runs `devops k8s doctor --format json`. When the cluster has findings, the command exits with
status 2, so the output begins with `Command exited with status 2:` followed by the JSON report.
Status 1 indicates the cluster could not be read or an API call failed.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `namespace` | `string` | No | - | - |
| `context` | `string` | No | - | - |

### `k8s_enable_tls`

Apply TLS secrets across Kubernetes cluster namespaces (argocd, monitoring, llm, otel).

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `stack` | `string` | No | `all` | - |
| `secret_name` | `string` | No | `homelab-tls` | - |
| `context` | `string` | No | `` | - |

### `k8s_lint`

Lint Kubernetes manifests against security best practices and deprecated APIs.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `manifest_path` | `string` | No | `.` | - |

### `k8s_logs_query`

Execute LogQL query across Kubernetes and cluster log streams (e.g. {app="web"} |= "error").

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `string` | Yes | - | - |
| `limit` | `integer` | No | `100` | - |
| `since` | `string` | No | `1h` | - |
| `namespace` | `string` | No | - | - |

### `k8s_logs_tail`

Tail recent log lines matching LogQL stream selector (e.g. {app="web"}).

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `string` | Yes | - | - |
| `lines` | `integer` | No | `50` | - |
| `namespace` | `string` | No | - | - |

### `k8s_pods`

List the pods of a Kubernetes namespace, or of every namespace when it is empty.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `namespace` | `string` | No | `default` | - |

### `k8s_security_stream`

Stream runtime security anomaly events and syscall alerts from Kubernetes Falco eBPF probes.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `namespace` | `string` | No | `falco` | - |
| `severity` | `string` | No | - | - |
| `tail_lines` | `integer` | No | `100` | - |
| `simulate` | `boolean` | No | `False` | - |

### `k8s_status`

Display pod status across infrastructure namespaces.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `k8s_teardown_stack`

Uninstall Kubernetes infrastructure or LLM stack and delete namespaces.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `stack` | `string` | No | `infra` | - |
| `context` | `string` | No | - | - |

### `k8s_tempo_info`

Retrieve Tempo distributed tracing HTTP API URL and OTLP trace endpoints.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `k8s_validate`

Validate Kubernetes manifest syntax and schemas against OpenAPI specifications.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `manifest_path` | `string` | No | `.` | - |

### `pr_check_readiness`

Validate PR merge readiness: verify no unresolved review threads, no conflicts, and clean state.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `pr_number` | `integer` | No | - | - |
| `allow_blocked_state` | `boolean` | No | `False` | - |
| `repo` | `string` | No | - | - |

### `pr_checks`

Inspect detailed status of GitHub Actions CI checks for a pull request.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `pr_number` | `integer` | Yes | - | - |

### `pr_close`

Close a pull request with optional comment and remote branch deletion.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `pr_number` | `integer` | Yes | - | - |
| `comment` | `string` | No | - | - |
| `delete_branch` | `boolean` | No | `False` | - |
| `repo` | `string` | No | - | - |

### `pr_diff`

View the unified git diff for a pull request.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `pr_number` | `integer` | Yes | - | - |
| `repo` | `string` | No | - | - |

### `pr_edit`

Edit an existing pull request title, body, base branch, or milestone.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `pr_number` | `integer` | Yes | - | - |
| `title` | `string` | No | - | - |
| `body` | `string` | No | - | - |
| `base` | `string` | No | - | - |
| `milestone` | `string` | No | - | - |
| `repo` | `string` | No | - | - |

### `pr_list`

List GitHub pull requests with review approval state and CI check summaries.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `limit` | `integer` | No | `10` | - |
| `state` | `string` | No | `open` | - |

### `pr_monitor`

Monitor PR CI checks, Copilot reviews, and review threads until ready for merge.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `pr_number` | `integer` | No | - | - |
| `timeout` | `integer` | No | `300` | - |
| `interval` | `integer` | No | `60` | - |
| `settle_timeout` | `integer` | No | `60` | - |

### `pr_ready`

Mark a draft pull request as ready for review and optionally begin monitoring.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `pr_number` | `integer` | Yes | - | - |
| `monitor` | `boolean` | No | `False` | - |
| `force` | `boolean` | No | `False` | - |
| `repo` | `string` | No | - | - |

### `pr_thread_reply`

Post an in-thread reply directly to a pull request review discussion thread.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `thread_id` | `string` | Yes | - | - |
| `body` | `string` | Yes | - | - |

### `pr_thread_resolve`

Programmatically mark a pull request review discussion thread as resolved.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `thread_id` | `string` | Yes | - | - |
| `without_reply` | `boolean` | No | `False` | - |

### `pr_threads_list`

List review discussion threads, file locations, and comments on a pull request.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `pr_number` | `integer` | Yes | - | - |
| `unresolved_only` | `boolean` | No | `True` | - |

### `pr_update_branch`

Update a pull request branch with latest commits from its base branch.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `pr_number` | `integer` | Yes | - | - |
| `repo` | `string` | No | - | - |
| `expected_head_sha` | `string` | No | - | - |
| `dry_run` | `boolean` | No | `False` | - |

### `prometheus_query`

Execute PromQL instant query against Prometheus endpoint.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `promql` | `string` | No | `up` | - |

### `rag_drift`

Detect staleness and drift between the working tree and the Qdrant vector index.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | `string` | No | `.` | - |
| `auto_sync` | `boolean` | No | `False` | - |

### `rag_index`

Index workspace files into Qdrant vector database for semantic retrieval.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | `string` | No | `.` | - |
| `project` | `string` | No | - | - |
| `force` | `boolean` | No | `False` | - |

### `rag_search`

Perform semantic vector search across indexed workspace codebase and architecture docs.

**Annotations:** `readOnlyHint: true`

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

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `repos_list`

List local workspace repositories and active git branches.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `repos_status`

Display uncommitted changes and branch drift across workspace repositories.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `repos_sync`

Fetch and pull tracking branches across workspace repositories.

**Annotations:** `readOnlyHint: false`

*No parameters required.*

### `review_branch`

Run an AI code review on git branch diff against base branch.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `branch` | `string` | No | `` | - |
| `base` | `string` | No | `main` | - |
| `persona` | `string` | No | `devsecops` | - |

### `review_export_feedback`

Append review verdicts the feedback dataset does not hold yet to the JSONL dataset.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `status` | `string` | No | `ALL` | - |
| `output_path` | `string` | No | `` | - |

### `review_findings`

List a session's findings, filtered by status, each with the number `review verify` takes.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `session_id` | `string` | No | `` | - |
| `status` | `string` | No | `` | - |

### `review_path`

Run an AI code review on local files matching pattern using specified persona.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | - |
| `pattern` | `string` | No | `*` | - |
| `persona` | `string` | No | `devsecops` | - |

### `review_pr`

Fetch GitHub PR diff and review using specified persona; optionally post comment.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | Yes | - | - |
| `post` | `boolean` | No | `False` | - |
| `persona` | `string` | No | `devsecops` | - |

### `review_stats`

View accuracy metrics and false-positive rates per reviewer persona.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `roadmap_close`

Preview closure: each delivered item it would close, with its comment, first in each
closed release that still holds an open issue and then in the current release, and the
current release's cut it would make or what holds it.

It never writes. `mode="plan"`, the default, reads GitHub and ends with the GraphQL points
spent and left once its store has sent a GraphQL request; `mode="dry-run"` makes no request
and returns the requests a run makes. A person or the service runs
`devops roadmap close --confirm`.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |
| `ref` | `string` | No | - | - |
| `mode` | `string (dry-run, plan)` | No | `plan` | - |

### `roadmap_intake`

Turn candidates into roadmap items: duplicate check, type, priority, Value, Effort and
placement, with the agent filing quota for an agent's new candidate (`title` with `body`,
and `source`, the link it came from, which `borrow_reason` needs).

`mode="plan"`, the default, previews: it reads GitHub and calls the model, writes nothing,
and reports what it spent. `mode="dry-run"` makes no request and returns the requests a run
makes; `mode="confirm"` makes the writes. The body is passed as text, never as a path, so
the tool reads no file of the caller's choosing.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |
| `ref` | `string` | No | - | - |
| `issues` | `array[integer]` | No | - | - |
| `title` | `string` | No | - | - |
| `body` | `string` | No | - | - |
| `source` | `string` | No | - | - |
| `borrow_reason` | `string (split, follow-up)` | No | - | - |
| `mode` | `string (dry-run, plan, confirm)` | No | `plan` | - |

### `roadmap_migrate`

Preview the one-time move of the roadmap's source to GitHub: its plan and report.

It never writes. `mode="plan"`, the default, reads GitHub and ends with the GraphQL points
spent and left; `mode="dry-run"` makes no request and returns the requests a run makes. A
person reviews the plan and runs `devops roadmap migrate --confirm`.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |
| `ref` | `string` | No | - | - |
| `mode` | `string (dry-run, plan)` | No | `plan` | - |

### `roadmap_refine`

Run a dry run of item refinement: returns the refinement plan without making any writes.

It never accepts a confirm argument, ensuring it is strictly read-only. When the model call
fails for an item, the tool fails, and its error still carries the plan naming that item.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |
| `ref` | `string` | No | - | - |
| `item` | `integer` | No | - | - |
| `limit` | `integer` | No | - | - |
| `source` | `string` | No | - | - |

### `roadmap_render`

Render docs/ROADMAP.md from GitHub's issues, milestones and board.

`mode="plan"`, the default, reads GitHub and prints the file without writing it, ending
with the GraphQL points spent and left. `mode="dry-run"` makes no request and returns the
requests a run makes; `mode="write"` writes the file.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |
| `ref` | `string` | No | - | - |
| `mode` | `string (dry-run, plan, write)` | No | `plan` | - |

### `roadmap_reprioritize`

Hold the current release to its admission rule, size limit and stall window, and start
the next release once it ships; prints each change with its reason.

`mode="plan"`, the default, previews: it reads GitHub, writes nothing, and ends with the
GraphQL points spent and left. `mode="dry-run"` makes no request and returns the requests a
run makes; `mode="confirm"` makes the changes.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |
| `ref` | `string` | No | - | - |
| `mode` | `string (dry-run, plan, confirm)` | No | `plan` | - |

### `roadmap_run`

Report the roadmap jobs that are due: runs nothing and returns the due tuple.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | - |

### `sandbox_deploy`

Deploy an isolated workload container sandbox with security containment and port allocation.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `image` | `string` | No | `python:3.14-slim` | - |
| `name` | `string` | No | - | - |
| `ports` | `array[integer]` | No | - | - |
| `workspace` | `string` | No | `.` | - |
| `memory` | `string` | No | `2g` | - |
| `cpus` | `number` | No | `2.0` | - |
| `network` | `string` | No | `isolated` | - |
| `network_mode` | `string` | No | - | - |
| `public_whitelist` | `array[string]` | No | - | - |
| `local_whitelist` | `array[string]` | No | - | - |
| `read_only` | `boolean` | No | `True` | - |
| `command` | `array[string]` | No | - | - |

### `sandbox_exec`

Execute a command inside an active sandbox container.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `instance_id` | `string` | Yes | - | - |
| `command` | `array[string]` | Yes | - | - |
| `workdir` | `string` | No | - | - |

### `sandbox_network_policy`

Generate declarative Kubernetes NetworkPolicy YAML for workload sandbox isolation.

Each whitelist item opens one TCP port: `host:port`, or 443 for a bare host or IP.
`allow_collector` adds one egress rule to the OTel collector's pods on TCP 4317 and 4318,
in the sandbox_namespace, public_whitelist and local_whitelist modes.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `network_mode` | `string` | No | `isolated` | - |
| `name` | `string` | No | `app-sandbox` | - |
| `namespace` | `string` | No | `sandbox` | - |
| `public_whitelist` | `array[string]` | No | - | - |
| `local_whitelist` | `array[string]` | No | - | - |
| `allow_collector` | `boolean` | No | `False` | - |

### `sandbox_status`

Inspect status of deployed sandbox containers.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `instance_id` | `string` | No | - | - |
| `all_instances` | `boolean` | No | `False` | - |

### `sandbox_stop`

Gracefully stop and remove a sandbox container.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `instance_id` | `string` | No | - | - |
| `all_instances` | `boolean` | No | `False` | - |
| `timeout` | `integer` | No | `10` | - |

### `scan_aibom`

Generate an AI Bill of Materials (AIBOM) cataloging models, datasets, and licenses.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | - |

### `scan_checkov`

Scan Infrastructure-as-Code (Terraform, Helm, Kubernetes, Dockerfile) via Checkov.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | - |

### `scan_complexity`

Inspect Python codebase for cyclomatic complexity and excessive indentation depth.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `src` | - |
| `max_complexity` | `integer` | No | `10` | - |
| `max_nesting_depth` | `integer` | No | `5` | - |

### `scan_fix`

Remediate vulnerable dependencies via lockfile upgrades and optional git branch creation.

**Annotations:** `readOnlyHint: false`

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

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | - |

### `scan_sbom`

Generate CycloneDX or SPDX Software Bill of Materials for target workspace.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | - |
| `format` | `string` | No | `cyclonedx` | - |

### `scan_semgrep`

Perform AST-based static code security analysis and rule enforcement via Semgrep.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | - |
| `config` | `string` | No | `auto` | - |

### `scan_trivy`

Run container, filesystem, or repository vulnerability scanning via Trivy.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | - |
| `scan_type` | `string` | No | `fs` | - |
| `severity` | `string` | No | `HIGH,CRITICAL` | - |

### `scan_uv_audit`

Run uv dependency audit / pip-audit to check workspace Python dependencies for known CVEs.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `requirements_file` | `string` | No | `` | - |

### `security_intel_network`

Check IP or domain threat intelligence via Shodan and Cloudflare Radar.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | Yes | - | - |

### `security_intel_package`

Query the OSV.dev vulnerability database for package CVE intelligence.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `package_name` | `string` | Yes | - | - |
| `version` | `string` | No | `` | - |
| `ecosystem` | `string` | No | `PyPI` | - |

### `ssh_audit`

Audit SSH key expiration dates and key file permissions.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `ssh_status`

Inspect age and rotation status of managed SSH keys in ~/.ssh.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `telemetry_logfire_status`

Check Logfire structured observability bridge status, token configuration, and recorded metrics.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `telemetry_profile`

Show the span waterfall Tempo recorded for a trace ID; the tool runs no command.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `trace_id` | `string` | Yes | - | - |

### `telemetry_status`

Check OpenTelemetry collector connectivity, Tempo HTTP API URL, and active telemetry settings.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `telemetry_test_span`

Emit a test OpenTelemetry trace span and metric to verify collector pipeline health.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | `string` | No | `mcp_test_span` | - |

### `tf_apply`

Apply OpenTofu / Terraform Infrastructure-as-Code changes.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `var_file` | `string` | No | `` | - |
| `auto_approve` | `boolean` | No | `False` | - |

### `tf_cost_estimate`

Estimate cloud infrastructure cost with Infracost FinOps engine.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `mock` | `boolean` | No | `False` | - |
| `max_monthly_cost` | `number` | No | - | - |

### `tf_notify_plan`

Format structured OpenTofu/Terraform plan summary for PR comments.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `plan_file` | `string` | No | `tfplan.json` | - |

### `tf_output`

Retrieve OpenTofu / Terraform outputs from state.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `json_format` | `boolean` | No | `True` | - |

### `tf_plan`

Generate and inspect an OpenTofu / Terraform execution plan.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `var_file` | `string` | No | `` | - |

### `tls_generate_ca`

Generate an X.509 Root CA key pair for local or homelab infrastructure.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `output_dir` | `string` | No | `` | - |
| `common_name` | `string` | No | `Homelab Root CA` | - |
| `validity_days` | `integer` | No | `3650` | - |

### `tls_generate_cert`

Generate an X.509 TLS certificate with Subject Alternative Names signed by local CA.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `common_name` | `string` | No | `localhost` | - |
| `sans` | `string` | No | `localhost,127.0.0.1,*.homelab.local` | - |
| `output_dir` | `string` | No | `` | - |
| `validity_days` | `integer` | No | `365` | - |

### `tls_inspect_cert`

Inspect and display metadata, validity, SANs, and expiration of a TLS certificate.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `cert_path` | `string` | Yes | - | - |

### `valkey_flush`

Flush and purge keys from current or all Valkey databases.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `all_databases` | `boolean` | No | `False` | - |

### `valkey_get`

Retrieve string value stored at Valkey key.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `key` | `string` | Yes | - | - |

### `valkey_info`

Inspect Valkey server configuration, memory allocation, and operational metrics.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `section` | `string` | No | - | - |

### `valkey_ping`

Test connection and measure latency to the workstation Valkey server.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `valkey_set`

Set string value of Valkey key with optional expiration TTL in seconds.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `key` | `string` | Yes | - | - |
| `value` | `string` | Yes | - | - |
| `ex` | `integer` | No | - | - |

### `valkey_stats`

Display quick diagnostic summary of Valkey server health, memory, and keys.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `vault_get`

Fetch secret from HashiCorp Vault or OS Keyring fallback.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | `string` | Yes | - | - |
| `key` | `string` | No | - | - |

### `vault_set`

Store secret key-value pairs in HashiCorp Vault KV-v2 engine.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | `string` | Yes | - | - |
| `key_values` | `array[string]` | Yes | - | - |

### `vault_status`

Check HashiCorp Vault cluster health and sealing status.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `vault_addr` | `string` | No | - | - |

### `vault_sync`

Synchronize secrets from HashiCorp Vault into the local OS Keyring.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | `string` | Yes | - | - |
| `keys` | `array[string]` | No | - | - |

### `workspace_list`

Show the active VS Code workspace file and configured repository directories.

**Annotations:** `readOnlyHint: true`

*No parameters required.*
