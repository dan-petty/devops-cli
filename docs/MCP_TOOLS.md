# FastMCP Tool Catalog

The `devops-cli` FastMCP server exposes DevOps automation and AI review capabilities to Model Context Protocol (MCP) clients and AI agents.

## Available Tools

| Tool Name | `readOnlyHint` | Description |
|---|---|---|
| [`ai_ast_graph`](#ai-ast-graph) | `true` | Synthesize whole-repository symbol dependency and reference graph. |
| [`ai_ast_parse`](#ai-ast-parse) | `true` | Parse source file concrete syntax tree and extract structural symbols. |
| [`ai_benchmark`](#ai-benchmark) | `true` | Benchmark, evaluate, and peer-grade candidate AI models across engineering tasks. |
| [`ai_chaos_model`](#ai-chaos-model) | `false` | Model dependency chaos engineering suite simulating provider faults and validating local failovers. |
| [`ai_constellation`](#ai-constellation) | `true` | Show the constellation flag: state, reason and recorded fallback route. |
| [`ai_cost_report`](#ai-cost-report) | `true` | Generate detailed spend and token report across backend services and servers. |
| [`ai_diagram`](#ai-diagram) | `true` | Generate visual Mermaid architecture topology or STRIDE threat modeling diagrams. |
| [`ai_failover`](#ai-failover) | `true` | Record a fallback route in the constellation flag; `devops ai gateway failover` records a failover route for a virtual model, and the gateway's own fallbacks move the traffic. |
| [`ai_gateway_failover`](#ai-gateway-failover) | `true` | Trigger or test circuit-breaker failover of a virtual model to secondary backends, or restore the default routes with --reset. |
| [`ai_gateway_probe_backend`](#ai-gateway-probe-backend) | `true` | Directly probe health and latency of an inference backend. |
| [`ai_gateway_routes`](#ai-gateway-routes) | `true` | List registered virtual models and target backend inference instances. |
| [`ai_gateway_status`](#ai-gateway-status) | `true` | Probe LLM Gateway health, latency, and circuit breaker metrics. |
| [`ai_harness_offload`](#ai-harness-offload) | `true` | Offload AST exploration, symbol cataloging, or file scouting to local sub-agent slot. |
| [`ai_harness_status`](#ai-harness-status) | `true` | Display the harness slots as configured; nothing here checks a model is reachable. |
| [`ai_ingest_library`](#ai-ingest-library) | `true` | Introspect an installed Python package and extract its public API contract. |
| [`ai_ingest_query_library`](#ai-ingest-query-library) | `true` | Search library contracts and documentation via semantic search or exact symbol lookup. |
| [`ai_pack_context`](#ai-pack-context) | `true` | Pack and prune source code context to fit token budget while preserving signatures. |
| [`ai_prewarm`](#ai-prewarm) | `false` | Prewarm local models into GPU VRAM or evict idle models across cluster nodes. |
| [`ai_quiesce`](#ai-quiesce) | `true` | Set the constellation quiesce flag with a reason; it stops nothing. |
| [`ai_rag_drift`](#ai-rag-drift) | `false` | Detect staleness and drift between the working tree and the Qdrant vector index. |
| [`ai_rag_index`](#ai-rag-index) | `false` | Scan and index workspace code and documentation into Qdrant vector database. |
| [`ai_rag_query`](#ai-rag-query) | `true` | Perform semantic search across indexed workspace code and documentation. |
| [`ai_read`](#ai-read) | `true` | Inspect and read source code across 3 multi-scale focal zoom levels (Topology, Structural Outline, Deep Focal Window). |
| [`ai_repomap`](#ai-repomap) | `true` | Generate compact whole-repository AST symbol and relationship map. |
| [`ai_resume`](#ai-resume) | `true` | Clear the constellation quiesce or failover flag. |
| [`ai_test_gen`](#ai-test-gen) | `true` | Generate failing pytest unit test scaffolds for functions or source files. |
| [`argo_cd_apps_list`](#argo-cd-apps-list) | `true` | List all ArgoCD applications. |
| [`argo_cd_apps_status`](#argo-cd-apps-status) | `true` | Show the sync and health of an Argo CD application, and check each image it pins.  An image the application pins as `<image>:<tag>@<digest>` in its kustomize images is checked against the digest its tag names in the registry now. Without --watch, the command exits 1 when the status cannot be read, a tag names another digest, or a registry gives no digest. |
| [`argo_fleet_sync`](#argo-fleet-sync) | `false` | Synchronize an application across a fleet of Kubernetes clusters with bounded concurrency. |
| [`argo_rollouts_analyze`](#argo-rollouts-analyze) | `false` | Evaluate metric rollback gates and trigger automated rollback on threshold violation. |
| [`branches_list`](#branches-list) | `true` | List branches across all repos. |
| [`ci`](#ci) | `true` | Run tests, linting, formatting, and type-checks. A run that selects test, security or typecheck first waits for a free gate slot, so the gates of parallel agents take turns. ci.gate_slots sets how many run at once. |
| [`config_audit_keys`](#config-audit-keys) | `true` | Audit OS Keyring token health, backend status, and zero-plaintext secret compliance. The audit scans each config file that the settings merge: the global config file and the project config file. It also scans config.yaml and .devops/config.yaml in the current directory. Exits 0 only when the audit is compliant. Exits 1 when a config file holds a plaintext secret, or when a config file cannot be read or parsed, reporting it unaudited. The full report prints before the exit. The alert of a leak names two commands. `devops config set <key>` stores a credential in the keyring. Add `--from-file <path>` for a multi-line credential, such as a PEM key. `DEVOPS_CLI_CONFIG=<file> devops config unset <key>` removes the value from the file of the leak. |
| [`config_output`](#config-output) | `true` | Output environment variables available for devops-cli configuration. |
| [`config_show`](#config-show) | `true` | Print every setting that a variable sets and every credential. A credential shows as set or not set, never its value. |
| [`docker_images`](#docker-images) | `true` | List local Docker images. |
| [`docker_sandbox`](#docker-sandbox) | `false` | Execute workload inside an isolated, disposable Docker container sandbox. |
| [`docker_sign`](#docker-sign) | `false` | Sign a container image using Sigstore Cosign (keyless or keyed). |
| [`docker_verify`](#docker-verify) | `true` | Verify container image signature or attestation using Sigstore Cosign. |
| [`gh_issues_close`](#gh-issues-close) | `false` | Close an open issue with its reason, completed or not planned. With --comment-file, the command posts the comment first, then closes the issue, so a failed close leaves the comment. It refuses a pull request and an issue that is already closed, because GitHub ignores a reason unless the state changes. |
| [`gh_issues_create`](#gh-issues-create) | `false` | Create a new issue linking milestone and taxonomy labels. |
| [`gh_issues_edit`](#gh-issues-edit) | `false` | Edit an existing issue title, body, state, milestone, or taxonomy labels. |
| [`gh_issues_list`](#gh-issues-list) | `true` | List repository issues with milestone, taxonomy labels, and status. |
| [`gh_issues_status`](#gh-issues-status) | `true` | Display aggregated issue counts by priority, type, and milestone. |
| [`gh_issues_triage`](#gh-issues-triage) | `true` | Audit open issues for mandatory taxonomy labels, and report those with no priority/* label as awaiting intake. |
| [`gh_issues_view`](#gh-issues-view) | `true` | Print one issue with its state, milestone, labels, assignees, dates and full body. |
| [`gh_labels_list`](#gh-labels-list) | `true` | List all labels defined in the remote repository. |
| [`gh_labels_sync`](#gh-labels-sync) | `false` | Synchronize repository labels against the declarative YAML schema. |
| [`gh_milestones_close`](#gh-milestones-close) | `false` | Close the milestone with this title or number. |
| [`gh_milestones_edit`](#gh-milestones-edit) | `false` | Edit a milestone's title, description, state, or due date; fields left out stay as they are. |
| [`gh_milestones_list`](#gh-milestones-list) | `true` | List every milestone, by due date and then by number, with its issue completion rate. |
| [`gh_pages_build`](#gh-pages-build) | `false` | Trigger a new deployment build for GitHub Pages. |
| [`gh_pages_status`](#gh-pages-status) | `true` | Inspect GitHub Pages deployment status, URL, branch, and HTTPS enforcement. |
| [`gh_pages_verify`](#gh-pages-verify) | `true` | Verify local repository readiness for GitHub Pages publishing. |
| [`gh_project_audit`](#gh-project-audit) | `true` | Audit the project board's views against the template. |
| [`gh_project_list`](#gh-project-list) | `true` | List available GitHub Projects v2 boards for user or organization. |
| [`gh_project_reconcile`](#gh-project-reconcile) | `false` | Reconcile Status and Priority on the cards already on the board, listing each change and its source; the board owns Status, and reconcile never writes Milestone, Value or Effort or adds a card. A planned value the board's field has no option for is refused before any write. A run that stops early (mutation budget, GraphQL quota or a failed write) says why and how many planned changes remain, and exits 1. Running it again continues from there: after the reset when the quota stopped it, and once the cause is fixed when a write failed. |
| [`gh_project_status`](#gh-project-status) | `true` | Inspect the declarative GitHub Projects v2 template structure and views. |
| [`gh_project_sync`](#gh-project-sync) | `false` | Find or create the project board from its template, link it, create the fields it lacks, and reconcile Status and Priority on the cards already on it. Sync adds no issue or pull request to the board, and a pull request's progress shows on its issue's card. No roadmap job reads the board: labels hold an item's fields. Exits 1 when reconcile stops early. |
| [`gh_rate_limit`](#gh-rate-limit) | `true` | Display GitHub REST and GraphQL API rate limits, quotas, and reset countdowns. |
| [`gh_runs_list`](#gh-runs-list) | `true` | List recent workflow runs for the repository or branch. |
| [`gh_runs_view`](#gh-runs-view) | `true` | View details and failure logs of a specific workflow run. |
| [`gh_views_audit`](#gh-views-audit) | `true` | Audit remote project views against standardized template specifications. |
| [`gh_views_spec`](#gh-views-spec) | `true` | Output JSON schema specification for all configured project views. |
| [`gh_views_sync`](#gh-views-sync) | `false` | Synchronize standardized views with the remote GitHub Projects v2 board. |
| [`grafana_dashboards_list`](#grafana-dashboards-list) | `true` | List all dashboards. |
| [`hydrate_tool_domain`](#hydrate-tool-domain) | `true` | Advertise the tools for one domain, which are withheld from the listing by default.  Call this before browsing a domain's tools. Available lazy domains include `argo`, `benchmark`, `branches`, `ci`, `docker`, `docs`, `gh`, `grafana`, `k8s`, `pr`, `prometheus`, `rag`, `repos`, `roadmap`, `sandbox`, `scan`, `security`, `ssh`, `telemetry`, `tf`, `tls`, `valkey`, `vault` and `verify`. Pass the domain name alone, for example `k8s`. |
| [`k8s_audit`](#k8s-audit) | `true` | Sanitize active K8s/Minikube cluster resource health using Derailed Popeye. |
| [`k8s_bootstrap`](#k8s-bootstrap) | `false` | Bootstrap homelab Kubernetes cluster with Minikube, Calico, and ingress. |
| [`k8s_chaos`](#k8s-chaos) | `false` | Run resilience and chaos experiments against Kubernetes workloads. |
| [`k8s_create_tls_secret`](#k8s-create-tls-secret) | `false` | Create or update a kubernetes.io/tls secret from certificate and private key files. |
| [`k8s_deploy_stack`](#k8s-deploy-stack) | `false` | Deploy one stack (infra, llm, logging, devops, gitea, chat) or all of them to Kubernetes with Helm and Kustomize.  Right after the namespaces, it pushes the Secrets of the base rows, its stacks and every detached stack whose namespace exists (`devops k8s push-secrets`), before anything that reads them. A locked or missing keyring stops it before it applies anything. |
| [`k8s_diff_helm`](#k8s-diff-helm) | `true` | Preview Kubernetes manifest diffs before executing a Helm upgrade. |
| [`k8s_doctor`](#k8s-doctor) | `false` | Diagnose Kubernetes cluster deployment health, correlate failures, and recommend remediations. |
| [`k8s_enable_tls`](#k8s-enable-tls) | `false` | Generate Homelab certificates and apply TLS secrets across Kubernetes cluster namespaces. |
| [`k8s_lint`](#k8s-lint) | `true` | Validate K8s manifests and Helm charts using Red Hat Kube-linter. |
| [`k8s_logs`](#k8s-logs) | `true` | Stream pod logs or execute LogQL queries across cluster log streams. |
| [`k8s_pods`](#k8s-pods) | `true` | List running pods with health status, restart counts, and age. |
| [`k8s_security_stream`](#k8s-security-stream) | `true` | Stream runtime security anomaly events from Kubernetes Falco eBPF probes. |
| [`k8s_status`](#k8s-status) | `true` | Show node and pod summary for the current context. |
| [`k8s_teardown_stack`](#k8s-teardown-stack) | `false` | Uninstall the k8s infrastructure / LLM stack and delete namespaces. |
| [`k8s_tempo_info`](#k8s-tempo-info) | `true` | Retrieve Tempo distributed tracing HTTP API URL and OTLP trace endpoints. |
| [`k8s_validate`](#k8s-validate) | `true` | Validate Kubernetes YAML manifests against OpenAPI schemas using Kubeconform. |
| [`pr_check_readiness`](#pr-check-readiness) | `true` | Validate PR merge readiness: conflicts, draft state, checks, review threads and grounding.  Grounding applies where the base holds openspec/changes/. The PR targets the default branch. It closes exactly one issue, an open issue of its own repository that holds a priority/* label: a roadmap item. GitHub closes that issue when the PR merges. The PR adds openspec/changes/archive/\<date\>-\<issue\>-\<slug\>/, which uv run devops openspec archive writes for that issue's change. Only that archive writes openspec/specs/ and openspec/changes/archive/. |
| [`pr_checks`](#pr-checks) | `true` | Check remote CI quality gate status on a pull request. |
| [`pr_close`](#pr-close) | `false` | Close a pull request. |
| [`pr_diff`](#pr-diff) | `true` | View diff of a pull request. |
| [`pr_edit`](#pr-edit) | `false` | Edit pull request base branch, title, body, or milestone. |
| [`pr_list`](#pr-list) | `true` | List pull requests with base targeting and review status. |
| [`pr_monitor`](#pr-monitor) | `true` | Wait until the checks of a PR settle, then name every blocker of its merge.  While a check runs or a Copilot review is active, it waits. Then it reports the blockers of the merge-readiness verdict and of its review gate (requested changes, Copilot's review, an approval of the head with --require-reviews). Exit 0: ready; 1: a check failed or could not be read; 2: another blocker; 3: the timeout passed first. |
| [`pr_ready`](#pr-ready) | `false` | Mark a draft pull request as ready for review once its checks pass.  It exits 1 when a check failed or could not be read and 8 while one runs. Every other blocker of the merge-readiness verdict prints as a warning. --force skips the checks. It sets the Status of the roadmap item the pull request closes to In Review. |
| [`pr_threads_list`](#pr-threads-list) | `true` | List PR review discussion threads, file locations, and comments. |
| [`pr_threads_reply`](#pr-threads-reply) | `false` | Post an in-thread reply to a PR review discussion thread. |
| [`pr_threads_resolve`](#pr-threads-resolve) | `false` | Programmatically mark one or more PR review discussion threads as resolved. |
| [`pr_update`](#pr-update) | `false` | Update pull request branch with latest commits from its base branch. |
| [`prometheus_query`](#prometheus-query) | `true` | Execute an instant PromQL query. |
| [`repos_list`](#repos-list) | `true` | List all cloned repositories. |
| [`repos_sync`](#repos-sync) | `false` | Fetch (and optionally pull) all tracking branches across repos. |
| [`review_branch`](#review-branch) | `true` | Review a git branch diff. |
| [`review_export_feedback`](#review-export-feedback) | `true` | Append review verdicts to the JSONL feedback dataset, which `devops ai prompt-eval` reads.  Each session's findings.json and candidates.json are read, and only the findings whose verdict the dataset does not hold yet are appended. An export that finds none leaves the dataset as it was. Without --status only INVALIDATED verdicts are exported. The dataset changes no prompt and no later review.  A subject reviewed more than once is exported once: its sessions share their findings by fingerprint v2. Each finding has the newest verdict a person gave it in any of those sessions, or else the verdict of the session that review history counts. --status selects by that verdict. A session that records no subject, and a finding with no fingerprint v2, are exported on their own. |
| [`review_findings`](#review-findings) | `true` | Inspect structured findings for a review session.  Each finding keeps its number, its place in findings.json, whatever filter the list applies, and `devops review verify --index` takes that number. With `--candidates` the list is candidates.json: every finding the review raised, the ones verification invalidated included, numbered for `devops review verify --candidate`. |
| [`review_path`](#review-path) | `true` | Review source files directly (no git required). |
| [`review_pr`](#review-pr) | `false` | Review a GitHub pull request. |
| [`review_stats`](#review-stats) | `true` | Compute and display review accuracy statistics across saved sessions. |
| [`roadmap_intake`](#roadmap-intake) | `false` | Turn candidates into items: every open issue with no priority/* label. The model compares each with the items and the issues closed as not planned, but not with an issue that has sub-issues, because its sub-issues deliver it. It names a possible duplicate for a person to close: intake never closes an issue and never drops a candidate. Each gets a type label and a scope label from the Conventional Commit title, a status/new label, Value and Effort labels and a reason comment, then its priority label last, and goes to the backlog. The model picks the type only for a title with no Conventional Commit type. A label a person set stays. Intake sets no milestone: a person plans the milestones, and a milestone an issue has stays. Close an issue as not planned to keep it off the roadmap: devops gh issues close \<number\> --reason not-planned. A candidate an agent files with --title and --body-file is labeled source/agent, and intake files it, a possible duplicate too, unless a run that stopped after filing left an open issue with its title and body, which intake then places; a text that looks like it holds a secret is refused. --dry-run makes no request and prints the requests a run makes; --plan, the default, reads GitHub and calls the model, writes nothing and reports what it spent; --confirm makes the writes. |
| [`roadmap_refine`](#roadmap-refine) | `true` | Refine roadmap items to Ready with proposed design, tasks, and acceptance criteria, using code and documentation. When a fact or a decision has no verified source, or a key question of the body has no answer, refine investigates it with tools that read the code and, for a public repository with a Firecrawl key, search the web. A design question gets the best-practice option with the options it compared, and only a decision that a person must make waits on a person. The plan says when web search is off. Without --item, refine takes items nearest place first: each open milestone's New items, by due date and then by number, then the backlog's P0 and P1 items, then the backlog's other New items, each place by priority. Only --limit stops a run. The number of Ready items does not stop it. In each open milestone and among the backlog's P0 and P1 items it also takes Ready items it has no record of, and sets one back to New when it finds it not ready. An item that an account other than the owner, a member or a collaborator opened waits on a person, and only --item refines it. An item on which refine wrote 2 comments in the last 24 hours also waits on a person and takes no place under --limit, and only --item refines it until the older comment is 24 hours old. An item refine cannot set to Ready gets one comment with its next step. The step is the questions a person answers, the split a person makes, or the open items it waits on. Refine looks at the item again after a reply, a body edit or the close of those items, or after a commit on the default branch changes a file that the block cites. The report groups every item by its next step. A part of an item that cannot be built or decided now moves to new issues through intake when the rest of the item is Ready. Each new issue starts with 'Split from #\<issue\>.', and refine names the new issues in its Ready comment and records them as refine.deferred. An item that is too big for one pull request still waits for a person to split it. An item whose model call fails is skipped and reported; the others are still refined, and refine then exits 1. |
| [`roadmap_run`](#roadmap-run) | `true` | Run the roadmap jobs that are due, in order: metrics, then intake, refine and the alternatives check, and record each one's last success. Intake is due on an issue reopened, and decides at most 5 candidates a run and keeps a record of those it left beside the schedule; refine is due every 31 minutes, on a first run, and after an intake that placed a critical fix or a P0 item; the alternatives check is due every 719 minutes and on a first run, and checks at most roadmap.alternatives.limit items. Without --confirm, or with --dry-run, prints the due list and runs nothing. |
| [`sandbox_deploy`](#sandbox-deploy) | `false` | Deploy an isolated background container sandbox with security containment. |
| [`sandbox_exec`](#sandbox-exec) | `false` | Execute a command inside an active sandbox container. |
| [`sandbox_network_policy`](#sandbox-network-policy) | `true` | Generate declarative Kubernetes NetworkPolicy YAML for workload sandbox isolation. |
| [`sandbox_status`](#sandbox-status) | `true` | Inspect status of deployed sandbox containers. |
| [`sandbox_stop`](#sandbox-stop) | `false` | Gracefully stop and tear down a sandbox container. |
| [`scan_aibom`](#scan-aibom) | `true` | Generate AI Bill of Materials (AIBOM) with model licenses and hardware estimates. |
| [`scan_complexity`](#scan-complexity) | `true` | Run AST-based cyclomatic complexity analysis. |
| [`scan_fix`](#scan-fix) | `false` | Remediate vulnerable dependencies via lockfile upgrades and optional git branch creation. |
| [`scan_injection`](#scan-injection) | `true` | Scan target files for prompt-injection smuggling vectors and canary tokens. |
| [`scan_sast`](#scan-sast) | `true` | Run static application security testing (SAST) via Semgrep. |
| [`scan_sbom`](#scan-sbom) | `true` | Generate Software Bill of Materials (SBOM) using Trivy (#1439). |
| [`scan_secrets`](#scan-secrets) | `true` | Run Gitleaks secret pre-filter scan across workspace or targets. |
| [`scan_trivy`](#scan-trivy) | `true` | Run Aqua Trivy vulnerability, secret, and misconfiguration scan. |
| [`scan_uv_audit`](#scan-uv-audit) | `true` | Audit the packages that the uv.lock of a project pins, as it is, for known vulnerabilities and adverse project statuses, with uv audit. |
| [`security_intel_network`](#security-intel-network) | `true` | Check IP or domain threat intelligence via Shodan and Cloudflare Radar. |
| [`security_intel_package`](#security-intel-package) | `true` | Query the OSV.dev vulnerability database for package CVE intelligence. |
| [`ssh_audit`](#ssh-audit) | `true` | List the managed SSH keys of the project prefix with their age and rotation status. |
| [`ssh_status`](#ssh-status) | `true` | Show the active SSH key and days until rotation. |
| [`telemetry_logfire`](#telemetry-logfire) | `true` | Display Logfire structured observability bridge status and token metrics. |
| [`telemetry_profile`](#telemetry-profile) | `true` | Run a devops-cli command, or name a trace, and show its span waterfall as Tempo recorded it. |
| [`telemetry_status`](#telemetry-status) | `true` | Check OpenTelemetry collector health, Tempo endpoint, and trace propagation status. |
| [`telemetry_test`](#telemetry-test) | `false` | Emit a test OpenTelemetry trace span and metric to the configured collector. |
| [`tf_apply`](#tf-apply) | `false` | Create or update OpenTofu infrastructure. |
| [`tf_cost_breakdown`](#tf-cost-breakdown) | `true` | Estimate monthly and hourly cloud infrastructure costs using Infracost. |
| [`tf_notify_plan`](#tf-notify-plan) | `true` | Format and post structured, collapsible OpenTofu/Terraform plan diffs to PR comments. |
| [`tf_output`](#tf-output) | `true` | Read an output variable from the OpenTofu state. |
| [`tf_plan`](#tf-plan) | `true` | Generate and show an OpenTofu execution plan. |
| [`tls_ca`](#tls-ca) | `false` | Generate a self-signed Root Certificate Authority (CA) key pair. |
| [`tls_cert`](#tls-cert) | `false` | Generate an X.509 TLS certificate signed by local CA or self-signed. |
| [`tls_inspect`](#tls-inspect) | `true` | Inspect and display metadata of an X.509 certificate. |
| [`valkey_flush`](#valkey-flush) | `false` | Flush and purge keys from current or all databases. |
| [`valkey_get`](#valkey-get) | `true` | Retrieve string value stored at key. |
| [`valkey_info`](#valkey-info) | `true` | Inspect server configuration, memory allocation, and operational metrics. |
| [`valkey_ping`](#valkey-ping) | `true` | Test connection and measure round-trip latency to the Valkey server. |
| [`valkey_set`](#valkey-set) | `false` | Set string value of key with optional expiration TTL. |
| [`valkey_stats`](#valkey-stats) | `true` | Display quick diagnostic summary of server health, memory, and keys. |
| [`vault_get`](#vault-get) | `true` | Fetch a secret from Vault, or from the OS keyring when Vault cannot answer.  The keyring answers only with no usable token, when Vault has no value at the path, or when Vault is unreachable; never after Vault rejects the token. The output names the source. |
| [`vault_set`](#vault-set) | `false` | Store secret key-value pairs in HashiCorp Vault KV-v2 engine. |
| [`vault_status`](#vault-status) | `true` | Inspect HashiCorp Vault cluster health and initialization status.  The health endpoint needs no token, and none is sent. The Token row names where the token other commands would use comes from, and why a stored token is not used for this address. |
| [`vault_sync`](#vault-sync) | `false` | Synchronize secrets from Vault into OS Keyring for offline/local CLI operations.  Reads Vault alone. A path with no secret fails, and a field named like the entry that holds the `devops vault login` token is never written. |

---

### `ai_ast_graph`

Synthesize whole-repository symbol dependency and reference graph.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_dir` | `string` | No | - | Target source directory to verify or analyze. |
| `max_files` | `integer` | No | `100` | Maximum source files to include. |
| `output_path` | `string` | No | - | Destination file path for output report or artifacts. |
| `fmt` | `string` | No | `json` | Output format for synthesized code graph: 'json' or 'dot'. |

### `ai_ast_parse`

Parse source file concrete syntax tree and extract structural symbols.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `file_path` | `string` | Yes | - | Parse source file concrete syntax tree and extract structural symbols. |
| `query` | `string` | No | `` | Optional Tree-Sitter S-expression query to execute against the syntax tree. |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `ai_benchmark`

Benchmark, evaluate, and peer-grade candidate AI models across engineering tasks.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `models` | `string` | No | - | Comma-separated candidate models (e.g. 'qwen2.5:0.5b,llama3.1:8b@http://gpu2:11434'). A model@url runs on that server, which gets the AI key only when it is the configured api_base_url, gateway_url or provider API. The output and the reports name it model@host[:port]. The MCP tool refuses a model@url. |
| `provider` | `string` | No | - | AI or cloud provider. |
| `benchmark_type` | `string` | No | `auto` | Benchmark mode: 'auto', 'chat', 'embedding'. |
| `tasks_filter` | `string` | No | - | Filter specific task categories or IDs (e.g. 'security,kubernetes'). |
| `concurrency` | `integer` | No | `4` | Number of concurrent model server workers (default: automatic per model count). |
| `format_type` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |
| `explain` | `boolean` | No | `False` | Explain benchmark metrics, terminology, and mathematical formulas. |
| `samples` | `integer` | No | `5` | Number of document sections or code chunks to run retrieval queries for. |

### `ai_chaos_model`

Model dependency chaos engineering suite simulating provider faults and validating local failovers.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `mode` | `string` | No | `all` | Chaos fault mode to simulate (latency, rate-limit, timeout, malformed-json, all). |
| `latency_ms` | `integer` | No | `500` | Synthetic network latency to inject in milliseconds. |
| `error_rate` | `number` | No | `1.0` | Probability of fault injection between 0.0 and 1.0. |
| `primary_provider` | `string` | No | `openai` | AI or cloud provider. |
| `primary_model` | `string` | No | `gpt-4o` | AI model identifier. |
| `fallback_provider` | `string` | No | `ollama` | Fallback AI provider to route execution to upon fault. |
| `fallback_model` | `string` | No | `qwen3-coder:30b` | Fallback AI model to route execution to upon fault. |
| `prompt` | `string` | No | `def test_health(): return True` | Prompt text or workload payload to evaluate. |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `ai_constellation`

Show the constellation flag: state, reason and recorded fallback route.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `ai_cost_report`

Generate detailed spend and token report across backend services and servers.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `by` | `string` | No | `server` | Breakdown grouping dimension: server, model, provider, backend, stage, all. |
| `days` | `integer` | No | - | Filter usage to the last N days (default: all lifetime). |
| `reference_model` | `string` | No | - | Reference model for counterfactual pricing (default: the ai.reference_model setting). |
| `hardware_cost` | `number` | No | - | Hardware purchase cost in USD to track pay-off against. |
| `format_opt` | `string` | No | `table` | Output format: table, json, yaml, prometheus. |
| `json_flag` | `boolean` | No | `False` | First-class alias for --format json. |

### `ai_diagram`

Generate visual Mermaid architecture topology or STRIDE threat modeling diagrams.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `diagram_type` | `string` | No | `arch` | Diagram type: 'arch' for architecture topology, 'threat' for STRIDE model. |
| `target_dir` | `string` | No | - | Target source directory to verify or analyze. |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `ai_failover`

Record a fallback route in the constellation flag; `devops ai gateway failover` records a failover route for a virtual model, and the gateway's own fallbacks move the traffic.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_provider` | `string` | No | `ollama` | Fallback AI provider to route execution to upon fault. |
| `target_model` | `string` | No | `qwen3-coder:30b` | Fallback AI model to route execution to upon fault. |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `ai_gateway_failover`

Trigger or test circuit-breaker failover of a virtual model to secondary backends, or restore the default routes with --reset.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `virtual_model` | `string` | No | - | Virtual model alias to trigger failover for (devops-chat, devops-coder, devops-reasoning, devops-embedding). Give none with --reset. |
| `simulate` | `boolean` | No | `True` | Simulate failover without altering active routing table. |
| `force` | `boolean` | No | `False` | Bypass model capability tier minimum checks during failover. |
| `reset` | `boolean` | No | `False` | Restore the default route of every virtual model and clear the circuit breaker. --simulate and --force apply only to a failover. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `ai_gateway_probe_backend`

Directly probe health and latency of an inference backend.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `backend` | `string` | Yes | - | Backend to probe (e.g. ollama). |

### `ai_gateway_routes`

List registered virtual models and target backend inference instances.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `provider` | `string` | No | - | Gateway provider: litellm or portkey. |

### `ai_gateway_status`

Probe LLM Gateway health, latency, and circuit breaker metrics.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `provider` | `string` | No | - | Gateway provider: litellm or portkey. |

### `ai_harness_offload`

Offload AST exploration, symbol cataloging, or file scouting to local sub-agent slot.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | `.` | Path to repository or source directory. |
| `symbol` | `string` | No | - | Symbol name (class or function) to inspect or search. |
| `pattern` | `string` | No | - | File glob pattern to scout. |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |

### `ai_harness_status`

Display the harness slots as configured; nothing here checks a model is reachable.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |

### `ai_ingest_library`

Introspect an installed Python package and extract its public API contract.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `package_name` | `string` | Yes | - | Introspect an installed Python package and extract its public API contract. |
| `max_depth` | `integer` | No | `1` | Maximum module recursion depth for package introspection. |
| `output_dir` | `string` | No | - | Directory path for generated output files. |

### `ai_ingest_query_library`

Search library contracts and documentation via semantic search or exact symbol lookup.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `string` | Yes | - | Search library contracts and documentation via semantic search or exact symbol lookup. |
| `package` | `string` | No | - | Filter by package distribution name. |
| `exact` | `boolean` | No | `False` | Perform exact qualified symbol lookup instead of semantic vector search. |
| `top_k` | `integer` | No | `5` | Maximum number of items to return or display. |
| `contracts_dir` | `string` | No | - | Path to directory containing exported library contract JSON files (default: libraries/ under the data directory where review data is kept). |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `ai_pack_context`

Pack and prune source code context to fit token budget while preserving signatures.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_path` | `string` | Yes | - | Path to source code file to pack and prune. |
| `referenced` | `string` | No | - | Comma-separated list of symbols referenced by caller to prioritize during pruning. |
| `max_tokens` | `integer` | No | `1500` | Maximum token budget for packed context output. |
| `strip_private` | `boolean` | No | `True` | Strip unreferenced private functions, methods, and attributes. |
| `skeletonize` | `boolean` | No | `True` | Replace function and method bodies with ellipsis (...) while preserving signatures. |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `ai_prewarm`

Prewarm local models into GPU VRAM or evict idle models across cluster nodes.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `model` | `string` | No | - | Model name to prewarm or evict (defaults to configured AI model). |
| `keep_alive` | `string` | No | `1h` | Keep-alive duration for loaded model (e.g. 1h, 24h, forever, or 0 for eviction). |
| `all_nodes` | `boolean` | No | `True` | Prewarm or evict model across all configured Ollama cluster nodes. |
| `evict` | `boolean` | No | `False` | Evict the model from GPU VRAM immediately (sets keep_alive to 0). |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `json_output` | `boolean` | No | `False` | Output results as structured JSON. |

### `ai_quiesce`

Set the constellation quiesce flag with a reason; it stops nothing.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `reason` | `string` | No | `Operator requested emergency quiesce` | Reason recorded with the constellation quiesce flag. |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `ai_rag_drift`

Detect staleness and drift between the working tree and the Qdrant vector index.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | `string` | No | `.` | Directory or file to index into vector store. |
| `auto_sync` | `boolean` | No | `False` | Automatically re-index stale and newly added files. |
| `fail_on_drift` | `boolean` | No | `False` | Exit with code 1 if index drift or git commit divergence is detected. |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `ai_rag_index`

Scan and index workspace code and documentation into Qdrant vector database.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | `string` | No | `.` | Directory or file to index into vector store. |
| `project` | `string` | No | - | Project / repository name override. |
| `force` | `boolean` | No | `False` | Force execution ignoring non-blocking warnings. |
| `include_kb` | `boolean` | No | `True` | Include bundled DevOps CLI Knowledge Base in docs collection. |
| `collection` | `string` | No | - | Target collection override. |
| `explain` | `boolean` | No | `False` | Explain RAG vector embeddings, Qdrant indexing, and terminology. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `ai_rag_query`

Perform semantic search across indexed workspace code and documentation.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `string` | Yes | - | Natural language query or code search term. |
| `project` | `string` | No | - | Project / repository name override. |
| `language` | `string` | No | - | Filter or target specific programming language. |
| `category` | `string` | No | - | Filter by category (code, docs, topics, tasks). |
| `top_k` | `integer` | No | - | Number of results to return. The default is the `ai.rag.top_k` setting. |
| `min_score` | `number` | No | - | Minimum similarity score (0.0 - 1.0). The default is the `ai.rag.score_threshold` setting. |
| `collection` | `string` | No | - | Target collection override. |
| `file_filter` | `string` | No | - | Filter by filepath glob pattern. |
| `explain` | `boolean` | No | `False` | Explain RAG vector embeddings, Qdrant indexing, and terminology. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `ai_read`

Inspect and read source code across 3 multi-scale focal zoom levels (Topology, Structural Outline, Deep Focal Window).

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_path` | `string` | Yes | - | Target file path to read or inspect. |
| `inspect` | `boolean` | No | `False` | Enable multi-scale semantic outline and inspection scanner. |
| `level` | `integer` | No | - | Focal zoom level: 0 (Topology: classes, functions, exports & hotspots), 1 (Structural Outline: control flow & signatures), 2 (Deep Focal Window: line slice). |
| `lines` | `string` | No | - | Line range for Level 2 focal window (e.g. '40:80'). |
| `symbol` | `string` | No | - | Target symbol name to inspect or focus on. |
| `format` | `string` | No | `markdown` | Output format: 'text', 'markdown', or 'json'. |
| `repo` | `string` | No | - | Repository or workspace root directory. |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `ai_repomap`

Generate compact whole-repository AST symbol and relationship map.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_dir` | `string` | No | - | Target source directory to verify or analyze. |
| `max_files` | `integer` | No | `100` | Maximum source files to include. |
| `include_tests` | `boolean` | No | `False` | Include test modules in symbol map. |
| `multilingual` | `boolean` | No | `False` | Enable multilingual polyglot scanning across Python, TypeScript, JavaScript, Go, Rust, Java, C#, C, C++, HCL, shell and Markdown. |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `ai_resume`

Clear the constellation quiesce or failover flag.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `ai_test_gen`

Generate failing pytest unit test scaffolds for functions or source files.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target_file` | `string` | Yes | - | Target source file to generate unit test scaffolds for. |
| `function_name` | `string` | No | - | Specific function to generate a test scaffold for. |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `argo_cd_apps_list`

List all ArgoCD applications.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `watch` | `boolean` | No | `False` | Watch application status changes live. |
| `interval` | `number` | No | `3.0` | Auto-refresh polling interval in seconds. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `argo_cd_apps_status`

Show the sync and health of an Argo CD application, and check each image it pins.

An image the application pins as `<image>:<tag>@<digest>` in its kustomize images is checked
against the digest its tag names in the registry now. Without --watch, the command exits 1
when the status cannot be read, a tag names another digest, or a registry gives no digest.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | `string` | Yes | - | Application name. |
| `watch` | `boolean` | No | `False` | Watch application status changes live. |
| `interval` | `number` | No | `3.0` | Auto-refresh polling interval in seconds. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `argo_fleet_sync`

Synchronize an application across a fleet of Kubernetes clusters with bounded concurrency.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `app_name` | `string` | Yes | - | Application name. |
| `clusters` | `string` | No | `dev,staging,prod` | Comma-separated list of target cluster names (e.g. dev,staging,prod) |
| `fleet_name` | `string` | No | `default-fleet` | Fleet identifier group name |
| `concurrency` | `integer` | No | `3` | Maximum concurrent cluster synchronization workers |
| `prune` | `boolean` | No | `False` | Allow deletion of resources omitted from the source repository. |
| `force` | `boolean` | No | `False` | Force execution ignoring non-blocking warnings. |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `argo_rollouts_analyze`

Evaluate metric rollback gates and trigger automated rollback on threshold violation.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | `string` | Yes | - | Rollout name. |
| `namespace` | `string` | No | `default` | Kubernetes namespace. |
| `error_rate_threshold` | `number` | No | `1.0` | Maximum allowable HTTP 5xx error rate percentage before triggering automated rollback |
| `auto_abort` | `boolean` | No | `True` | Automatically trigger rollout abort when metric analysis violates threshold |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `branches_list`

List branches across all repos.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `base_dir` | `string` | No | - | Base repository root directory. |
| `all_branches` | `boolean` | No | `False` | Include remote branches. |

### `ci`

Run tests, linting, formatting, and type-checks. A run that selects test, security or typecheck first waits for a free gate slot, so the gates of parallel agents take turns. ci.gate_slots sets how many run at once.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `fix` | `boolean` | No | `True` | Auto-fix lint/format before reporting status. |
| `check` | `boolean` | No | `False` | Run in check-only mode without automatically applying formatting or lint fixes. |
| `cache` | `boolean` | No | `True` | Reuse a cached verdict when the codebase is unchanged. Results are recorded either way. |
| `force` | `boolean` | No | `False` | Bypass CI execution cache and force re-execution of all quality gates. |
| `only` | `array[string]` | No | - | Run only the specified check names (comma-separated or repeated). |
| `skip` | `array[string]` | No | - | Skip the specified check names (comma-separated or repeated). |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `config_audit_keys`

Audit OS Keyring token health, backend status, and zero-plaintext secret compliance. The audit scans each config file that the settings merge: the global config file and the project config file. It also scans config.yaml and .devops/config.yaml in the current directory. Exits 0 only when the audit is compliant. Exits 1 when a config file holds a plaintext secret, or when a config file cannot be read or parsed, reporting it unaudited. The full report prints before the exit. The alert of a leak names two commands. `devops config set <key>` stores a credential in the keyring. Add `--from-file <path>` for a multi-line credential, such as a PEM key. `DEVOPS_CLI_CONFIG=<file> devops config unset <key>` removes the value from the file of the leak.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `config_output`

Output environment variables available for devops-cli configuration.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `export` | `boolean` | No | `False` | Print environment variables as shell export statements. |
| `json_output` | `boolean` | No | `False` | Print environment variables as JSON. |

### `config_show`

Print every setting that a variable sets and every credential. A credential shows as set or not set, never its value.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `docker_images`

List local Docker images.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | `string` | No | - | Filter containers or images by name. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `docker_sandbox`

Execute workload inside an isolated, disposable Docker container sandbox.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `command` | `array[string]` | Yes | - | Workload command to execute inside container sandbox |
| `image` | `string` | No | `python:3.14-slim` | Docker container image to execute within |
| `workspace` | `string` | No | `.` | Workspace directory to mount |
| `memory` | `string` | No | `2g` | Memory limit (e.g. 2g, 512m) |
| `cpus` | `number` | No | `2.0` | CPU limit |
| `network` | `string` | No | `isolated` | Network mode: isolated | sandbox_namespace | public_whitelist | local_whitelist | bridge |
| `network_mode` | `string` | No | - | Multi-tier network mode: isolated | sandbox_namespace | public_whitelist | local_whitelist | bridge |
| `public_whitelist` | `string` | No | - | Comma-separated public domains/IPs allowed for egress |
| `local_whitelist` | `string` | No | - | Comma-separated local URLs/IPs allowed for egress |
| `read_only` | `boolean` | No | `False` | Mount workspace as read-only |
| `rootless` | `boolean` | No | `True` | Run container with host user UID/GID |
| `seccomp_profile` | `string` | No | - | Seccomp profile file for the container, in the JSON format of `docker --security-opt seccomp=<file>`, in place of the engine's default profile. Its defaultAction must refuse the system calls that it does not name. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `docker_sign`

Sign a container image using Sigstore Cosign (keyless or keyed).

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `image` | `string` | Yes | - | Target container image reference (name:tag or digest) |
| `key` | `string` | No | - | Path to private key or keyring:\<name\> |
| `keyless` | `boolean` | No | `True` | Sign keylessly using OIDC/Fulcio |
| `oidc_token` | `string` | No | - | OIDC identity token or keyring:\<name\> for keyless signing |
| `annotation` | `array[string]` | No | - | Custom supply chain key=value annotations |
| `upload` | `boolean` | No | `True` | Upload signature to remote registry |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `docker_verify`

Verify container image signature or attestation using Sigstore Cosign.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `image` | `string` | Yes | - | Target container image reference to verify |
| `key` | `string` | No | - | Path to public key or keyring:\<name\> |
| `certificate_identity` | `string` | No | - | Expected signer certificate identity (SAN/email/URI) |
| `certificate_oidc_issuer` | `string` | No | - | Expected OIDC certificate issuer URL |
| `attestation` | `boolean` | No | `False` | Verify in-toto attestation predicate instead of signature |
| `predicate_type` | `string` | No | - | Attestation predicate type (e.g. slsaprovenance, spdx, custom) |
| `insecure_ignore_tlog` | `boolean` | No | `False` | Ignore Rekor transparency log verification |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_issues_close`

Close an open issue with its reason, completed or not planned. With --comment-file, the command posts the comment first, then closes the issue, so a failed close leaves the comment. It refuses a pull request and an issue that is already closed, because GitHub ignores a reason unless the state changes.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | Yes | - | Number of the issue to close. |
| `reason` | `string (completed, not-planned)` | Yes | - | Why the issue closes: completed, or not-planned for a rejected or superseded issue. |
| `comment_file` | `string` | No | - | File with the comment to post before the close, such as the evidence for a not-planned close. Give - to read it from standard input. |
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Make no request: print the requests a run makes, in order. |

### `gh_issues_create`

Create a new issue linking milestone and taxonomy labels.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `title` | `string` | Yes | - | Issue title |
| `body` | `string` | No | `` | Issue description |
| `milestone` | `string` | No | - | Target milestone |
| `label` | `array[string]` | No | - | Taxonomy label (repeatable) |
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_issues_edit`

Edit an existing issue title, body, state, milestone, or taxonomy labels.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | Yes | - | Issue number to edit. |
| `title` | `string` | No | - | New issue title. |
| `body` | `string` | No | - | New issue body text. |
| `state` | `string` | No | - | New state (open or closed). |
| `milestone` | `string` | No | - | New milestone title, or its number (e.g. 2026-11-05). |
| `clear_milestone` | `boolean` | No | `False` | Remove milestone linkage from the issue. |
| `add_label` | `array[string]` | No | - | Taxonomy label to attach (repeatable). |
| `remove_label` | `array[string]` | No | - | Taxonomy label to detach (repeatable). |
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_issues_list`

List repository issues with milestone, taxonomy labels, and status.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | Target repository |
| `state` | `string` | No | `open` | Issue state: open, closed, all |
| `milestone` | `string` | No | - | Filter by milestone |
| `label` | `string` | No | - | Filter by label |
| `limit` | `integer` | No | `30` | Max issues to return |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_issues_status`

Display aggregated issue counts by priority, type, and milestone.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_issues_triage`

Audit open issues for mandatory taxonomy labels, and report those with no priority/* label as awaiting intake.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_issues_view`

Print one issue with its state, milestone, labels, assignees, dates and full body.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | Yes | - | Issue number. |
| `repo` | `string` | No | - | Target repository |

### `gh_labels_list`

List all labels defined in the remote repository.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_labels_sync`

Synchronize repository labels against the declarative YAML schema.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `file` | `string` | No | `.github/labels.yml` | Path to declarative labels.yml file |
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Preview label reconciliation without making changes |

### `gh_milestones_close`

Close the milestone with this title or number.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | `string` | Yes | - | The milestone's exact title, or its number when no milestone has that title. |
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_milestones_edit`

Edit a milestone's title, description, state, or due date; fields left out stay as they are.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | `string` | Yes | - | The milestone's exact title, or its number when no milestone has that title. |
| `title` | `string` | No | - | New milestone title |
| `description` | `string` | No | - | New milestone description |
| `state` | `string` | No | - | New state (open or closed) |
| `due_on` | `string` | No | - | ISO due date (YYYY-MM-DD) |
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_milestones_list`

List every milestone, by due date and then by number, with its issue completion rate.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `state` | `string` | No | `all` | Milestone state filter (open, closed or all) |
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_pages_build`

Trigger a new deployment build for GitHub Pages.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_pages_status`

Inspect GitHub Pages deployment status, URL, branch, and HTTPS enforcement.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_pages_verify`

Verify local repository readiness for GitHub Pages publishing.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `root_dir` | `string` | No | `.` | Path to project root directory |

### `gh_project_audit`

Audit the project board's views against the template.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `template_file` | `string` | No | - | Path to the project template JSON; defaults to .github/project-template.json at the repository root. |
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_project_list`

List available GitHub Projects v2 boards for user or organization.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `owner` | `string` | No | - | Target user or organization |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_project_reconcile`

Reconcile Status and Priority on the cards already on the board, listing each change and its source; the board owns Status, and reconcile never writes Milestone, Value or Effort or adds a card. A planned value the board's field has no option for is refused before any write. A run that stops early (mutation budget, GraphQL quota or a failed write) says why and how many planned changes remain, and exits 1. Running it again continues from there: after the reset when the quota stopped it, and once the cause is fixed when a write failed.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `project_number` | `integer` | No | - | GitHub Projects v2 board number |
| `state` | `string` | No | `all` | Filter issue/PR states (open, closed, all) |
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Make no request, reads included, and list the requests a run makes. |
| `plan_only` | `boolean` | No | `False` | Read the board and the repository and list the changes a run makes, making none. |

### `gh_project_status`

Inspect the declarative GitHub Projects v2 template structure and views.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `template_file` | `string` | No | - | Path to the project template JSON; defaults to .github/project-template.json at the repository root. |

### `gh_project_sync`

Find or create the project board from its template, link it, create the fields it lacks, and reconcile Status and Priority on the cards already on it. Sync adds no issue or pull request to the board, and a pull request's progress shows on its issue's card. No roadmap job reads the board: labels hold an item's fields. Exits 1 when reconcile stops early.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `template_file` | `string` | No | - | Path to the project template JSON; defaults to .github/project-template.json at the repository root. |
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Make no request and describe what a sync does. |
| `reconcile_fields` | `boolean` | No | `True` | Also reconcile Status and Priority on the cards already on the board, from issue and pull request state and labels. |

### `gh_rate_limit`

Display GitHub REST and GraphQL API rate limits, quotas, and reset countdowns.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_runs_list`

List recent workflow runs for the repository or branch.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `limit` | `integer` | No | `10` | Maximum number of items to return or display. |
| `branch` | `string` | No | - | Filter by branch |
| `repo` | `string` | No | - | Target repository |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_runs_view`

View details and failure logs of a specific workflow run.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `run_id` | `integer` | Yes | - | Workflow run database ID. |
| `log_failed` | `boolean` | No | `False` | Display logs for failed jobs or steps in the workflow run. |
| `full_log` | `boolean` | No | `False` | Display full execution logs for the workflow run. |
| `job` | `string` | No | - | Filter workflow run logs to a specific job ID. |
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_views_audit`

Audit remote project views against standardized template specifications.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `template_file` | `string` | No | - | Path to the project template JSON; defaults to .github/project-template.json at the repository root. |
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `gh_views_spec`

Output JSON schema specification for all configured project views.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `template_file` | `string` | No | - | Path to the project template JSON; defaults to .github/project-template.json at the repository root. |

### `gh_views_sync`

Synchronize standardized views with the remote GitHub Projects v2 board.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `template_file` | `string` | No | - | Path to the project template JSON; defaults to .github/project-template.json at the repository root. |
| `repo` | `string` | No | - | Target repository |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `grafana_dashboards_list`

List all dashboards.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `hydrate_tool_domain`

Advertise the tools for one domain, which are withheld from the listing by default.

Call this before browsing a domain's tools. Available lazy domains include `argo`,
`benchmark`, `branches`, `ci`, `docker`, `docs`, `gh`, `grafana`, `k8s`, `pr`,
`prometheus`, `rag`, `repos`, `roadmap`, `sandbox`, `scan`, `security`, `ssh`, `telemetry`,
`tf`, `tls`, `valkey`, `vault` and `verify`.
Pass the domain name alone, for example `k8s`.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `domain` | `string` | Yes | - | - |

### `k8s_audit`

Sanitize active K8s/Minikube cluster resource health using Derailed Popeye.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `k8s_bootstrap`

Bootstrap homelab Kubernetes cluster with Minikube, Calico, and ingress.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `k8s_dir` | `string` | No | `k8s` | Directory containing Kubernetes manifests. |
| `auto_start` | `boolean` | No | `True` | Auto-start minikube if stopped. |
| `stack` | `string` | No | `all` | Stack to operate on: infra | llm | logging | devops | gitea | chat | all. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `k8s_chaos`

Run resilience and chaos experiments against Kubernetes workloads.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `experiment` | `string` | No | `pod-kill` | Resilience experiment name (e.g., pod-kill, latency-inject). |
| `deployment` | `string` | No | `sample-app` | Target deployment to disrupt. |
| `namespace` | `string` | No | `default` | Kubernetes namespace. |
| `duration` | `integer` | No | `30` | Reconciliation monitoring window in seconds. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `k8s_create_tls_secret`

Create or update a kubernetes.io/tls secret from certificate and private key files.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `secret_name` | `string` | Yes | - | Name of the Kubernetes TLS secret to create or update. |
| `namespace` | `string` | No | `default` | Kubernetes namespace. |
| `cert_path` | `string` | No | `` | Path to TLS certificate file (.crt or .pem). |
| `key_path` | `string` | No | `` | Path to TLS private key file (.key or .pem). |
| `context` | `string` | No | - | Kubernetes cluster context name. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `k8s_deploy_stack`

Deploy one stack (infra, llm, logging, devops, gitea, chat) or all of them to Kubernetes with Helm and Kustomize.

Right after the namespaces, it pushes the Secrets of the base rows, its stacks and every detached stack whose namespace exists (`devops k8s push-secrets`), before anything that reads them. A locked or missing keyring stops it before it applies anything.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `k8s_dir` | `string` | No | `k8s` | Path to k8s/ config directory. |
| `stack` | `string` | No | `infra` | Stack to operate on: infra | llm | logging | devops | gitea | chat | all. |
| `context` | `string` | No | - | Kubernetes cluster context name. |
| `domain` | `string` | No | - | Domain to substitute for template (defaults to k8s.domain in config.yaml). |
| `wait` | `boolean` | No | `True` | Wait for Helm releases and workloads to become ready before returning. |
| `timeout` | `string` | No | `10m` | Timeout for Helm operations when waiting. |
| `port_forward` | `boolean` | No | `False` | Start background port-forwarding daemons for deployed services. |
| `configure_urls` | `boolean` | No | `False` | Auto-configure devops-cli settings with detected Kubernetes service URLs. |
| `push_secrets` | `boolean` | No | `True` | Push the stacks' Secrets from the OS keyring before applying anything (--no-push-secrets for a cluster without a keyring). |
| `argocd_revision` | `string` | No | - | Derive the Argo CD host overrides from this Git revision instead of each Application's targetRevision, to stage them before a pull request merges into main (Argo CD-managed clusters only). |
| `dry_run` | `boolean` | No | `False` | Print the releases, manifests and Secrets (key names only) a deploy would apply, and run nothing. |

### `k8s_diff_helm`

Preview Kubernetes manifest diffs before executing a Helm upgrade.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `release_name` | `string` | Yes | - | Name of deployed Helm release. |
| `chart_path` | `string` | No | `.` | Path to local Helm chart directory or packaged archive. |
| `namespace` | `string` | No | - | Kubernetes namespace. |
| `values` | `array[string]` | No | - | Values YAML files to override release defaults. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `k8s_doctor`

Diagnose Kubernetes cluster deployment health, correlate failures, and recommend remediations.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `namespace` | `string` | No | - | Target specific Kubernetes namespace (default: all namespaces). |
| `context` | `string` | No | - | Target Kubernetes cluster context (default: resolved context). |
| `tail` | `integer` | No | `20` | Number of container log lines to tail per flagged container. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |
| `stack` | `string` | No | - | Check one stack end to end in place of the cluster rules: gitea. The gitea checks read Applications gitea and gitea-manifests, the volume of claim gitea-shared-storage, the Pod Security of namespace gitea and the host of Ingress gitea-ingress. Through that host, they check the sign-in page, the refusal of an anonymous API read, the token challenge of the registry, and the clone URL of a temporary private repository, which they make as gitea_admin with keyring gitea_admin_password and then delete. Last, they check that the pod reaches no address outside the cluster. Exits 2 when a check fails. |

### `k8s_enable_tls`

Generate Homelab certificates and apply TLS secrets across Kubernetes cluster namespaces.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `context` | `string` | No | - | Kubernetes cluster context name. |
| `tls_dir` | `string` | No | `` | Directory with generated TLS certificates. |
| `secret_name` | `string` | No | `homelab-tls` | Name of the Kubernetes TLS secret to create or update. |
| `stack` | `string` | No | `all` | Stack to operate on: infra | llm | logging | devops | gitea | chat | all. |
| `overwrite` | `boolean` | No | `False` | Overwrite existing files or resources if they exist. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `k8s_lint`

Validate K8s manifests and Helm charts using Red Hat Kube-linter.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | Target K8s manifest file or directory to lint. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `k8s_logs`

Stream pod logs or execute LogQL queries across cluster log streams.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `pod` | `string` | No | `` | Pod name. |
| `query_arg` | `string` | No | - | Optional LogQL query string when using query subcommand |
| `query` | `string` | No | - | LogQL query expression |
| `container` | `string` | No | - | Specific container name within the pod. |
| `namespace` | `string` | No | - | Kubernetes namespace. |
| `follow` | `boolean` | No | `False` | Follow stream or log output in real time. |
| `tail` | `integer` | No | `100` | Number of recent lines to display. |
| `limit` | `integer` | No | `100` | Max lines for LogQL query |
| `since` | `string` | No | `1h` | Time range for LogQL query |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `k8s_pods`

List running pods with health status, restart counts, and age.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `namespace` | `string` | No | - | Kubernetes namespace. |
| `label` | `string` | No | - | Kubernetes label selector filter (e.g. app=frontend). |
| `all_namespaces` | `boolean` | No | `False` | Query pods across all namespaces. |
| `watch` | `boolean` | No | `False` | Continuously refresh pod list in real-time terminal display. |
| `interval` | `number` | No | `3.0` | Auto-refresh polling interval in seconds. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `k8s_security_stream`

Stream runtime security anomaly events from Kubernetes Falco eBPF probes.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `namespace` | `string` | No | `falco` | Kubernetes namespace. |
| `label` | `string` | No | `app.kubernetes.io/name=falco` | Kubernetes label selector filter (e.g. app=frontend). |
| `severity` | `string` | No | - | Minimum severity filter threshold (Notice, Warning, Error, Critical). |
| `duration` | `integer` | No | `30` | Observation streaming window duration in seconds. |
| `tail` | `integer` | No | `100` | Number of historical log lines to stream. |
| `follow` | `boolean` | No | `False` | Continuously stream live log output. |
| `simulate` | `boolean` | No | `False` | Generate simulated kernel eBPF security anomalies for testing. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |
| `output` | `string` | No | - | Export discovered alerts to JSON file |

### `k8s_status`

Show node and pod summary for the current context.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `k8s_teardown_stack`

Uninstall the k8s infrastructure / LLM stack and delete namespaces.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `k8s_dir` | `string` | No | `k8s` | Path to k8s/ config directory. |
| `stack` | `string` | No | `infra` | Stack to operate on: infra | llm | logging | devops | gitea | chat | all. |
| `context` | `string` | No | - | Kubernetes cluster context name. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `k8s_tempo_info`

Retrieve Tempo distributed tracing HTTP API URL and OTLP trace endpoints.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `k8s_validate`

Validate Kubernetes YAML manifests against OpenAPI schemas using Kubeconform.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `manifest_path` | `string` | No | `.` | Manifest file or directory path. |
| `k8s_version` | `string` | No | `master` | Target Kubernetes OpenAPI version. |
| `strict` | `boolean` | No | `True` | Disallow additional undeclared properties. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `pr_check_readiness`

Validate PR merge readiness: conflicts, draft state, checks, review threads and grounding.

Grounding applies where the base holds openspec/changes/. The PR targets the default branch.
It closes exactly one issue, an open issue of its own repository that holds a priority/*
label: a roadmap item. GitHub closes that issue when the PR merges. The PR
adds openspec/changes/archive/\<date\>-\<issue\>-\<slug\>/, which uv run devops openspec archive
writes for that issue's change. Only that archive writes openspec/specs/ and
openspec/changes/archive/.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | No | - | PR number to verify (defaults to current branch PR) |
| `allow_draft` | `boolean` | No | `False` | Report a draft pull request as ready; GitHub still refuses to merge one. |
| `allow_pending_checks` | `boolean` | No | `False` | Treat checks that are still running as acceptable rather than blocking. |
| `allow_blocked_state` | `boolean` | No | `False` | Allow mergeable_state 'blocked' (e.g. when executing within CI while checks/approvals are pending) |
| `auto_resolve` | `boolean` | No | `False` | Automatically resolve review discussion threads that have received a reply from someone other than the thread opener. |
| `allow_replied_threads` | `boolean` | No | `False` | Treat review discussion threads that have received a reply from someone other than the thread opener as addressed rather than blocking. |
| `repo` | `string` | No | - | Target repository in OWNER/REPO format. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `pr_checks`

Check remote CI quality gate status on a pull request.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | Yes | - | Pull request number. |
| `repo` | `string` | No | - | Target repository in OWNER/REPO format. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `pr_close`

Close a pull request.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | Yes | - | Pull request number. |
| `comment` | `string` | No | - | Comment text to include when closing the pull request. |
| `delete_branch` | `boolean` | No | `False` | Delete remote topic branch upon closing. |
| `repo` | `string` | No | - | Target repository in OWNER/REPO format. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `pr_diff`

View diff of a pull request.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | Yes | - | Pull request number. |
| `repo` | `string` | No | - | Target repository in OWNER/REPO format. |
| `color` | `string` | No | `auto` | Whether to colorize diff (always, never, auto). |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `pr_edit`

Edit pull request base branch, title, body, or milestone.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | Yes | - | Pull request number. |
| `base` | `string` | No | - | Change the base branch for this pull request. |
| `title` | `string` | No | - | Set the new title. |
| `body` | `string` | No | - | Set the new body. |
| `repo` | `string` | No | - | Target repository in OWNER/REPO format. |
| `milestone` | `string` | No | - | Set the milestone for this pull request. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `pr_list`

List pull requests with base targeting and review status.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `state` | `string` | No | `open` | Filter by state (open, closed, merged, all). |
| `limit` | `integer` | No | `30` | Maximum number of items to return or display. |
| `repo` | `string` | No | - | Target repository in OWNER/REPO format. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `pr_monitor`

Wait until the checks of a PR settle, then name every blocker of its merge.

While a check runs or a Copilot review is active, it waits. Then it reports the blockers of
the merge-readiness verdict and of its review gate (requested changes, Copilot's review, an
approval of the head with --require-reviews). Exit 0: ready; 1: a check failed or could not
be read; 2: another blocker; 3: the timeout passed first.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | No | - | Pull request number. |
| `interval` | `integer` | No | `60` | Polling interval in seconds between check queries. |
| `timeout` | `integer` | No | `300` | Maximum time in seconds to wait for checks and reviews. |
| `settle_timeout` | `integer` | No | `60` | Grace period in seconds to allow Copilot review sessions to initialize. |
| `require_reviews` | `boolean` | No | `True` | Wait for active Copilot review sessions to conclude and check for unresolved threads. |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `repo` | `string` | No | - | Target repository in OWNER/REPO format. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `pr_ready`

Mark a draft pull request as ready for review once its checks pass.

It exits 1 when a check failed or could not be read and 8 while one runs. Every other
blocker of the merge-readiness verdict prints as a warning. --force skips the checks. It
sets the Status of the roadmap item the pull request closes to In Review.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | Yes | - | Pull request number. |
| `repo` | `string` | No | - | Target repository in OWNER/REPO format. |
| `monitor` | `boolean` | No | `False` | Automatically transition to monitoring checks and reviews after marking ready. |
| `force` | `boolean` | No | `False` | Bypass failing check verification and force ready status |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `pr_threads_list`

List PR review discussion threads, file locations, and comments.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | Yes | - | Pull request number. |
| `repo` | `string` | No | - | Target repository in OWNER/REPO format. |
| `unresolved_only` | `boolean` | No | `False` | Filter to display only unresolved review discussion threads. |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `pr_threads_reply`

Post an in-thread reply to a PR review discussion thread.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `thread_id` | `string` | Yes | - | Review thread GraphQL ID (e.g. PRRT_...). |
| `body` | `string` | Yes | - | Reply message text to append directly to the review thread. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `pr_threads_resolve`

Programmatically mark one or more PR review discussion threads as resolved.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `thread_ids` | `array[string]` | Yes | - | One or more review thread GraphQL IDs to resolve. |
| `without_reply` | `boolean` | No | `False` | Force resolution of review threads even if they lack a reply from someone other than the thread opener. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `pr_update`

Update pull request branch with latest commits from its base branch.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | No | - | Pull request number to update (optional if --all is specified). |
| `all_prs` | `boolean` | No | `False` | Update every open pull request that the current account wrote. |
| `base` | `string` | No | - | With --all, update only the pull requests into this base branch. |
| `repo` | `string` | No | - | Target repository in OWNER/REPO format. |
| `expected_head_sha` | `string` | No | - | Expected SHA of the pull request's HEAD ref for optimistic locking. |
| `dispatch_ci` | `boolean` | No | `False` | Dispatch the ci.yml workflow on the head branch after updating. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `prometheus_query`

Execute an instant PromQL query.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `expr` | `string` | Yes | - | PromQL expression. |
| `at` | `string` | No | - | Evaluation timestamp for instant vector query. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `repos_list`

List all cloned repositories.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `base_dir` | `string` | No | - | - |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `repos_sync`

Fetch (and optionally pull) all tracking branches across repos.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `base_dir` | `string` | No | - | - |
| `pull` | `boolean` | No | `True` | - |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `review_branch`

Review a git branch diff.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `branch_name` | `string` | No | - | Branch to review (default: current branch). |
| `base` | `string` | No | `main` | Base git branch to diff against (default: main). |
| `repo_path` | `string` | No | `.` | Repository root directory (default: current directory). |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |
| `summary` | `boolean` | No | `False` | Has no effect: every review runs the staged pipeline, which does not read it. |
| `full` | `boolean` | No | `False` | Print the whole report to the terminal: every finding with its details, every dependency and every network reference. By default the terminal lists CRITICAL to MEDIUM findings, with details for CRITICAL and HIGH, and gives LOW and INFO findings, dependencies and network references one line each that points at review.md. |
| `explain` | `boolean` | No | `False` | Explain code review personas, severity levels, and terminology. |
| `no_pre_analysis` | `boolean` | No | `False` | Disable pre-analysis and metadata refresh. |
| `pre_analysis_only` | `boolean` | No | `False` | Run pre-analysis only and skip subsequent stages. |
| `no_static_scan` | `boolean` | No | `False` | Disable the static scan: the security analyzers and the Ruff, mypy and complexity evidence. |
| `static_scan_only` | `boolean` | No | `False` | Run static scanning only and skip subsequent stages. |
| `no_group_analysis` | `boolean` | No | `False` | Disable model-driven group analysis. |
| `no_reporting` | `boolean` | No | `False` | Disable consolidated report generation; the review keeps no session. |
| `reporting_only` | `boolean` | No | `False` | Run report generation only. |
| `no_cache` | `boolean` | No | `False` | Bypass LLM response cache and force fresh inference. |
| `force` | `boolean` | No | `False` | Force fresh review execution without cache. |
| `append_cache` | `boolean` | No | `False` | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `concurrency` | `integer` | No | - | Max concurrent workers for parallel review. Through the gateway it is capped at the gateway's backend slots. |
| `parallel` | `boolean` | No | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `logfire` | `boolean` | No | - | Enable or disable Logfire structured observability and agent turn tracing. |

### `review_export_feedback`

Append review verdicts to the JSONL feedback dataset, which `devops ai prompt-eval` reads.

Each session's findings.json and candidates.json are read, and only the findings whose
verdict the dataset does not hold yet are appended. An export that finds none leaves the
dataset as it was. Without --status only INVALIDATED verdicts are exported. The dataset
changes no prompt and no later review.

A subject reviewed more than once is exported once: its sessions share their findings by
fingerprint v2. Each finding has the newest verdict a person gave it in any of those
sessions, or else the verdict of the session that review history counts. --status selects
by that verdict. A session that records no subject, and a finding with no fingerprint v2,
are exported on their own.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `output` | `string` | No | - | JSONL dataset to append to (default: the configured data.feedback_dataset_path). |
| `reviews_dir` | `string` | No | - | Directory containing review sessions. |
| `status` | `string` | No | `INVALIDATED` | Finding status to export: INVALIDATED, VERIFIED, MITIGATED, or ALL. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `review_findings`

Inspect structured findings for a review session.

Each finding keeps its number, its place in findings.json, whatever filter the list
applies, and `devops review verify --index` takes that number. With `--candidates` the list
is candidates.json: every finding the review raised, the ones verification invalidated
included, numbered for `devops review verify --candidate`.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `session` | `string` | No | - | Session ID or substring (default: latest). |
| `session_opt` | `string` | No | - | Session ID or substring (default: latest). |
| `status_filter` | `string` | No | - | Filter by status: VERIFIED | UNVERIFIED | INVALIDATED | MITIGATED. |
| `unverified` | `boolean` | No | `False` | Show unverified findings only. |
| `invalidated` | `boolean` | No | `False` | Show INVALIDATED findings only; add --candidates to look among every finding the review raised. |
| `verified` | `boolean` | No | `False` | Show verified findings only. |
| `mitigated` | `boolean` | No | `False` | Filter findings by MITIGATED status |
| `candidates` | `boolean` | No | `False` | List candidates.json: every finding the review raised, reported or not. |
| `severities` | `array[string]` | No | - | Show only findings of this severity: CRITICAL, HIGH, MEDIUM, LOW or INFO (repeatable). |
| `details` | `boolean` | No | `False` | Display full finding descriptions and fix recommendations. |

### `review_path`

Review source files directly (no git required).

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `targets` | `array[string]` | No | - | File(s) or directory(ies) to review. |
| `pattern` | `string` | No | `*` | Glob pattern for matching files. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |
| `summary` | `boolean` | No | `False` | Has no effect: every review runs the staged pipeline, which does not read it. |
| `full` | `boolean` | No | `False` | Print the whole report to the terminal: every finding with its details, every dependency and every network reference. By default the terminal lists CRITICAL to MEDIUM findings, with details for CRITICAL and HIGH, and gives LOW and INFO findings, dependencies and network references one line each that points at review.md. |
| `explain` | `boolean` | No | `False` | Explain code review personas, severity levels, and terminology. |
| `no_pre_analysis` | `boolean` | No | `False` | Disable pre-analysis and metadata refresh. |
| `pre_analysis_only` | `boolean` | No | `False` | Run pre-analysis only and skip subsequent stages. |
| `no_static_scan` | `boolean` | No | `False` | Disable the static scan: the security analyzers and the Ruff, mypy and complexity evidence. |
| `static_scan_only` | `boolean` | No | `False` | Run static scanning only and skip subsequent stages. |
| `no_group_analysis` | `boolean` | No | `False` | Disable model-driven group analysis. |
| `no_reporting` | `boolean` | No | `False` | Disable consolidated report generation; the review keeps no session. |
| `reporting_only` | `boolean` | No | `False` | Run report generation only. |
| `no_cache` | `boolean` | No | `False` | Bypass LLM response cache and force fresh inference. |
| `force` | `boolean` | No | `False` | Force fresh review execution without cache. |
| `append_cache` | `boolean` | No | `False` | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `watch` | `boolean` | No | `False` | Continuously watch target paths for changes and review only the changed files. |
| `debounce_ms` | `integer` | No | `500` | Debounce window in milliseconds for filesystem watcher. |
| `concurrency` | `integer` | No | - | Max concurrent workers for parallel review. Through the gateway it is capped at the gateway's backend slots. |
| `parallel` | `boolean` | No | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `logfire` | `boolean` | No | - | Enable or disable Logfire structured observability and agent turn tracing. |

### `review_pr`

Review a GitHub pull request.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | Yes | - | Pull request number. |
| `repo` | `string` | No | - | Target repository in OWNER/REPO format. |
| `post_comment` | `boolean` | No | `False` | Post the review as a comment on the GitHub PR. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |
| `summary` | `boolean` | No | `False` | Has no effect: every review runs the staged pipeline, which does not read it. |
| `full` | `boolean` | No | `False` | Print the whole report to the terminal: every finding with its details, every dependency and every network reference. By default the terminal lists CRITICAL to MEDIUM findings, with details for CRITICAL and HIGH, and gives LOW and INFO findings, dependencies and network references one line each that points at review.md. |
| `explain` | `boolean` | No | `False` | Explain code review personas, severity levels, and terminology. |
| `no_pre_analysis` | `boolean` | No | `False` | Disable pre-analysis and metadata refresh. |
| `pre_analysis_only` | `boolean` | No | `False` | Run pre-analysis only and skip subsequent stages. |
| `no_static_scan` | `boolean` | No | `False` | Disable the static scan: the security analyzers and the Ruff, mypy and complexity evidence. |
| `static_scan_only` | `boolean` | No | `False` | Run static scanning only and skip subsequent stages. |
| `no_group_analysis` | `boolean` | No | `False` | Disable model-driven group analysis. |
| `no_reporting` | `boolean` | No | `False` | Disable consolidated report generation; the review keeps no session. |
| `reporting_only` | `boolean` | No | `False` | Run report generation only. |
| `no_cache` | `boolean` | No | `False` | Bypass LLM response cache and force fresh inference. |
| `force` | `boolean` | No | `False` | Force fresh review execution without cache. |
| `append_cache` | `boolean` | No | `False` | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `concurrency` | `integer` | No | - | Max concurrent workers for parallel review. Through the gateway it is capped at the gateway's backend slots. |
| `parallel` | `boolean` | No | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `logfire` | `boolean` | No | - | Enable or disable Logfire structured observability and agent turn tracing. |

### `review_stats`

Compute and display review accuracy statistics across saved sessions.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `reviews_dir` | `string` | No | - | Directory containing review sessions. |

### `roadmap_intake`

Turn candidates into items: every open issue with no priority/* label. The model compares each with the items and the issues closed as not planned, but not with an issue that has sub-issues, because its sub-issues deliver it. It names a possible duplicate for a person to close: intake never closes an issue and never drops a candidate. Each gets a type label and a scope label from the Conventional Commit title, a status/new label, Value and Effort labels and a reason comment, then its priority label last, and goes to the backlog. The model picks the type only for a title with no Conventional Commit type. A label a person set stays. Intake sets no milestone: a person plans the milestones, and a milestone an issue has stays. Close an issue as not planned to keep it off the roadmap: devops gh issues close \<number\> --reason not-planned. A candidate an agent files with --title and --body-file is labeled source/agent, and intake files it, a possible duplicate too, unless a run that stopped after filing left an open issue with its title and body, which intake then places; a text that looks like it holds a secret is refused. --dry-run makes no request and prints the requests a run makes; --plan, the default, reads GitHub and calls the model, writes nothing and reports what it spent; --confirm makes the writes.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | Repository as owner/name (default: this checkout's origin). |
| `ref` | `string` | No | - | Branch, tag or commit to read .github/labels.yml at (default: the repository's default branch). |
| `issue` | `array[integer]` | No | - | Only this issue (repeatable). |
| `title` | `string` | No | - | Title of a candidate that is not an issue yet; intake files it, and names a possible duplicate for a person to close. Needs --body-file. |
| `body_file` | `string` | No | - | File holding the new candidate's body. Needs --title. |
| `source` | `string` | No | - | Link the new candidate came from, such as the item it splits or the review that found it; the filed body ends with it. Intake never names the issue that this link names, or a sub-issue of that issue, as a possible duplicate of the candidate. |
| `filed_by` | `string (agent, person)` | No | `agent` | Who files the new candidate: an agent's is labeled source/agent; a person's is not. |
| `limit` | `integer` | No | - | Decide at most this many candidates, the oldest first, and leave the rest for a later run. Without it, intake decides every candidate. It keeps no record of what it decided; the intake that devops roadmap run and the Service run keeps one, so a candidate it left undecided waits behind the fresh ones. |
| `dry_run` | `boolean` | No | `False` | Make no request, to GitHub or a model: print the requests a run makes, in order, with placeholders for values a read gives. |
| `plan_only` | `boolean` | No | `False` | Read GitHub and call the model, print each planned change and what the run spent, and write nothing. Intake without a mode flag does this. |
| `confirm` | `boolean` | No | `False` | Plan as --plan does, then make the writes on GitHub. |

### `roadmap_refine`

Refine roadmap items to Ready with proposed design, tasks, and acceptance criteria, using code and documentation. When a fact or a decision has no verified source, or a key question of the body has no answer, refine investigates it with tools that read the code and, for a public repository with a Firecrawl key, search the web. A design question gets the best-practice option with the options it compared, and only a decision that a person must make waits on a person. The plan says when web search is off. Without --item, refine takes items nearest place first: each open milestone's New items, by due date and then by number, then the backlog's P0 and P1 items, then the backlog's other New items, each place by priority. Only --limit stops a run. The number of Ready items does not stop it. In each open milestone and among the backlog's P0 and P1 items it also takes Ready items it has no record of, and sets one back to New when it finds it not ready. An item that an account other than the owner, a member or a collaborator opened waits on a person, and only --item refines it. An item on which refine wrote 2 comments in the last 24 hours also waits on a person and takes no place under --limit, and only --item refines it until the older comment is 24 hours old. An item refine cannot set to Ready gets one comment with its next step. The step is the questions a person answers, the split a person makes, or the open items it waits on. Refine looks at the item again after a reply, a body edit or the close of those items, or after a commit on the default branch changes a file that the block cites. The report groups every item by its next step. A part of an item that cannot be built or decided now moves to new issues through intake when the rest of the item is Ready. Each new issue starts with 'Split from #\<issue\>.', and refine names the new issues in its Ready comment and records them as refine.deferred. An item that is too big for one pull request still waits for a person to split it. An item whose model call fails is skipped and reported; the others are still refined, and refine then exits 1.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | Repository as owner/name (default: this checkout's origin). |
| `source` | `string` | No | `.` | Path to the repository checkout (defaults to current directory). |
| `item` | `integer` | No | - | Specific issue number to refine instead of selecting by priority. Refine refines it when it is open and New or Ready, even when nothing changed since its last round, whoever opened it, and however many comments refine wrote on it. |
| `limit` | `integer` | No | `3` | Maximum number of items to refine in this run (default 3). |
| `dry_run` | `boolean` | No | `False` | Make no request and change no git ref: print what refine would plan and run, with placeholders. |
| `confirm` | `boolean` | No | `False` | Refine the items and write the proposed designs to GitHub. Without it, refine prints its plan only. |

### `roadmap_run`

Run the roadmap jobs that are due, in order: metrics, then intake, refine and the alternatives check, and record each one's last success. Intake is due on an issue reopened, and decides at most 5 candidates a run and keeps a record of those it left beside the schedule; refine is due every 31 minutes, on a first run, and after an intake that placed a critical fix or a P0 item; the alternatives check is due every 719 minutes and on a first run, and checks at most roadmap.alternatives.limit items. Without --confirm, or with --dry-run, prints the due list and runs nothing.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | - | Repository as owner/name (default: this checkout's origin). |
| `dry_run` | `boolean` | No | `False` | Make no request: print the due list of jobs and the reason each is due, and run nothing. |
| `confirm` | `boolean` | No | `False` | Execute the due roadmap jobs. Without it, run prints the due list only. |

### `sandbox_deploy`

Deploy an isolated background container sandbox with security containment.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `command` | `array[string]` | No | - | Optional container command |
| `image` | `string` | No | `python:3.14-slim` | Container image for the sandbox workload. |
| `name` | `string` | No | - | Friendly identifier name for the sandbox instance. |
| `ports` | `array[integer]` | No | - | Container port(s) to dynamically expose on available host ports. |
| `workspace` | `string` | No | `.` | Host workspace path to mount into container /workspace. |
| `memory` | `string` | No | `2g` | Memory limit for the container (e.g. 512m, 2g). |
| `cpus` | `number` | No | `2.0` | CPU quota limit for the container (e.g. 1.0, 2.0). |
| `read_only` | `boolean` | No | `True` | Mount root filesystem as read-only with a tmpfs /tmp. |
| `network` | `string` | No | `isolated` | Docker network mode (bridge | host | none). |
| `network_mode` | `string` | No | - | Multi-tier network mode: isolated | sandbox_namespace | public_whitelist | local_whitelist | bridge |
| `public_whitelist` | `string` | No | - | Comma-separated public domains/IPs allowed for egress |
| `local_whitelist` | `string` | No | - | Comma-separated local URLs/IPs allowed for egress |
| `env` | `array[string]` | No | - | Environment variable in KEY=VALUE format. |
| `seccomp_profile` | `string` | No | - | Seccomp profile file for the container, in the JSON format of `docker --security-opt seccomp=<file>`, in place of the engine's default profile. Its defaultAction must refuse the system calls that it does not name. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `sandbox_exec`

Execute a command inside an active sandbox container.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `instance_id` | `string` | Yes | - | Unique instance ID or name of the sandbox. |
| `command` | `array[string]` | Yes | - | Command and arguments to execute inside sandbox |
| `workdir` | `string` | No | - | Working directory inside the container for command execution. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `sandbox_network_policy`

Generate declarative Kubernetes NetworkPolicy YAML for workload sandbox isolation.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `network_mode` | `string` | No | `isolated` | Network mode: isolated | sandbox_namespace | public_whitelist | local_whitelist | bridge |
| `name` | `string` | No | `app-sandbox` | Name prefix for the NetworkPolicy resource |
| `namespace` | `string` | No | `sandbox` | Target Kubernetes namespace |
| `public_whitelist` | `string` | No | - | Comma-separated public destinations allowed for egress, each opening one TCP port: scheme://host:port, host:port or [v6]:port. A bare host, IP or CIDR, or https, gets 443 and http 80; any other scheme needs a port. Names are resolved when the policy is generated, so regenerate it when a name's addresses change. |
| `local_whitelist` | `string` | No | - | Comma-separated local or private destinations allowed for egress, with the same forms and ports as --public-whitelist: scheme://host:port, host:port or [v6]:port; a bare host, IP or CIDR, or https, gets 443 and http 80; any other scheme needs a port. Names are resolved when the policy is generated, so regenerate it when a name's addresses change. |
| `allow_collector` | `boolean` | No | `False` | Add one egress rule to the OTel collector's pods in the otel namespace on TCP 4317 and 4318 (sandbox_namespace, public_whitelist and local_whitelist modes) |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `sandbox_status`

Inspect status of deployed sandbox containers.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `instance_id` | `string` | No | - | Unique instance ID or name of the sandbox. |
| `all_instances` | `boolean` | No | `False` | Apply operation across all registered sandbox instances. |
| `json_output` | `boolean` | No | `False` | Output details in structured JSON format. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `sandbox_stop`

Gracefully stop and tear down a sandbox container.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `instance_id` | `string` | No | - | Unique instance ID or name of the sandbox. |
| `all_instances` | `boolean` | No | `False` | Apply operation across all registered sandbox instances. |
| `timeout` | `integer` | No | `10` | Graceful stop timeout in seconds before SIGKILL. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `scan_aibom`

Generate AI Bill of Materials (AIBOM) with model licenses and hardware estimates.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | Target directory or model repository to analyze for AI models and AIBOM. |
| `format_type` | `string` | No | `cyclonedx` | AIBOM format output (cyclonedx, json). |
| `output_file` | `string` | No | - | Destination file path for generated AIBOM manifest. |

### `scan_complexity`

Run AST-based cyclomatic complexity analysis.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | Target directory or Python file to analyze for complexity. |
| `max_complexity` | `integer` | No | `10` | Maximum acceptable cyclomatic complexity per function (default 10). |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `scan_fix`

Remediate vulnerable dependencies via lockfile upgrades and optional git branch creation.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | Target project directory containing lockfile or dependencies |
| `package` | `string` | No | - | Specific vulnerable package to remediate |
| `min_severity` | `string` | No | `HIGH` | Minimum vulnerability severity (LOW|MEDIUM|HIGH|CRITICAL) |
| `apply` | `boolean` | No | `False` | Apply lockfile upgrades directly |
| `create_branch` | `boolean` | No | `False` | Create a git topic branch for the remediation |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `scan_injection`

Scan target files for prompt-injection smuggling vectors and canary tokens.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | Target file or directory to scan for prompt-injection smuggling vectors. |
| `sarif` | `string` | No | - | Write findings to this path as a SARIF 2.1.0 document. |
| `min_severity` | `string` | No | - | Drop findings below this severity (CRITICAL|HIGH|MEDIUM|LOW|INFO). |
| `suppress` | `string` | No | - | Suppression policy file; inherited policies are resolved via 'extends'. |
| `show_suppressed` | `boolean` | No | `False` | List findings hidden by the suppression policy and the rule that hid them. |
| `fail_on` | `string` | No | - | Exit non-zero when a finding at or above this severity survives suppression. |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `scan_sast`

Run static application security testing (SAST) via Semgrep.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | Target directory or file to scan with Semgrep AST rules. |
| `config` | `string` | No | `p/default` | Semgrep ruleset config: a local path, or a registry id such as p/default. The scan reads a registry id from the ruleset that `devops review rules fetch` cached. The rule pack of devops-cli runs with it. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `scan_sbom`

Generate Software Bill of Materials (SBOM) using Trivy (#1439).

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | Target directory, file, or repository to scan. |
| `format_type` | `string` | No | `cyclonedx` | SBOM format output (cyclonedx, spdx, json). |
| `output_file` | `string` | No | - | Destination file path for generated SBOM document. |

### `scan_secrets`

Run Gitleaks secret pre-filter scan across workspace or targets.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | Target directory or file to scan for secrets. |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `scan_trivy`

Run Aqua Trivy vulnerability, secret, and misconfiguration scan.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | Target directory, file, or repository to scan. |
| `scan_type` | `string` | No | `fs` | Trivy scan mode: fs, image, config, repo. The config mode scans IaC files for misconfigurations. |
| `severity` | `string` | No | `UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL` | Comma-separated severity levels to include. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `scan_uv_audit`

Audit the packages that the uv.lock of a project pins, as it is, for known vulnerabilities and adverse project statuses, with uv audit.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |

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

List the managed SSH keys of the project prefix with their age and rotation status.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `key_dir` | `string` | No | - | Directory where SSH keys are stored. |
| `prefix` | `string` | No | - | Optional prefix for the SSH key name (defaults to config setting, devcontainer name, or basename pwd). |
| `all_projects` | `boolean` | No | `False` | List the managed keys of all projects, not only the keys of the prefix. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `ssh_status`

Show the active SSH key and days until rotation.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `key_dir` | `string` | No | - | Directory where SSH keys are stored. |
| `prefix` | `string` | No | - | Optional prefix for the SSH key name (defaults to config setting, devcontainer name, or basename pwd). |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `telemetry_logfire`

Display Logfire structured observability bridge status and token metrics.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `output_format` | `string` | No | `table` | Output format type (table, json, yaml, markdown). |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |

### `telemetry_profile`

Run a devops-cli command, or name a trace, and show its span waterfall as Tempo recorded it.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `trace_id` | `string` | Yes | - | Trace ID to read from Tempo and show, instead of running a command. |

### `telemetry_status`

Check OpenTelemetry collector health, Tempo endpoint, and trace propagation status.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `telemetry_test`

Emit a test OpenTelemetry trace span and metric to the configured collector.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | `string` | No | `devops-cli.manual_test` | Name for test span. |
| `logfire` | `boolean` | No | `False` | Emit test span via Logfire bridge. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `tf_apply`

Create or update OpenTofu infrastructure.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | Target directory containing OpenTofu configuration. |
| `var_file` | `string` | No | - | Path to variable definitions file. |
| `plan_file` | `string` | No | - | Explicit plan file to apply. |
| `auto_approve` | `boolean` | No | `False` | Skip interactive confirmation prompts. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `tf_cost_breakdown`

Estimate monthly and hourly cloud infrastructure costs using Infracost.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | Target directory containing OpenTofu configuration. |
| `mock` | `boolean` | No | `False` | Use deterministic mock cost output |
| `max_monthly_cost` | `number` | No | - | Maximum allowable monthly cost budget threshold |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `tf_notify_plan`

Format and post structured, collapsible OpenTofu/Terraform plan diffs to PR comments.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `plan_file` | `string` | No | - | Path to raw plan output or log file. |
| `pr_number` | `integer` | No | - | Pull Request number to post plan comment to. |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |
| `output_format` | `string` | No | `table` | Output format (table, json, yaml, csv) |

### `tf_output`

Read an output variable from the OpenTofu state.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | Target directory containing OpenTofu configuration. |
| `json_output` | `boolean` | No | `False` | Output findings or metrics as JSON. |
| `output_format` | `string` | No | `table` | Output format (table, json, yaml, csv) |
| `raw` | `boolean` | No | `False` | Output raw string without formatting or shell escapes. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `tf_plan`

Generate and show an OpenTofu execution plan.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | Target directory containing OpenTofu configuration. |
| `var_file` | `string` | No | - | Path to variable definitions file. |
| `out` | `string` | No | - | Write generated plan to file. |
| `destroy` | `boolean` | No | `False` | Generate a plan to destroy all resources. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `tls_ca`

Generate a self-signed Root Certificate Authority (CA) key pair.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `output_dir` | `string` | No | `` | Directory to save certificate and key files. |
| `common_name` | `string` | No | `Homelab DevOps Root CA` | Common Name for the certificate (e.g. *.example.internal). |
| `organization` | `string` | No | `Homelab DevOps` | Organization name. |
| `country` | `string` | No | `US` | 2-letter country code. |
| `validity_days` | `integer` | No | `3650` | Validity period in days. |
| `key_size` | `integer` | No | `2048` | RSA key size in bits (2048 or 4096). |
| `overwrite` | `boolean` | No | `False` | Overwrite existing files. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `tls_cert`

Generate an X.509 TLS certificate signed by local CA or self-signed.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `common_name` | `string` | No | `homelab.local` | Common Name for the certificate (e.g. *.example.internal). |
| `san` | `array[string]` | No | - | Subject Alternative Names (DNS names or IP addresses). |
| `ca_cert` | `string` | No | - | Path to signing CA certificate (ca.crt). |
| `ca_key` | `string` | No | - | Path to signing CA private key (ca.key). |
| `output_dir` | `string` | No | `` | Directory to save certificate and key files. |
| `validity_days` | `integer` | No | `365` | Validity period in days. |
| `key_size` | `integer` | No | `2048` | RSA key size in bits (2048 or 4096). |
| `organization` | `string` | No | `Homelab DevOps` | Organization name. |
| `overwrite` | `boolean` | No | `False` | Overwrite existing files. |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `tls_inspect`

Inspect and display metadata of an X.509 certificate.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `cert_path` | `string` | Yes | - | Path to X.509 certificate file (.crt or .pem). |

### `valkey_flush`

Flush and purge keys from current or all databases.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `all_databases` | `boolean` | No | `False` | Flush all databases instead of just active one |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `valkey_get`

Retrieve string value stored at key.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `key` | `string` | Yes | - | Key to retrieve |

### `valkey_info`

Inspect server configuration, memory allocation, and operational metrics.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `section` | `string` | No | - | Specific INFO section (server, memory, clients, stats) |

### `valkey_ping`

Test connection and measure round-trip latency to the Valkey server.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `valkey_set`

Set string value of key with optional expiration TTL.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `key` | `string` | Yes | - | Key name to set |
| `value` | `string` | Yes | - | Value to associate with key |
| `ex` | `integer` | No | - | Expiration timeout in seconds |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `valkey_stats`

Display quick diagnostic summary of server health, memory, and keys.

**Annotations:** `readOnlyHint: true`

*No parameters required.*

### `vault_get`

Fetch a secret from Vault, or from the OS keyring when Vault cannot answer.

The keyring answers only with no usable token, when Vault has no value at the path, or when
Vault is unreachable; never after Vault rejects the token. The output names the source.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | `string` | Yes | - | Vault secret path (e.g. secret/data/myapp or vault://secret/data/myapp#token) |
| `key` | `string` | No | - | Specific secret field key to extract |
| `show` | `boolean` | No | `False` | Display secret in plain text without masking |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `vault_set`

Store secret key-value pairs in HashiCorp Vault KV-v2 engine.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | `string` | Yes | - | Vault secret path (e.g. secret/data/myapp) |
| `key_values` | `array[string]` | Yes | - | Key-value pairs to store (format: KEY=VALUE) |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `vault_status`

Inspect HashiCorp Vault cluster health and initialization status.

The health endpoint needs no token, and none is sent. The Token row names where the token
other commands would use comes from, and why a stored token is not used for this address.

**Annotations:** `readOnlyHint: true`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |

### `vault_sync`

Synchronize secrets from Vault into OS Keyring for offline/local CLI operations.

Reads Vault alone. A path with no secret fails, and a field named like the entry that holds
the `devops vault login` token is never written.

**Annotations:** `readOnlyHint: false`

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `path` | `string` | Yes | - | Vault secret path to synchronize into OS Keyring |
| `keys` | `array[string]` | No | - | Specific keys to sync (syncs all keys if omitted) |
| `dry_run` | `boolean` | No | `False` | Preview execution plan without mutating external state. |
