# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.28] - 2026-10-07

### Added
- Every reported scanner finding and dependency advisory is admitted with its producer's anchor (`ToolAnchor` or `AdvisoryAnchor`) and a location validated against the reviewed commit in `devops_cli.review.admission.admit()`, writing `findings.sarif` and rendering introduced, pre-existing, and suppressed findings in `review.md`, one suppressed row per file and line (only scanner findings are compared with the base revision; every dependency advisory is listed as introduced), with admission rejections counted by type in `profile.json`; an inline marker suppresses only findings of its own tool (`nosec` for Bandit, `nosemgrep` or `no-semgrep` for Semgrep, `noqa` for Ruff), and findings from the review's models are not admitted (#871, #1295, #1341).
- Increase in-cluster `roadmap-service` analysis task context window in `k8s/devops/configmap.example.yaml` from 16k (`16384`) to 64k (`65536`) tokens (#1271).

### Changed
- Unify pull request check runs and commit status contexts retrieval into a single fail-closed reader supporting combined statuses across >30 contexts and reporting zero checks as pending across `pr wait`, monitor, and readiness (#769).

### Fixed
- Defend dashboard domain panels against mounting race conditions by deferring snapshot rendering when unmounted or during child query races, preventing `NoMatches` worker failures (#519).
- Isolate MCP in-process child process stdio to temporary files to prevent protocol stream corruption, return bounded masked failure output with FastMCP `ToolError` on non-zero exit codes, and expand `ci_run` tool to accept any gate check name with budgeted timeout (#839).
- Ensure `web_fetch` reports failed HTTP fetches as tool failures (`ToolFailed`) and security blocks as errors, rather than returning failure descriptions as page text (#894).
- Align all hand-written documentation (`README.md`, `ARCHITECTURE.md`, `RELEASE_CYCLE.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `docs/DEVCONTAINER_USAGE.md`, `docs/VISION.md`, `k8s/README.md`, and `k8s/llm/profiles/README.md`) to name only commands, options, flags, and architecture patterns that exist, backed by static argv validation in `devops docs check` (#921).
- Reviews of branches and pull requests scan an isolated detached worktree of the reviewed revision under user data root instead of the active checkout, preventing uncommitted edits from leaking into review findings or symbol metadata (#1047).
- Git change set parsing uses `git diff --name-status -M` to ensure deleted files are never passed to static analyzers, and renames track the target path at head while preserving old paths (#1047).
- Single-file path reviews resolve repository root via `git rev-parse --show-toplevel`, and uncommitted reviews report scanning in place (#1047).
- Pre-analysis of the worktree reuses cached metadata when content hash matches the commit blob, bypassing mtime checks (#1047).
- PR reviews fetch head from `refs/pull/N/head` and mark partial context when unavailable (#1047).
- Path classes loaded from `.devops/review.toml` route fixtures and golden sets to secret scanning only, skipping general analyzers (#1047).
- Detailed per-tool coverage matrix recorded in `profile.json` and rendered under `## Coverage` in `review.md` (#1047).
- Gitleaks regex fallback deleted in favor of deterministic binary execution; missing binary reports as not installed (#1047).
- Ensure a review verifier verdict that both confirms and refutes its finding stays unverified with a `verifier-contradiction` note rather than ending `VERIFIED` or `verifier-inconclusive`, even when its reason repeats the title or confirms the claim (#1059).
- A failing embedding model pauses RAG lookups with a circuit breaker after three consecutive transient errors instead of permanently ending RAG for the run, while permanent errors from unknown or unserved models stop RAG with one warning (#1065).
- Route lookups concurrently once healthy while coordinating a single probe after failures, avoiding serialized wait loops across concurrent review workers (#1065).
- Hash prompt-prefixed text for L1 and Valkey L2 embedding cache keys, supporting distinct model prompt prefixes across `qwen3-embedding`, `bge-m3`, `nomic`, and `e5` families (#1065).
- Pin `CONST_KNOWN_EMBEDDING_DIMENSIONS["qwen3-embedding"]` to 1024, honor configured `ai.rag.top_k` and `ai.rag.score_threshold` (including threshold 0), skip package manager lockfiles, and bound semantic chunks to 8,192 estimated tokens, which is 32,768 characters at the project's four-characters-per-token estimate (#1065, #1296).
- End failed indexing batches with exit 1 naming the first and last file. A run without `--force` resumes where it failed: a file is cached once all of its chunks are stored and as incomplete until then, so a file that spanned the failed batch is embedded again, and its stored chunks are purged if it is deleted or edited first (#1065, #1296).
- Route review requests through the LLM gateway with `least-busy` routing and `cancel_on_disconnect: true`, avoiding edge cut stalls and backend queue build-up on Ollama (#1069).
- `devops ai gateway connect` automatically discovers and configures the gateway's NodePort address on the LAN, probing `/health/liveliness` and `/model/info` while bypassing edge timeouts (#1069).
- Enforce single retry layer across LLM client transports: retryable status codes (408, 429, 5xx) retry with exponential backoff while non-retryable 4xx errors fail immediately without retry loops (#1069).
- Lower a gateway review's file workers from 16 to three, the sum of `DEFAULT_GATEWAY_REVIEW_SLOTS`, or to `ai.ollama_max_parallel` per `ai.ollama_urls` entry when that is more. Each file's personas still query the gateway in parallel, so requests in flight can exceed the slot count. Isolate persona retry execution, and purge expired or CLOSE-WAIT connections from the HTTP connection pool (#1069).
- Track `main` across all Argo CD git-source `targetRevision` fields under `k8s/argocd/` while retaining the release version pin for the service image in `k8s/devops/kustomization.yaml` (#1261).
- Fix Portkey AI Gateway liveness and readiness probe path to `/` and align GPU Feature Discovery image to `nvcr.io/nvidia/k8s-device-plugin:v0.16.2` (#1267).
- Disable ambient Logfire pytest plugins in test runner configuration to prevent network DNS lookups in dry-run tests (#1267).
- Resolve Argo CD application synchronization and manifest generation failures: specify valid port `number: 3100` for `loki-ingress`, deduplicate Grafana dashboard ConfigMap ownership between `base` and `monitoring`, remove redundant `Service/pyroscope` alias colliding with the Pyroscope Helm chart, and remove the homelab domain from the committed overlays; a native `deploy-stack --stack infra` applies `k8s/monitoring/dashboards` itself (#1279, #1297).
- Supply the homelab's values to Argo CD at deploy time instead of from the repository (#1290):
  - `devops k8s deploy-stack` renders ConfigMap `devops-cli-config` from `config.yaml`, outside any Application.
  - It writes the hosts each of the Applications `devops` and `ingress` renders, at the revision Argo CD builds (or `--argocd-revision`), onto the Application as Kustomize patches. The `cluster` app-of-apps ignores those patches.
  - It renders everything before it writes, and refuses an unset service setting or domain by name.
  - `teardown-stack` deletes the ConfigMap, and the repository no longer tracks `k8s/devops/configmap.yaml`.

### Security
- Redact secret-bearing argv items from async subprocess telemetry command summaries and terminate the entire POSIX process group on subprocess timeouts (#780).
- Render untrusted web pages as escaped markdown within context budget with dynamic backtick fencing, chrome/dialog decomposition, prompt boundary tag sanitization, and response URL provenance isolation (#896).

## [0.2.27] - 2026-10-06

### Added
- **Kubernetes deployment health diagnosis (`devops k8s doctor`)**:
  - Add `devops k8s doctor` command and `k8s_doctor` FastMCP tool to diagnose cluster deployment health and correlate symptoms across nodes, pods, and warning events (#408).
  - Attribute workload symptoms to cluster-level root causes, absorbing resident pods into node findings and identifying stuck PersistentVolume reclaims (#408).
  - Support `--namespace`, `--context`, `--tail`, `--format table|json|yaml`, and `--dry-run` execution with deterministic ranking and secret masking (#408).
- **Argo CD GitOps cluster state reconciliation**:
  - Introduce a two-level root Application topology (`bootstrap` tracking `main` and `cluster` tracking the active release branch) managing 20 leaf Applications (8 raw manifests and 12 multi-source Helm charts) (#755).
  - Establish `homelab` and `homelab-system` AppProjects with cluster-scoped kind whitelisting and orphaned resource tracking (#755).
  - Add declarative domain overlays under `k8s/overlays/homelab/` replacing templated overlays and standardizing ingress patching (#755).
  - Add `monitoring/grafana-admin` secret to keyring push table with live credential adoption (#755).
- **Sequential pipeline stage context budgeting**:
  - `MultiAgentPipeline` allocates carried outputs from prior stages newest-first up to `DEFAULT_PIPELINE_STAGE_CONTEXT_TOKENS` (4,096 tokens, overridable via `--stage-context-tokens` or constructor), listing older stages that get no budget by name only and appending `ScratchpadBuffer.render_context_summary()` once after carried outputs outside the budget (#859).
  - `PipelineStepResult` records `context_tokens` (exact token count of carried context sent to the stage) and `context_truncated` (#859).
- **`devops pr update --dispatch-ci` flag**:
  - Add `--dispatch-ci` to `devops pr update` to poll the head branch SHA and trigger `ci.yml` via GitHub Actions workflow dispatch after updating branches (#984).
  - Grant `actions: write` permission exclusively to `update-pull-requests` in `.github/workflows/update-prs.yml` and add architectural invariants gating Actions write permissions across all workflows (#984).
- **Pinned invariants survive memory summarization, lead every system prompt and recur on a cadence**:
  - Partition `AgentMemory` with an `invariants` store that survives extractive and LLM summarization as well as `clear()` operations (#985).
  - Prepend non-negotiable operational rules verbatim at the head of every system prompt, recur compressed reminders on a 3-turn cadence using stdlib `textwrap.shorten`, and seed `devops ai chat` sessions with `DEFAULT_CHAT_INVARIANTS` (#985).
- **OpenTelemetry tracing for background service and Kubernetes workloads**:
  - Enable OpenTelemetry export in `k8s/devops/configmap.yaml` targeting the in-cluster collector at `http://otel-collector-opentelemetry-collector.otel.svc.cluster.local:4318` (#1197).
  - Add egress rule to `k8s/devops/networkpolicy.yaml` (`devops-default-perimeter`) permitting TCP ports 4318 and 4317 to namespace `otel` for all current and future workloads in namespace `devops` (#1197).
  - Configure `OTEL_SERVICE_NAME: roadmap-service` in `k8s/devops/roadmap-service/deployment.yaml` (#1197).
  - Instrument `create_service_app` with HTTP request tracing and timing middleware (skipping trace spans on `/healthz`, `/readyz`, `/metrics` probes) and trace batch job executions in `RepoWorker._execute_batch` (#1197).
- **DevOps Stack in `deploy-stack` & `stack all`**:
  - Add `"devops"` stack to `devops k8s deploy-stack` and automatically include it in `devops k8s deploy-stack --stack all`, ensuring all in-cluster manifests (`networkpolicy.yaml`, `serviceaccount.yaml`, `configmap.yaml`, `cronjob.yaml`, and `roadmap-service`) and secrets are deployed and kept up to date (#1225).
  - Pre-register namespace `devops` in `k8s/namespaces.yaml` with `restricted` pod-security standards and ArgoCD Prune=false annotations (#1225).
  - Add automated rollout restart of `deploy/roadmap-service` in namespace `devops` during stack deployment to apply updated ConfigMap values immediately (#1225).
  - Update `AGENTS.md` instructions with the architectural requirement that all in-cluster Kubernetes resources must have a managed stack path in `deploy-stack --stack all` (#1225).
- **GitHub Traffic Metrics & Automated Telemetry Ingestion in Roadmap Service**:
  - Add GitHub repository traffic and engagement telemetry instruments (`devops_cli_project_traffic_views_total`, `devops_cli_project_traffic_views_uniques_total`, `devops_cli_project_traffic_clones_total`, `devops_cli_project_traffic_clones_uniques_total`, `devops_cli_project_traffic_referrers_total`, `devops_cli_project_traffic_paths_total`, `devops_cli_project_stars_total`, and `devops_cli_project_forks_total`) (#1227).
  - Implement `record_project_metrics_in_registry` to populate in-memory metrics registry for direct Prometheus scraping via `roadmap-service:8000/metrics` (#1227).
  - Add scheduled `metrics` job to `DEFAULT_DUE_TABLE` in `roadmap-service` running immediately on startup and every 15 minutes to continuously refresh repository velocity and traffic metrics (#1227).
  - Add GitHub Traffic & Repository Engagement section with stat and bargauge panels to the `Project & Engineering Velocity` Grafana dashboard (`k8s/monitoring/dashboards/project-metrics.json`) (#1227).
  - Add traffic and referral summaries to `devops gh metrics` CLI output (#1227).
- **Dynamic DevOps ConfigMap Generation & Sanitized Template**:
  - Add `k8s/devops/configmap.example.yaml` template with sanitized placeholder repositories and account name (#1231).
  - Add `/k8s/devops/configmap.yaml` to `.gitignore` and untrack it from version control to prevent user repos and bot accounts from leaking (#1231).
  - Add `devops_cli.k8s.configmap` module with `ensure_devops_configmap` and `render_devops_configmap_content` to dynamically materialize and synchronize the cluster ConfigMap from active configuration (`service.repos`, `service.machine_account`, or `k8s.github_account`) (#1231).
  - Update `devops k8s deploy-stack` and `devops k8s render` to ensure `configmap.yaml` is generated from active settings before applying manifests (#1231).
- **GitHub & Cloudflare Published Service Status Monitoring**:
  - Add `devops gh status`, `devops cloudflare service-status`, and unified `devops status` commands to monitor published upstream platform operational status, active incidents, and component health (#1235).
  - Add Statuspage domain models (`StatuspageSummary`, `StatuspageComponent`, `StatuspageStatus`, `StatuspageIncident`) and telemetry client in `devops_cli.telemetry.service_status` (#1235).
  - Register `devops_cli_upstream_service_status` and `devops_cli_upstream_component_status` OpenTelemetry/Prometheus instruments, recorded continuously by the metrics adapter in `devops roadmap run` (#1235).
  - Integrate published service status into Grafana dashboards: stat panel on `ingress-tunnel.json` (Cloudflare Service Status) and dedicated row with GitHub and Cloudflare status panels on `project-metrics.json` (#1235).
- **Keep issues with open or merged pull requests in active releases**:
  - Update roadmap store pull request queries (`open_pull_requests`) to index both `OPEN` and `MERGED` states via GitHub GraphQL and in-memory store (#1244).
  - Add `Event.PR_JOINED` and `Reason.PULL_REQUEST` transitions so items with in-flight or merged pull requests joining a started or cut release are admitted and kept rather than demoted to the backlog (#1244).
  - Guard release start and descoping rules so items with pull requests remain in the starting release even if `New` or `Blocked`, and are excluded from over-cap descoping victims (#1244).

### Changed
- **Stack lifecycle and release management delegation**:
  - Update `devops k8s deploy-stack` to detect Argo CD-managed clusters, run secret push, and delegate manifest and Helm reconciliation to GitOps (#755).
  - Guard `devops k8s teardown-stack` against manual execution when Argo CD manages the cluster (#755).
  - Pin Helm release versions across all stack manifests and CLI upgrade commands (#755).
  - Automate Argo CD git `targetRevision` rewriting to the next open roadmap release during `release prepare` and `release cut` (#755).
  - Enforce `Prune=false,Delete=false` sync options across all namespaces and persistent volume claims (#755).
- **Instruction surfaces and agent documentation**:
  - Remove hardcoded gate counts across documentation surfaces, aligning with unified gated quality gate terminology (#840).
  - Rescope automatic Copilot review statements to PRs into `main` only, noting monthly token budget rationale (#840).
  - Update issue template references in `AGENTS.md` to supported templates (`bug_report.yml`, `feature_request.yml`) (#840).
  - Add `--force` flag to `devops ai agents`, refusing to overwrite existing `AGENTS.md` without `--force` while writing pointer stubs and exiting non-zero (#840).
  - Remove vestigial `_pointer_stub` helper from `devops_cli.commands.ai` (#840).
  - Add offline test suite `tests/test_agents_md_claims.py` verifying issue template existence, persona enum consistency, and pointer stub byte equality (#840).
- **Required CI checks bind merges into release and main**:
  - Remove deprecated `.github/branch-protection.yml` and clarify help text across `devops gh branch-protection` commands to indicate management of classic branch protection rather than rulesets (#842).
  - Author ADR 0004 recording the CI verification policy, required check names (`Static Analysis` and `Tests & Coverage`), strict mode, `update-prs.yml` dispatch route, and owner decisions on Copilot reviews (#842).
  - Add glossary definitions for `Gate`, `Check`, and `Required check` to `CONTEXT.md` (#842).
- **Dependency updates from closed Dependabot pull requests**:
  - Bump `fastapi` from 0.141.1 to 0.142.2 (#1201).
  - Bump `gitpython` from 3.1.62 to 3.2.0 (#1202).
  - Bump `genai-prices` from 0.1.6 to 0.1.9 (#1200).
- **Transition from Dependabot to Renovate (`.github/renovate.json`)**:
  - Replaced `.github/dependabot.yml` with `.github/renovate.json` for GitHub Actions and Docker dependency tracking (#1219).
  - Disabled automated Python package updates in Renovate to manage `uv` dependencies deliberately as part of project workflow with synchronized `uv.lock`.
- **Devops Kubernetes services route to qwen3.8:27b on ollama-48gib-slow**:
  - Update `devops-background` in `k8s/llm/gateway/configmap.yaml` to serve `ollama_chat/qwen3.8:27b` on `http://ollama-48gib-slow.llm.svc.cluster.local:11434` (#1221).
  - Configure `k8s/devops/configmap.yaml` (`devops-cli-config`) to route default `model`, `tasks.analysis.model`, and `tasks.chat.model` to `devops-background` on the background tier (#1221).
  - Synchronize gateway routing catalog in `src/devops_cli/k8s/gpu_matrix.py`, workload profiles comments in `k8s/llm/profiles/ollama-profiles.yaml`, documentation in `k8s/README.md`, and Ollama knowledge base (#1221).
- **GPU Configuration Matrix & Service Aliases Asset Extraction**:
  - Extract static dictionaries (`profiles`, `provider_service_aliases`, `speed_tier_service_aliases`, and `gateway_routes`) from `src/devops_cli/k8s/gpu_matrix.py` into structured JSON asset `src/devops_cli/k8s/gpu_matrix.json` (#1223).
  - Eliminate obsolete and vestigial `vllm` references from hardware profiles, service aliases, and CLI filtering options (#1223).
  - Streamline `src/devops_cli/k8s/gpu_matrix.py` from 845 lines to under 130 lines by loading the JSON asset via cached parser, eliminating iterative dynamic attribute loops (#1223).
- **Agent instructions for continuous roadmap-service, concurrency guardrails, and health checks**:
  - Documented in-cluster `roadmap-service` architecture, continuous daemon execution (`devops serve --service`), webhook handling, and autonomous batch jobs (#1236).
  - Established strict concurrency guardrails prohibiting overlapping manual roadmap mutations (`devops roadmap close --confirm`, `devops roadmap intake --confirm`) while `roadmap-service` is active (#1236).
  - Provided comprehensive verification and liveness diagnostic procedures (`kubectl` deployment/pod status, HTTP `/readyz` and `/healthz` probes, logs, metrics), credential rotation recovery, and safe offline manual fallback protocols (#1236).

### Removed
- **Automated PR synchronization workflow (`update-prs.yml`)**:
  - Removed `.github/workflows/update-prs.yml`, eliminating automated base-branch merges into open pull requests on push events and associated Actions approvals and duplicate CI runs (#1217).

### Fixed
- **PR monitor fail-closed Copilot review state handling**:
  - `devops pr monitor` reports Copilot review state as `unread` with `unread_reason` when timeline or review reads fail, rather than reporting `completed` or `idle` (#806).
  - Treat `unread` Copilot state as not review-ready and keep polling until settle/timeout, reporting the unread reason upon timeout rather than certifying ready (#806).
  - Include unread Copilot review diagnostics in `failure_reasons` and JSON/YAML structured output (#806).
- **CI quality gate execution cache tree certification**:
  - The CI execution cache verifies whole-tree state against deterministic Git and blob fingerprints, removing the legacy file-subset caching path and `--files` CLI parameter (#838).
  - Compute workspace fingerprint before quality gates execute for full, non-dry runs, certifying after checks pass that the tree did not mutate during the run before saving cache (#838).
  - Emit a warning and record nothing in the CI cache if the working tree changed during gate execution, preserving existing cache and exiting with the passing verdict (#838).
  - Treat file arguments or `--files` flags passed to `devops ci` as Click usage errors with exit code 2 and 0 gate executions (#838).
- **CLI startup imports no telemetry when disabled**:
  - Set `PYDANTIC_DISABLE_PLUGINS=logfire-plugin` unconditionally at module level before importing `devops_cli` modules, ensuring the Logfire pydantic plugin is disabled across all CLI invocations (#858).
  - Deleted `logfire.instrument_pydantic()` and decoupled `devops_cli.exceptions` from AI domain exceptions, preventing `pydantic_ai`, `logfire`, and `opentelemetry.sdk` from loading on top-level and subcommand `--help` invocations (#858).
  - Re-derived timing ceiling test assertions in tree-sitter, context packer, inspection, and fastmcp suites as runaway bounds ($\ge 20\times$ baseline and $\ge 1\text{ s}$) (#858).
  - Eliminated duplicated coverage step duration in CI pipeline gate summaries and consolidated pytest worker configurations into a single `pyproject.toml` setting (#858).
- **`skip_rag` parameter propagation in multi-agent pipeline**:
  - Forward `skip_rag` from `MultiAgentPipeline.run` to `agent.run(...)` and pass `skip_rag=not rag` in `devops ai pipeline` command (#859).
- **Streamed interactive chat turn history and memory rollback**:
  - `_stream_interactive_chat_turn` appends the user prompt to `agent.memory` before invoking `client.chat_messages_stream`, ensuring the model receives both prompt and prior conversation history (#874).
  - Pop trailing user entries from `agent.memory` before falling back to `agent.run` during thinking-only stream turns, and when streamed turns fail or are interrupted with `KeyboardInterrupt`, leaving agent memory as it was (#874).
- **CI quality gate and subcommand execution under dry-run**:
  - `devops ci` checks, runners, and subcommands start zero subprocesses and mutate no external state when `--dry-run` is active (#885).
  - Return dry-run `CheckResult`s carrying `dry_run=True` and render ordered `PlannedRequest` execution plans via `render_request_plan` for single checks and aggregate runs (#885).
  - Bypass coverage artifact cleanup and prevent saving or clearing gate cache under dry run (#885).
  - Add planned index run preview to `devops ci coverage --build-index --dry-run` without writing cache files or hashing source trees (#885).
- **Egress guards refuse cloud metadata in every numeric, NAT64, and provider form**:
  - Replaced ad-hoc string prefix checks (`startswith("169.254.")`) and partial lists with `pydantic_ai._ssrf` network classifiers and `dnspython` syntax parsing (#897).
  - Enforced refusal of IPv4 link-local, IPv6 link-local (`fe80::/10`), NAT64 metadata (`64:ff9b::169.254.169.254`), 6to4, Teredo, dword/hex/octal representations, fullwidth dot encodings, and provider internal metadata hostnames (`metadata.google.internal`, `metadata.goog`, AWS/Azure/GCP metadata endpoints) across all egress paths (#897).
  - Refactored `is_loopback_host` and `is_cloud_metadata_host` to deterministically parse and classify addresses without brittle subset heuristics (#897).
- **Knowledge base commands, options, and component references accuracy**:
  - Add static Markdown command argv collector and integrate into `devops docs check` to ensure all command lines and options in knowledge base articles resolve statically (#920).
  - Synchronize all Python package versions with `pyproject.toml`, remove phantom settings and environment variables (`DEVOPS_CLI_CONFIG_PATH`, `DEVOPS_CLI_LOG_LEVEL`), update default embedding models, and replace legacy numbered gate terminology with unified Gated standards across all 80 bundled knowledge base articles (#920).
- **Dependabot target branch and taxonomy labels (`.github/dependabot.yml`, `.github/labels.yml`)**:
  - Target Dependabot to `main` across `github-actions`, `pip`, and `docker` ecosystems without hardcoding release version branches (#1189).
  - Apply standard taxonomy labels (`type/chore` with `scope/ci`, `scope/cli`, and `scope/infra`) to Dependabot configurations and register missing scopes in `labels.yml` to satisfy `devops gh labels audit` (#1189).
- **Service image build provenance subject name in `release.yml`**:
  - Add explicit `subject-name: ghcr.io/${{ github.repository }}/service` to the `Attest Build Provenance` step in `.github/workflows/release.yml`, satisfying the requirement of `actions/attest-build-provenance@v2` when `subject-digest` is provided (#1192).
- **Domain Templating in `deploy-stack` & Roadmap-Service Ingress**:
  - Automatically substitute domain placeholders in Kubernetes manifests during `devops k8s deploy-stack` using `resolve_template_domain()`, preventing redeployments from reverting ingress hostnames to `example.com` (#1229).
  - Add `--domain / -d` support to `devops k8s deploy-stack`, aligning it with `apply` and `render` (#1229).
  - Update `k8s/devops/roadmap-service/ingress.yaml` to use `pathType: Prefix` on `/webhooks/github` for robust webhook routing (#1229).
  - Register `roadmap-service` Ingress route in `k8s/ingress/ingress-routes.yaml` for complete coverage under Cloudflare Wildcard Tunnel integration (#1229).
- **Grafana Dashboard "Value" Ghost Series**:
  - Filter `{api_base!=""}` on Litellm gateway panels in `k8s/monitoring/dashboards/llm-stack.json` to prevent unrouted metric samples (`{}`) from displaying as `"Value"` in legends (#1235).
  - Fix legend format placeholders from `{{ node }}` to `{{ instance }}` in CPU and Memory utilization panels in `k8s/monitoring/dashboards/k8s-views-global.json` (#1235).
- **DevOps CLI Telemetry dashboard command variable covers all registered subcommands**:
  - Update `$command` template variable in `k8s/monitoring/dashboards/devops-cli.json` (`devops-cli-telemetry`) to a custom variable pre-populated with all 39 registered devops subcommands (#1241).
  - Prevent subcommands with zero recent Prometheus invocations from being missing from the dropdown filter and repeating subcommand latency breakdown panels (#1241).
  - Add test coverage in `tests/test_grafana_dashboards.py` verifying that every registered CLI subcommand is covered by the dashboard's template variable options and query (#1241).
- **Discriminate Kubernetes manifests for Kube-linter and Pluto review scans**:
  - Filter candidate files in review static scanner pipeline via `_is_scannable_manifest` and `_scan_kubernetes_manifests`, preventing missing/deleted files from triggering scanner `lstat` failures (#1242).
  - Implement `is_kubernetes_manifest` check verifying `apiVersion` header presence and schema document structure, ensuring generic non-manifest YAML files (workflows, label taxonomies, dependabot configs) are bypassed by Kube-linter and Pluto (#1242).
- **Security audit fix**:
  - Upgrade `multidict` from 6.8.0 to 6.9.1 in `uv.lock` resolving vulnerability GHSA-54p9-h82j-f925 (#1242).
- **Scope roadmap reprioritization pull request queries to avoid full repository enumeration**:
  - Update `_OPEN_PULL_REQUESTS_QUERY` and `_OpenPullRequestsPayload` to query `openPrs` (`states: [OPEN]`) and `recentPrs` (`states: [MERGED]`, newest first) within a single GraphQL query, preventing single-page `_require_whole` truncation exceptions against repository-wide historical pull requests (#1246).
  - Retain backwards-compatible `AliasChoices` for `pullRequests` payload mapping in unit test doubles (#1246).
- **Classify project metrics and upstream status snapshot instruments as gauges**:
  - Add `InstrumentKind.GAUGE` to `src/devops_cli/telemetry/instruments.py` and route gauge emissions to `tracer.record_gauge(...)` (#1253).
  - Reclassify point-in-time inventory instruments (`PROJECT_ITEMS_TOTAL`, `PROJECT_COMMITS_TOTAL`, `PROJECT_PRS_TOTAL`, `PROJECT_CI_RUNS_TOTAL`, `PROJECT_RELEASES_TOTAL`, `PROJECT_STARS_TOTAL`, `PROJECT_FORKS_TOTAL`, `PROJECT_TRAFFIC_*`, `UPSTREAM_SERVICE_STATUS`, `UPSTREAM_COMPONENT_STATUS`) from `COUNTER` to `GAUGE`, preventing the OpenTelemetry Collector's `deltatocumulative` processor from monotonically accumulating point-in-time snapshots into vastly inflated metrics on Grafana dashboard `project-metrics.json` (#1253).
  - Update Panel 5 in `k8s/monitoring/dashboards/project-metrics.json` to compute interval per release by dividing release interval sum by count (#1253).
  - Update `docs/TELEMETRY.md` and add test coverage in `tests/test_telemetry_instruments.py` for gauge metric recording (#1253).

### Security
- **Collaborator trigger guard and expression isolation in `update-prs.yml`**:
  - Restrict the `issue_comment` trigger in `.github/workflows/update-prs.yml` to repository collaborators (`OWNER`, `MEMBER`, `COLLABORATOR`), ensuring unauthorized PR comments produce a skipped job without consuming Actions runner minutes (#754).
  - Move GitHub Actions expressions (`${{ ... }}`) out of `run:` script bodies into step `env:` variables to eliminate shell injection attack surfaces (#754).

## [0.2.26] - 2026-10-04

### Added
- **Coverage Reverse Index Test Selection (`devops ci coverage --build-index`, `devops ci test`)**:
  - Added `--build-index` option to `devops ci coverage` to generate a per-worktree reverse coverage index (`coverage_index.json`) mapping source files to covering test files using `COVERAGE_CORE=ctrace` and `--cov-context=test` (#406).
  - Enhanced `devops ci test` to select tests deterministically from the reverse coverage index, automatically incorporating working-copy drift since index creation and falling back to text-based selection on missing sources (#406).
  - Added atomic persistence and pre-/post-run working-tree mutation verification during index generation, aborting and cleaning up when repository files change during the run (#406).
  - Enforced full test suite escalation when trigger files (`conftest.py`, `pyproject.toml`, `uv.lock`, `.python-version`) change, with `--no-fallback` rejection support (#406).
- **Ruff Correctness Rule Families (`B`, `RUF`, `ASYNC`)**:
  - Extended Ruff lint selection to whole rule families `B` (flake8-bugbear), `RUF` (Ruff-specific rules), and `ASYNC` (flake8-async), catching runtime bugs, mutable defaults, and unhandled exception chains (#420).
  - Selected targeted single rules: `SIM115` (unclosed file handles), `PT011`, `PT015`, and `PT017` (pytest assertion and raises integrity), and `PGH003` (explicit type ignore codes) (#420).
  - Configured `allowed-confusables` for typographic mathematical and informational glyphs (`–`, `×`, `ℹ`) and enabled `ignore-without-code` in mypy configuration (#420).
  - Resolved all 146 rule violations across the codebase, added architectural invariant tests for suppression rules and mypy configuration, and lowered the C901 suppression ceiling from 66 to 65 (#420).
- **devops-cli in the cluster (`k8s/devops/`, `devops k8s run-job`)**:
  - Namespace `devops` with a suspended CronJob template, a token-less service account and a default-deny perimeter; cluster jobs reach the gateway directly (#741).
  - `devops k8s run-job -- ARGS` creates a Job from the template with only its args changed, follows its log and exits with its exit code; `--dry-run` reads nothing, not even the CronJob, and prints the kubectl requests a run would make (#741).
- **Cluster Secrets from the keyring (`devops k8s push-secrets`)**:
  - One table lists every Secret the stacks read; the command adopts live values, generates the ones nobody types and needs `--rotate` to replace a live value (#741).
  - Server-side apply from stdin: values never reach argv, files, annotations or output (#741).
  - `--dry-run` makes no request, reads included, and prints the requests a push would make in order with placeholders; `--plan` reads the keyring, the cluster and, for the machine account, gh's own record of it, says so, and prints each key's state (#741).
  - The machine account's token comes from gh's keyring through `gh auth` alone: gh must list the login with a keyring token its own check passes, and devops-cli never calls GitHub with that token, so a run keeps one GitHub identity (#741).
- **Hidden prompt for credentials (`devops config set KEY`)**:
  - Omitting VALUE for a credential prompts for it, keeping it out of shell history (#741).
- **Single-Entry Item Intake (`devops roadmap intake`, FastMCP `roadmap_intake`)**:
  - Open issues off the board, unfinished items and new `--title`/`--body-file` candidates get a duplicate check, a code-checked type, Priority, Value and Effort, and a placement; P0 needs verified evidence from a trusted source (#742).
  - Agent candidates are labelled `source/agent` and open, borrow (`budget/borrowed`) or fold under the agent filing quota (#1153), with its numbers on every run (#742).
  - The dry-run rule (#412): `--dry-run` makes no request, to GitHub, a model or the telemetry collector, and prints the requests a run makes in order with placeholders, as an `IntakePlan` marked as a dry run, each request a `PlannedRequest` (#741) that shows the exact `gh` command where it is known without a read, the condition it runs on and whether it repeats per page or per candidate; `--plan`, which intake without a mode flag runs, reads GitHub and calls the model, writes nothing and reports its spend (GitHub requests by REST, REST search and GraphQL, embedding and proposal calls); `--confirm` writes. The FastMCP tool takes `mode` (`plan` by default, `dry-run` or `confirm`), and a FastMCP tool dispatched in-process with `--dry-run` exports no telemetry either (#742).
  - Agent instructions file new work through intake, and `devops gh issues triage` reports issues off the board as awaiting intake instead of missing a milestone (#742).
- **`devops roadmap close`**: closes as completed each open issue that a pull request merged into the current release's branch closes, with one comment saying what changed (the pull request, its merge commit, the first section of its body and its changed-file count) and how it was verified (each check run with its bucket, and the Acceptance Criteria of the issue's task file at the merge commit). A pull request whose check runs can't be read closes nothing, and the run exits non-zero. Once the release holds no open item, at least one item closed as completed and no release pull request, it writes `docs/ROADMAP.md` on `chore/cut-vX.Y.Z` in the clone at `--root` and opens the release pull request into the default branch, ready for review, through the shared cut path; completed items with no changelog fragment are listed. Writes only with `--confirm`; `--plan` previews, `--dry-run` makes no request. MCP mirror `roadmap_close` previews only (#743).
- The roadmap store reads every pull request merged into a branch, with its merge and head commits and changed paths, from both adapters (#743).
- **`devops roadmap refine`**: item refinement to Ready with proposed design, tasks, and acceptance criteria. Selects New items from the next planned release by priority, then New backlog items up to the release cap. Gathers minimal repository context (`CONTEXT.md`, ADRs, cited files, grep identifiers) and up to 3 Tavily search queries for public repositories. Uses structured model output (`RefinementProposal`) validated deterministically against repository commits, cited lines, and verified sources. Writes sanitized plain-text markdown between markers `<!-- devops-roadmap-refine:start -->` and `<!-- devops-roadmap-refine:end -->` on the issue body with SHA/branch tracking and 65k size limit guard. Items that fit in one pull request with complete criteria and no open questions move to Ready with reason comments; oversized items remain New with `refine.needs_split="true"` and are descoped by reprioritization. Supports `--dry-run` and `--confirm`. Hooks into `apply_intake` for critical fixes and P0 features. Added FastMCP mirror tool `roadmap_refine` and due table integration in `devops roadmap run` (#744).
- **Continuous Service Mode for `devops serve`**:
  - Added dedicated continuous service mode (`devops serve --service`) for in-cluster deployment, processing and authenticating GitHub webhooks with per-repo single-concurrency job dispatch and coalesced batches (#752).
  - Added `ServiceConfig` to configuration settings (`repos`, `machine_account`, `poll_interval_seconds`, `drain_timeout_seconds`) and managed credential `service.webhook_secrets` (`DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS`) for repo-to-secret HMAC mapping (#752).
  - Added structured single-line JSON log formatter (`JsonLogFormatter`) emitting timestamp, level, logger, message, and contextual metadata with zero credential, payload, or signature leakage (#752).
  - Implemented `POST /webhooks/github` route with 25 MiB size enforcement, Content-Type verification, constant-time HMAC-SHA256 signature verification, 10,000-delivery LRU deduplication, ping handling, and machine-account suppression (#752).
  - Added `/healthz`, `/readyz`, and `/metrics` Prometheus endpoints recording delivery outcomes, trigger sources, job counts, job durations, start timestamps, and queue depth (#752).
- **Production Service Image for Scheduled Jobs and Webhook Handlers (`Dockerfile`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`)**:
  - Root `Dockerfile` multi-stage build packaging Python 3.14 runtime, `gh` CLI, `git`, and `devops-cli` virtual environment into a hardened, non-root (`1000:1000`), read-only container with `/etc/gitconfig` credentials (#753).
  - Pinned base images (`python:3.14-slim-trixie`, `ghcr.io/astral-sh/uv`) by SHA256 digest with BuildKit layer caching and minimal attack surface (#753).
  - CI workflow `service-image` job validating content change detection, build/load smoke testing under full sandbox constraints (`--read-only`, `--tmpfs`, `--cap-drop ALL`, `no-new-privileges`), and Trivy vulnerability auditing (#753).
  - Release workflow `service-image` job publishing `ghcr.io/dan-petty/devops-cli/service:v<version>` and `:latest` with SPDX SBOM generation and cryptographic build provenance attestation via GitHub Actions (#753).
  - Dependabot `docker` ecosystem tracking in `.github/dependabot.yml` and release routine verification instructions in `docs/ROUTINE_TASKS.md` (#753).
- **`devops roadmap run`**: evaluates the roadmap due table across landed jobs (`intake`, `close`, `reprioritize`) in a fixed execution order, tracking each job's last successful run time per repository in `<data dir>/roadmap/<owner>/<name>/schedule.json`. Clones repositories for jobs requiring code checkouts to `<data dir>/roadmap/<owner>/<name>/clone`, synced to the tip of `origin/release/vX.Y.Z` with session identity. Supports `--dry-run` and `--confirm` modes. Wires `service_job` adapter to `devops serve --service` for processing coalesced trigger batches. Adds FastMCP mirror tool `roadmap_run` reporting due jobs (#981).
- **Roadmap Service Kubernetes Deployment**:
  - Added single-replica `Recreate` Deployment for `roadmap-service` in the `devops` namespace running `serve --service --host 0.0.0.0 --port 8000 --workers 1` with restricted security context, `devops-cli` Secret environment, and health probes (#1083).
  - Added dedicated 1Gi `local-path` PersistentVolumeClaim (`roadmap-service-home`) mounted at `/home/devops` with Argo CD prune/delete protection (#1083).
  - Added ClusterIP Service and Traefik Ingress routing external traffic strictly to `POST /webhooks/github` (#1083).
  - Added `roadmap-service-ingress` NetworkPolicy admitting incoming connections on TCP 8000 only from Traefik in `kube-system` and Prometheus scraping in `monitoring` (#1083).
  - Added Prometheus egress rule in `k8s/monitoring/networkpolicy.yaml` allowing TCP 8000 metrics scraping into namespace `devops` (#1083).
  - Registered `DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS` in the cluster secrets push table with `deployment/roadmap-service` rollout restart targeting (#1083).
  - Updated `devops-cli-config` ConfigMap with `service.repos` and `service.machine_account` (#1083).
- Runtime dependency `graphql-core==3.3.0` (#1125).
- `devops roadmap reprioritize`, `migrate` and `render --plan`: a read-only preview that ends with the GraphQL points spent and left; `migrate` and `reprioritize` without a mode flag still preview, and `render` without one writes the file (#1125).
- **Agent Filing Quota Specification & Pure Quota Engine (`devops_cli.roadmap.quota`, `.github/roadmap.toml`, `.github/labels.yml`)**:
  - Six roadmap quota configuration keys (`open_issue_limit`, `throttle_start_fraction`, `overage_step_fraction`, `release_credit_base`, `release_credit_per_delivered_item`, `release_item_target`) with Pydantic field constraints and declared repository defaults in `.github/roadmap.toml` (#1153).
  - Pure calculation module `src/devops_cli/roadmap/quota.py` exposing exact arithmetic implementations of `ratio(n, config)`, `release_credit(delivered, config)`, and `allowance(n, delivered, closures, config)` (#1153).
  - Added declarative repository labels `source/agent` and `budget/borrowed` in `.github/labels.yml` (#1153).
  - Established agent filing quota, borrowing, and consolidation guardrails in `AGENTS.md` and `src/devops_cli/ai/instruction_generator.py` (#1153).
- **Grafana Observability Enhancements (`k8s/monitoring/dashboards/`)**:
  - Added 30-day, 90-day, and 1-year AI spend run rate projection stat panels to `ai-spend.json` (#1158).
  - Added rolling average trend lines (`rate(...)[6h]` and `rate(...)[30m]`) across AI spend timeseries panels (#1158).
  - Added subcommand template variable (`$command`) and per-subcommand repeating latency timeseries panels to `devops-cli.json` (#1158).
  - Added GPU memory percentage utilization timeseries panel with 90% and 95% threshold alert lines to `llm-stack.json` (#1158).
  - Added ingress traffic breakdown by host/router panel to `ingress-tunnel.json` (#1158).
  - Enabled router and service Prometheus metrics labels in Traefik ingress configuration (`k8s/ingress/traefik-values.yaml`) (#1158).

### Changed
- **Logging Namespace Pod Security Standards**:
  - Dropped `logging` namespace Pod Security Standards enforcement level from `privileged` to `baseline` in `k8s/namespaces.yaml`, as Loki and Loki canary require no hostPath mounts or elevated capabilities (#548).
  - Updated Kubernetes stack documentation in `k8s/README.md` to document the single-shipper architecture where Alloy ships container logs to Loki (#548).
- **deploy-stack pushes Secrets first (`devops k8s deploy-stack`)**:
  - Pushes the stacks' Secrets after the namespaces and before any manifest or release; `--no-push-secrets` skips it, and `--dry-run` lists key names (#741).
  - A locked keyring stops it before it applies anything; the devcontainer auto-deploy passes `--stack` and its failure warning names the unlock (#741).
- **A dry run exports no telemetry (`--dry-run`)**:
  - A command's own `--dry-run` no longer sends its spans and metrics to the telemetry collector, so a dry run makes no external request (#741).
- **Service image tag follows the release (`devops release prepare`, `devops release check`)**:
  - The bump pins `k8s/devops/kustomization.yaml` to `v<version>`, and the check fails when they differ (#741).
- **One GitHub session per process (`devops_cli.github.session`)**:
  - gh and git act only as the token `gh auth token` gives; `gh auth` sees the environment unchanged (#767).
  - Each identity keeps its own quota ledger and response cache (#767).
  - Removed `github.token`, `DEVOPS_CLI_GITHUB_TOKEN` and the unused GraphQL client: run `gh auth login`, then `keyring del devops-cli github_token` and revoke that token (#767).
- **Hermetic CI Runner & Bubblewrap Test Confinement (`.github/workflows/ci.yml`, `pyproject.toml`, `tests/conftest.py`)**:
  - Removed runner package installations (`sudo apt-get update`, `bubblewrap`, `python-is-python3`, and `sysctl` unprivileged user namespace relaxation) from `.github/workflows/ci.yml` (#832).
  - Registered `bwrap` pytest marker in `pyproject.toml` and introduced `pytest_collection_modifyitems` hook in `tests/conftest.py` to skip bubblewrap-dependent live tests when `bubblewrap` is not installed on the host (#832).
  - Made sandbox namespace refusal test hermetic using an executable stub binary in `tests/test_host_sandbox.py` (#832).
  - Added architectural invariant test in `tests/test_architectural_invariants.py` ensuring GitHub Actions workflows never mutate the runner and that `.devcontainer/Dockerfile` installs bubblewrap (#832).
- **Unified CI Quality Gate & Workflow Parity (`src/devops_cli/commands/ci.py`, `.github/workflows/ci.yml`, `tests/test_ci.py`)**:
  - Unified all CI verification gates into a single ordered `CheckSpec` table in `src/devops_cli/commands/ci.py`, ensuring CLI subcommands and aggregate gates execute identical check and fix commands (#843).
  - Added `--only` and `--skip` selection options to `devops ci` with mutual exclusivity and invalid name rejection, and ensured single-row execution streams output directly without buffering (#843).
  - Aligned `.github/workflows/ci.yml` jobs (`static`, `test`, `dependency-freshness`) to execute through `devops ci`, eliminating drift between local quality gates and remote GitHub Actions CI (#843).
  - Standardized Bandit security scanning on `-ll` across all scanners, removing global `-s B608` skips, applying targeted `# nosec B608` annotations to `instruction_generator.py` and `stack_lifecycle.py`, and removing obsolete `build_bandit_cmd` (#843).
  - Removed redundant `--xml` flag from `devops ci coverage` as `.data/coverage.xml` is written by default (#843).
  - Added offline workflow-to-table parity verification in `tests/test_ci.py` asserting all gate checks run through `devops ci` (#843).
- **Fail-closed release path (`devops release prepare`, `devops release pr`)**:
  - One shared, fail-closed release cut path (`cut_release`) creates `chore/cut-v<version>` from `origin/release/v<version>`, updates `pyproject.toml`, `src/devops_cli/__init__.py`, `uv.lock`, and the in-cluster service image tag on the cut branch, pushes with `--force-with-lease`, and opens the release pull request into `main` (#982).
  - Validates working tree cleanliness before any branch or file is touched, refusing dirty state with exit code 1 (#982).
  - Version for `devops release pr` is resolved from `pyproject.toml` on the checked-out cut branch rather than the caller's pre-checkout directory (#982).
  - Release PR opening fails closed immediately upon push errors or rejected labels/milestones, removing warn-and-continue fallback logic (#982).
  - Grounding exemption is restricted to `chore/cut-vX.Y.Z` into the default branch; PRs targeting release branches or forked cuts are held to full grounding (#982).
- The `roadmap_render`, `roadmap_migrate` and `roadmap_reprioritize` MCP tools take `mode` instead of `dry_run`, as `roadmap_intake` does: `plan` by default, `dry-run` makes no request, `write` (render) and `confirm` (reprioritize) write (#1125).
- **Grafana Visualization & AI Spend Reference Model**:
  - Resized Pyroscope continuous profiling CPU and memory allocation flamegraphs to full 100% width (`w: 24`) and stacked vertically in `sre-service.json` (#1158).
  - Restyled local savings by backend server in `ai-spend.json` as smooth individual lines with 20% semi-transparent fill (#1158).
  - Aligned default local AI equivalent reference model `DEFAULT_AI_REFERENCE_MODEL` from `gpt-4o` to `gpt-4o-mini` across defaults, pricing models, CLI commands, and example configuration to match commercial equivalents for `qwen3.8:27b` (#1158).

### Removed
- **Fluent Bit Logging Agent and Ingress**:
  - Removed Fluent Bit from the Kubernetes logging stack, manifests, and CLI stack lifecycle in favor of Alloy in `infra`, eliminating duplicate log scraping, unlabelled log streams, and unauthenticated ingress (#548).
  - Deleted `k8s/logging/fluent-bit-values.yaml` and `fluent-bit-ingress` in `k8s/ingress/ingress-routes.yaml` (#548).
  - Removed Kubernetes API server egress rule (TCP 443, 6443, 10250) from `k8s/logging/networkpolicy.yaml`, restricting `logging` egress strictly to intra-namespace and CoreDNS (#548).
  - One-time manual post-merge cleanup commands:
    ```bash
    helm uninstall fluent-bit -n logging --kube-context <cluster-context> --wait
    kubectl --context <cluster-context> delete ingress fluent-bit-ingress -n logging
    kubectl --context <cluster-context> label --dry-run=server --overwrite ns logging pod-security.kubernetes.io/enforce=baseline
    uv run devops k8s deploy-stack --stack logging --context <cluster-context>
    kubectl --context <cluster-context> get pods -n logging
    kubectl --context <cluster-context> get ns logging --show-labels
    kubectl --context <cluster-context> get networkpolicy logging-default-perimeter -n logging -o jsonpath='{.spec.egress[*].ports[*].port}'
    ```
- **Hand-made Secret steps (`k8s/README.md`, `k8s/cloudflared/secret.example.yaml`)**:
  - The `--from-literal` instructions and deploy-stack's client-side Qdrant Secret, which leaked the key into an annotation, are gone (#741).
  - `sync-secrets` no longer copies the Qdrant key into the keyring (#741).
- `devops gh issues close-merged` and the closure sweep in `github/issue_closure.py`, replaced by `devops roadmap close` (#743).
- **Dead Webhook Infrastructure**:
  - Removed obsolete `WebhookEventDispatcher`, `WebhookEvent`, `GitHubWebhookVerificationError`, and deleted legacy `graphql.py` and its tests in favor of canonical service mode webhook router (#752).
- **Removed options and fallback helpers (`devops release pr`)**:
  - Removed `--push/--no-push` option from `devops release pr` (#982).
  - Removed `_build_pr_fallback_cmd`, `_strip_pr_cmd_flag`, and `_checkout_release_branch` (#982).

### Fixed
- **Network Reference Extraction Grounded in URLs and IP Literals**:
  - Replaced heuristic bare-word and domain string inspection with strict URL parsing (`urllib.parse.urlsplit`) across any scheme and IP literal parsing (`ipaddress`), ensuring bare words, hostnames, and arbitrary identifiers are never extracted as network references (#431).
  - Eliminated heuristic constants (`CONST_BRANCH_PREFIXES`, `CONST_CODE_CONFIG_PREFIXES`, `CONST_COMMON_PROPERTY_SUFFIXES`, `CONST_TELEMETRY_CALL_NAMES`, `CONST_STANDARD_RECEIVER_IDENTIFIERS`, `CONST_EXCLUDED_FILE_MIME_TYPES`) and removed dead extraction routines, visitors, and shims (#431).
  - Simplified Python AST literal extraction to inspect all string constants directly for URLs and IPs, including in dictionary keys and function call arguments, without relying on telemetry or identifier blacklists (#431).
  - Renamed package repository asset filtering to host-only `is_trusted_registry_host(host: str) -> bool` based strictly on `CONST_EXCLUDED_PUBLIC_REGISTRIES` (#431).
  - Consolidated network reference types strictly to `"url"` and `"ip"`, removing all legacy `"domain"` reference categorization across models, extractors, and table formatters (#431).
- **GitHub write pacing decided from the request gh sends (`devops_cli.github.request_classifier`)**:
  - `run_gh` gives GitHub's one-second write interval to GraphQL mutations (`gh api graphql` with the document in `-f`/`-F query=`, an `@file`, stdin or an `--input` body, `operationName` included) and to `gh api` calls gh sends as an implicit POST (any field or `--input`), so `pr threads resolve-all`, project view and roadmap field writes, and the REST pull request fallback are paced (#1125).
  - `gh api`'s argv is read with `argparse` in every form gh accepts (`-XPOST`, `-X=POST`, `--method=post`, attached fields), and GraphQL documents with graphql-core, loaded only for a `graphql` request. A request that can't be read counts as a write (#1125).
  - High-level gh commands are classified by the verb in the verb position: a read verb (`view`, `list`, `status`, `checks`, `diff`, `show`, `item-list`, `field-list`) or the `search` group reads, any other verb writes. `gh project link` is now a write and `gh issue list --label sync` a read (#1125).
  - High-level commands find the verb past `-R`/`--repo` and `--owner`, so `gh -R o/r issue list` and `gh project --owner o item-list 2` are reads (#1125).
  - The write interval holds across resources within a process: a REST write and a GraphQL write acquired together are scheduled at least the interval apart. Only the write moves; reads keep their quota's pace and never wait behind another resource's write or quota reset (#1125).
  - A `gh api` write with `--paginate` goes to gh once, as given, paced as a write, instead of page by page as a read with `?page=1` added to its endpoint (#1125).
  - A `gh api` call is cached only when gh sends it as a GET with no field or body: a method in any form (`-X=POST`, `-XHEAD`), an attached field (`-ftitle=x`, `--field=k=v`) or an `--input` body, which the old token check let through, is no longer cached, so a repeated write is sent; reads cache as before (#1125).
  - A high-level gh command is cached only when the verb in the verb position reads: a read verb elsewhere in argv (`pr create --title list`) made the write cacheable (#1125).
  - Roadmap board reads go through the store's own paged GraphQL query instead of `gh project item-list`, which fetched every field of every item and reported no cost (a `reprioritize --dry-run` spent 2,025 of the 5,000 hourly points on 2026-10-04 while the limiter counted one call). Each page asks for `rateLimit`, and `run_gh` charges the points a GraphQL response reports. Project sync (`devops gh project sync`) reads its board with the same paged query (#1125).
  - Every board read passes a Projects filter at the source and leaves archived items out (`items(query:, archivedStates: [NOT_ARCHIVED])`); the backlog and candidate reads pass `is:open`. The read is checked against the total for the same filter, so an archived item no longer stops migrate with "Read 930 of 931", and a count that changes during the read is read again once before the run fails (#1125).
  - Before a board read, the run reads GraphQL's own `rateLimit` and the filter's total, and stops with a clear message, spending nothing on pages, when the read would leave less than 250 points; a read stops before any page while fewer than 250 are left (#1125).
  - `devops roadmap migrate`, `render`, `reprioritize` and `intake` end with one line giving the GraphQL points the run spent and the points left, read from GraphQL itself (#1125).
  - `devops roadmap reprioritize`, `migrate` and `render` `--dry-run` make no request at all: they read neither GitHub nor the roadmap configuration (a `reprioritize --dry-run` spent 2,025 GraphQL points on 2026-10-04). Each returns its real result type marked as a dry run and prints the requests a run makes, in order, each with its exact `gh` command and stdin, built by the store's own argument builders, with `<placeholders>` for values a read gives (#412, #1125).
  - `devops roadmap intake --dry-run` shows the exact `gh` command of every store request, a board write's reads included (#1125).
- **Grafana Dashboard Projections, Rolling Averages, and Panel Layouts**:
  - Consolidated multi-series rolling average queries in `ai-spend.json` into unified aggregate totals (`Total Rolling Avg`) across all servers and models, eliminating per-item rolling average line sprawl (#1175).
  - Updated AI spend and savings projections in `ai-spend.json` to calculate rates over the observed dashboard interval (`[$__range]`) extrapolated to 30-day, 90-day, and 1-year windows, replacing the fixed 1-hour active rate (#1175).
  - Fixed empty Time to First Token p95 panel in `llm-stack.json` by querying `litellm_llm_api_time_to_first_token_metric_bucket` grouped by model, eliminating failed joins on volatile LiteLLM deployment identifiers (#1175).
  - Restored Node Exporter Full dropdown selectors and system metrics by setting `useIntegrationAllowList: true` and adding `node_uname_info`, `node_load.*`, `node_disk_io_now`, and `node_netstat_Tcp_CurrEstab` to `includeMetrics` in `k8s-monitoring-values.yaml` (#1175).
  - Provisioned local `nvidia-dcgm.json` dashboard with bottom panels (GPU SM Clocks, GPU Utilization, Tensor Core Utilization, GPU Framebuffer Memory Used) organized into a balanced 2x2 grid, replacing upstream dashboard 12239's 50% single-column layout (#1175).
  - Corrected project velocity panels in `project-metrics.json` to evaluate cumulative release, milestone, and CI run counters directly as snapshot states rather than `increase()` deltas (#1175).
  - Added service traffic fallback to Traffic by Ingress Host / Router in `ingress-tunnel.json` (#1175).

## [0.2.25] - 2026-10-03

### Added
- **Model-in-the-Loop Prompt Benchmarking (`devops review corpus score`, `devops ai runs compare`)**:
  - `devops review corpus score --runs N` scores the latest N reviews of a corpus as one arm, and `--session` is repeatable. The score counts the runs that found and reported each injection, gives pass@k and pass^k, and gives the mean of each figure beside its `[min, max]` across the runs. It refuses sessions that ran different prompts, `--runs` beyond the reviews that exist, and `--session` beside `--runs`. The report says `not model-pinned` when a gateway group the review used serves more than one model (#413).
  - Each review's `profile.json` records `prompt_digest`, a digest of every prompt under `ai/tasks/` and `ai/personas/`, and corpus scores record it in their setup with the run count and the personas that replied. A corpus score also counts the findings the review raised, the verifier invalidated and verification kept (#413).
  - `devops ai runs compare` shows each run's range beside its mean when either run has one, and whether the ranges overlap (`overlaps`, `apart`, or `—` for a run without a range) (#413).
- **Per-Model Gateway Groups for the Review Pool (`k8s/llm/gateway/configmap.yaml`)**:
  - `qwen3-coder:30b` and `gpt-oss:20b`, the two models `devops-review` serves, each have a gateway group of their own. Each group copies its model's `devops-review` deployments (model, backend and weight, in order) with no `max_input_tokens` and no fallback, so a review pinned to one model is routed as the pool routes that model. `devops-review` and its weights are unchanged (#475).
- **Review Verification Task Environment Overrides (`devops_cli.config`)**:
  - `DEVOPS_CLI_AI_TASK_VERIFICATION_PROVIDER`, `DEVOPS_CLI_AI_TASK_VERIFICATION_MODEL`, `DEVOPS_CLI_AI_TASK_VERIFICATION_REASONING_EFFORT` and `DEVOPS_CLI_AI_TASK_VERIFICATION_OLLAMA_URLS` set `ai.tasks.verification.*`, as the analysis task's variables set `ai.tasks.analysis.*`. They override a verification model set in a config file, so one shell pins a review's analysis and verification to one gateway group (#475).
- **Benchmarks Without Static Scanners (`devops review benchmark --no-static-scan`)**:
  - `--no-static-scan` runs every review of the benchmark without the static scanners, so a scanner hit on an injected defect does not count as the model's recall. The run's setup records `static_scan`, so every benchmark setup now differs from earlier runs' in that key (#475).
- **Alertmanager, With a Webhook Receiver That Waits for Its Secret (`k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/grafana-values.yaml`)**:
  - The prometheus chart's Alertmanager is enabled, and Prometheus finds it through the chart's pod discovery. Since #734 removed kube-prometheus-stack, the stack had no Alertmanager and no alert rules, and Grafana had no Alertmanager datasource (#549).
  - Alerts without a routed severity go to the `null` receiver, which sends nowhere. `critical` and `warning` alerts go to `webhook`, which reads its URL from the `url` key of the Secret `alertmanager-webhook` in `monitoring` (`url_file`). The Secret is mounted optional, as a directory, so Alertmanager starts without it and picks up the file without a restart once it is created; until then each webhook notification fails and nothing leaves the cluster (#549).
  - A Not Ready node inhibits its targets' `TargetDown`, and a rule's critical alert inhibits its own warning (#549).
  - Grafana provisions the `Alertmanager` datasource (`uid: alertmanager`), so its Alerting pages list the alerts and silences (#549).
- **Alert Rules for the Homelab Nodes, GPUs, Storage and the Monitoring Stack Itself (`k8s/monitoring/prometheus-values.yaml`, `k8s/logging/loki-values.yaml`)**:
  - 23 rules in four groups: a node not Ready, a scrape target down, a node rebooted (uptime under 30 minutes, so a node that stayed down for hours still counts), no active `k3s` or `k3s-agent` unit, `nvidia-power-limit` not active, GPU temperature over 85 °C and at 90 °C, total GPU power over a 1000 W site budget, host filesystems under 10% and 5% free, kubelet-reported volumes under 10% free (no volume on this cluster reports them yet), Prometheus data over 80% of its claim, and Prometheus, Loki and Alertmanager health (#549).
  - No rule watches the controller manager, scheduler or proxy, which k3s runs inside its server process and nothing scrapes, so the false `KubeControllerManagerDown`, `KubeSchedulerDown` and `KubeProxyDown` of kube-prometheus-stack do not return (#549).
  - Retention is watched: `PrometheusSizeLimitCutHistory` fires when a size cap deletes blocks before the 30 days kept by time, and `LokiRetentionNotRunning` fires when Loki's compactor has not applied retention for over an hour. Loki's retention comes on with #550's Loki migration, whose Loki upgrade also starts the Loki scrape, so that alert has no series before the migration and afterwards fires only if the compactor stops applying retention (#549).
  - `PrometheusStorageNearClaim` reads this server's own TSDB series (`job="prometheus"`) and the largest claim size, so a second Prometheus or kube-state-metrics, as scraped for hours on 2026-10-01/02, does not stop it from evaluating (#549).
  - The Prometheus server's kubernetes-pods job scrapes Loki and Alertmanager through their pod annotations (`singleBinary.podAnnotations` in `k8s/logging/loki-values.yaml`), for their health rules. The Loki scrape exists only where the logging stack runs, so an infra-only cluster has no Loki target to report down (#549).
  - #550's `log-and-metric-retention` rules, `LogOrMetricVolumeDiskLow` and `PrometheusNearRetentionSizeCap`, route through the same receiver, and `PrometheusNearRetentionSizeCap` reads this server's own TSDB series (`job="prometheus"`) like `PrometheusStorageNearClaim` (#549).
  - `tests/test_k8s_monitoring_alerting.py` pins the rule set and checks that every expression selects only series a scrape in `k8s/` serves (#549).
- **Alerting Documented in `k8s/README.md`**:
  - The rules with their thresholds and waits, the receiver and its Secret, and planned maintenance: a `node="<node>"` silence, with `amtool` in the Alertmanager pod or Grafana's Silences page, then `kubectl drain`, so the single Alloy metrics pod moves off the node and `ClusterMetricsMissing`, which has no `node` label, does not page (#549).
  - The rule table lists every rule once, #550's two volume rules included, and says where the storage rules overlap; retention itself stays in #550's Log and Metric Retention section, which now says its alerts route through Alertmanager (#549).
- **An Alert Before the Log or Metric Volume Fills (`k8s/monitoring/prometheus-values.yaml`)**:
  - `LogOrMetricVolumeDiskLow` fires when the root filesystem of the node holding Loki's `storage-loki-0` or Prometheus's `prometheus-server` claim has had less than 10% free for 30 minutes. local-path does not hold a volume to its claimed size, so a volume fills when its node's filesystem does. The rule follows each claim through its pod to the node, so it moves with the volume (#550).
  - `PrometheusNearRetentionSizeCap` fires when the TSDB has used over 80% of `server.retentionSize` for an hour, before the cap would delete blocks younger than 30 days (#550).
  - Prometheus evaluates both and Grafana's alert list shows them. No Alertmanager is deployed yet, so they notify no one (#550).
- **Log and Metric Retention Is Written Down (`k8s/README.md`)**:
  - A new section says how long Loki and Prometheus keep data, what deletes it, each volume's size, why Loki's volume cannot simply be resized, and what the two alerts watch (#550).
- **Ruff Enforces the Complexity Cap of 10 (`pyproject.toml`, `uv run devops ci`, the `ruff-check` pre-commit hook)**:
  - `pyproject.toml` selects `C901` and sets `[tool.ruff.lint.mccabe] max-complexity = 10`, so a function over the cap (standard McCabe) fails `ruff check` in `devops ci`, in the `ruff-check` pre-commit hook and in GitHub CI. `AGENTS.md` called the cap strictly enforced, but nothing checked it: `C901` was not selected, and the `structural-invariants` hook only printed a note (#586).
  - The 66 functions over the cap when it was turned on, 65 in `src/` and 1 in `tests/`, carry a `# noqa: C901` marker. `ruff check --select C901 --add-noqa` wrote the markers in one run, and no function was decomposed in this change. `RUF100` reports a marker once its function is back under the cap, and the default `devops ci --fix` removes it. `PGH004` bans the blanket `noqa` that would hide `C901` without naming it (#586).
  - With `RUF100` selected, nine `noqa` codes that did nothing are gone. Five name rules the project does not select: `S310` three times in `ai/gateway_bench.py`, `S603` in `ai/gateway_tune.py` and `S102` in `tests/test_ai_gateway_tune.py`. Four sit where Ruff raises nothing: `F401` twice in `tests/test_exceptions.py`, and `N802` in `tests/test_sandbox_metrics.py` and `tests/test_sandbox_probe.py`. The `# nosec` comments that Bandit reads stay, and the reason "the script under test" stays as a plain comment (#586).
  - `test_c901_suppressions_stay_under_the_ceiling` counts the `C901` markers in `src/` and `tests/`, in every spelling Ruff honours, including a form feed or a no-break space where a space would go. It fails when the count exceeds `DEFAULT_C901_SUPPRESSION_CEILING` (66), names the files that carry markers, and says to decompose the function rather than raise the ceiling. A change that removes markers lowers the ceiling in the same change (#586).
  - `test_the_complexity_cap_has_no_escape` fails when `[tool.ruff]` or `[tool.ruff.lint]` holds a key outside its allowlist. The allowlists keep out Ruff's deprecated top-level `per-file-ignores` and `extend-ignore`, as well as `include`, `extend`, `extend-exclude` and `lint.exclude` (#586).
  - The same test fails when `exclude` is not `["repos"]`, when `C901`, `RUF100` or `PGH004` is not enforced or a per-file ignore waives it, or when `max-complexity` is not 10. A rule counts as enforced only when `select` names it by its own code, because Ruff reads `C9` as `C90`, so `C90` selected with `C9` ignored turns `C901` off (#586).
  - It also fails when a file under `src/` or `tests/` has a file-level exemption, when a `ruff.toml`, `.ruff.toml` or `pyproject.toml` sits under those directories, or when a `ruff.toml` or `.ruff.toml` sits beside `pyproject.toml` (#586).
  - It fails when a file under `src/` or `tests/` carries one of Ruff's own suppression comments naming `C901`: a `# ruff: ignore[C901]`, a `# ruff: disable[C901]` that holds until its `enable` or the end of the file, or a `# ruff: file-ignore[C901]`. One such comment hides any number of functions and leaves no marker to count, so these comments are banned rather than counted (#586).
  - It fails when an `.ignore` or `.gitignore` sits under `src/` or `tests/`, when an `.ignore` sits beside `pyproject.toml`, or when the project's `.gitignore` matches a source file there. Ruff skips the files an ignore file lists. Ignore files outside the checkout differ per machine and never reach GitHub CI's clean checkout. No test runs a Ruff process (#586).
- **GenAI Span Attributes Checked Against Pinned Semantic Conventions (`devops telemetry semconv refresh`, `devops_cli.telemetry.semconv`)**:
  - `src/devops_cli/telemetry/semconv_genai.json` pins the OpenTelemetry GenAI semantic conventions (`open-telemetry/semantic-conventions-genai`, which has no tagged release) to commit `b31e9e8ea26ac1c086d3313d474e31d7c3f391ae`, resolved with weaver 0.26.1, as their current attribute keys, metric names and span types (#588).
  - A gate test fails, naming `file:line`, on any quoted string starting with `gen_ai.` in `src/devops_cli/`, comments and docstrings included, that is not a current attribute key or metric name, and on any f-string that builds one (#588).
  - `devops telemetry semconv refresh --commit <sha>` resolves the conventions at a commit with `weaver registry package --v2` and rewrites the snapshot. It writes nothing and exits 1 when weaver is not on PATH, the commit is not a full SHA, or weaver fails or times out. A person runs it; the gate never does (#588).
- **Branch and PR Reviews Compute Their Own Symbol Delta (`devops review branch`, `devops review pr`)**:
  - Each review records the symbols that every changed Python file added, removed and kept since the commit its diff starts at, so an earlier `devops ai analyze branch` run is no longer needed. That commit is the merge base for a branch, `HEAD` for uncommitted changes, and the merge base from GitHub's compare endpoint for a pull request, not the base branch's tip. A branch's files are read at its own commit, so reviewing a branch that is not checked out, or one with uncommitted deletions, does not count the checkout's removals as the branch's. A renamed file is compared with its old path, an added file's symbols are all added, and a file whose base or head cannot be read gets no delta (#593).
  - Verification exempts a finding only when it cites a symbol this review's diff removed, and moves it to the file's diff hunk without asking the model. The summary's Symbol Delta row and `removed_symbol_findings_count` count only the reviewed files (#593).
- **Every Model Reply Carries the Reason It Ended (`devops_cli.ai.client`, `devops_cli.ai.direct`)**:
  - `LLMResponse.finish_reason` holds pydantic-ai's `FinishReason` (`stop`, `length`, `content_filter`, `tool_call` or `error`), read from the OpenAI-compatible `finish_reason`, Anthropic's `stop_reason` and Ollama's `done_reason` through three tables in `config/constants.py`. `max_tokens` and `model_context_window_exceeded` become `length`. An absent or unmapped value is `None`, meaning unknown, so truncation is never guessed. `to_model_response` passes the reason on and `from_model_response` reads it (#599).
  - `ai.llm.dispatch` and `ai.llm.stream` set `gen_ai.response.finish_reasons` to the provider's reason, and leave it out when the reason is unknown (#599).
- **The Spend Ledger and Review Profiles Count Why Replies Ended (`devops_cli.ai.spend`, `devops review`)**:
  - The spend ledger gains a `finish_reason` column. A ledger created before it gains the column in place and keeps its rows. Chat dispatches, streams and the pydantic-ai direct calls record the reason, and observers registered with `observe_llm_calls` receive it with each call (#599).
  - Each stage in a review's `profile.json` counts its replies by reason (`finish_reasons`, with `unknown` when the provider gave none) and the replies cut at their token cap by serving backend (`truncated`). When any reply hit the cap, the profile's summary line says how many (#599).
- **Review Sessions Record Their Subject, and History Counts Each Subject Once (`devops review`)**:
  - Every session's findings.json and candidates.json record its subject: the target type and ref, and a digest of the review pages. Both findings.json writers record it, and the persona-loop writer now stamps `generated_at` in UTC, as the pipeline does (#607).
  - One reader (`ai/review/history.py`) lists the completed sessions in a reviews directory and counts one session per subject: the one with the most human verdicts, then the most findings with a verdict, then the newest. A machine re-run or a `--no-verification` run never displaces verdicts a person wrote. Sessions written before this change each count on their own, as target-only or unkeyed. The reader parses only the fields the figures read, so it takes a fraction of a second where a full parse took seconds (#607).
- **Readiness Requires a PR to Close One Issue and Change Its Task File (`devops pr check-readiness`)**:
  - Every PR except the release PR (`release/vX.Y.Z` from the same repository into the default branch) is blocked unless its body closes exactly one issue, read as `devops gh issues close-merged` reads it, and it adds, modifies or renames that issue's `docs/agent/tasks/task-<issue>-*.md`. Each missing piece is one blocker that names it. A repository whose base has no `docs/agent/tasks/` is not checked (#704).
  - The changed files come from `pulls/{n}/files?per_page=100`, paged to the end. Where the check applies, a failed read is a blocker that names the failure; elsewhere it is a warning. The read replaces `gh pr diff --name-only`, which returned an empty list on any failure (#704).
- **GitHub-Sourced Roadmap: One-Time Migration and Generated View (`devops roadmap migrate`, `devops roadmap render`)**:
  - `devops roadmap migrate` makes GitHub the roadmap's source of truth (ADR 0001). It brings the board in line with `.github/project-template.json`: it moves the cards of options the template replaces, deletes fields the template lacks, and lists the option renames, additions and removals a person makes in the board's field settings, because GitHub's API can't keep an option's id. `--confirm` refuses before any write until the renames and additions are made. It fills unset Status and Priority from `status/*` and `priority/*` labels, closes release epics as not planned and takes them off the board, moves the open items of milestones beyond the planning horizon to the backlog and deletes those milestones, fills unset Value and Effort from the `docs/ROADMAP.md` matrix, and records each rejected or not-building idea as an issue closed as not planned. It edits no issue body and never overwrites a set field. It prints the plan and a four-section report (P0 feature candidates, entries without an issue, entries whose issue is closed, planned writes) and writes only with `--confirm`; a second run plans nothing (#739).
  - `devops roadmap render` writes `docs/ROADMAP.md` from GitHub: the current release, the planned releases within the horizon, then the backlog by priority, one line per item with its Status, Priority, Value and Effort. Two runs on the same state write the same bytes, and a failed read writes nothing (#739).
  - `.github/roadmap.toml` names the board and the roadmap jobs' settings (`release_cap`, `discovery_threshold`, `planning_horizon`, `stall_days`), and rejects unknown keys. Both commands read it, the board template and `docs/ROADMAP.md` through the contents API at `--ref` (#739).
  - MCP tools `roadmap_render` and `roadmap_migrate`, which only previews, in a new lazy `roadmap` domain (#739).
  - The roadmap store gains board creation from the template, field deletion, card listing, writes and removal, issue creation and closing with a reason and comment, Release deletion, workflow listing and repository file reads, in both adapters (#739).
  - `docs/VISION.md` holds the design principles and the themes from `docs/ROADMAP.md`, without release numbers (#739).
- **The Current Release's Admission, Cap, Descoping and Stall Rules (`devops roadmap reprioritize`)**:
  - `devops roadmap reprioritize` holds the current release, the open milestone with the lowest version, to its rules, and starts each release. After a release starts, only a critical fix (a P0 `type/bug` or `type/security` item) joins it: any other item added moves to the backlog, and a P0 feature to the next planned release. A fix that takes the release over its cap of 12 descopes the lowest-ranked unstarted item that is not a fix, and while the release holds more than the larger of its cap and its size at start, its lowest-ranked unstarted items leave too, so an item moved back to Ready after a fix filled the release makes room. An unstarted item that is Blocked, has an open blocked-by link outside the release, carries the `needs-split` label or is the last one not done is descoped to the next planned release, and an admitted critical fix only when it is Blocked. An In Progress item with no status change, pull request update or commit for 14 days goes back to Ready and is descoped (a critical fix stays), and an idle In Review item gets one nudge per window. While the release pull request is open, draft or not, and once it has merged until GitHub Release vX.Y.Z is published, the release is cut and a critical fix goes to the next release (#740).
  - When the release pull request has merged and GitHub Release vX.Y.Z is published, the job closes the milestone if it is still open, creates `release/vX.Y.Z` for the next release at the default branch's head when it is missing, sends its New items to the backlog and its Blocked items out, fills it to 12 from Ready items no person placed (critical fixes, then P0 features, then Priority, Value and number) or trims it to 12 into the planned release after it, and creates planned milestones up to the planning horizon. A release a person cut and shipped before any run started it, with its milestone still open, as while a run that would have stopped and waited, is skipped too: the run starts the first release after the shipped ones, or a first run records it, and closes every shipped milestone last, the current one first, where it used to start the shipped release, pull backlog items into it and close only the one before it. A start, or a first run at a ship, that stops at its last writes, the closes of the shipped milestones, has made every other: the next run holds the release it started or recorded to the rules and closes the milestones last, so an item a person added in between is judged then, not left until a later run is due; once that release has shipped too, its milestone closed by `release.yml` or not, the next run starts the one after it. A release a person cut before any run started it starts with nothing pulled in: nothing joins a cut release. A milestone closed without its release shipping starts nothing, and the plan says so. A backlog item a person put there stays out, even one no job ever placed, whose issue's events the start reads, and one the job had sent there before a person placed it elsewhere and back: each gets a `Left` mark naming where a person took it out of (#740).
  - The board's run record card (`Roadmap run record`) keeps the release the job last started, or recorded at its first run, and its size then, so a cleared admitted mark or an empty release never makes the job start a release again. The job names a release by its milestone number in the run record and in an item's marks, so a release renamed after it started is not started again and keeps its admitted items, while the plan and the comments use its new title. The first run records the admitted set of the release under way and moves nothing, the same release whether or not `release.yml` closed a shipped milestone; it and each start admit the release's closed items too, so one reopened there stays, and a closed item that leaves the release loses its mark like an open one, so one a person puts back and reopens is judged as a join. With the run record card gone while items carry the job's marks, the job refuses to run and names the card instead of recording a new baseline; with the card there but its `Started` mark not a milestone number, as an older version or a hand edit leaves it, the job refuses with its own message, which gives the number to set. A milestone older than the started release, such as a hotfix milestone, is held to no rule (#740).
  - Each change to an item is recorded as pending before its writes, and its reason comment is posted once, so a run that stops part-way is finished by the next one, which first judges the change again: a placement or status a person set since stands, and a change the rules no longer make, such as a fix's admission after the release was cut, is put back and decided anew. GitHub takes a field write as two calls, the job record and then the milestone or the board field, so the pending mark records each field as begun in the job-record write, before the field call, and as written in a job-record write once that call returns, and the next run counts a field as the job's only when the job wrote it and it has not changed since: the written mark keeps the field's event count or Status clock as the job's write left it, so a person who sets a field to the change's value after a dropped change put it back keeps it. For a field only begun it reads the issue's Release events or the Status's last change: a field call that never landed is made again, or its record taken back, so no `Left` mark names a release the item never reached and a release start still pulls in the item it began to; a field that holds the change's value may be the job's call that landed and reported a failure, or a person's edit, which no read tells apart, so the change is finished with its comment, and that value is never put back, written or recorded as the job's: the job record keeps no value for that field, so when the job moves an item it had placed itself, such as one a release start pulled in or a descope sent on, the next run never reads the job's own move as a person taking the item out of that place and gives it no `Left` mark, and the move clears a `Left` mark the item carried, as a confirmed move does. The job never puts back a value a person set, even the one the change was going to write, and never overwrites a person who set a field back to what it held before; the job record of a begun field a person set since is dropped, not put back to what it held before the change, so a person who moves an item back to where a job last placed it, after a stopped release start's milestone call had pulled it in, keeps it there, and the rerun's start does not pull it in again. When the issue's events show the item never joined the stopped change's target, its milestone call never landed, so that record is put back instead: an item a person moved out of the backlog and back while the rerun waited is still where the job placed it, and the start pulls it in. A change stopped before it began its Status write leaves the item's Status clock as it is, so a person who set an idle item In Progress again, or moved it into review and back, before the rerun of its stall descope keeps it in the release; and such a Status counts as the person's whatever it holds, so the rerun never writes Ready over it: a descope whose milestone call landed with nothing to show the job made it is finished with the person's Status left as it is, and one about a release that has shipped since gives way to the person's edit. A start judges an item an interrupted run moved into it like any other, and drops an interrupted pull-in whose milestone call never landed before its release shipped, so the item is judged by the start of the release after it rather than moved into the shipped one. A critical fix that joins while the stall rule readies or nudges it is admitted by that change, so a run that stops part-way through it never announces the fix's admission twice, nor sends it to the backlog after the stall comment said it stays; and a move out of the release that a person undid before its comment was posted leaves the item admitted, even when the run that posts the comment stops before its last write. The job refuses a board #739's migrate has not finished, one whose Status field lacks New or Blocked or still has Todo or Backlog, or that still holds an open release epic, naming `devops roadmap migrate` (#740).
  - Every rule reads one transition table (`TRANSITIONS` in `devops_cli.roadmap.reprioritize`). Each item the job moves, readies, admits or nudges gets a one-line reason comment; it never sets Priority, Value or Effort. It writes GitHub state only with `--confirm`; `--dry-run` lists each change with its reason. The MCP tool `roadmap_reprioritize` previews unless it is called with `dry_run=False`, and `is_due(changes, now, last_stall_check)` says when a change since the last poll makes the job due (#740).
- **Store Reads and Writes for the Release Rules (`devops_cli.roadmap`)**:
  - Both roadmap store adapters read blocked-by links, an issue's comments and its joins and leaves of releases, when an Item's Status last changed, open pull requests with their last update and last commit, a release's pull requests, whether its GitHub Release is published, the default branch and any branch, and create a branch, comment on an issue, keep a job's own marks (`Admitted`, `Left`, `Nudged`, `Pending`) in an Item's job record, also in the write that records a field's value (`set_field(..., marks=...)`), set or drop the value the job record holds for a field without setting it (`set_marks(..., recorded=..., forgotten=...)`), and keep the run record. Changes read from the issue events now carry the Item's Release and job record as they are when read. In the in-memory adapter a renamed milestone's issues and pull requests show its new title, as on GitHub, and a person can reopen an issue (#740).
- **`needs-split` Label (`.github/labels.yml`)**:
  - A person applies it to an item too big for one pull request, and reprioritization descopes the item until it is split (#740).
- **One Roadmap Store for Releases, Items and Board Fields (`devops_cli.roadmap`)**:
  - `RoadmapStore` reads and writes Releases, Items, Candidates, board fields and issue-event changes behind one interface, with a GitHub adapter over `gh` and an in-memory adapter for tests. Reads page through every result and raise rather than return an empty or partial result. Each Item write also records the value the store set in the board's `Job record` field (ADR 0002), so a later job can tell a person's change from its own (#768).
- **Why a Finding Has No Verdict (`devops review`, `profile.json`)**:
  - A finding the verifier was shown and its reply gave no verdict on carries the note `verifier-no-verdict`, and one whose verifier reply held no verdicts that could be read carries `verifier-reply-unparsed`. In session `20261001-224227`, 233 of 357 unverified findings carried no note, so a reader could not tell them apart (#846).
  - A finding the verifier judged and left unverified says why: `verifier-self-refutation` when its invalidation rested only on the finding's own claim and was withdrawn, and `verifier-inconclusive` when the verdict neither confirmed, refuted nor found a mitigation, or both confirmed and refuted. A finding the verifier was shown no longer stays unverified without a note. In session `20261002-214641`, 9 reported findings had no verdict and no note: 5 withdrawn self-refutations, 3 cut replies and 1 inconclusive verdict (#846).
  - A file whose verification failed is still reported, and each of its unverified findings carries `verification-unavailable` with the error's type, as when the verifier cannot be reached. Before, they were reported with no note (#846).
  - `profile.json` counts each unverified finding's note by kind under `verdict_distributions.verification_note`: `verifier-no-verdict`, `verifier-reply-unparsed`, `verifier-reply-cut`, `verifier-self-refutation`, `verifier-inconclusive`, `verification-unavailable`, `criteria-non-discriminating`, `other` for a note in words, and `none` for a finding verification never reached (#846).
  - A finding whose criteria passed both ways keeps the note `criteria-non-discriminating` when the verifier's verdict on it is inconclusive. A verdict, or one of the other notes above, replaces it (#846).
- **The Review Report Counts Timed-Out Criteria (`devops review path|branch|pr`, `devops_cli.ai.review.pipeline`)**:
  - `review.md` gains an "Executable Criteria" section after "Verdict Field Distributions", which counts the executable criteria of the session's candidate findings as Passed, Failed, Timed Out and Not Run. Only a criterion that ran to a non-zero exit is counted as failed: one stopped at its time limit is timed out, and one the sandbox could not start (no bubblewrap, a spawn error) or stopped for its output is not run, as the verdict already treated it. A session without executable criteria has no such section (#847).
  - `CriterionExecutionResult` and `HostSandboxResult` carry `timed_out`, set when the sandbox stopped the command at its limit, so `findings.json` and `candidates.json` record it for each criterion. Sessions saved earlier load with `timed_out` false (#847).
- **Judging Candidates the Review Dropped (`devops review findings --candidates`, `devops review verify --candidate`)**:
  - `devops review findings --candidates` lists candidates.json, every finding the review raised, including the ones verification invalidated, which never reach findings.json (#949).
  - `devops review verify --candidate <n>` gives a verdict on a candidate. A candidate marked VERIFIED or MITIGATED moves into findings.json with `verified_by` set to the adjudicator, and a later verdict on that candidate updates its copy there (#949).
  - A verdict given with `--index` is recorded on the candidate the finding reports in candidates.json as well, so `review findings --candidates` and review history never keep a verdict findings.json withdrew (#949).
  - A candidate's copy in findings.json is the finding of the same persona, title and location, or the copy a verdict moved, which names its candidate (`moved_from_candidate`). A verdict on one persona's candidate leaves alone the finding another persona reported with the same title at the same location, and a candidate its copy cannot tell apart from another, of the same persona, title, location and description, is refused with the number to judge with `--index` (#949).
  - A candidate whose defect findings.json already reports under another title, because consolidation merged it or kept another persona's report of it, is not added a second time. The command names that finding, to be judged with `--index` instead (#949).
- **Verdict Provenance (`devops review verify --adjudicator`, MCP `verify_finding`)**:
  - `--adjudicator {human,agent}` records who gave a verdict, `human` by default. The MCP `verify_finding` tool always records `agent`, since MCP clients are untrusted (#949).
  - Only a person's verdict teaches the learned catalog (INVALIDATED) or records a mitigation in the ledger (MITIGATED) (#949).
  - Review history ranks a subject's sessions by a person's verdicts, those on candidates kept out of findings.json included, then by findings with any verdict. An agent's verdict counts in neither, so it never raises its session above another of the same subject (#949).
  - An agent's verdict on a finding a person judged, through `--adjudicator agent` or the MCP tool, is refused, so an agent can neither replace a person's verdict nor withdraw what it recorded in the catalog and ledger (#949).
- **A Person's Verdict Suppresses That Claim in Later Reviews (`devops review verify`, `devops review`)**:
  - A person's INVALIDATED verdict records the one claim it disproved in the learned catalog (`.data/common_hallucinations.json`): the project the code belongs to, the file relative to its checkout, the first line its location cites, a hash of the lines it cites, each stripped of surrounding whitespace, and the identifiers of those lines that the title names, or the description when the title names none. A later review of that project invalidates a finding making the same claim at the same line with `deterministic:person_verdict` before any model is asked about it, whichever tool or persona raised it and however it is worded: a Semgrep `exec` finding a person judged suppresses Bandit's B102 at the same line, as review session `20261002-214641` reported it. A verdict on one `except Exception as err:` handler reaches no other handler that reads the same, and a verdict in one repository no other repository's identical code, though both share a data directory. A change to the cited lines, or an edit above them that moves them, raises the claim again (#950).
  - A suppression needs a code identifier. Python's keywords (`in`, `for`, `with`, ...) and common English words never count, and in a prose or configuration file, such as Markdown, YAML or JSON, only a name with an underscore or a camelCase hump does. A verdict on a finding that names no such identifier of its cited lines, or whose session recorded no code at its location, records no entry and says so; the verdict itself still stands (#950).
  - Every saved finding carries `cited_code`: the project, the file relative to its checkout, the first line and the lines its location cites as the review read them, at most 40, with secrets masked and only from a non-secret file inside the reviewed checkout. A verdict keys its claim on that record only, never on the file as it reads when the verdict is given, which may hold code the person never saw; a verdict on a session saved before this change records nothing (#950).
  - `devops review pr` writes the PR head into a temporary directory named after the checkout it runs in, so the review is shown that checkout's judged claims and suppresses them in the head's files (#950).
- **`devops ai prompt-eval --include-deterministic`**:
  - Counts the records a deterministic check labelled, which are now left out by default (#950).
- **Review Prompt Consistency Tests (`tests/test_review_prompt_consistency.py`)**:
  - A test fails when a prompt file under `ai/tasks/` or `ai/personas/` is loaded nowhere, when a prompt a reviewer reads names what `review.md` or the verifier calls a non-defect (`http://`, `NotImplementedError`, masking markers, `default_factory`, `os.kill(pid, 0)`) anywhere but the prompt that says so, and when any prompt asks for a CVE ID or lets a finding stand on an advisory identifier. Others pin the threat model and evidence bar below, a single masking-marker rule in the reviewer and the verifier that names only markers `mask_secrets` writes, a test rule that keeps a real credential or vulnerability in a test file reportable, an untrusted source in every security rule that requires a guard, a JSON reply format in the served `code_review_prompt` MCP prompt and no partial field list on a review page, which the reply schema answers, the reviewer's severity bands in the verifier, a measurement that runs the persona its baseline ran and counts only the review tool's masking markers as a failure, example replies without `HIGH`, `CRITICAL` or a confidence of 0.9 or more, and `.devops/review.md` within the 8,000 characters a review reads (#951).
- **Docs-Claims Tests for the Review Loop**:
  - Every metric `docs/SELF_IMPROVEMENT.md` names is a registered instrument, every `devops review` and `devops ai review` example in AGENTS.md, the hand-written pages under `docs/` and the knowledge base parses with the Typer app, and every path they name for the feedback dataset is the one the exporter writes (`tests/test_docs_review_loop.py`). Markdown is read with markdown-it-py, now a declared development dependency (#952).
- **A Deploy Path for Every LLM Manifest (`tests/test_k8s_llm_gateway.py`)**:
  - A test fails on any manifest under `k8s/llm` that no kustomization, deploy-stack manifest list or Helm release applies (#953).
- **Registered Telemetry Variables (`DEVOPS_CLI_TELEMETRY_ENABLED`, `DEVOPS_CLI_TELEMETRY_ENDPOINT`, `devops_cli.telemetry.tracer`)**:
  - The two variables set `telemetry.enabled` and `telemetry.endpoint` the way every other `DEVOPS_CLI_*` variable sets its key, and `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` list them. The tracer takes both from the settings, so a variable, the project config and the user config each count in the documented order (#956).
- **Grafana Service & Cluster Workload Graphs Sum & Average Lines (`k8s.monitoring.dashboards`)**:
  - Added dedicated, properly labeled `Total (Sum)` and `Average (Mean)` PromQL baseline lines to primary multi-series timeseries graphs across `sre-service.json`, `ingress-tunnel.json`, `k8s-views-nodes.json`, `k8s-views-pods.json`, and `llm-stack.json` (#968).
  - Maintained 100% static lint conformance with zero errors across all 12 shipped Grafana dashboards, verified by `devops grafana dashboards lint` and `test_dashboards_contain_properly_labeled_sum_and_average_lines` (#968).
- **RAG Queries Timed by Stage, and Qdrant Retries Counted (`devops_cli.ai.rag.retriever`, `devops_cli.ai.rag.qdrant`, `devops_cli.telemetry.instruments`)**:
  - Each RAG query observes `devops_cli_rag_query_duration_ms` once per stage under a `stage` label: `embedding` (the query's embedding request), `search` (the Qdrant searches), `ranking` (projection, hybrid fusion and reranking) and `total` (the whole query, which the unlabelled observation used to be). Each observation also carries `outcome` (`ok` or `error`): a stage that fails, such as an embedding that times out, records its time as `error`, so the panels show the tail it causes (#975).
  - `devops_cli_qdrant_retries_total` counts each Qdrant request retried after a transient error, by `operation` (the client method, such as `search_points`) and `error_type`. The Qdrant client raises every transport error as a `ResponseHandlingException`, so `error_type` is the class of the error inside it, such as `RemoteProtocolError` for a dropped keep-alive connection or `ReadTimeout` for a request that waited out its timeout, and not the wrapper's class, which every network error shared. Collection and file names stay in the log, not the labels (#975).
- **Per-Stage RAG Latency and Qdrant Retry Panels (`k8s/monitoring/dashboards/devops-cli.json`)**:
  - The dashboard's first row gains "RAG Query Stage Latency (p95)", the p95 of `embedding`, `search` and `ranking` over the last hour, and "Qdrant Retries by Operation and Error", retries per hour. The rows below move down one panel height (#975).
- **Pyroscope UI Endpoints, Port-Forwarding, and Grafana Dashboards (`k8s.monitoring`)**:
  - Added `--pyroscope-port` (default 4040) to `devops k8s port-forward` and enabled continuous profiling forwarding for `svc/pyroscope:4040` (#977).
  - Announced `Pyroscope UI: http://localhost:4040 (namespace: monitoring)` in `devops k8s deploy-stack` connection summary (#977).
  - Added `pyroscope.url` service discovery to `devops k8s configure-urls` for cluster-native proxy and nodeport addressing (#977).
  - Added dedicated Continuous Profiling dashboard (`pyroscope.json`, UID `devops-pyroscope`) and integrated Pyroscope CPU and Memory flamegraph panels into `sre-service.json` (#977).
- **The Whole Review on the Terminal (`devops review path|branch|pr --full`)**:
  - `--full` prints every finding with its detail panel, every dependency and every network reference, as reviews printed them before (#987).
- **Findings by Severity (`devops review findings --severity`)**:
  - `--severity` lists the findings of one severity and is repeatable. It takes any spelling a review accepts, so `informational` means INFO. Each finding keeps its number in findings.json, the one `devops review verify --index` takes, and `--severity` combines with the status filters and `--candidates` (#987).
- **Review Recall Set (`tests/fixtures/review_recall/recall_set.json`, `docs/SELF_IMPROVEMENT.md`)**:
  - The known real findings that review session `20261002-205520` did not generate, plus the two broad excepts in `ai/spend/pricing.py` it did, each with its file, revision, the line range of the defective construct, class and tracking issue. Tests in `tests/test_review_prompt_consistency.py` fail when no prompt that reaches a file names its class (the DevSecOps persona's *Where to Look*, or the page prompt for the file's kind), when the page prompt a file gets carries a rule that silenced the persona, when the persona keeps a rule that silenced it or lacks one this change restored, when a restored class may be reported above MEDIUM or LOW, and, in a clone that holds the revision, when a cited range no longer holds the finding's evidence (#1015).
  - `docs/SELF_IMPROVEMENT.md` describes how a person scores recall on the set beside #951's corpus A/B: three fresh reviews (`--no-cache`, `--no-static-scan`) of the set's files per arm, a script that counts the samples that found and that reported each finding and lists every other finding on the set's files for labelling, a bar of 2 of 3 samples for each Network Exposure finding that counts only matches describing the set's defect, with the other classes counted, not gated, a precision guard on the files session `20261002-205520` reported findings on, and a review from both arms of the NetworkPolicies, Ingress and Service manifests and security documents the restored rules reach (#1015).
- **A Background Tier Group, `devops-background` (`k8s/llm/gateway/configmap.yaml`)**:
  - `devops-background` is the only chat group with a deployment on ollama-48gib-slow: `qwen3-coder:30b`, with a 1,100 s timeout, under the review client's 1,200 s read timeout so a call the client abandoned frees the tier's one slot, and no gateway retries. It sets no `max_input_tokens`, because LiteLLM would apply that window to every `qwen3-coder:30b` deployment. `devops-review` falls back to it once its own retries fail, gateway timeouts included. `devops-chat` does not, because fallbacks chain and compose or reasoning failures would reach it through `devops-coder` (#1064).
  - `k8s/README.md` shows how `devops review path --watch` (analysis, verification and compose), `devops ai pipeline`, `devops ai agents` and `devops ai analyze` use it through environment overrides with `DEVOPS_CLI_AI_MAX_RETRIES=1`, never through `config.yaml` (#1064).
- **The Review Profile Keeps Why Each Analyzer Failed and How Long Each Ran (`profile.json`)**:
  - `static_analyzer_reasons` holds the reason review.md gives for each analyzer that failed, and `static_analyzer_seconds` how many seconds each analyzer's scans ran (#1079).
- **Each Node's Journal Reaches Loki Through the Alloy Log Collector (`k8s/monitoring/k8s-monitoring-values.yaml`)**:
  - The chart's node logs feature (`nodeLogs`) runs on the `alloy-logs` DaemonSet that already ships pod logs and reads `/var/log/journal` on every node, so no agent is installed on a host. It keeps kernel lines at every priority (GPU Xid errors, machine checks, thermal events), the `k3s`, `k3s-agent`, `nvidia-power-limit`, `containerd` and `systemd-journald` units and systemd's own start, stop, exit and restart lines about them at info and above, and every other line at warning and above. Lines carry `job="integrations/kubernetes/journal"`, `instance` (the node), `unit`, `transport` and `level`, with `boot_id` as structured metadata. On 2026-10-03 all four nodes lost power together three times, and the timeline had to be rebuilt from each host's local journal (#1080).
  - Each unit may send 1 line/s after a burst of 10,000, which covers a boot and the 8 hours the reader goes back after a restart; kernel lines have no limit. Alloy counts the lines the limit drops per unit in `loki_process_dropped_lines_by_label_total` on its own `/metrics`, which Prometheus does not scrape. Measured on the four live nodes' journals for 2026-10-01 and 2026-10-02, the filter keeps 6.7 MB of text a day across the cluster, 7.5 MB on the busiest day, about 0.6% of the 1.27 GB a day Loki already takes in. The busiest unit peaked at 1,091 lines in a minute and 2,887 in an hour, inside the limit. The budget is 20 MB of text a day (#1080).
  - Loki keeps journal lines for 30 days only once #550's compactor retention (`retention_period: 720h` with `compactor.retention_enabled`) is applied; until then Loki deletes nothing by age. At the 5.7 times compression of Loki's current chunks, the 6.7 MB of text a day is about 1.2 MB a day on disk, 36 MB over 30 days, and the 20 MB a day budget at most about 106 MB (#1080).
- **Prometheus Keeps the Series That Explain a Host Failure (`k8s/monitoring/k8s-monitoring-values.yaml`)**:
  - The host metrics allowlist adds `node_boot_time_seconds`, `node_hwmon_temp_celsius`, `node_hwmon_chip_names`, `node_pressure_.*`, `node_edac_correctable_errors_total`, `node_edac_uncorrectable_errors_total`, `node_nvme_info` and `node_systemd_unit_state`, and names `node_filesystem_avail_bytes` and `node_filesystem_size_bytes`, which the chart's default list already keeps (#1080).
  - node-exporter's systemd collector, off by default, reports only the units above. It reaches the host's D-Bus socket through the node root the chart already mounts at `/host/root` (`DBUS_SYSTEM_BUS_ADDRESS`). The chart's filesystem-type exclusion is repeated, because Helm replaces the argument list (#1080).
  - Counted from each node's exporter before the change, the list adds 41 to 66 series per node, 207 across the four live nodes, against a budget of 100 per node: 0.3% of Prometheus's 63,864 head series and 3.5 of its 874 samples/s, about 18 MB over 30 days. Prometheus keeps 30 days by time and has no size cap, so the new series keep 30 days of history from the apply (#1080).

### Changed
- **One JSON Shape for Every Corpus Score (`devops review corpus score --json`)**:
  - `--json` and the kept run's results are the arm's score for any number of runs. The single-session figures moved under `scores[0]` (#413).
- **Loki's Volume Holds 30 Days of Logs (`k8s/logging/loki-values.yaml`)**:
  - `singleBinary.persistence.size` is `20Gi`, up from `2Gi`. Measured on 2026-10-03, pod logs arrived at 0.5 to 1.3 GB a day from 2026-09-30 on, 1.3 GB on the busiest day, and are stored at about 11:1. The host journals that #1080 adds are estimated from journal file growth at about 0.04 GB a day, and the sizing allows 0.2 GB a day for them. 30 days take about 4.5 GB, and about 9.4 GB at a pessimistic 5:1 with every day as busy as the busiest (#550).
  - Kubernetes does not let an upgrade change a StatefulSet's `volumeClaimTemplates`, and local-path cannot expand a claim in place. Applying the new size takes deleting the StatefulSet with `--cascade=orphan` and rebinding the existing volume to the new claim, which keeps the logs already stored. The task file lists the commands (#550).
- **Prometheus Keeps 30 Days Under a Size Cap That Does Not Bind First (`k8s/monitoring/prometheus-values.yaml`)**:
  - `server.retentionSize: 16GB` (16 GiB, 80% of the 20Gi volume) caps the TSDB, and `server.retention: 30d` still decides what is deleted. Measured on 2026-10-03, 30 days take about 5 GB, and #1080's roughly 270 host series add under 0.1 GB (#550).
- **The `structural-invariants` Hook Checks Nesting Only (`.pre-commit-config.yaml`, `devops_cli.security.structural_invariants`)**:
  - The hook no longer counts complexity or prints its "Not blocking" complexity note, because complexity is now Ruff's `C901`. `breaches` and `check_structural_invariants` return only the nesting breaches and take no `max_complexity`, `measure` returns a function's nesting depth, and `MAX_COMPLEXITY` is gone. Nesting is measured as before: the old and new measures agree on all 14,749 functions in `src/` and `tests/` (#586).
  - `measure` walks a function with its own stack instead of recursing, so a long expression such as a 3,000-term sum is measured instead of stopping the hook with a `RecursionError` traceback. The released hook already failed that way at 3,000 terms. A parser stack overflow is reported as a file the hook could not parse (#586).
  - Two tests are removed. `test_complexity_is_reported_without_blocking` started a hook subprocess, and `test_filesystem_get_tools_complexity` guarded a function that `C901` now covers (#586).
- **LLM Spans Write the GenAI Conventions' Keys, Each Once (`devops_cli.ai.client`, `devops_cli.ai.direct`)**:
  - `ai.llm.dispatch` and the stream span are CLIENT spans of the conventions' inference type, with `gen_ai.operation.name` (`chat`), `gen_ai.provider.name`, `gen_ai.request.model`, and `server.address` and `server.port` when one backend host served the request. The stream span also sets `gen_ai.request.stream`. Token usage, the response model and finish reasons are written only on `ai.llm.dispatch`, so a request's usage is counted once, and no old key is written beside its replacement (#588).
  - Saved Jaeger or Logfire queries need these renames. Keys the conventions do not define moved under `llm.*` (#588):
    - span `gen_ai.chat` → `ai.llm.chat`, span `gen_ai.stream` → `ai.llm.stream`
    - `gen_ai.system` → `gen_ai.provider.name`, with `claude` written as `anthropic`
    - `gen_ai.usage.prompt_tokens` → `gen_ai.usage.input_tokens`, `gen_ai.usage.completion_tokens` → `gen_ai.usage.output_tokens`
    - `gen_ai.usage.total_tokens` → removed (it is input plus output)
    - `gen_ai.server.address`, which held the backend description → `server.address` (the host) and `server.port`
    - `gen_ai.response.model`, which held the backend description or `cache` → the model the provider reports, unset when unknown
    - `gen_ai.ttft_seconds`, `gen_ai.time_to_first_token_ms` → `gen_ai.response.time_to_first_chunk` (seconds)
    - `gen_ai.tokens_per_second`, `gen_ai.token_rate_tok_per_sec` → `llm.tokens_per_second`
    - `gen_ai.wall_seconds` → `llm.wall_seconds`, `gen_ai.processing_seconds` → `llm.processing_seconds`
    - `gen_ai.duration_seconds` → removed with `record_llm_metrics`
    - `gen_ai.server.served_by` → `llm.served_by`
    - `gen_ai.usage.cost_usd` → `llm.usage.cost_usd`
    - `gen_ai.cached` → `llm.cached`
    - `gen_ai.request.priority` → `llm.request.priority`
    - `gen_ai.request.enable_thinking`, `gen_ai.enable_thinking` → `llm.request.enable_thinking`
    - `gen_ai.request.message_count`, `gen_ai.messages_count` → `llm.request.message_count`
    - `gen_ai.request.system_prompt_length` → `llm.request.system_prompt_length`
    - `gen_ai.prompt_preview` → `llm.prompt_preview`, `gen_ai.response_preview` → `llm.response_preview`
    - `gen_ai.thinking` → `llm.response.thinking`
    - `gen_ai.sanitize` → `llm.stream.sanitize`
    - `gen_ai.stream_chunks_count` → `llm.stream.chunk_count`
- **A Stream Ends Only on Its Provider's Final Frame (`devops ai chat`, `devops_cli.ai.client`)**:
  - OpenAI-compatible and Anthropic streams are read with httpx2's `EventSource`, which splits lines on CR and LF alone, and Ollama streams are split on LF from the raw bytes. A delta holding a raw U+2028, which the old line reader split in two and dropped, now arrives intact. Each event, and each unterminated Ollama line, is limited to 1 MiB (`DEFAULT_AI_STREAM_MAX_EVENT_BYTES`), and the whole stream is still limited to 50 MiB. Chunks are still yielded as they arrive (#599).
  - A stream is complete on a chunk with a finish reason or `[DONE]` (OpenAI-compatible), `message_stop` (Anthropic) or `done: true` (Ollama). A stream that ends before that, an error frame, and an event stream sent with another content type raise `AIClientError`, where each used to return its partial text as a whole reply. An error frame's message is masked and cut to 256 characters. A stream cut after it yielded output is not replayed on the next Ollama host (#599).
  - A stream that fails after yielding output records its spend with finish reason `error`, then re-raises. One that fails before its first chunk records nothing, as a failed non-streamed call records nothing (#599).
- **`devops review stats` Counts Each Review Subject Once (`devops review stats`)**:
  - Its tables count one session per subject, so a re-review or each `devops review benchmark` run no longer adds its findings again. `Total Sessions` is replaced by `Sessions: N (counted C: R repeat sessions collapsed, T target-only, U unkeyed)`. Its findings still come from findings.json, the findings each session reported (#607).
- **A Task File Ticks a Box Only for Work That Is Done (`docs/agent/tasks/`, `AGENTS.md`)**:
  - `tests/test_agent_task_files.py` fails on an unchecked box outside a code fence. Work not done is a plain bullet naming its follow-up issue, and a check only a person can run is a plain bullet starting "Pending a person:". The 17 task files that held unchecked boxes are brought into line, and `AGENTS.md` no longer asks for typed verification results: the PR's passing checks are the verification (#704).
- **The PR Template and the Release PR Body Ask Only What No Check Decides (`.github/pull_request_template.md`, `devops release`)**:
  - The template asks for a summary, the type of change, the base branch, `Closes #<issue>` and the task file. Its 15-box quality-gate checklist is gone, and so is the example closing reference in a comment, which read as closing that issue in any body that kept it (#704).
  - The release PR body no longer carries the seven quality boxes it ticked on every ready release PR without reading anything (#704).
- **Board Statuses and Fields Follow ADR 0001 (`.github/project-template.json`, `devops gh project sync`)**:
  - Status options are New, Ready, In Progress, In Review, Done and Blocked. Category and the Milestone text field are gone, and the Value vs Effort view groups by Value. An unset Status and the `status/backlog` label now read as New, and reconcile no longer writes the Milestone field the board mirrors (#739).
  - `devops gh project sync` creates missing fields and never edits an existing field's options. GitHub gives every option it is sent a new id, so once the template changed its option request would have cleared Status on every card. No command edits an existing board's options; a person makes the edits `devops roadmap migrate` lists in the board's field settings, which keep ids (#739).
  - `devops gh project workflows list` expects New on add and reopen and In Review on a linked pull request, and no longer asks for the auto-add, auto-close or auto-archive workflows (#739).
  - `docs/ROADMAP.md` carries a banner: GitHub is its source, `devops roadmap render` regenerates it at the next cut, and work is added by opening an issue (#739).
- **Readiness Blocks a PR Into a Release Branch That Closes Another Release's Item (`devops pr check-readiness`)**:
  - A PR into `release/vX.Y.Z` is blocked when the one issue it closes is not in release vX.Y.Z. The blocker names the issue and the release it is in, or says it is in the backlog. PRs into the default branch, the release PR and release-process PRs are not affected (#740).
- **A Job Record the Store Can't Read Stops the Read (`devops_cli.roadmap.github_store`)**:
  - A card's job record that is not a JSON object, or gives a key the store knows a value that is not text, now fails the read and names the card, where it used to read as empty, which made an admitted item look newly added. A key this version doesn't know, such as one a newer version writes, is left out of the read and kept by every write (#740).
- **A Field Write Records the Job's Value First (`devops_cli.roadmap.github_store`)**:
  - The GitHub adapter's `set_field` writes the job record, with the value and any marks given with it, before it sets the field, so a write that stops between GitHub's two calls never leaves a field the job changed with no record of it (#740).
- **`devops gh milestones edit` and `close` Take a Version (`devops gh milestones`)**:
  - Both take a version, with or without the leading `v`, and no longer a milestone number. The milestone commands and the milestone close after `devops release tag --push` run on the roadmap store (#768).
- **A Mitigated Finding Is Not a Verified One (`devops review path|branch|pr`, `devops review verify`, `devops_cli.ai.review.verdicts`)**:
  - A MITIGATED verdict, a model's or a person's, sets `verified=False`, and so does the merge of two findings whose best verdict is MITIGATED. MITIGATED defaulted to verified, so 11 of the 28 mitigations in review session `20261001-224227` counted as verified defects (#845).
- **The Verifier Is Told What a Mitigation Needs (`devops review path|branch|pr`, `ai/tasks/verify_finding_system.md`)**:
  - The verifier's instructions say a perimeter file is a repository-relative path to code or configuration in the reviewed tree, never documentation such as the project's conventions, that the mechanism names an identifier in backticks which a perimeter file or the finding's file holds, and that a mechanism describing the defect is no mitigation. The prompt digest changes, so cached verifier replies are not replayed (#845).
- **Criteria Settle a Verdict Only on Evidence About the Cited Code (`devops review`)**:
  - A passing verification or invalidation criterion settles a verdict only when it runs the code the finding cites and checks the outcome. A `python -c` script counts when it checks a value from the cited code: a name it imports from the cited module, the cited file read and parsed (`json.loads`, `yaml.safe_load`, `tomllib.loads`), or anything computed from either. The check is an `assert` over such a value, a `raise` or failing exit under a condition over one, or `sys.exit`, `exit` or `raise SystemExit` of a comparison or `not` over one. In session `20261001-224227`, 36 findings were VERIFIED by criteria and none of their 37 passing commands checked the cited code; one was a regex echoed against a literal, on a CRITICAL finding that cited CVE-2021-44228. Replayed with their recorded results, all 36 of that session's criteria-VERIFIED findings and 59 of its 61 criteria-INVALIDATED findings now go to the verifier (#846).
  - These never count: `grep`, `git grep`, `git log`, `wc`, `cat`, `head`, `tail`, `find` and every other command; a script that inspects code (`hasattr`, `inspect.getsource`, `__code__`) instead of running it; a search of a cited file's text (`'os.system' in Path('app.py').read_text()`, `re.search` over it), so a cited Python file counts only through its import; a test that something exists (`assert f`, `f is not None`, `Path(...).exists()`, `os.path.isfile(...)`); a check that does not depend on the cited code (`import app; assert 1 == 1`, `raise SystemExit(0)`, `exit(0)`); and `sys.exit(f(...))`, which exits 0 whenever `f` returns None (#846).
  - A passing invalidation criterion no longer dismisses a finding whatever it runs. A grep that found the line the finding cites settled INVALIDATED, a verdict the verifier never saw (#846).
  - A command that does not count is still recorded in `criteria_execution_results` and leaves the finding to the verifier. Only commands that count are listed in `verified_criteria_matched` and `invalidated_criteria_matched`, and criteria that settle nothing no longer give the finding a confidence (#846).
  - A verification and an invalidation criterion that both pass, whether or not they count, cannot tell the defect from its absence: the finding stays unverified with the note `criteria-non-discriminating` and goes to the verifier. In session `20261001-224227`, 215 findings had criteria that passed both ways (#846).
  - Inspection is read from the script's syntax tree instead of matched as text, so `content_type(...)` is no longer taken for `type(...)` (#846).
- **The Verifier Judges the Claim, Not the Pipeline's State (`devops review`)**:
  - The verifier is shown an allowlist of each finding's fields: its number, severity, location, title, description, fix, references, category, both criteria lists as written, and the observed and expected values. It is no longer shown the reviewer's confidence, status, reportability or reasoning, nor the criteria results with their run times. Verifying a finding again sends the same prompt byte for byte, so with the response cache on, verifying an unchanged file again replays the first reply instead of reaching the model. The run times made every prompt with executed criteria new, and the branch reviews of release/v0.2.25 replayed only 3 and 6 verifier replies. A field added to findings later stays out of the verifier prompt until it is added to the allowlist (#846).
  - A refutation cites a line only through a citation key such as `citation_line`. The `location` a verdict repeats and a line number in its reason no longer count, so a refutation without a citation leaves the finding unverified (#846).
  - A refutation of the finding's criteria rather than its claim (its reason calls them tautological, or says they only confirm the code exists) that cites no line leaves the finding unverified, noting why (#846).
- **Python Criteria Run Up to 30 s (`devops review path|branch|pr`, `devops_cli.ai.review.review_environment`)**:
  - A `python` or `python3` criterion runs for up to 30 s (`DEFAULT_CRITERIA_PYTHON_TIMEOUT_SECONDS`), since it imports the reviewed code; `grep`, `git` and the other commands keep 5 s. In the saved review sessions, 1,353 of 4,027 python criterion runs (34%) hit the 5 s limit, most of them while still importing the code they were to check (#847).
  - The limit was measured by replaying the 1,115 distinct python criteria that hit 5 s in 14 saved sessions, offline through the sandbox with the repository's `.venv` first on `PATH`, four at a time: half finished within 6.2 s, 95% within 15.4 s and 99% within 22.5 s, and 1,111 (99.6%) within 30 s. Two more finished by 36 s and two ran to the 60 s cap. A random 60 of them, run one at a time on a quiet host, all finished within 8.8 s, so most of the time past that is criteria contending with each other (#847).
  - A criterion that now finishes within the longer limit settles a verdict only as the evidence rule allows (#846): one that prints what the cited code returns still settles nothing, and one that asserts over it counts as evidence, which settles INVALIDATED as an invalidation criterion and leaves the finding to the verifier as a verification criterion. With the 30 s limit alone, a print-only criterion replayed at 6.8 s on a made-up HIGH finding ended VERIFIED with confidence 1.0 (#847).
- **Scanner Errors Become a Failed Outcome in One Place (`devops_cli.security.registry`)**:
  - `ScannerRegistry.scan_all` takes `names`, the scanners to run, every registered one by default, and `devops scan report` runs through it instead of its own loop. A scanner that raises is recorded as failed there, with its error as the reason. The `image` parameter is gone: `image=` is passed on to each scanner with the other keyword arguments (#915).
- **Item PRs Add a Changelog Fragment and Leave `CHANGELOG.md` and `docs/ROADMAP.md` to the Cut (`AGENTS.md`, `RELEASE_CYCLE.md`, `docs/agent/tasks/README.md`, `.github/pull_request_template.md`)**:
  - The rules say to add `changelog.d/<issue>.md` and not to edit `CHANGELOG.md` or `docs/ROADMAP.md` in an item PR, and that release-process PRs use `chore/open-vX.Y.Z` or `chore/cut-vX.Y.Z` branches. The entries that were under `## [Unreleased]` are now `changelog.d/593.md`, `changelog.d/704.md`, `changelog.d/739.md` and `changelog.d/768.md`, text unchanged (#933).
- **Review Reports Lead With What Was Verified (`devops review path|branch|pr`, `devops_cli.ai.review.stages.reporting`)**:
  - Findings rank reportable first, then VERIFIED, UNVERIFIED and MITIGATED, then by severity, location and title. A model's confidence no longer ranks them: in session `20261001-224227` UNVERIFIED findings at confidence 1.0 ranked above VERIFIED ones (#948).
  - The executive summary counts the findings by status, each status with its severities, and lists the findings verification never reached and the MITIGATED ones apart. The report's summary section and the terminal's Review Summary table count them the same way. The session's headline read "563 reportable findings (21 Critical, 263 High)" across every status (#948).
  - The headline names the defect classes that recur among VERIFIED findings, most severe first, then most frequent, the first three by name. A class seen once, a finding title or a CVE is never a theme, and Key Bad Patterns gives one line per recurring class. The headline used to name the first reference or title of the first-sorted findings, so CVE-2021-44228 on an UNVERIFIED finding headlined the session, and Key Bad Patterns ran to 280 bullets, 257 of them for a single finding (#948).
  - The analyzer line is computed from the scan: the analyzers that ran, the critical findings they reported, and those on built-in patterns only, failed or not installed. It was a literal, "with 0 critical findings", while Bandit, Semgrep and Pluto had failed, and it counted Gitleaks among the analyzers executed when only its built-in patterns ran (#948).
- **One Defect Taxonomy (`devops_cli.ai.review_schema`, `devops review stats`)**:
  - A finding's category is the CWE it cites, in its category or its references, as `CWE-<n>`, or else a class of the closed `DefectClass` enum named by the category's words or, with no category, the title's. The original is kept as `category_raw`. The persona has written no category since #951, so the pipeline assigns one. Session `20261001-224227`'s 148 category strings fall into 27 classes (#948).
  - The report's themes, its category baseline table and `devops review stats` group findings by one function, `resolve_finding_category`, which reads a finding saved by an earlier session the same way (#948).
- **Severities Capped by Their Evidence (`devops review path|branch|pr`)**:
  - Once verdicts are final, CRITICAL requires VERIFIED; a title hedged with "Potential", "May", "Could" or the like is MEDIUM at most; and a finding in a test or a document is LOW at most unless it concerns a verified secret, which a secret scanner's match counts as. A capped finding keeps the severity it was given as `severity_raw` in findings.json and candidates.json. Replayed over session `20261001-224227`, the 563 reported findings go from 21 CRITICAL and 263 HIGH to 5 and 165 (#948).
  - The caps apply when the report is written. A later verdict through `devops review verify` changes a finding's status, not its severity (#948).
  - A scanner's absolute path is read from the repository root, so a checkout under a directory named `tests` does not make every scanner finding a test finding (#948).
- **Planning Documents and Generated References Stay Off Persona Pages (`devops review path|branch|pr`)**:
  - Path, branch and pull request reviews keep `docs/ROADMAP.md`, `CHANGELOG.md`, `changelog.d/`, `docs/agent/tasks/`, `docs/adr/`, `docs/commands/*.md` and `docs/CLI_REFERENCE.md` off persona pages, as they kept lockfiles, with one predicate for all three. In the branch reviews of release/v0.2.25 those paths took 24-27% of the persona pages, and none of the findings raised on them held up. A file named as a path review's target is still reviewed (#948).
  - Gitleaks still reads every file kept off the pages, lockfiles included, and Semgrep does not. A secret it finds there is reported against that file at its severity, HIGH at most until verified, and never capped as a document finding (#948).
  - The verifier of a finding in such a file is sent the numbered lines around what the finding cites, or around the package a Trivy location such as `uv.lock:requests` names, never the whole file: this repository's uv.lock is 558 kB (#948).
- **Stable Finding Numbers (`devops review findings`, `devops review verify`, MCP `verify_finding`)**:
  - `review findings` numbers each finding by its place in findings.json, or in candidates.json with `--candidates`, whatever status filter it applies, and `verify --index` takes that number. Before, a filtered list was renumbered from 1, so `verify --index` put the verdict on a different finding (#949).
  - The MCP `verify_finding` tool counts from 1, as the CLI does, and refuses 0 (#949).
  - `verify --title` refuses a substring that more than one title contains, naming their numbers, instead of judging the first match. Naming more than one of `--index`, `--title` and `--candidate` is refused (#949).
- **No Default Verdict (`devops review verify`)**:
  - `--status` is required. It defaulted to INVALIDATED, so one careless call both invalidated a finding and taught the learned catalog (#949).
- **The Personas Are Shown What People Disproved (`devops review`)**:
  - The false positives in the persona prompt are the claims people judged in reviews of the target repository, the most often judged first, under "reported against this codebase". A repository with none is shown the curated builtin entries under their own heading, which no longer says they were reported against it, and another repository's judged claims are never shown. A judged claim's title and reason are masked and their prompt boundary tags escaped. The new heading prompts change the prompt digest (#950).
- **The Learned Catalog Learns Only From a Person (`devops_cli.ai.review.common_hallucinations`)**:
  - The deterministic checks (syntax, missing symbol, missing header, None dereference, catalog match) no longer write to the catalog, and a builtin catalog match is matched against the shipped entries only. Registering anything but a claim a person judged is refused (#950).
  - The ledger's writers take turns on a lock beside it (`common_hallucinations.json.lock`), and a ledger that cannot be read, or a record that does not validate, logs a warning instead of a debug message (#950).
- **A Verdict Withdraws What It No Longer Stands Behind (`devops review verify`)**:
  - Any verdict but INVALIDATED withdraws the learned-catalog entry a person's earlier INVALIDATED verdict on the finding recorded, and any but MITIGATED the ledger entry of an earlier MITIGATED one. Only a reset to UNVERIFIED withdrew them, so a finding a person judged INVALIDATED and then VERIFIED would have stayed suppressed in every later review as "A person judged this claim INVALIDATED" (#950).
- **`devops ai benchmark --type` Refuses an Unknown Type**:
  - `--type` (`--mode`) takes `auto`, `chat` or `embedding` and refuses anything else. `--type suite`, which this release removes, and any other unknown value ran the chat tasks benchmark, which calls models; the `embed` and `embeddings` spellings are refused as well (#950).
- **`devops review export-feedback` Appends to One Dataset**:
  - The export appends to the configured dataset, `.data/feedback_dataset.jsonl` (`data.feedback_dataset_path`), skipping each finding whose session, persona, location, title and verdict the dataset already holds, so a later verdict on a finding is appended rather than lost. It wrote the file over each time (#950).
  - It reads each session's candidates.json beside findings.json, where the findings the review kept out of its report keep their verdicts, so the default `--status INVALIDATED` sees the review's invalidations (#950).
  - Each record carries the session's `subject`, and the finding's `category`, `references` and `cited_excerpt`, the excerpt of its cited code (#950).
  - An export that finds nothing new leaves the dataset as it was, and says so (#950).
  - The documentation, the AI and RAG cheatsheet among it, names that one path; it named `.data/agent/`, `.data/reviews/` and `.data/feedback.jsonl` variants (#950).
- **`devops ai prompt-eval` Reports per Labeller**:
  - Each count is reported for each labeller (`human`, `agent`, `llm`, `criteria`, `unknown`, ...), and a record a deterministic check labelled (`deterministic:*`) is counted as excluded: scoring the deterministic layer against its own labels is circular. A claim a person judged is left out of the replay, so the layer is not credited with repeating that person's label (#950).
- **Review Prompts State a Threat Model and an Evidence Bar (`devops review`)**:
  - The DevSecOps persona says what is untrusted (network and fetched content, model output, pull request and issue text, repositories under review, Kubernetes and cloud API data, server requests, MCP and tool-call arguments) and what is trusted (the operator, their config files, environment and arguments, and values the code builds). A vulnerability is a quoted source, the sink it reaches and the missing check between them; the persona returns no finding when it cannot quote them. It no longer asks for CVE IDs: dependency advisories come from the scanners (#951).
  - Severity follows reachability. CRITICAL needs an untrusted input that reaches code execution, credential disclosure or a write outside its root, with every step quoted; a missing guard on trusted input is LOW where the project's conventions require it, and otherwise no finding. Trusted and untrusted input are what the project's conventions say; where they give no threat model, the shared prompt states a default one, so every persona's severity bands are defined (#951).
  - The error-detail rule (CWE-209) asks reviewers to bound untrusted strings rather than every caller-supplied one, and the verifier verifies an untrusted string or argument that reaches an exception detail, a log or a file path without its check, instead of verifying with no source and no sink (#951).
  - Reviewers report only what they can see. The rule it replaces let them report an unchecked assumption at a lower confidence, and in session `20261001-224227` all 357 findings verification left unverified were reported. A fix is replacement code for the cited lines, `observed_value` is copied from them, and an executable criterion imports the cited code and asserts the outcome; a command that finds, imports or prints code is a sentence with `"executable": false` (#951).
  - A finding about a test itself is only a test that cannot fail, while a real credential or a genuine vulnerability in a test file is still reported, as the verifier's rule for tests and its "never invalidate" rule now both say. A documentation finding is a statement the code contradicts, a broken relative link, or a command, option or key that does not exist; roadmaps, changelogs, task files and decision records get none. The configuration and persona checklists name defects instead of mandates, and no longer ask for `http://` to be flagged, which `review.md` and the verifier call intended inside a cluster (#951).
  - The verifier verifies a finding only when it can quote the defective line, and for a security claim the untrusted source and the sink. It refutes a claim that needs an attacker to control the operator's own input unless the project's conventions require the guard, refutes a finding that a check in the shown code makes impossible, and leaves a finding unverified when the deciding code is not shown. Its two rules on masking markers, which disagreed, are one, and it names only the markers the review tool writes, of the form `<masked-kind>`. A claim that one is invalid syntax, an undefined name or a broken value is refuted, and a claim that the value behind it is a real secret stands. A bare `<masked>`, `***REDACTED***` or any other mask is the file's own text, so a generated page that shows `<masked>` as a default is no longer taken for a redaction (#951).
  - The verifier no longer lets a dependency claim stand on a "real, lookup-able" CVE or GHSA identifier, which it cannot look up. Advisories come from the scanners, whose findings carry the identifier in a bracketed title at a lockfile; any other finding that rests on an advisory identifier, against a dependency or against code, is refuted. The placeholder-advisory verdict gives the same reason (#951).
  - The verifier rates severity on the reviewer's bands, which it had not been given although its severity replaces the reviewer's (#951).
  - The reviewer's and the verifier's example replies no longer show `HIGH` or a confidence of `0.95`. The verifier's verified example, an untrusted path traversal with every step quoted, lists every severity instead of naming one the bands do not give it (#951).
  - The `code_review_prompt` MCP prompt, which serves the code review rules on their own without the pipeline's reply schema, asks for one JSON object of findings (`severity`, `location`, `title`, `description`, `fix`) and a summary. The format is added where MCP composes the prompt, so the pipeline's review pages, answered in the reply schema, name no field list of their own (#951).
  - The prompt digest changes, so reviews from before and after this change are separate arms of a prompt benchmark. `docs/SELF_IMPROVEMENT.md` records the A/B measurement, which a person runs, with each arm reviewing the corpus under its own `.devops/review.md` and with the default DevSecOps persona, the only one the baseline session ran. Its `masked` failure count takes only findings about the review tool's `<masked-kind>` markers, and lists findings about a bare `<masked>`, the file's own text, apart as the known-positive check (#951).
- **`devops ai chat` Cites Advisories Only From Tool Output**:
  - The chat prompt no longer asks for CVE identifiers (#951).
- **The Persona Reply Schema Holds Only What a Reviewer Writes (`devops_cli.ai.review_schema`)**:
  - The fields of `Finding` and `ReviewResult` that the pipeline owns (verdicts, criteria results, citations, confidence, the recommendation, scanner and dependency data) are left out of their JSON schema, which the persona system prompt carries as the reply format. The schema falls from 8,220 to 1,674 characters. Replies and saved findings still parse every field. Reviewers are no longer asked for a `category`, so per-category metrics infer it (#951).
- **devops-cli's Own Review Exemptions Live in `.devops/review.md`**:
  - `.devops/review.md` gains this repository's trusted and untrusted inputs, where a tree devops-cli reviews, scans, analyzes or ingests is untrusted even when it is the user's own, and the facts about its own code that `review.md` and the verifier sent to every project's review: model backend URLs, offline URL parsing, empty ledgers, GraphQL payloads, Prometheus queries, hardware daemonsets, LLM egress policies, decommissioned backends, Jaeger v2, metric labels, Tenacity retries and the shared client pool. Its NodePort rule, which named a manifest path that does not exist, covers every NodePort in the `k8s/` manifests and Helm values, as the verifier's dropped rule did. The shared rule that GitHub logins need no case folding is dropped rather than moved: logins are case-insensitive, so it hid real bugs (#951).
- **`docs/SELF_IMPROVEMENT.md` Describes the Review Loop as It Runs**:
  - Section 1 follows a review through its six stages, the verdicts `devops review verify` records, what a person's verdict teaches (the learned catalog, the mitigations ledger, review history), the feedback dataset and its one reader, and where each kind of review data lives, naming the file and line of each step. It says what the loop does not do: there is no `performance` or `sre` persona and no ensemble by default, `devops review verify` runs nothing, the export reaches no RAG index and no prompt, a persona does not look the catalog up, and `review_output_instruction.md` and `--summary` belong to a path no CLI review takes (#952).
  - Section 2 follows the four steps of `tasks/review.md` instead of five phases, and section 3's remediation workflow records an agent's verdict with `--adjudicator agent` and says what it changes (#952).
  - Section 4 lists the two metrics a review sends, `devops_cli_review_duration_seconds` and `devops_cli_findings_total`, with their labels and the review's trace spans; it listed five metrics no code sends. Section 5.6 says where each calibration signal is read (#952).
  - A calibration record for review session `20261001-224227` gives its counts (903 candidates, 563 reported, 178 VERIFIED), the hand triage (489 of the 563 false, 46 confirmed and none above MEDIUM, 163 of the 178 VERIFIED false), the nine failure signatures the prompt A/B counts, and the mechanism each failure now has (#952).
- **AGENTS.md, the Knowledge Base and `CONTEXT.md` Agree With It**:
  - AGENTS.md no longer says the feedback export grounds RAG or refines prompts, says the default review runs the DevSecOps persona alone, describes what a review enforces about CVE citations, and tells agents to file a candidate issue for friction, an interface inconsistency, a bad pattern or a suggestion instead of adding it to `docs/ROADMAP.md` (ADR 0001). The generator's devops-cli template carries the same rules (#952).
  - The knowledge base's review pages describe the stages, personas, verification and feedback dataset as they run, and every `devops review` example in them parses: `devops ai review patch`, `--provider`, `--model`, `--orchestration-shape` and `--post-pr` are gone (#952).
  - `CONTEXT.md` defines a mitigated verdict as a defect a named guard in named files limits, as the verifier does, and adds unverified (#952).
- **`devops review` Help Says What the Options Do**:
  - `--persona` and `--all` name the personas each runs, `--summary` says it has no effect, `findings --invalidated` says findings.json holds only the findings a later verdict invalidated, and `export-feedback` names its reader and its default status. `docs/commands/review.md`, `docs/commands/ai.md`, `docs/CLI_REFERENCE.md` and the README are regenerated (#952).
- **`--secret` Is `--secret-name` (`devops ai runs connect`)**:
  - The option names the Kubernetes Secret that holds the run index's Valkey password, not the password, and is now called what `devops k8s enable-tls` and `devops tls enable-k8s` call theirs. `--secret` is gone without an alias (#956).
- **`OTEL_EXPORTER_OTLP_ENDPOINT` Is Only the Fallback (`devops_cli.telemetry.tracer`, `telemetry.endpoint`)**:
  - `telemetry.endpoint` is unset by default. The collector is `DEVOPS_CLI_TELEMETRY_ENDPOINT`, else the configured `telemetry.endpoint`, else OpenTelemetry's own `OTEL_EXPORTER_OTLP_ENDPOINT`, else `http://localhost:4318`. `OTEL_EXPORTER_OTLP_ENDPOINT` used to override the configuration files (#956).
  - Every command that saved the configuration wrote the built-in `telemetry.endpoint: http://localhost:4318` into the file, and saves no longer do. A file saved before this change still names that endpoint, which now outranks `OTEL_EXPORTER_OTLP_ENDPOINT`. To let the variable choose the collector, delete the line or set `DEVOPS_CLI_TELEMETRY_ENDPOINT` (#956).
- **`devops ai ast parse --query` Queries Only Files in a Known Language (`devops ai ast parse`)**:
  - A file whose extension names no supported language was queried as Python. It now exits 1 with the error a plain parse gives (#959).
- **The `--level` Help Promises No Token Budget (`devops ai read`)**:
  - The help described Level 0 as "<200 tokens", a figure only the guessed count supported. It now lists what the topology holds: classes, functions, exports and hotspots (#959).
- **Review Data Has One Place for Every Command: the Main Worktree in devops-cli's Own Repository, `~/.local/share/devops-cli` From Any Other (`devops ai ingest`, `devops ai prompt-eval`, `devops ai runs`, `devops ai cost`, `devops pr check-readiness`, `devops dashboard`)**:
  - What a review keeps, its sessions, history and baselines, the hallucination catalog, the mitigations ledger, the feedback dataset, runs, samples, library contracts and AI spend, resolves a relative data directory in one place whichever command reads or writes it (`resolve_review_data_path`): under the main worktree in devops-cli's own repository, as before, and under `~/.local/share/devops-cli` from any other repository, so it is in `~/.local/share/devops-cli/.data` there by default. A review started in another repository keeps it there (#972), and the commands that share it would have resolved it under the repository they ran in: the dashboard, `devops ai prompt-eval`, `devops ai runs`, `devops ai cost` and the mitigations perimeter check of `devops pr check-readiness` would have found no session, verdict, run, spend or mitigation such a review recorded (#972).
  - Library contracts are `libraries/` under that data directory, where each command used `.data/libraries` relative to the working directory, so a contract `devops ai ingest library` wrote in one directory reached no review started in another (#972).
  - `devops ai prompt-eval --dataset` resolves a relative path where review data is kept, as `data.feedback_dataset_path` does (#972).
  - Outside devops-cli's own repository, review data a repository's `.data` already holds stays there and is no longer read. Move it into `~/.local/share/devops-cli/.data` to keep it, or set an absolute `DEVOPS_CLI_DATA_DIR` naming that `.data`, which every command then uses for all of its data. Other data, such as the analysis cache, the CI cache, logs and sandboxes, still resolves under the main worktree outside a review (#972).
- **The Code and Docs Collections Are Searched at Once (`devops_cli.ai.rag.retriever`)**:
  - `SemanticRetriever.search` queries its target collections in parallel, so a query waits for the slower search, not both one after the other. The points are pooled in the collections' order, not the order the replies come back in, so the results, their order, which duplicate is kept and the fused scores are the same as before. A collection whose search fails still adds no points. The first collection is searched on the calling thread and the others on daemon threads that carry the trace context, so each `ai.rag.qdrant_search` span stays under `ai.rag.search`. They are joined before the search returns, except after Ctrl-C, which still stops a query such as `devops ai rag query` at once, and lets the process exit, rather than waiting out a stalled search's retries (#975).
- **The Qdrant Request Timeout Is a Setting, 300 s by Default (`devops_cli.config.settings`, `devops_cli.ai.rag.qdrant`)**:
  - `qdrant.timeout` (`DEVOPS_CLI_QDRANT_TIMEOUT`) sets how many seconds each Qdrant request waits per attempt. It defaults to 300 s, since 60 s is too short for a homelab Qdrant search and 300 to 600 s suits one, and must be greater than 0. `QdrantClient` defaulted to `DEFAULT_HTTP_TIMEOUT_SECONDS`, one hour per request, and no caller set a timeout, so a stalled search could hold a RAG query for an hour per attempt (#975).
  - Every place that builds the client passes the setting: review investigation, the `rag_search` tool, `devops ai rag query` and indexing. Indexing's upserts and deletes go through the same client, so they wait the same time per attempt. A timed-out request is retried after a reconnect, as before, up to 3 attempts (#975).
  - The client uses the timeout as given. A floor of 60 s no longer raises a smaller value, and a fraction of a second is sent to the Qdrant client rounded up to whole seconds, not down to 0 (#975).
- **Review Terminal Output Lists What Matters and Summarizes the Rest (`devops review path|branch|pr`, `devops_cli.ai.review.pipeline`)**:
  - The findings table lists CRITICAL, HIGH and MEDIUM findings, each under its number in `review.md`, and detail panels follow for CRITICAL and HIGH only. LOW and INFO findings are one line that counts them by status and gives the path to `review.md` and the command that lists them, such as `devops review findings <session> --severity LOW --details` (#987).
  - Dependencies are one line: packages scanned, vulnerable by severity, and not checked, pointing at the report's "External Dependencies" section. A table follows only for vulnerable packages (#987).
  - Network references are one line: references found, local and external, and flagged by reputation, pointing at the report's "Network References & Endpoints" section. A table follows only for flagged endpoints (#987).
  - The closing line names the session directory and `review.md`. `review.md` and `findings.json` are unchanged (#987).
  - Rendered from saved sessions at 120 columns, the branch review `20261002-180320` (126 findings, 58 dependencies, 162 network references) prints 1,731 lines instead of 3,469, and the path review `20261001-224227` (563 findings, 58 dependencies, 531 network references) prints 9,043 instead of 15,708. The detail panels of CRITICAL and HIGH findings make up most of what remains (#987).
- **Every Ollama Tier Keeps One Model Loaded and Serves One Request at a Time (`k8s/llm/profiles/ollama-profiles.yaml`)**:
  - All nine Ollama DaemonSets set `OLLAMA_MAX_LOADED_MODELS` and `OLLAMA_NUM_PARALLEL` to `1`. Ollama reserves KV cache for `OLLAMA_CONTEXT_LENGTH` × `OLLAMA_NUM_PARALLEL` tokens, so a tier now holds one context instead of two or four. In review session `20261003-051015`, gemma4:31b on ollama-48gib-slow reserved 512,000 tokens (4 × 128,000), put only 44 of its 61 layers on the GPU, and then failed to load; on ollama-64gib each call took 18 to 25 minutes, past the client's 1,200 s timeout (#1061).
  - Requests to a busy tier now queue in Ollama, and a tier that serves both an embedding model and a chat model, such as ollama-48gib-slow, unloads one to load the other (#1061).
- **The Project's Claude Code Settings Are Checked In (`.claude/settings.json`, `.gitignore`)**:
  - `.gitignore` ignored the whole `.claude/` directory, so the shared Claude Code settings (enabled plugins and permission rules) were never committed. It now ignores `.claude/*` and re-includes `.claude/settings.json`; personal settings (`.claude/settings.local.json`), `.claude/scratch/` and `.claude/worktrees/` stay ignored (#1087).

### Removed
- **`SpanHandle.record_llm_metrics` (`devops_cli.telemetry.tracer`)**:
  - Removed without a replacement. Nothing called it, and it wrote renamed and private keys beside the current ones. A reply's GenAI attributes are written by the `ai.llm.dispatch` span alone (#588).
- **Line-Based Stream Helpers (`devops_cli.ai.client`)**:
  - `_consume_streaming_lines`, `_read_response_lines`, `_extract_claude_stream_chunk`, `_extract_openai_stream_chunk`, `_extract_ollama_stream_chunk`, `_extract_ollama_stream_tuple` and `_extract_stream_chunk` are replaced by `_read_event_stream`, `_read_ndjson_stream` and one frame parser per provider in `devops_cli.ai.client.streaming`. The five that `devops_cli.ai.client` re-exported are removed from it, with no alias (#599).
- **ROADMAP-to-GitHub Sync (`devops gh issues sync-roadmap`, `devops gh issues reconcile-roadmap`, `devops gh milestones sync`, `devops release epic`)**:
  - Removed without shims, with `github/roadmap_sync.py`, `github/release_epics.py`, `--create-release-epics`, the ROADMAP-heading milestone extraction and the MCP tools `gh_sync_roadmap`, `gh_issue_reconcile_roadmap`, `gh_milestone_sync` and `release_epic_sync`. GitHub is the roadmap's source of truth, so nothing pushes `docs/ROADMAP.md` to it any more (#739).
- **pytest, rg and file Are No Longer Criteria Commands (`devops review path|branch|pr`, `devops_cli.config.constants`, `devops_cli.ai.review.review_environment`)**:
  - `CONST_ALLOWED_CRITERIA_BINARIES` drops `pytest`, `rg` and `file`. A criterion naming one is kept as a sentence and never run. A passing existing test shows no defect, and none of the three was on the sandbox's PATH: all 11 pytest criterion runs in the saved review sessions had failed with `bwrap: execvp pytest` (#847).
  - pytest is refused in the forms the validator reads too: `python -m pytest` or `python -m _pytest` (or one of their submodules); a `python -c` script that imports `main` or `console_main` from `pytest` or `_pytest`, or reaches either through a name it imports them as or through `__import__('pytest')` or `importlib.import_module` of a pytest module's name; and `find -exec pytest`, since `find` may no longer run commands (see Fixed). Under the repository's interpreter and the 30 s python limit they would run the project's real tests, and a `pytest.main` whose return value is discarded exits 0 whatever the tests do, even for a test file that does not exist. A criterion may still import pytest, for `pytest.raises` or a test module that imports it. A script that names the runner only at run time, as in `getattr(pytest, 'main')` or `runpy.run_module('pytest', run_name='__main__')`, still passes the validator and runs the tests (#847).
  - A pytest criterion settles no verdict, whatever its form: one the validator refuses stays a sentence, and the evidence rule counts only a `python -c` script that asserts over the cited code or calls the cited test directly (#847).
  - The review prompts (`ai/tasks/review.md`, `ai/tasks/review_output_instruction.md`) describe an executable criterion as a `python -c` command only, and so does `docs/SELF_IMPROVEMENT.md` (#847).
- **The Deterministic Embedding Fallback (`devops_cli.ai.rag.embeddings`)**:
  - `EmbeddingsEngine._deterministic_fallback`, `EmbeddingVector` and `EmbeddingList` are removed without a replacement. Embeddings come from a model or raise `EmbeddingsError` (#945).
- **`devops ai benchmark --suite` and `--dataset`, the MCP `benchmark_suite` Tool and `devops_cli.ai.benchmark.suite`**:
  - The suite sent empty prompts, from `benchmark_suite_system.md` and `benchmark_suite_user.md`, which never existed, scored the fix as the code under test and counted UNVERIFIED findings as not vulnerable. Its models (`BenchmarkSuiteCase`, `BenchmarkSuiteEvaluation`, `ModelSuiteMetrics`, `BenchmarkSuiteReport`), its leaderboard table and `--type suite` go with it; #413's corpus arms (`devops review corpus score`) replace it. A test now fails when a prompt file the code loads by name does not exist (#950).
- **Unused Review Prompts (`devops_cli.ai.tasks`)**:
  - `diff_review_prompt.md` and `review_pipeline_eval.md` are deleted. Nothing loaded them, yet they changed the prompt digest (#951).
- **The Single-Ollama Manifests (`k8s/llm/ollama-host-service.yaml`, `k8s/llm/values-ollama.yaml`)**:
  - `ollama-host-service.yaml` bridged an `ollama` Service to Ollama on the minikube host, and `values-ollama.yaml` held values for the `ollama/ollama` chart. Nothing has applied either since the in-cluster Ollama tiers replaced them. Both are deleted without a replacement, and `k8s/README.md` port-forwards `svc/ollama-16gib` for the Ollama API instead of `minikube service ollama` (#953).
- **The `ollama.llm.svc.cluster.local` Name in the Homelab Certificate (`devops tls homelab`, `devops tls enable-k8s`, `devops k8s enable-tls`)**:
  - The homelab TLS bundle no longer lists `ollama.llm.svc.cluster.local`, a Service nothing deploys. `*.llm.svc.cluster.local` still covers the Ollama tiers (#953).
- **Unregistered Telemetry Variables (`DEVOPS_TELEMETRY_ENABLED`, `DEVOPS_OTEL_ENDPOINT`, `DEVOPS_CLI_OTEL_ENDPOINT`)**:
  - The tracer read these three names, which no documentation listed, ahead of the configuration. They are gone without a shim; use `DEVOPS_CLI_TELEMETRY_ENABLED` and `DEVOPS_CLI_TELEMETRY_ENDPOINT`. The `devops telemetry profile` error names the new variable (#956).
- **Nested Settings Variables (`devops_cli.config.settings.Settings`)**:
  - `Settings` no longer reads `DEVOPS_CLI_<SECTION>__<FIELD>`. `load_settings()` never applied that form, so `DEVOPS_CLI_TELEMETRY__ENABLED=false` left telemetry on, but a bare `Settings()`, which builds the configuration reference and the API's `/config` answer, did read it (#956).
- **`NVDClient` (`devops_cli.security`, `devops_cli.security.vulnerability_lookup`)**:
  - `NVDClient` and its record parser are deleted with their export and test. Nothing called them (#956).
- **Dead Scanner Helpers (`devops_cli.security.semgrep`, `devops_cli.security.bandit`)**:
  - `_execute_and_parse_semgrep` and `_execute_bandit_subprocess` are removed without a replacement, with the imports and loggers only they used. Nothing called them; both scanners run through `BaseSecurityScanner`. A hygiene test fails on any module-level private function in `security/*.py` that nothing in `src/` or `tests/` references (#957).
- **Per-Layer Wasted Bytes (`devops docker analyze-layers`, `DiveLayerInfo`)**:
  - Dive's export has no per-layer wasted bytes, so `DiveLayerInfo.wasted_bytes` and the layer table's `Wasted (MB)` column were always 0. Both are removed. The image's wasted bytes stay in the summary line and in `--json` (#957).
- **The MCP Sampling Model Stub (`devops_cli.ai.agents`)**:
  - `MCPSamplingModel` is removed without a replacement, with its exports from `devops_cli.ai.agents` and `devops_cli.ai.agents.pydantic_agent`. It called the MCP SDK's async `ServerSession.create_message` without awaiting it, so a real session's completion was the text of a coroutine object, and a failed call, or no session, returned the fixed text `MCP sampling response generated via client session callback.` as if a model had written it. No command built it. `PydanticAgent.set_mcp_sampling_model`, which sets an `MCPToolset`'s sampling model, stays (#958).
- **Unused OS Access and Tool Search Classes (`devops_cli.ai.harness`)**:
  - `MountDir`, `OSAccess` and the harness `ToolSearch` are removed with their module, `ai/harness/os_access.py`, and with their exports from `devops_cli.ai`, `devops_cli.ai.agents` and `devops_cli.ai.harness`. Deleting `CodeMode` (#947) left `MountDir` and `OSAccess` without a user, and only its own test used the harness `ToolSearch`. `devops_cli.ai.agents.ToolSearch` is pydantic-ai's capability and stays; `devops_cli.ai.ToolSearch`, which was the harness class, is gone (#958).
- **Dead Round-Robin State and Duplicate URL Policies (`devops_cli.ai.client`, `devops_cli.ai.providers.ollama`, `devops_cli.ai.rag.investigator`)**:
  - `LLMClient` no longer copies the round-robin index, locks, semaphores and active-request map of `devops_cli.ai.client.network` as class attributes, nor keeps `_ollama_url_index` and `_ollama_url_lock`. The index was copied once at import and never followed the module's (#960).
  - `read_limited_json` and `LLMClient._read_limited_json` are replaced by `request_limited_json`. `validate_base_url`'s `allow_loopback_for_local_tooling`, the Ollama provider's `_is_loopback_or_private_allowed` and `_validate_ollama_url`, and the investigator's second Qdrant URL check are replaced by `validate_configured_service_url` (#960).
- **The `embeddinggemma:300m` Gateway Groups and bge-m3 on ollama-16gib-fast (`k8s/llm/gateway/configmap.yaml`)**:
  - No Ollama or gateway log shows a request to `embeddinggemma:300m`, and devops-cli's defaults and docs do not use it. Both of its groups are deleted (#1064).
  - `bge-m3:latest` keeps one deployment, on ollama-48gib-slow. On ollama-16gib-fast, which keeps one model loaded and serves `devops-chat` and `devops-review`, an embedding would evict the chat or review model (#1064).

### Fixed
- **Run Setups Name the Model That Verified (`devops_cli.ai.run_store`)**:
  - A review's run setup resolves verification as reviews do, layered on the analysis task. With `ai.tasks.verification` unset, which is the default, it now records the analysis model and that group's pool for verification, not the base `ai.model`. Setups also record each task's `temperature` and `top_p`. This changes the setups that `devops review benchmark`, `devops review samples validate --review` and `devops review corpus score` record, so their fingerprints differ from earlier runs' (#413).
- **Loki Deletes Logs Once They Are 30 Days Old (`k8s/logging/loki-values.yaml`)**:
  - `compactor.retention_enabled` is on, with `compactor.delete_request_store: filesystem`, which Loki 3 requires before it starts with retention on. `limits_config.retention_period: 720h` was set, but only the compactor applies it, and only with retention on. Loki never deleted a chunk by age: its retention had never run, and chunks 12 days old were still stored while the period read 2 hours (#550).
- **The Docs Name What Enforces the Complexity Cap (`AGENTS.md`, `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`)**:
  - These four files said `devops scan complexity` and the architectural invariant tests enforced the cap of 10. They now say that Ruff `C901` enforces it through `uv run devops ci` and the pre-commit hook, and that a test keeps the number of functions carrying markers from growing. `AGENTS.md` adds that a function over the cap is decomposed, never suppressed, and that `test_the_complexity_cap_has_no_escape` rejects Ruff's own `ruff:` suppression comments and ignore files that hide a source (#586).
  - They also say that the `structural-invariants` hook and `test_no_excessive_nesting_in_src` enforce nesting, and that `devops scan complexity` reports a different, in-house count and does not gate (#586).
- **Reviews No Longer Use Another Run's Symbol Delta (`devops review`)**:
  - Pre-analysis kept symbol lists that another review or `devops ai analyze branch` had cached. Verification read the newest cached analysis, whichever run wrote it, and the summary added up that analysis when the reviewed files had no delta. A finding could be exempted for a symbol that a different branch removed. Now only the session's own delta counts (#593).
- **`devops ai analyze branch` Compares a Renamed File With Its Old Path (`devops ai analyze branch`)**:
  - A renamed file is analysed at its new path and compared with its old one at the merge base. The plain `--name-status` parser read `old.py<TAB>new.py` as one path that does not exist, so it recorded the file as deleted. A reused file's delta is now computed again, because the cached one may be against an older merge base (#593).
- **Cut Replies Are No Longer Cached (`devops_cli.ai.client`)**:
  - A reply that ended at its token cap (`length`), was filtered (`content_filter`) or failed (`error`) is returned but not stored in the response cache, so the next identical call reaches the provider instead of the cut reply for 7 days. Replies cached before this change expire as before, or go at once with `devops ai cache clear` (#599).
- **The Dispatch Span No Longer Says Every Reply Stopped (`devops_cli.ai.client`)**:
  - `gen_ai.response.finish_reasons` was hard-coded to `["stop"]` on every `ai.llm.dispatch` span (#599).
- **The Historical Baseline FP Rate Leaves Out the Session It Compares (`devops review`)**:
  - Corrects #434's "Historical Baseline FP Rate" column in review.md. It counted the session being compared, because findings.json is written before the report, and counted a re-reviewed subject once per session. Its history also read only the reported findings in findings.json, while the session side counted every finding raised. One earlier VERIFIED session with the current INVALIDATED session on disk read `50.0% (1/2)`, and two copies of the earlier session made it `25.0% (1/4)` (#607).
  - The baseline now leaves the current session out, counts each subject once and reads every finding each earlier session raised (candidates.json, or findings.json without one). A category shows figures once any counted earlier session has it, including on a first re-review, and a note under the table gives the earlier sessions counted and the repeats collapsed (#607).
- **Roadmap Store Listings Fail Closed (`devops_cli.roadmap.github_store`)**:
  - The GitHub adapter reads each REST listing (milestones, issues, an issue's events, comments and blocked-by links) a full page at a time and raises, naming the read and the page, when a page is not a JSON list. Through `api --paginate`, a page answered with exit 0 and a body that is not a list, such as a proxy's error page, ended the listing there, so a bad first page read as an empty listing and a later one as a short one, and a first run could record a release as holding no items (#740).
- **Editing a Milestone No Longer Closes It (`devops gh milestones edit`)**:
  - `edit` sends only the fields it is given. Before, `devops gh milestones edit v0.2.25 --description x` also sent `state=closed` whenever a GitHub token resolved, and closed the milestone (#768).
  - When GitHub can't be read, `devops gh milestones list` exits 1 and names the failed read, instead of printing "No milestones found" (#768).
- **A Mitigation Stands Only on Code the Reviewed Tree Holds (`devops review path|branch|pr`, `devops_cli.ai.review.verification`)**:
  - A model's MITIGATED verdict stays MITIGATED only when every perimeter file resolves inside the reviewed tree through `safe_resolve_subpath`, and an identifier its mechanism names (`_extract_code_symbols`) appears in a perimeter file or in the finding's own file. An absolute path, even to a file in the tree, a `../` escape, a symlink, a directory and a missing file are unresolved, and a pull request review's tree holds only the pull request's files. Otherwise the finding is UNVERIFIED, stays reported, drops the line the verdict cited, and its `verification_note` names the check that failed. The finding's own file is read where its location points, absolute as a scanner writes it or relative, so a mechanism held only there still counts. A HIGH "Command injection via os.system" finding that the verifier called mitigated by a "shlex.quote wrapper in safe_exec" in `src/does/not/exist.py`, citing line 999 of a four-line file, was MITIGATED with no note and the review recommended APPROVE; it is now UNVERIFIED with a `mitigation-unproven` note saying that `src/does/not/exist.py` does not resolve inside the reviewed tree, and the review requests changes (#845).
  - A documentation file, the conventions file `.devops/review.md` among them, is no perimeter, and a mechanism that negates itself ("caught but not logged", "does not fully sanitize", "is expected to handle", "intended to", "too permissive") describes the defect rather than what limits it. Replayed against session `20261001-224227`'s 28 MITIGATED verdicts, 26 become UNVERIFIED: 19 mechanisms name no code identifier, 5 describe the defect and 2 perimeters are `.devops/review.md`. The 2 naming `validate_service_url` and `is_relative_to()` in the files that hold them stay MITIGATED (#845).
  - A verdict that names no reason, mechanism or perimeter files says which, under the same note kind (#845).
- **A Confirmation Cites a Line Its File Has (`devops review path|branch|pr`, `devops_cli.ai.review.verification`)**:
  - A model's VERIFIED verdict whose `citation_line` is below 1 or past the end of the finding's file is UNVERIFIED, stays reported and drops the citation, with a `citation-out-of-range` note naming the line, the file and its length. A citation inside the file stays VERIFIED. A scanner's finding, located by an absolute path inside the reviewed tree, is checked the same way. Each verdict of a reply is checked on its own: a fabricated one leaves the others as they were (#845).
- **A Confirmation or Mitigation Its Own Reason Contradicts Is Not Applied (`devops review path|branch|pr`, `devops_cli.ai.review.verification`)**:
  - A model's VERIFIED or MITIGATED verdict whose reason denies the finding's claim is UNVERIFIED, stays reported and drops its citation, with a `verifier-contradiction` note quoting the denial. In review session `20261003-012555` qwen3-coder confirmed two Semgrep findings, "Untrusted user input in `importlib.import_module()`", with reasons ending "No user input reaches this point" and "These are not derived from untrusted user input", and #948's ranking put both among the report's top 8 rows; in session `20261003-005122` it called two of the same findings mitigated on the same grounds. The guard mirrors the self-refutation guard on the same claim words and negations: a negation followed by at least two consecutive words of the claim that the claim does not negate itself (#845).
  - A confirmation whose reason supports the claim is still applied, also when it negates a guard ("this does not prevent path traversal") or a word the claim negates too ("no input validation" against "Missing input validation"). Over 778 cached VERIFIED and MITIGATED verdicts, the plain mirror (any negation and 60% of the claim's words) would have set aside 318; this guard sets aside 13, 12 of which argue their finding away (#845).
  - A verdict whose reason says a criterion passed ("verified by the test execution which passes") when every recorded run of a criterion failed gets the same note. Session `20261003-005122` confirmed a finding that way while its criterion had failed with `No module named 'pytest'` (#845).
- **The Profile Counts Mitigations That Proved Nothing (`devops review path|branch|pr`, `devops_cli.ai.review_schema`)**:
  - `verdict_distributions.verification_note` in `profile.json` counts `mitigation-unproven`, `citation-out-of-range` and `verifier-contradiction` notes as their own kinds. A mitigation degraded for want of a mechanism or perimeter was noted in free text and counted as `other` (#845).
- **A Perimeter Path Matches Only Itself (`devops review branch|pr`, `devops pr check-readiness`, `devops_cli.ai.review.mitigations`)**:
  - The perimeter-change warning stripped paths with `.lstrip("./")`, which cut the dot off `.github/...` and `.devops/...` and the root off an absolute path, so a change to `github/workflows/ci.yml` warned about a mitigation whose perimeter is `.github/workflows/ci.yml`, and `etc/hostname` matched `/etc/hostname`. It now strips a leading `./` only. An absolute path inside the repository is read relative to its root, so a person's mitigation of a scanner finding, whose perimeter is the finding's absolute path, still warns when that file changes; an absolute path outside the repository matches only itself (#845).
- **A Verifier Reply Cut at Its Token Cap Settles No Verdict (`devops review`)**:
  - A verifier reply that ended at its token cap (finish reason `length`) no longer settles a verdict, even when JSON repair can close it. Every finding it was to judge stays unverified with the note `verifier-reply-cut`. In session `20261002-214641`, JSON repair closed a reply cut mid-reason into an INVALIDATED verdict on `ai/mcp/server.py:202`, whose reason ended "is therefore incorrect; the", and the finding left the report (#846).
- **What the Verifier Writes Reaches the Saved Finding (`devops review`)**:
  - The pipeline copies every field verification owns, listed once as `VERDICT_FIELDS` beside `apply_verdict`, from the verified finding back onto the saved one. Its own list of fields left out the severity, so a finding kept the reviewer's severity after the verifier rated it (#846).
  - Confidence is kept between 0 and 1 whenever a verdict is written. A command given as both a verification and an invalidation criterion was counted twice, and 3 findings of session `20261001-224227` carried a confidence of 2.0 (#846).
  - A reviewer's reply can no longer bring its own confidence, citation line, mitigating mechanism, perimeter files, regression test or criteria results. They are cleared on parsing with the rest of the verification state (#846).
- **Offline Tests (`tests/test_finding_repetition_compression.py`)**:
  - The monologue test no longer reads the local `.data` response cache (#846).
- **Criteria Run in the Reviewed Repository's Own Environment (`devops review path|branch|pr`, `devops_cli.sandbox.host`)**:
  - When the reviewed repository has a `.venv/bin`, the host sandbox puts it first on `PATH`, so `python` and `python3` are the repository's interpreter with its own dependencies and `ruff` is its ruff. The sandbox's `PATH` was `/usr/local/bin:/usr/bin:/bin`, so `python` was the system's Python, whose third-party modules came from the devops-cli install in `/usr/local/lib/python3.14/dist-packages`, and `ruff` was not found: all 6 ruff criterion runs in the saved review sessions had failed with `bwrap: execvp ruff`. A repository without a `.venv/bin`, or whose `.venv` links outside it, keeps the system `PATH` (#847).
  - A criterion that imports the reviewed project's test dependencies no longer fails on the import. In review session `20261002-214641` the invalidation criterion for `tests/test_security_bandit.py:142-154`, a `python -c` importing that test module and so pytest, failed with `No module named 'pytest'`; replayed through the sandbox it exits 0 (#847).
  - A virtualenv's `python` links to the interpreter it was made from. When that lies outside the sandbox's mounts, as uv's managed CPython under `~/.local/share/uv/python` does, the sandbox binds its installation read-only, or the link would dangle. The repository chooses where the link points, so the installation is bound only when it holds CPython's standard library (`lib/python3.*/os.py`), contains neither the home directory nor the repository, and has no `.ssh`, `.aws`, `.kube` or `.git` in its path. A virtualenv whose `python` cannot be bound, or links to nothing, is passed over and the system `PATH` stands (#847).
- **A Python Criterion Is `python -c <script>` or `python -m <module>` (`devops review path|branch|pr`, `devops_cli.ai.review.review_environment`, `devops_cli.ai.review.criteria_evidence`)**:
  - A python criterion is accepted only with `-c` or `-m` as its first argument; any other shape is refused and kept as a sentence. Python reads its own options up to the first `-c` or `-m`, inside a cluster such as `-Bc` too, and passes what follows to that script or module, but the validator and the evidence rule read the command otherwise. The evidence rule took the script after the first `-c` token wherever it stood, so `python -m this -c '<assert>'` and `python -Bc pass -c '<assert>'` exited 0 without running the assertion, and a failing assertion over the cited code settled VERIFIED with confidence 1.0, or as an invalidation criterion INVALIDATED. The validator looked for `-c` anywhere before it looked for `-m`, so `python -m socket -c pass` ran a forbidden module; and it missed a `-c` inside a cluster, so `python -Bc '<script>' -c pass` checked only `pass` and ran a script that imports `subprocess`. Both now read the command one way (`python_invocation`): the script or module Python runs is the one checked, and a `-c` after `-m` is the module's argument, which settles nothing. All 3,710 distinct python criteria in the saved review sessions have `-c` or `-m` first (#847).
  - `python -m` refuses a submodule of a forbidden module (`http.server`, `urllib.request`), as an import of one was already refused (#847).
  - A `find` criterion may only search: `-exec`, `-execdir`, `-ok`, `-okdir`, `-delete`, `-fprint`, `-fprint0`, `-fprintf` and `-fls` are refused. `-exec` ran any binary on the sandbox's `PATH`, allowlisted or not, and pytest among them once the repository's `.venv/bin` led it (#847).
- **A Scanner Reason With Brackets Prints as Written (`devops scan report`, `devops scan trivy|secrets|sast|iac`)**:
  - The "was not run" and "failed during execution" warnings read a scanner's reason as Rich markup. A reason with a closing tag such as `[/x]` stopped `devops scan report` with a `MarkupError` and exit code 1 after it had written the SARIF file. The reason now prints literally (#915).
- **Open PRs Into a Release Branch No Longer Conflict on `CHANGELOG.md` (`changelog.d/`, `devops release prepare`, `devops release changelog --update`)**:
  - Each PR's entry is its own `changelog.d/<issue>.md`. The cut merges every fragment into the version's section, categories in Keep a Changelog order and fragments in issue order within each, deletes them in the same run and leaves `## [Unreleased]` an empty heading. A misnamed file, text outside a category or an unknown category stops the cut before any write and names the file. A dry run lists the fragments and writes nothing, and with no fragments the section is written as before (#933).
- **Readiness Blocks a PR That Changes `CHANGELOG.md` or `docs/ROADMAP.md` (`devops pr check-readiness`)**:
  - A PR into a `release/*` branch that adds, modifies, renames or removes either file gets one blocker naming it and the fragment to add instead. Release-process PRs, `chore/open-vX.Y.Z` or `chore/cut-vX.Y.Z` optionally followed by `-<slug>` from the same repository into `release/vX.Y.Z`, are exempt from grounding as the release PR is (#933).
- **Reviews Ask an Unserved Embedding Model Once, Then Run Without RAG (`devops review`, `devops_cli.ai.rag.investigator`)**:
  - A review against a gateway whose backends serve only the review model asked for the embedding model on every RAG lookup: once per finding in verification, per file in the review payloads, in pre-analysis and per persona prompt. Every request failed and logged a warning, and on a node that keeps one model loaded each one could swap out the review model. Now the first lookup whose query cannot be embedded turns RAG off for the rest of the process. It logs one warning that names the model and the error, and says how to fix it: serve the model, point `ai.tasks.embedding` at a backend that serves it, or set `ai.rag.enabled: false`. Later lookups return no context without building a retriever or sending a request, and `clear_investigation_cache()` lifts the stop. Until the model has answered a lookup, lookups that run at once take turns, so the review workers' parallel per-file lookups (16 on a gateway) send one request between them rather than one each before the first failure comes back. Once the model answers, lookups run in parallel again. Five findings against a gateway that answers HTTP 400 now send one embedding request, not five, and four review workers looking up their files at once send one, not four (#945).
- **A Failed Embedding Raises Instead of Becoming a Hash Vector (`devops_cli.ai.rag.embeddings`, `devops_cli.ai.rag.retriever`)**:
  - `EmbeddingsEngine` turned four failures into a hash of the text: an HTTP error, an unreachable endpoint, a text every Ollama node refused, and a missing provider. Retrieval then searched Qdrant with that vector and could hand unrelated chunks to the verifier as context, and `devops ai rag index` and `devops ai ingest index-libraries` would have stored it. Each failure now raises `EmbeddingsError`. Its message names the model, each endpoint or node it asked, and the HTTP status with the start of the reply, or the error. `SemanticRetriever.search` and `retrieve_context` raise it rather than returning no results (#945).
  - These commands now print the error and exit 1 rather than show a traceback: `devops ai rag index`, `index-kb`, `query` and `drift --auto-sync`, and `devops ai ingest index-libraries` and `query-library`. Indexing stores no vector for a text the model did not embed. The agents' `rag_search` tool returns `RAG search unavailable: <error>. Fallback: use search_code.`, as it does when Qdrant is unreachable (#945).
  - When Ollama batches run in parallel, the first batch that every node refuses cancels the batches still queued, rather than sending them to the same nodes (#945).
- **A Change Made Only of Routed Files Calls No Model (`devops review branch|pr`)**:
  - A branch or pull request whose changed files were all lockfiles, planning documents or generated references paged into one empty page, which the legacy engine sent to the model. Such a review now calls no model, runs the secret scan on those files, writes its report and says that nothing was left for the personas, or, with the static scan off, that none of the files was read. Its findings.json names no persona (#948).
- **The Verifier Only Lowers a Severity (`devops_cli.ai.review.verification`, `devops_cli.ai.review.pipeline`)**:
  - A verifier reply could raise a finding's severity. It can now only lower it, the persona's value stays as `severity_raw`, and the pipeline keeps the lowered value, which its copy-back used to drop (#948).
- **Advisories Come From This Session's Scan (`devops_cli.ai.review.verification`, `devops_cli.ai.review_schema`)**:
  - A CVE or GHSA id stays in a finding's references only when a vulnerability record of this session's scan carries it, OSV's or one Trivy reported. Any other is removed and `reference_note` says which, and a finding left with no reference had it as its only evidence and is INVALIDATED as `deterministic:unbacked_advisory`. Session `20261001-224227` cited 11 CVEs from Log4j, polkit, Apache httpd, OpenSSH, axios and JUnit against a Python CLI whose 58 dependencies it had scanned clean (#948).
  - A record's aliases match too, and OSV's `aliases` are now kept on each record. The batch lookup a review makes returns ids only, so a review's records carry no alias yet, and a finding citing the CVE of a PYSEC or GHSA record the scan found is stripped (#948).
  - Verification checks a finding against every dependency the session scanned, whichever file declared it, and against the packages Trivy found vulnerable, which no longer count as scanned clean. Each file's verification passed none, so a claim against a dependency the scan found clean was never checked (#948).
  - A persona reply's `external_dependencies` and `network_references` are cleared when it is parsed, so no check trusts a dependency a model declares clean, and a finding's `severity_raw` and `reference_note`, which only the pipeline writes, are cleared whether the reply was parsed from text or by the agent framework (#948).
  - The placeholder check also catches ids of ascending digits such as `CVE-2023-1234`, not only `x`, `n` and `?` runs, unless this session's scan carries the id: sequential ids are published ones too, `CVE-2016-1234` (glibc) and `CVE-2023-1234` (Chrome) among them, and Trivy's own finding of one must stand (#948).
- **Verdicts Given at Once (`devops review verify`, MCP `verify_finding`)**:
  - Verdicts given on one session at the same time, as an MCP client's parallel calls give them, take turns under a lock on the session (`.verify.lock`). Each call read the session's files before another wrote them and wrote over that verdict, though every call reported success (#949).
  - A verdict whose session files cannot be written is not recorded: files already written are put back, each learned-catalog or ledger entry it updated is put back as it was, every field included, each it created is removed, and the command exits 1. A reset withdraws the entries it released only once the files are written (#949).
- **Resets Undo Their Side Effects (`devops review verify --status UNVERIFIED`)**:
  - A finding records one id for each learned-catalog or mitigations-ledger entry a person's verdicts on it created or added to (`learned_catalog_ids`, `mitigation_ledger_ids` in findings.json). Resetting it to UNVERIFIED withdraws each: an entry another verdict also recorded loses one count (`occurrence_count` in the catalog, the new `verdict_count` in the ledger) and stays, and one nothing else recorded is removed. Every other entry is left alone (#949).
- **Feedback Records Are Not Human by Default (`devops_cli.ai.review.exporter`)**:
  - `FeedbackRecord.verified_by` defaults to `unknown`, not `human`, so the export labels a record `human` only when a person judged the finding (#949).
- **One Settings Load per Review (`devops review path`, `branch`, `pr`)**:
  - Each command loads the configuration once; it loaded it twice (#949).
- **Machine-Learned Catalog Entries Are Purged (`devops review`)**:
  - The first load of the learned catalog removes every entry the review's own checks taught it, and logs once how many. In session `20261001-224227` its 35 entries were all `general`, with signatures pairing common words such as `exception` and `handling`; had their ground truth ever passed, they would have invalidated 240 of that session's 903 candidates, 19 VERIFIED HIGH findings among them (#950).
- **The Harness Planning and Playwright Guidance Load From Their Prompt Files (`devops_cli.ai.harness`)**:
  - `planning_guidance.md` and `playwright_guidance.md` did not exist, so the exported `DEFAULT_PLANNING_GUIDANCE` and `DEFAULT_PLAYWRIGHT_GUIDANCE` held inline fallbacks that differed from the guidance the capabilities used. Both prompts are now files, and the capabilities and the exports read the same text (#950).
- **Port-Forward Reaches the Ollama Tier (`devops k8s port-forward`, `devops k8s configure-urls`)**:
  - `devops k8s port-forward --stack llm` forwarded `svc/ollama`, which nothing has deployed since the Ollama tiers replaced the single workload, so the Ollama forward failed. It now forwards `svc/ollama-16gib`, the default tier's Service, on port 11434 (#953).
  - `devops k8s configure-urls --stack llm` looks up `ollama-16gib` instead of the missing `ollama` Service. It still detects no cluster address for Ollama, because the tier's Service is ClusterIP, with no NodePort or load balancer. As before, it sets `ai.ollama_urls` to `http://localhost:11434` only while something answers there, which the forward above now can (#953).
- **Failover to Ollama Reaches a Deployed Service (`devops ai gateway failover`, `devops_cli.ai.gateway`)**:
  - `devops-chat` and `devops-embedding` failed over to `ollama.llm.svc.cluster.local`, which nothing deploys. They now fail over to the default Ollama tier, the same `ollama-16gib` Service their default routes use (#953).
- **Portkey's Ollama Egress Selects the Ollama Tiers (`k8s/llm/portkey/networkpolicy.yaml`)**:
  - The rule selected `app.kubernetes.io/name: ollama`, which no deployed pod carries. It now selects `llm.devops.io/provider: ollama`, which every tier carries, on port 11434 (#953).
- **A Failed Embedding Fails the Model Instead of Scoring It (`devops ai benchmark --type embedding`, `devops_cli.ai.benchmark.embedding_runner`)**:
  - A model whose embedding requests failed, on an unreachable server or one that does not serve it, was scored anyway. With every request failing it printed `✓ ... → 35.0%`: a p50 latency of 0.0 earned full latency points, and the recommendations named it the lowest-latency model and, at dimension 0, the most memory-efficient. Now the first failed request ends the model's run and no later request is sent. The run prints `✗ <model> on <server> | <error>`, and its result has `failed: true`, the error cut to 256 characters, the latencies of the requests that succeeded before it, or null, and no scores (#954).
  - A failed run ranks after every scored one, with no medal, `-` for each metric and `failed` for the score, and the Markdown report lists each with its error under "Failed Runs". The server summaries and the recommendations count only scored runs (#954).
  - A server the benchmark refuses to reach, or a run that raises anything else, is reported failed rather than dropped from the report with only a log line (#954).
  - In the report JSON, `latency_ms_p50`, `latency_ms_p95` and a server's `avg_latency_p50_ms` are null rather than 0.0 when no request was timed (#954).
- **Registry and Build Text Prints As Written (`devops docker push`, `devops docker build`)**:
  - A push status or error from the registry, and each line of build output, was read as Rich markup. An error such as `denied: [/v2/repo] access` ended `docker push` in a `MarkupError` traceback instead of the error and exit 1, `[internal]` vanished from a line, and `[link=...]` text became a terminal link. The text now prints as written, and control characters are still stripped (#955).
- **Scraped Metrics Print As Written (`devops sandbox metrics`)**:
  - Label values and `# TYPE` text from the scraped endpoint were read as Rich markup in the metrics table, so a label value such as `[/]` ended the command in a `MarkupError` traceback, and others could add styles or links. The metric name, type and labels are now shown as written. The label string is still cut to 40 characters, before it is escaped, so the cut never lands inside an escape. The target in the table titles is shown as written too (#955).
  - A `# TYPE` line counts only when it names a metric and gives a type the Prometheus text format defines: `counter`, `gauge`, `histogram`, `summary` or `untyped`, in any case. Any other line is ignored, and the samples' type is inferred from their name, in the table and in `--json`, as for a metric with no `# TYPE` line. That includes the OpenMetrics-only types, such as `info` and `stateset` (#955).
  - The scrape error carries the HTTP client's exception text, which can quote the endpoint's own bytes, as h11's `illegal header line` does. It prints as written in the `SCRAPE WARNING` line and the error line, and the target prints as written in the healthy and threshold-exceeded lines too (#955).
- **The CLI Reference Shows Defaults That Cannot Be Credentials (`devops docs generate`, `devops_cli.docs.generator`)**:
  - A default was masked whenever a credential keyword appeared anywhere in the option's name or envvar, so `--max-tokens` (TOKEN), `--valkey-port` (vaLKEY), `--key-size`, `--max-tokens-increase`, the TLS key path and two Kubernetes Secret names showed `<masked>`. The reference now shows `1500`, `200`, `0.2`, `6379`, `2048`, the path, `homelab-tls` and `valkey-runs-auth` (#956).
  - A text default is masked when the option's name or envvar names a credential, matched word by word: TOKEN, SECRET, PASSWORD, PASSPHRASE, CREDENTIAL, AUTH or APIKEY, or API followed by KEY. A name that ends in NAME holds what a credential is called, so `--secret-name` is shown. A number, a boolean or a path is never masked. An option that hides its input, Click's own marker for a secret, is always masked (#956).
- **An Off Switch Reads as an Off Switch (`devops docs generate`, `devops_cli.docs.generator`)**:
  - The reference listed a boolean's off switch among its aliases, as in `--rootless`, `--root`, although `--root` turns the host UID/GID mapping off. Off switches now follow a slash, as in `--rootless` / `--root` and `--follow`, `-f` / `--no-follow` (#956).
- **A Failed OSV Lookup Is Not a Clean Package (`scan_osv`, the `security_intel_package` tool, `devops scan fix --package`, `devops_cli.security.vulnerability_lookup`)**:
  - `OSVClient.query_package` returns a `PackageLookupResult`, as `query_batch` does, and a failed lookup carries its `reason`: OSV's status code or the request's error, capped at 256 characters. `scan_osv` answers `OSV lookup failed: <reason>` instead of `No known vulnerabilities found`, and `devops scan fix --package <name>` stops with the reason instead of planning nothing (#956).
- **Nothing Claims an NVD Lookup (`security_intel_package`, `scan_osv`, `devops ai review`, `docs/cheatsheets/security_and_ssh.md`)**:
  - devops-cli queries OSV.dev for package advisories and never NVD. The tool descriptions, `scan_osv`'s reply, the review report's dependency heading and console tables, the security cheatsheet and the code review manual no longer say it queries NVD (#956).
- **The `k8s_pods` Tool Lists the Namespace It Is Given (`k8s_pods`, `devops_cli.ai.mcp.server`)**:
  - The tool validated its `namespace` and then ran `devops k8s status`, which ignored it. It runs `devops k8s pods -n <namespace>`, or `devops k8s pods -A` when the namespace is empty (#956).
- **Knowledge-Base Examples Import Names That Exist (`devops_cli/libraries/fastmcp.md`, `devops_cli/libraries/pydantic_ai.md`)**:
  - The FastMCP manual's tool example imported `pods` from `devops_cli.commands.k8s`, which has no such name, and returned a canned string. It now shows the real `k8s_pods` tool, and the manual says tools run the `devops` CLI through `_run_mcp_cmd`. The Pydantic AI manual's example no longer imports `Finding` from `devops_cli.models.review`, a module that does not exist. A test fails on any `devops_cli` import in a knowledge-base Python example that does not resolve (#956).
- **One Section per Cadence Letter (`docs/ROUTINE_TASKS.md`)**:
  - The final pre-commit stage was a second `Cadence B`. It is now `Cadence A (final stage)`, so B, C, D and E keep naming what task files cite them for (#956).
- **Dive Layer Analysis Says When There Is None (`devops docker analyze-layers`, the `docker_analyze_layers` tool, `devops_cli.security.dive`)**:
  - Without a `dive` on PATH, or with one that is a symlink, `run_dive_analysis` returned a made-up analysis for any image: 98% efficient, 150 MB, and two layers, `FROM python:3.14-slim` and a `COPY` of uv. Any dive error returned a 100% efficient image of 0 bytes. The result now has a `status`, `ran`, `unavailable` or `failed`, and a `reason`, and only a `ran` result carries measurements (#957).
  - `analyze-layers` prints `Dive layer analysis unavailable: <reason>` (or `failed: <reason>`) as a warning and exits 1 when dive did not run. `--json` prints the result with its `status` and `reason` and also exits 1. The `docker_analyze_layers` tool answers `Dive not available: <reason>` or `Dive analysis failed: <reason>` instead of an efficiency score (#957).
  - With `--json`, stdout holds only the JSON document. The `Analyzing container image layers ...` line came first and made it invalid JSON (#957).
  - Each layer command in the table is shown as written. Commands come from the image's history, which whoever built the image controls, and they were read as Rich markup: `pip install uvicorn[standard]` showed as `pip install uvicorn`, and a command could add styles or terminal links (#957).
  - Dive runs as `dive <image> --json <file>`, with the file in a private temporary directory, and that file is read. `--json -` made dive write a file named `-` into the working directory while the code parsed dive's progress text on stdout. The export is read by the keys dive writes: `image.efficiencyScore`, `image.inefficientBytes`, `image.sizeBytes`, and each layer's `index`, `digestId`, `sizeBytes` and `command`. The `devops scan` dive adapter runs dive the same way, so an inefficient image is a finding there instead of an empty run (#957).
- **`devops k8s rbac-audit` Audits the Cluster (`devops k8s rbac-audit`, `devops_cli.k8s.rbac`)**:
  - The command made no cluster call and always printed one fixed `PASS` row. It now reads `kubectl get clusterrolebindings,rolebindings -o json` and `kubectl get clusterroles,roles -o json`, with `--all-namespaces`, or `-n <namespace>` when `--namespace` is given. It lists each subject that a binding grants the built-in `cluster-admin`, `admin` or `edit` ClusterRole, or a role with `*` in its verbs, resources or API groups. ServiceAccounts in `kube-system` and `system:` users and groups are cluster components and pass, except `system:anonymous`, `system:unauthenticated`, `system:authenticated` and `system:serviceaccounts`, which stand for every client or every service account. A user named `system:serviceaccount:<ns>:<name>` or a group named `system:serviceaccounts:<ns>` is that namespace's ServiceAccounts and passes only in `kube-system`. The control-plane grants that k3s and kubeadm make on every cluster pass too, so a fresh cluster passes: users `kube-apiserver` and `k3s-cloud-controller-manager` (k3s) and group `kubeadm:cluster-admins` (kubeadm 1.29+). Names read from the cluster are shown literally, not as markup (#957).
  - It exits 1 when it finds a violation, and when kubectl cannot read the objects, showing kubectl's error. A clean cluster prints how many bindings it audited. `--namespace` has help text (#957).
- **Checkov's Built-In Fallback Finds the `latest` Base Images and Privileged Containers It Missed (`devops scan`, `devops_cli.security.checkov`)**:
  - Dockerfiles: a `FROM` with flags, such as `FROM --platform=$BUILDPLATFORM python:latest AS build`, and an untagged `FROM alpine` are flagged as pulling `latest`. A digest pins either. `scratch` and an earlier stage's name are skipped. `USER` is matched in any case, so `user nobody` no longer reports a container running as root (#957).
  - Dockerfiles are read as Docker reads them. A line ending in `\`, or in the character a `# escape=` directive sets, continues on the next line. The body of a BuildKit heredoc (`RUN python3 - <<EOF` up to `EOF`) is not read as instructions. A continued `FROM` or `USER` is found. Lines in a heredoc are never taken for instructions: a Python `from pathlib import Path` there is not a base image, and an nginx `user nginx;` is not a `USER` (#957).
  - A `$ARG` in an image skips the check only where it can hide the tag or digest, as in `python:${TAG}` or `$BASE`. `${REGISTRY}/library/python:latest` and an untagged `${REGISTRY}/python` are flagged (#957).
  - Kubernetes YAML: each document's pod spec is read wherever its kind keeps it (`spec`, `template.spec`, `spec.template.spec`, `spec.jobTemplate.spec.template.spec`), with its `containers`, `initContainers` and `ephemeralContainers`. The resources in a `List`'s `items`, which is what `kubectl get -o yaml` writes, and in an OpenShift Template's `objects` are read the same way. A privileged DaemonSet, StatefulSet, Job or CronJob is found, and `privileged: True`, `yes` or `on` counts. A file that does not parse as YAML, such as a Helm template, is matched line by line. So is YAML nested too deep to parse; it does not stop the scan. Manifests are parsed with libyaml when PyYAML has it, which keeps large CRD bundles fast. Checkov is not installed in the devcontainer or CI, so this fallback is what `devops scan` runs there (#957).
  - Each resource is walked once, so YAML anchors fanned out through a `List`'s `items` cannot make the scan run for hours, and a file nested deeper than the parser can follow is checked line by line (#957).
- **`devops scan complexity` Measures a Function Defined Directly in Another on Its Own (`devops_cli.security.complexity`)**:
  - A `def` or `class` written directly in a function body was walked as part of that function: its branches and depth counted toward the enclosing function, and it was never reported. Nested functions and classes are now measured on their own wherever they appear. The methods of a class defined in a function are methods, and a function nested in a method is not one (#957).
- **Toolset Instructions Reach the Agent's Run Prompt (`devops_cli.ai.agents`)**:
  - `PydanticAgent.run`, `run_sync`, `run_async` and `iter` build their system prompt with a `RunContext`. Given one, a devops-cli `FunctionToolset` or `AbstractToolset` answered with a coroutine that was closed unread, so its instructions were missing from the prompt of every run while `run_stream`, which passes no context, had them. pydantic-ai's own toolsets were missing with or without a context. A devops-cli `AbstractToolset` is now asked for its instructions synchronously. Any `FunctionToolset`, devops-cli's or pydantic-ai's, gets the run's context and its coroutine is run to completion, so its dynamic instructions render too (#958).
  - Inside a running event loop the coroutine cannot be run from synchronous code. A devops-cli `FunctionToolset` then gives its static instructions, and each dynamic one it leaves out is logged at debug level. A pydantic-ai toolset's instructions are skipped with a debug log record naming the toolset, and a toolset that raises is logged as a warning. All of these were dropped silently (#958).
- **Deferred Tool Hooks Get the Run's Context (`devops_cli.ai.agents`)**:
  - A `HandleDeferredToolCalls` handler taking `(ctx, requests)` was called with the requests alone during a run, which then ended with a `TypeError`. The loop now passes its `RunContext`. The call is chosen by the handler's signature alone: a handler that can be called with the requests alone, such as `(requests)` or `(requests, **kwargs)`, gets them alone, and any other gets `(ctx, requests)`, with a fresh `RunContext` when it is called without one (#958).
  - Every capability inherits pydantic-ai's async `handle_deferred_tool_calls(ctx, *, requests)`, and the loop called it with the requests alone. A run with any other capability, such as `Thinking`, ahead of the handler, or with no handler at all, ended with a `TypeError` once a tool needed approval. Only a capability that overrides the hook is asked, with the run's context, and its coroutine is run to completion. A capability's own `handle_deferred` method gets the context when it can take a second positional argument (#958).
  - Inside a running event loop an async hook cannot be run from synchronous code. The lookup then stops with a warning naming the capability, and the requests go back to the caller as `DeferredToolRequests`, so no capability after it, such as an approving `HandleDeferredToolCalls`, decides in its place (#958).
- **SQLite Memory Keeps What It Writes (`devops_cli.ai.harness.SqliteMemoryStore`)**:
  - The store opens a connection per call and defaulted to `:memory:`, which gives each connection a new empty database: a write reported `ok` and the next read returned nothing. `database` is now required, takes a `str` or a `Path`, and refuses `:memory:` and the empty name, which does the same with a temporary file. `InMemoryStore` keeps memory for the life of the process (#958).
- **Stopping a Background Command Ends Its Whole Process Group (`devops_cli.ai.harness.Shell`)**:
  - `stop_command` found the group through the leader's pid, which fails once the leader has exited and been reaped, and swallowed the error, so the leader's children kept running while it reported the command terminated. It also sent SIGKILL only when the leader outlived SIGTERM, so a child ignoring SIGTERM kept running. The group is now signalled by its id, which is the leader's pid, and probed until no member is left, and the members still there when the grace period ends get SIGKILL. The grace period is `Shell(stop_grace_seconds=...)`, 3 s by default. A group it may not signal, and a leader that outlives SIGKILL, are logged as warnings (#958).
- **Polyglot Outlines Parse With Tree-Sitter (`devops ai read --inspect`, MCP `ai_read`, `devops_cli.ai.inspection`)**:
  - The outlines of every non-Python file, at all three levels, came from the regex fallback alone and never from the tree-sitter grammars the project ships. That included a Python file that does not compile. They now come from one `TreeSitterEngine.parse_code` parse, which still falls back to the regex parser when a grammar finds nothing. Take a Rust file declaring `pub fn plain(x: i32)`, `pub fn process<T: Clone>(x: T) -> T`, `pub const fn c()` and `unsafe fn u()`. Its outline listed only `plain`, and `--symbol process` showed lines 1-4 of the file without saying the symbol was not found. All four functions are now listed, and `--symbol process` shows its own line (#959).
  - A Level 1 skeleton line for a TypeScript, Go, Rust or Java function held only its parameter list, `(x: string, y: number)`, with no name or return type. It is now the declaration line, `export function a(x: string, y: number): Promise<void> {}` (#959).
  - Level 0 lists every method. One whose class the file declares is listed under it, and any other among the functions: a Go method on a type declared in another file of the package as `Server.Close`, which was left out, and a C++ out-of-class definition by its qualified name, `Widget::draw` (#959).
  - A C++ `.h` header was outlined as C. Its outline was labelled `c` and listed none of its classes or methods, so `--symbol` found none of them. A header is now outlined as C++ when its content uses C++ and as C otherwise, as `devops ai ast parse` reads it (#959).
- **Topology Token Counts Measure the Outline (`devops ai read --inspect --level 0`, `devops_cli.ai.inspection`)**:
  - At Level 0, `outline_tokens` and `token_reduction_pct` were a guess: six tokens a symbol plus a one-line summary. The guess left out the docstrings, bases, method lists, exports and hotspots that the outline prints. Both now count the markdown the outline renders. The guess put `inspection.py`'s own topology at 291 tokens when it renders 1351, so it claimed a reduction of 96.4% against a real 83.2% (#959).
- **The Regex Fallback Signs and Finds Declarations as Tree-Sitter Does (`devops_cli.ai.ast.fallback`)**:
  - The fallback now signs every symbol it finds with the line that declares its name, as the tree-sitter engine does. Before, a function or method held only its parameter list (TypeScript, Go, Rust, Java) or a rebuilt `(args) -> ret` (Python), and a class, struct, interface or Terraform block held no signature (#959).
  - The fallback finds Rust functions with any qualifier the language allows (`const`, `async`, `safe`, `unsafe`, `extern "C"`) and with generics, `pub fn process<T: Clone>(x: T)`. It finds TypeScript functions with generics, `function f<T>(x: T)`, and declared as `export default function` (#959).
- **Tree-Sitter Gives Go Methods Their Type and Signs a Symbol With the Line That Names It (`devops ai ast parse`, `devops ai repomap --json`, MCP `ai_ast_parse`, `devops_cli.ai.ast.engine`)**:
  - A Go method had no owner. It now belongs to the type its receiver names, through a pointer, type arguments or parentheses, as the regex fallback has it: `func (l *List[T]) Push(v T)` is `List`'s (#959).
  - A symbol under a Java annotation, a C# attribute or a TypeScript decorator was signed with the annotation's line, `@Override` or `[HttpGet("{id}")]`, with no name or return type. It is now signed with the line that holds its name, `public String toString() {` (#959).
- **`ai.timeout` and `ai.tasks.<task>.timeout` Set How Long an LLM Request Waits (`devops ai`, `devops review path|branch|pr`, `devops_cli.ai.client`, `devops_cli.ai.review.runner`)**:
  - `LLMClient` waits the timeout its caller passes, else the task's configured `timeout`, else 3,600 s. It read only the caller's, so both keys were accepted and documented but did nothing for chat, metadata, analysis, verification or compose requests (#960).
  - A review's analysis, verification and compose clients wait their task's configured `timeout`, and 1,200 s only when none is set. The review runner passed 1,200 s to all three over any configured value (#960).
  - An Ollama model resolved for pydantic-ai carries `ai.timeout` as its request timeout (#960).
  - Both keys must be positive and finite, and `docs/CONFIGURATION.md` says what `ai.timeout` sets and what applies when it is unset (#960).
- **A Provider Reply Is Read Only Up to Its Size Limit (`devops ai`, `devops review path|branch|pr`, `devops_cli.ai.client.network`)**:
  - Claude, OpenAI-compatible and Ollama chat replies, and the model lists from `/models` and `/api/tags`, are streamed through `request_limited_json`, which refuses a Content-Length over the 50 MiB limit before reading and stops reading once the decoded body passes it. The client buffered the whole body and only then checked its size, so a model endpoint, or anyone on the path to a plain-http Ollama URL, could send a multi-GB reply and exhaust the CLI's memory. With the limit lowered to 4 KiB, each of the five calls now stops a 2,000-chunk reply within its first 5 chunks; all 2,000 were read before (#960).
  - A reply that is not 2xx has its body read under the same limit, still raises the HTTP error the providers handle, and is never parsed. A reply that is JSON but not an object is refused (#960).
  - Size-limit messages name the limit in MB, KB or bytes; a 4 KiB limit read "0MB" (#960).
- **A Remote Model Goes Where Its Settings Say, or Resolving It Fails (`devops_cli.ai.pydantic_ai_bridge`, `devops_cli.ai.durable`, `devops_cli.ai.gateway`)**:
  - An `ai.api_base_url`, `ai.gateway_url` or `ai.portkey_url` that cannot be used raises a `ConfigurationError` naming that setting, and a model pydantic-ai cannot build, including one whose provider's optional package is not installed, raises one naming `ai.provider` and `ai.model` with pydantic-ai's reason, such as its "Did you mean" hint. Both returned the bare model string, so `api_base_url: localhost:8000/v1` (no scheme) sent `openai:gpt-4o` to `https://api.openai.com/v1/` with the configured endpoint and key dropped (#960).
  - Under `ai.provider: gateway` every model name is a route of the `ai.gateway_provider` gateway, sent whole as `LLMClient` sends it, so an Ollama tag such as `mistral:7b` stays a route. Under `openai`, `copilot` and `claude`, a name whose text before its first colon names no provider, such as `devops-review` or `qwen3-coder:30b`, takes the provider's prefix: `openai` and `copilot` as OpenAI chat models, the API `LLMClient` uses, with `copilot` on Copilot's API, and `claude` as `anthropic`. A provider is one this repository registers or pydantic-ai knows (`is_pydantic_ai_provider`). `litellm:` and `portkey:` models are OpenAI chat models sent to `ai.gateway_url` and `ai.portkey_url` under every provider, `ollama` included; `litellm:<model>` lost its prefix and could not be inferred, left to pydantic-ai it went to `https://api.openai.com/v1/`, and under `ollama` it was an Ollama model of that name (#960).
  - `create_pydantic_ai_agent` falls back to `PydanticAgent` only when pydantic-ai's `Agent` refuses its arguments, and `create_durable_pydantic_agent` no longer catches every error from resolving its model, so a configuration error reaches the caller. The durable factory handed the native `Agent` the bare name, which pydantic-ai sent to the vendor's endpoint (#960).
  - The fallback cascade `"cascade"` is LiteLLM's and Portkey's `devops-chat` route, then `ai.model` on Ollama itself, and `GatewayRouter.build_pydantic_cascade_model` is a route and its failover route on the router's gateway, then `ai.model` on Ollama, which a failover to `direct-ollama` names. Their bare members (`litellm`, `portkey`, `ollama` and the routes) were read as model names: building either raised pydantic-ai's "Unknown model", and under provider `ollama` every member was an Ollama model of that name (#960).
- **The Example Config's Local RAG Backends Pass the SSRF Guard (`devops review path|branch|pr`, `devops ai rag`, `devops_cli.core.validation`, `devops_cli.ai.rag`)**:
  - `validate_configured_service_url` is the one policy for service URLs from the user's own configuration: loopback (`localhost`, 127.0.0.0/8, ::1) passes without `ai.allow_private_network`, every other non-public host still needs it, and cloud metadata hosts are always refused. Qdrant, the Ollama, OpenAI and gateway embedding calls, the Ollama provider, the LLM client and `create_pydantic_ai_provider`, which builds the bridge's remote models, use it. With `config.example.yaml` as shipped, `QdrantClient("http://localhost:6333")` raised `SSRFBlockedError` and every embedding call to `http://localhost:11434` was refused, so RAG never ran; the client also refused the example's gateway at `http://localhost:4000/v1` (#960).
  - The first RAG lookup of a run that fails, such as on a vector store the guard refuses, logs one WARNING with the cause; later ones log at debug. All of them logged at debug, so a refused backend left RAG off without a word (#960).
- **`--namespace` No Longer Selects the Kubeconfig Context (`devops argo workflows`, `devops argo rollouts`)**:
  - `workflows list`, `workflows submit` (and its `--wait` poll), `workflows logs`, `rollouts list` and `rollouts status` handed `--namespace` to the Argo custom resource client as the kubeconfig context. Outside a pod, `-n argo` failed with a missing-context error, or reached another cluster when a context of that name existed. They now use the current context and send `--namespace` only as the namespace (#961).
- **A Workspace File the Command Cannot Read Is Left As It Was (`devops workspace add`, `devops workspace remove`)**:
  - A workspace file over the size limit, not UTF-8, not plain JSON, or without a `folders` list was read as empty, and `add` then saved one folder over it, dropping every folder and setting it held. VS Code accepts comments and trailing commas in a `.code-workspace` file, so a file VS Code wrote could trigger it. Both commands now print the error, say the file was left unchanged, and exit 1. A file that does not exist yet still starts empty (#961).
- **Only a Listener on 127.0.0.1:9418 Counts as a Running Git Daemon (`devops devcontainer post-start`)**:
  - Any live process named by `/tmp/git-daemon.pid` counted as the daemon. `git daemon` never removes that file, and `/tmp` is a volume that outlives container rebuilds, so after a rebuild post-start could report the daemon running and never start it. The port probe is now the only check (#961).
- **Port-Forward Records Survive Concurrent Runs and Reused Pids (`devops k8s port-forward`, `devops k8s port-forward-status`, `devops k8s port-forward-stop`)**:
  - Every read-change-save of the state file holds an exclusive lock on `port_forwards.lock` beside it, from the read to the save, and a run holds it while it starts its forwards. Two runs at once, or a stop during a start, no longer save over each other's records and leave forwards that hold their local ports but are never listed or stopped (#961).
  - `port-forward-status` with no state file returns at once and creates no `.data/k8s/` directory or lock file where it runs (#961).
  - The state file is written to a temporary file and moved into place, so a read never sees it half written (#961).
  - Each record keeps its process's start time from `/proc/<pid>/stat`. A forward counts as running, and `port-forward-stop` signals it, only while its pid still has that start time, so a pid the kernel has since handed to another process is neither listed nor sent SIGTERM. Where `/proc` cannot be read, a live pid is still enough. A state file written before this change has no start times, so it reads as no forwards and the next start saves over it; forwards it recorded keep running until ended by hand (#961).
- **A TLS Secret kubectl Rejects No Longer Deletes the Live One (`devops k8s create-tls-secret`, `devops k8s enable-tls --overwrite`, `devops tls enable-k8s`)**:
  - The commands deleted the secret and then created the new one, so a certificate and key kubectl rejects, such as a rotated certificate with the old key, or an API error left the namespace with no secret, and its ingresses fell back to the default certificate. The secret is now rendered with `kubectl create secret tls --dry-run=client -o yaml` and applied over the existing one with `kubectl apply -f -` only once it renders. Nothing is deleted. A failure shows kubectl's error and leaves the existing secret in place, and `create-tls-secret` reports `Applied TLS secret` (#961).
- **The Drift Report Says When It Could Not Be Saved (`devops ai audit-library-usage`)**:
  - A report that could not be written, to an unwritable analysis directory or a full disk, was dropped without a word, and the previous run's `api_drift_report.json` stayed in place as if current. The failure is now logged and shown as a warning (on stderr with `--json`), the previous report is removed before each write, and the command prints where it saved the report (#961).
- **`devops gh labels sync` Fails When gh Does (`devops gh labels sync`, `devops gh labels list`)**:
  - Without a token and with gh logged out, the failed `gh label list` read as no labels and every failed `gh label create` went unseen, so the command printed `Label sync complete` and exited 0. A failed `gh label` call now raises, and the command prints the error and exits 1 (#961).
  - `gh label list` is asked for up to 1000 labels. It stopped at 30, one short of `.github/labels.yml` (#961).
  - `sync_repository_labels` (`devops_cli.github.labels`) takes a typed client and calls it directly. Its fallbacks retried a call that raised `TypeError` without the repository, which no client accepts, and skipped a client lacking a method while still counting the label as created (#961).
- **Semgrep AST Scanner Timeout Realignment & Target Filtering (`devops_cli.security`)**:
  - Realigned `BaseSecurityScanner.scan` default execution timeout from `DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS` (30s) to `DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS` (300s), ensuring external CLI scanners executing against multi-file changesets or repository diffs do not trigger premature `TimeoutExpired` aborts (#963).
  - Filtered non-code targets (documentation markdown files, lockfiles like `uv.lock`, and binary assets) in `_build_scan_command` using `CONST_SEMGREP_EXCLUDED_EXTENSIONS`, preventing unnecessary file parsing overhead during Semgrep AST security reviews (#963).
  - Hardened `_resolve_cwd` for multi-file target lists using `os.path.commonpath` to resolve the common root directory rather than pinning the subprocess to the parent directory of the first file (#963).
- **RAG Query Latency No Longer Flattens at 5 s (`devops_cli.telemetry.instruments`, `k8s/monitoring/dashboards/devops-cli.json`)**:
  - `devops_cli_rag_query_duration_ms` buckets stopped at 5 s, below the query's own timeouts, so in any hour where more than 5% of queries took longer the "RAG Query Latency (p50, p95)" panel's p95 read exactly 5000 ms. The buckets now run to 600 s (`10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 15000, 30000, 60000, 120000, 300000, 600000` ms), past the gateway embedding request's 30 s and the default `qdrant.timeout` of 300 s, up to 600 s, the top of the range that suits a homelab Qdrant. The panel descriptions state the new cap, 600000 ms (#975).
  - The panel now reads `stage="total"`. The series earlier releases sent carry no `stage` label and buckets that stop at 5000 ms. The panel leaves them out rather than mix the two bucket sets in one quantile, so it draws only queries recorded by this release or later, from any host. The old series stay in Prometheus until retention drops them (#975).
- **Review Tables Print Untrusted Text as Written (`devops review findings`, `devops review path|branch|pr`)**:
  - `devops review findings` read finding titles, locations, personas and verdict reasons as Rich markup. A title holding a closing tag such as `[/{status_color}]` stopped the command with a `MarkupError`, and a lowercase bracket such as `[standard]` vanished. A review's dependency and network tables did the same with package names, versions, targets and statuses, so `uvicorn[standard]` printed as `uvicorn`. They are escaped now (#987).
- **Bandit Runs on Reviews of More Than 50 Python Files, and a Failed Analyzer Says Why (`devops ai review`, `devops scan report`, `devops_cli.security.bandit`, `devops_cli.security.base`)**:
  - `BanditScanner` passes `-q` in each of its command shapes: a file list, a single file and `-r <directory>`. Over more than 50 files Bandit 1.9 draws a progress bar on stdout ahead of its JSON report, so the report did not parse, and the exit code 1 that meant "issues found" was recorded as a failure. Every branch review with more than 50 changed Python files, `release/v0.2.25`'s among them, reported `! Failed during execution: Bandit` and left Bandit's findings out, as did `devops scan report` of a directory holding more than 50 Python files (#1009).
  - A scanner that exits non-zero with output that is not JSON now fails with a reason that says so and quotes the start of that output on one line, then as much of stderr as fits in 256 characters, as in `Scanner exited with code 1; output was not JSON, starting "Working... ━━━━ 100% 0:00:20 { "errors": [] …"; stderr: …`. The reason quoted only stderr, which for Bandit was its INFO log (#1009).
  - The session report's Static Analyzers table gives a failed analyzer's reason after its state, as in `failed: Scanner exited with code 1; output was not JSON, …`, with pipes escaped and line breaks folded. The console line names the analyzer and points there: `! Failed during execution: Bandit (the report's Static Analyzers table says why)` (#1009).
- **The DevSecOps Persona Reports Misconfiguration and Error-Handling Defects Again (`devops review`, `devops ai review`)**:
  - #951 defined a security finding only as a quoted path from an untrusted source to a sink, said most files have no security defect, and excused any choice the manifests or conventions document. In session `20261002-205520`, the first branch review with those prompts, 367 of 380 persona replies held no finding, and none of the four real findings earlier reviews had reported was generated: ingress from `0.0.0.0/0` in `k8s/monitoring/networkpolicy.yaml` (#953) and `k8s/otel/networkpolicy.yaml` (#913), a broad `except` in `ai/rag/investigator.py` (#423), and the `trust_remote_code` claim in `docs/VISION.md` (#921) (#1015).
  - A finding is a quoted vulnerability path or a quoted misconfiguration: the setting or line, and what it exposes or permits that its job does not need, with no untrusted source. A misconfiguration the manifests or conventions justify, by saying why it is safe, is not a finding; a comment that only restates the rule or names its sources, as the monitoring policy's does, is not a justification. The persona returns no finding only when it can quote no vulnerability, no misconfiguration, no false security claim in a document and no other defect a *Where to Look* class names, and the sentence "Most files have no security defect" is gone. On code it keeps an evidence bar: a value that reaches no sink it can quote is not a vulnerability, and most code has none. The persona's role names the setting that permits more than its job needs beside the untrusted path (#1015).
  - *Where to Look* adds **Network Exposure**, a NetworkPolicy, Ingress, Service, firewall rule or security group that admits `0.0.0.0/0`, every namespace or every pod to a port whose known consumers are fewer than that. A port the manifests or conventions say must face every source, and say why that is safe, such as an API that authenticates every request, is not exposure; a port open to every address without that reason is. Egress to every address with cloud metadata blocked is not exposure, and no NetworkPolicy rule is SSRF. A NetworkPolicy publishes no port, so the persona is asked to rate the finding MEDIUM at most unless it quotes the node port, load balancer, host port or Ingress route that does. It also adds **Error Handling**, a broad `except` that hides an unexpected error from the operator by logging it below warning or not at all, or that swallows one where failing closed matters, such as authentication, verification, a security check or data integrity, which the persona is asked to rate LOW, and higher only with a quoted consequence such as a skipped check (#1015).
  - The configuration page prompt, which NetworkPolicies, Ingresses and Services get, names **Network Exposure**: a rule that admits more sources to a port than its consumers need. Its sentence "A setting the workload does not need is not a defect", which contradicted the misconfiguration rule, now reads that a *missing* setting the workload does not need, such as a CPU limit, is not a defect (#1015).
  - The documentation prompt reports a false security claim again: a statement that the program applies a security control that the code contradicts or does not apply. #951 asked every documentation finding to quote the code line that contradicts it, which a claim about a control the code lacks cannot do. The evidence bar, the rule against advisory identifiers from memory, and the exemption for roadmaps, changelogs, task files and decision records stay as #951 left them (#1015).
  - The verifier asked every security finding for an untrusted source and a sink before it could be **Verified**, so a restored misconfiguration could not be. It now asks a vulnerability for the source and the sink, and a misconfiguration for the quoted setting and what it exposes or permits beyond its job (#1015).
  - The prompt digest changes, so reviews from before and after this change are separate arms of a prompt benchmark (#1015).
- **Passing Criteria Leave a Finding for the Verifier Instead of Verifying It (`devops review path|branch|pr`, `devops_cli.ai.review.review_environment`)**:
  - A passing verification criterion no longer settles VERIFIED. One that counts as evidence is recorded in `verified_criteria_matched`, gives the finding no confidence, and leaves it unverified, so the verifier is shown it and its verdict applies. The evidence rule tells whether a command runs the cited code and checks the outcome, not which side of the claim a pass supports. In review session `20261003-012555`, both verification criteria of a false finding on `ai/review/chunker.py:395` ("Undefined method call on PurePosixPath"; `PurePath.full_match` exists on Python 3.13 and later) asserted that `skips_persona_review` returns the right value, the opposite of the claim. Replayed under the 30 s python limit, both passed and the finding ended VERIFIED by criteria at confidence 1.0, a verdict the verifier never saw and that the report would rank first (#1043).
  - A passing invalidation criterion that counts still settles INVALIDATED, and criteria that pass on both sides still leave the finding unverified with the note `criteria-non-discriminating`. Replayed with the results they recorded, none of the 2,461 candidate findings with a passing criterion in the saved review sessions ends VERIFIED by criteria (#1043).
  - Merging duplicate findings into a VERIFIED one keeps the adjudicator of a verified input. It no longer writes `criteria` when the inputs named none, nor takes the adjudicator of an input that was not verified (#1043).
- **Running the Cited Test Counts as Evidence (`devops review path|branch|pr`, `devops_cli.ai.review.criteria_evidence`)**:
  - A `python -c` criterion that calls, as a statement of its own, the test whose definition spans the cited line, imported from the cited test module, counts as evidence: the test's own asserts are the check. A test is a module-level function named as pytest names one (`test...`) in a file pytest collects (`test_*.py`, `*_test.py`). An async test does not count, since a bare call only creates its coroutine, and neither does a call inside a `try` or handed to another function such as `pytest.raises`. A bare call of any other function still does not count: it shows only that the function did not raise for those inputs (#1043).
  - In session `20261003-012555`, the invalidation criterion of `tests/test_rag_multi_project_indexer.py:66`, a claim that the test raises TypeError, called that test and passed in 4.1 s; the finding now ends INVALIDATED by criteria instead of reaching the verifier, whose reply was cut. Filed as a verification criterion, as on `tests/test_pipeline_protocol.py:114` in session `20260928-201857`, where a claim that the test is wrong was VERIFIED by criteria, the same kind of call leaves the finding to the verifier (#1043).
- **A Hedged Title Is MEDIUM at Most, Whoever Verified It (`devops review path|branch|pr`, `devops_cli.ai.review.calibration`)**:
  - A hedged title ("Potential", "May", "Could") VERIFIED by criteria no longer keeps a severity above MEDIUM, and `CONST_REVIEW_EVIDENTIAL_ADJUDICATORS` is removed. Criteria settle no VERIFIED verdict, and the verifier's confirmation is not evidence enough to lift the cap. Replayed over session `20261001-224227`, 8 of its HIGH findings, hedged and VERIFIED by criteria, are now MEDIUM (#1043).
- **The Scanned-Clean Check Needs Advisory Wording, and the First Early Check to Fire Gives the Reason (`devops ai review`, `devops_cli.ai.review.verification`)**:
  - A finding is INVALIDATED as `deterministic:scanned_clean_dependency` only when its title or description names, as a word, a dependency this session's scan reported CLEAN with no advisory record and also uses advisory wording somewhere in that text: the word "CVE" or "CVEs", a CVE id included, a GHSA id, "advisory" or "advisories", "unpatched", "known vulnerability" or "known vulnerabilities", or "vulnerable version". The name and the wording need not be next to each other. "Vulnerable" alone and "outdated" no longer trigger it, because a CLEAN scan says only that the pinned version carries no known advisory. It says nothing about how the code uses the package, what a Kubernetes manifest does, or whether the version is current (#1044).
  - Since #948 gave the check every dependency a session scanned, any security finding that named one of them as a word was INVALIDATED with the reason `This run's own advisory scan reports <name> CLEAN`. The names included kubernetes, httpx2, keyring, pytest, docker and bandit. Among the findings were a command injection in a Kubernetes client call, an SSRF through httpx2, a path traversal in a Bandit test helper, and Semgrep's own `yaml.kubernetes.security.*` findings. Replayed with session `20261003-012555`'s 58 CLEAN dependencies over 5,904 saved candidates in 36 sessions, the check fires on 8 candidates (6 distinct, none VERIFIED or reportable in its own run) instead of 111 (83 distinct, 26 VERIFIED, 34 of them Semgrep Kubernetes findings) (#1044).
  - The early checks stop at the first one that fires. Each check writes its verdict on the finding itself, and every check used to run, so the last one to fire overwrote the reason the first gave. A manifest finding that cited `CVE-2024-xxxx` and mentioned Kubernetes best practices was given "advisory scan reports kubernetes CLEAN" instead of the placeholder-advisory reason (#1044).
- **The Slow Tier Keeps Its Embedding Model Loaded Beside qwen3-coder and Leaves Every Interactive Pool (`k8s/llm/profiles/ollama-profiles.yaml`, `k8s/llm/gateway/configmap.yaml`)**:
  - Since #1061 every Ollama tier kept one model loaded, but the gateway still sent ollama-48gib-slow both embedding groups and five chat groups, so each chat request routed there evicted the embedding model and each embedding evicted the chat model. During a review pinned to `qwen3-coder:30b`, the tier loaded a runner 10 times in four minutes, alternating bge-m3 and qwen3-coder, and 6 of 124 `/api/embed` requests waited 31 to 40 s, past the client's 30 s embedding timeout. The first such failure turns RAG off for the rest of the run (#1064).
  - ollama-48gib-slow sets `OLLAMA_MAX_LOADED_MODELS` to `2` and `OLLAMA_KEEP_ALIVE` to `-1`, so its embedding model and `qwen3-coder:30b` stay loaded together and neither reloads after 5 idle minutes. `OLLAMA_NUM_PARALLEL` stays `1` on every tier, and every other tier still keeps one model loaded (#1064).
  - The gateway sends ollama-48gib-slow no interactive or review traffic: its deployments in `devops-chat`, `devops-review`, `qwen3-coder:30b`, `gemma4:31b` and `qwen3.8:27b` are removed. At one request at a time, background work there would queue in front of review calls, and Ollama predicts a dense ~30B model too large to fit beside the embedder, so loading one evicted it. `qwen3-coder:30b` still copies `devops-review`'s qwen3-coder deployments exactly (#1064).
- **A Review's Semgrep Scan Finishes Again, Still Isolated From the Reviewed Tree (`devops review`, `devops_cli.security.semgrep`, `devops_cli.security.base`)**:
  - Since #972 a review ran Semgrep from a temporary directory and named each reviewed file by its absolute path in the tree. Semgrep 1.178.0 takes a target that is a regular file under its working directory as it is, and for any other starts a `semgrep-core` process that walks the target's whole checkout, nested worktrees and `repos/` included. Semgrep ran out of its 300 s timeout in 11 of 11 reviews and returned nothing, so they lost the findings only Semgrep makes, such as `runAsNonRoot` and `allowPrivilegeEscalation` on the Ollama DaemonSets (#1079).
  - A review now hard-links each file Semgrep scans into that temporary directory at its path in the reviewed tree, or copies it when linking fails, and names it `./<that path>`. Findings keep the reviewed tree's paths and line numbers. Only the targets are there, so no `.semgrepignore`, `.semgrep.yml` or `.semgrep/` rule of the tree reaches the scan, and a reviewed file that is a link out of the tree is left out. A file the tree names like an option, such as `--config=x.yml` or `--autofix`, or `-`, is still only a file to Semgrep. On this repository's 387-file branch review, with a local rule file and no network, the review's scan took 24 to 32 s in its four batches. One run of the same files took 8.4 to 15.5 s this way and 148.8 s with the files named from outside its working directory (#1079).
  - A review scans its files in batches of at most 100, each under its own timeout, so a batch that runs out of time loses only its own files, and the reason says which batch it was (#1079).
  - Every scanner a review or `devops scan` runs gets an empty stdin, never the caller's, such as the request stream of `devops mcp` (#1079).
- **A Scanner That Runs Out of Time Says So (`devops review`, `devops scan report`, `devops_cli.security.base`)**:
  - A timeout read `failed: Scanner execution failed: Command '['semgrep', 'scan', …` in review.md, SARIF and the CLI, cut off before the reason. It now reads `timed out after 300 s` (#1079).
- **Release Notes Fit GitHub's Body Limits (`devops release notes`, `devops release changelog`, `devops release pr`, `devops release sync-notes`)**:
  - GitHub refuses a Release body over 125,000 characters and a pull request body over 65,536, and v0.2.25's changelog section is 196,525. Notes that fit are printed unchanged. Longer notes keep every `###` category and each entry's title, drop the sub-bullets, and end with a link to the version's section of `CHANGELOG.md` at its tag; titles that still do not fit are cut at the last whole entry, with a count of those left out. v0.2.25's notes come to 22,780 characters (#1097).
  - The release PR body counts its other sections against the PR limit. Entries are read with the changelog parser the cut uses, now with markdown-it-py, and the link's anchor comes from mdit-py-plugins; both are declared dependencies, where before they arrived only through Rich and Textual (#1097).
- **Review Personas Are Shown Only the Target's Judged Claims (`devops review path`, `branch`, `pr`)**: the persona loop built its system prompt without the review's target, so a review run from another checkout was shown the working directory's disproved claims, which could suppress a valid finding. Every layer from `_execute_review_workflow` and `ReviewPipelineOrchestrator` down to `render_negative_exemplars` now requires the target, so no caller can fall back to the working directory (#1100).
- **A Review of Another Checkout Reads That Checkout's Analysis Metadata**: `--summary` and the persona loop loaded file analysis metadata from the working directory's repository; they now load it from the target's (#1100).

### Security
- **Logs Leave Loki Only by Age (`k8s/logging/loki-values.yaml`)**:
  - `limits_config.deletion_mode: disabled` keeps Loki's log delete API closed. The delete-request store that retention requires would otherwise open it, and with `auth_enabled: false` any pod allowed to reach Loki could delete logs without credentials (#550).
- **Scanner Failure Reasons Are Masked Before They Are Cut (`devops scan report`, `devops ai review`, `devops docker analyze-layers`, the `docker_analyze_layers` tool, `devops_cli.security.base`, `devops_cli.security.dive`)**:
  - A scanner's failure reason quotes an exception, stderr or the start of output that was not JSON. It reached SARIF `toolExecutionNotifications`, the CLI warnings and review.md's Static Analyzers table without masking, so a `ghp_` token or a `user:password@` URL in a scanner's error was written out as it was. `ScanOutcome` now masks every reason with `mask_secrets`, then cuts it to 256 characters (`CONST_MAX_ERROR_DETAIL_LENGTH`), ending in `…` when cut, whichever scanner or code path produced it (#915).
  - Some reasons were cut before anything masked them, which can split a credential so that no pattern matches the part left, and others were not cut at all. A scanner that raised during `devops scan report` gave a reason as long as its error: 5,124 characters for a 5,000-character error. Those early cuts are gone. Output that was not JSON is masked before its start is quoted, and every scanner reason, #1009's for output that was not JSON among them, is capped at the same 256 characters (#915).
  - Dive cut its stderr or error to 256 characters before anything masked it, so a private key it quoted lost its END marker, was not recognized, and reached `devops docker analyze-layers`, the `docker_analyze_layers` tool, and through `devops scan report` the SARIF file and the CLI. Dive's reason is now masked, then cut to the same 256 characters (#915).
- **Reviews Run Nothing From, and Take No Conventions From, the Tree Under Review (`devops review`, `devops_cli.ai.review`)**:
  - The type check that dismisses a claimed `None` dereference ran `uv run mypy --strict <file>` in whatever directory the CLI was started from. Started inside a repository under review, `uv run` synced that project and ran its build backend, and mypy loaded that project's config and plugins. The check now runs devops-cli's own interpreter in isolated mode, `python -I -m mypy --strict`, from an empty temporary directory, with devops-cli's own config, which loads only the `pydantic.mypy` plugin its `[tool.mypy]` loads. Nothing of the reviewed tree runs, even when `PYTHONPATH` names it. A target whose imports devops-cli's interpreter cannot resolve fails the check, which leaves the finding to the model verifier (#946).
  - The check keeps mypy's cache in devops-cli's cache directory (`<data dir>/cache/typecheck-probe/`), one per interpreter, and runs one probe at a time, so a cold pass over a module's imports is paid once rather than by every probe (#946).
  - `devops review branch` read `AGENTS.md` and `.devops/review.md` from the branch's working tree and gave them to the personas and the verifier, so a branch could add exemptions that suppress findings about itself. It now reads both with git where its diff starts: the merge base of the branch and its base, or `HEAD` for uncommitted changes. `devops review pr` already read them from the pull request's base and is unchanged (#946).
  - `devops review branch` no longer takes the checked-out branch as its own base when the base has no local branch. A CI checkout or single-branch clone of a feature was reviewed against `<feature>~1`, its last commit only, under conventions its earlier commits set. The base is now `origin/<base>` when only that exists, and with no base at all the diff fails (#946).
  - The conventions lookup stops at the root of a defect corpus, which its manifest marks, so a corpus under `.data/reviews/corpora/` is no longer reviewed under the conventions of the checkout around it. The manifest is read as the conventions are: at their revision, so a branch cannot add one to hide its base's conventions, and on disk only as a regular file, so a FIFO or a link to `/dev/zero` cannot hang the lookup or exhaust memory. `devops review corpus generate` copies the first source's conventions files only where the source has them, and no longer writes placeholders in their place. Each review's `profile.json` records `conventions_digest`, a digest of the conventions its prompts carried, which `prompt_digest` does not cover, and empty when they carried none (#946).
  - The conventions lookup reads only regular files within the tree under review. On disk it followed links, so a reviewed tree's `AGENTS.md` linked to a file outside it put that file's text into the prompts. A conventions file that is a link, or that resolves outside the repository, is now skipped, as the chunker skips a linked source file, and a link committed at the revision a branch review reads is skipped too, where its target's path had been read as the conventions. A project that keeps `.devops/review.md` as a link must make it a regular file. A file reached through a linked directory is skipped too, inside the tree as well as out of it, so a path review and a branch review of one tree read the same files (#946).
  - `read_file_at_revision` (`devops_cli.git.operations`) reads only a regular file: it looks the path up with `git ls-tree` and reads the blob by its object id. A directory, which `git show` printed as a listing, and a link, whose blob is the path it points to, read as absent. It accepts any path inside the repository, refusing only an empty or absolute path, one that starts with `-`, or one with a `..` part, so a branch review from a subproject whose name holds a space or a character outside ASCII reads that subproject's conventions, and a changed file named so gets its symbol delta (#946).
- **Model-Written Scripts No Longer Run in the CLI's Process (`devops_cli.ai.harness`)**:
  - `DynamicWorkflow`, `WorkflowAgent` and `CodeMode` are removed without a replacement, with their `run_workflow` and `run_code` tools and their exports from `devops_cli.ai`, `devops_cli.ai.agents` and `devops_cli.ai.harness`. Both tools ran a model-written Python script with `exec` in the CLI's own process, and neither sandbox contained it: each handed the script the `typing` and `asyncio` modules, so `typing.sys.modules['os']` reached `os`, and in `run_workflow` `asyncio.create_subprocess_exec` started processes. No command built any of the three classes (#947).
  - A gate test fails when any module in `src/devops_cli` calls the `exec` or `eval` builtin (#947).
- **The Monitoring Perimeter Admits Traefik, Not Every Pod (`k8s/monitoring/networkpolicy.yaml`)**:
  - Ingress rule 2 of `monitoring-default-perimeter` admitted `ipBlock: 0.0.0.0/0` beside its Traefik peer, on the Grafana, Prometheus, Alloy, kube-state-metrics, node-exporter, DCGM exporter and Pyroscope ports. kube-router, the cluster's policy engine, matches an ingress CIDR against pod addresses, so every pod in every namespace could query and remote-write Prometheus, which has no authentication, and read Grafana as an anonymous Viewer. The CIDR is removed and no address range replaces it. Traefik in `kube-system`, the only way in from the Cloudflare tunnel, keeps every port it had (#953).
  - `devops k8s port-forward` is unaffected: `kubectl port-forward` enters the pod's own network namespace. `devops k8s configure-urls --addressing proxy` reaches Grafana, Prometheus and Pyroscope through the API server on the control-plane node, which kube-router admits only to pods on that node, so those addresses answer only while the pods run there. `k8s/README.md` says how each path gets through (#953).
- **Qdrant Runs With the Container Security Context Its Values Declare (`k8s/llm/values-qdrant.yaml`)**:
  - The values set a top-level `securityContext`, which the `qdrant/qdrant` chart never reads, so dropping every capability never reached the pod. They now set `containerSecurityContext`, which the chart renders: user and group 1000 to match `podSecurityContext`, non-root, not privileged, no privilege escalation, a read-only root filesystem, every capability dropped, and the `RuntimeDefault` seccomp profile. The chart's own defaults had kept the root filesystem read-only, with group 2000 and no capability or seccomp settings (#953).
- **An MCP Client Cannot Name the Benchmark's Server (`benchmark_embeddings` MCP tool)**:
  - The tool refuses a `model` holding `@` or `://`, which `devops ai benchmark` reads as `model@endpoint` and sends that model's requests to, and a `provider` other than `ollama`, `claude`, `copilot`, `openai` or `gateway`. It raises `ValidationError` before any command runs. A client calling `benchmark_embeddings(provider="openai", model="x@https://<host>")` had the benchmark send `POST https://<host>/v1/embeddings` with the configured AI key as its bearer token. The model now runs on the configured servers, and naming a server stays on the command line (#954).
- **The AI Key Goes Only Where the Configuration Sends It (`devops ai benchmark`)**:
  - The embedding and chat benchmarks give a client the AI key only when the client sends it to the configured `ai.api_base_url`, `ai.gateway_url` or the configured provider's own API, compared by scheme, host and port. A `model@url` entry or a `--servers` URL anywhere else gets no key, and the embeddings engine does not take `OPENAI_API_KEY` or the keyring's key in its place. A gateway client sends to `gateway_url` whatever the model names, so it keeps the key. The `--models` help says so (#954).
- **Telemetry Stays Off When the Configuration Cannot Load (`devops_cli.telemetry.tracer`, `devops_cli.config.settings`)**:
  - A configuration layer that could not be read, or a registered `DEVOPS_CLI_*` variable that could not apply, left telemetry on and exporting to `OTEL_EXPORTER_OTLP_ENDPOINT` or `http://localhost:4318`, even when that layer set `telemetry.enabled: false`. `DEVOPS_CLI_TELEMETRY_ENABLED` and `DEVOPS_CLI_TELEMETRY_ENDPOINT` now still decide when the settings cannot load. Unless `DEVOPS_CLI_TELEMETRY_ENABLED` turns export on, it stays off, since the layer that cannot be read may be the one turning it off (#956).
- **`devops ai ast parse --query` Checks the Size Cap Before Reading (`devops ai ast parse`, MCP `ai_ast_parse`, `devops_cli.ai.ast.engine`)**:
  - A plain parse refused a file over the AST size cap of 50 MiB, but `--query` read the whole file and passed it to the parser, so an MCP client could make the server read and parse a file of any size. The query now runs through the new `TreeSitterEngine.query_file`. It applies the plain parse's size check before reading the file and the same `.h` header detection. Over the cap, it exits 1 with the same "Unsupported language or file size exceeded" error (#959).
- **A Gateway's Key Stays With the Gateway (`devops_cli.ai.pydantic_ai_bridge`)**:
  - Under `ai.provider: gateway`, a model named with a vendor's prefix, such as `openai:gpt-4o`, is a route sent to the gateway. pydantic-ai built it as a model at the vendor's public endpoint (`https://api.openai.com/v1/`) holding the configured API key, so the prompts and the gateway's key left for the vendor (#960).
- **A pydantic-ai Model Is Sent to a Private Host Only With the Opt-In (`devops_cli.ai.pydantic_ai_bridge`, `devops_cli.ai.providers`)**:
  - `create_pydantic_ai_provider` validates its base URL with `validate_configured_service_url` and takes `allow_private_network`, which the bridge passes from `ai.allow_private_network`. It allowed every host but cloud metadata, so with the opt-in off, `openai:gpt-4o` under an `ai.api_base_url` on an RFC-1918 address built a model that sent the prompts and the API key there, though `LLMClient` refuses that URL. A model whose `ai.api_base_url`, `ai.gateway_url` or `ai.portkey_url` is such a host now raises a `ConfigurationError` naming the setting; loopback still needs no opt-in (#960).
- **The LLM Client Never Sends to a Cloud Metadata Host (`devops_cli.ai.client.network`)**:
  - A base URL on a cloud metadata host is refused even with `ai.allow_private_network` set. `validate_base_url` skipped every check when private hosts were allowed (#960).
- **A Review Takes No Config or Data From the Repository It Starts In, Unless That Is devops-cli's Own (`devops review`, `devops ai review`, the MCP review tools)**:
  - Every `devops review` command reads a tree devops-cli does not own, or what a review of one wrote, and started in another repository none now reads a project config it was not told to. Started inside a repository that commits `.devops/config.yaml` naming its own `ai.gateway_url`, a review sent its model traffic, with the API key as a bearer token, to that host. A review started there reads the user-level config (`~/.config/devops-cli/config.yaml`) and, as the explicit opt-in, the file `DEVOPS_CLI_CONFIG` names; outside the review commands the project layer still applies (#972).
  - devops-cli's own repository is exempt: the one whose checkout holds the source of the devops-cli that runs, as an editable install's does, with every worktree of it. Its code already runs in the process, so a review started there reads its project config and keeps all of its data under the main worktree's `.data`, as before #972. A clone nested in that checkout, such as one under `repos/` or `.data/samples/`, is another repository, and an installed devops-cli, in site-packages or outside any repository, trusts no repository this way (`is_own_source_repository`, #972).
  - The root command holds the rule for `devops review` and `devops ai review` before it opens the command's span, which builds the process's tracer from the config. A `telemetry.endpoint` the repository's `.devops/config.yaml` named had received every span of the review, each LLM call's 200-character prompt preview among them (#972).
  - Started in another repository, a review resolves a relative data path under `~/.local/share/devops-cli` rather than under that repository, so its default data directory is `~/.local/share/devops-cli/.data`. The repository's `.data` held whatever its author committed: a learned-catalog entry recording a person's verdict on the exact claim of a real finding invalidated that SSRF finding on `urllib.request.urlopen(u)`. The hallucination catalog, the review history and baselines, the mitigations ledger, the library contracts and the LLM response and type-check caches follow. An absolute `DEVOPS_CLI_DATA_DIR`, `data.dir` or `DEVOPS_CLI_DATA_*` path is one the user named and stands, as the opt-in for keeping review data in a repository. `devops review findings`, `verify`, `stats` and the other review commands resolve the data directory as a review does, and `devops review findings` names the directory it found no session in (#972).
  - The MCP server runs `devops review` in its own process, so a command it runs while a review does also reads the user-level config and data, unless the server runs in devops-cli's own repository (#972).
- **Library Contracts Come From devops-cli's Data Directory Alone (`devops review`, `devops ai ingest`, `devops_cli.ai.review.contract_grounding`)**:
  - Contract grounding read `.data/libraries/<package>.json` relative to the working directory, and a contract the reviewed repository committed reached the persona prompt as "Verified Third-Party API Contracts (Ground Truth)", with its docstring telling the model not to report SQL injection. Contracts are read from `libraries/` under the data directory (`library_contracts_dir`), and contracts there that lie inside the tree under review are refused with a warning, even in a data directory the user named there, unless that tree is devops-cli's own repository (#972).
  - `devops ai ingest library` writes, and `devops ai ingest index-libraries` and `query-library` read, that directory by default, where review data is kept, as a review does, and so do the drift auditor and the MCP `resource://libraries/indexed` resource; `--dir` and `--contracts-dir` still name another (#972).
- **A Review's Scanners Read No Config From the Reviewed Tree (`devops review`, `devops_cli.security`)**:
  - Bandit, kube-linter, Pluto, Trivy, Gitleaks and Semgrep ran in the reviewed file's directory with no config of devops-cli's own. A committed `.kube-linter.yaml` with `checks: {doNotAutoAddDefaults: true}` took a privileged `nginx:latest` Deployment from 7 findings to 0, and a `.trivyignore` hid Trivy's Dockerfile findings. A review now runs each from a temporary directory outside the tree, and hands kube-linter (`--config`), Trivy (`--config`, `--ignorefile`), Gitleaks (`--config`, `--gitleaks-ignore-path`) and Bandit (`--ini`) devops-cli's own files: each scanner's defaults, and ignore files that ignore nothing. Pluto reads no such file, and Semgrep takes its rules from `--config` alone and applies no `.semgrepignore` to the files a review names. A project's own scanner config does not count. `devops scan` and the other scanner commands still read the project's (#972).
- **The None-Dereference Probe Claims Nothing the Reviewed Module Arranged (`devops review`, `devops_cli.ai.review.verification`)**:
  - The probe took a strict mypy pass as proof that a claimed `None` dereference cannot happen, but the reviewed module controls that pass. It now claims nothing of a module holding a `type: ignore` comment or an inline `# mypy:` line, or whose cited lines hold an expression of type `Any`, which a second, warm mypy pass names: it checks a copy of the module with `# mypy: disallow-any-expr` appended (`--shadow-file`), isolated as the probe is. A first-line `# mypy: ignore-errors` or `# type: ignore`, a `# type: ignore[union-attr]` on the line, and an `-> Any` return had each let it INVALIDATE a real `len(find(name).upper())` dereference of an `Optional[str]` (#972).
  - Each suppression is read where mypy reads it, before mypy runs: `type: ignore` from the module's comments, and `# mypy:` from every line that starts with it, a line inside a string too, as mypy 2.3.1 takes it. The module is read as mypy decodes it, after any byte order mark, and a module that declares an encoding other than UTF-8 gets no claim. A `# mypy: ignore-errors` line inside a triple-quoted string, and a `# mypy:` line spelled `+ACM- mypy:` under a `# coding: utf-7` declaration, had each let it INVALIDATE the same dereference (#972).
- **The MCP Profile Tool Runs Nothing, and `devops telemetry profile` Runs Only devops-cli (`telemetry_profile`, `devops telemetry profile`)**:
  - The `telemetry_profile` MCP tool took a `command`, which `devops telemetry profile` split with `shlex` and ran with the user's full environment, so a prompt-injected agent with the server attached could run any program with every credential in reach. The tool now takes only a required `trace_id` and shows the waterfall Jaeger recorded for that trace. A call that still passes `command` is refused as a parameter the tool does not have, and nothing runs (#980).
  - `devops telemetry profile <command>` runs only a devops-cli command line: its first word must be `devops`, and the rest runs as `python -P -m devops_cli.entry`, the entry point the `devops` script calls, under the running interpreter, so another `devops` found first on PATH is not what runs either. `-P` keeps the working directory off the child's import path, as it is for the `devops` script, so a `token.py` or a `devops_cli/` in the directory profiled from does not run in place of devops-cli's own code. Any other command line, or one `shlex` cannot split, is refused with a message and exit 1 before a process starts. The child keeps the full environment, as it would run directly, since only devops-cli itself, imported from where it is installed, receives it (#980).
  - `docker_sandbox` ends its options with `--` before the workload command, and the lazy proxy in front of each command group passes `--` on to the command behind it, where it had consumed it. A workload command starting with an option, such as `["--root", "id"]`, set `devops docker sandbox`'s own `--root` and ran the container as root, and `sandbox_exec(command=["--workdir", "/", "id"])` set its workdir, although `sandbox_exec` and `sandbox_deploy` already sent `--`. A user's `devops sandbox exec <id> -- <command>` reaches the sandbox intact the same way (#980).
- **Loki Admits Only the OpenTelemetry Collector from `otel` (`k8s/logging/networkpolicy.yaml`)**: Loki's 3100 ingress from `otel` named the whole namespace, and Loki runs without authentication, so Jaeger or any later `otel` workload could push and query logs. The peer now combines the namespace with the collector release's pod labels; the shape was checked live under the cluster's kube-router, which enforces it with `ports` on ingress (#1100).
- **The Loki Peer Is Tied to the Collector Release It Names**: a test checks the policy's `app.kubernetes.io/instance` and `app.kubernetes.io/name` against the `otel-collector` release `devops k8s` installs and its chart, so renaming the release or overriding the chart name fails the tests instead of cutting the collector off from Loki (#1100).

## [0.2.24] - 2026-10-01

### Added
- **Stack Dashboards Chart Only What Their Exporters Serve (`k8s/monitoring/dashboards/`)**:
  - The LLM gateway, OpenTelemetry collector and new Prometheus server dashboards query only series their exporters serve, checked in tests against captured exporter output, with no `or vector(0)` fallback, so a panel without data reads "No data" instead of zero. vLLM and the unverified Qdrant row are gone, and the collector's own telemetry is scraped through pod annotations (#693).
- **devops-cli Dashboards Chart What the CLI Sends (`k8s/monitoring/dashboards/`, `devops grafana dashboards sync`)**:
  - The devops-cli and AI spend dashboards chart command latency at p50, p95 and p99, error share by command, findings by severity, and reviews by target type, reading every counter through `rate()` or `increase()`. Panels say when a value is approximate, and grouped panels no longer draw an unlabelled zero series (#692).
  - A kustomize `configMapGenerator` provisions six dashboards through the Grafana sidecar in place of the hand-copied ConfigMaps, and `dashboards sync` skips dashboards Grafana reports as provisioned (#692).
- **SARIF Runs Reflect What Each Scanner Did (`devops scan report --sarif`)**:
  - Only a scanner that ran gets a SARIF run, zero results included, with `invocations[].executionSuccessful` and its start and end times. A scanner that was unavailable, failed, not applicable or fell back to built-in patterns gets no run, only a notification on devops-cli's own invocation, so an upload never closes a tool's alerts for a scan that did not happen, and built-in pattern findings are attributed to devops-cli rather than to the real tool (#708).
  - Non-gating findings, such as Dive's efficiency score, are emitted at `note` level as `problem.severity: recommendation`, without a `security-severity` (#708).
  - Emitted documents are validated against the vendored OASIS SARIF 2.1.0 schema in tests (#708).
- **Roadmap Planning Glossary & GitHub-Source ADR (`CONTEXT.md`, `docs/adr/`)**:
  - Added `CONTEXT.md`, the glossary for release planning and the roadmap jobs, and `docs/adr/0001-github-is-the-roadmap-source.md`, which makes GitHub issues, milestones and the project board the roadmap's source of truth (#746).
  - Scheduled the roadmap jobs in `docs/ROADMAP.md` (#739-#744, with #745 in the backlog), revised the #697 and #704 entries, and removed the superseded #418, #696 and #699 entries (#746).
- **Roadmap Service Decisions, Machine-Account & Polling ADRs (`CONTEXT.md`, `docs/adr/`)**:
  - Resolved the glossary's open boundaries (Item, Candidate, Blocked, Dependency, Stalled, Cut, Current release, Critical fix, Value, Effort, Reprioritization, Closure) and added Service, the homelab deployment that runs the roadmap jobs (#756).
  - Added `docs/adr/0002-roadmap-jobs-act-as-a-machine-account.md` and `docs/adr/0003-polling-is-how-the-roadmap-sees-changes.md`, revised the #739-#743 roadmap entries, moved #741 to v0.2.26 beside #752 and #753, and added #754 and #755 to the backlog (#756).
- **Architecture Review Planning (`CONTEXT.md`, `docs/ROADMAP.md`)**:
  - Added the Code review glossary terms (Finding, Verdict, Review session, Known false positive) (#782).
  - Planned the architecture review's ten deepening candidates and five defects as #767-#781: the gitleaks list-target regression as a v0.2.24 critical fix, the roadmap store in v0.2.25, the GitHub session in v0.2.26 and the rest in the backlog (#782).
- **Dashboard Keeps Its Place Across Refreshes (`devops dashboard`, `devops tui`)**:
  - A refresh keeps each table's highlighted row and its horizontal and vertical scroll, on every tab, instead of returning to the first row every five seconds. Rows carry stable keys, so repeated records stay separate rows and a record that vanishes leaves the cursor at its index (#684).
  - The AI Review findings sub-tab shows the highlighted finding's full record in a detail pane beside the table, toggled with `i`, with model-written markup and control characters shown literally. Every finding of a session is listed, not just the first 50 (#684).
- **Truthful Pod Status, Filters and a Pod Inspector (`devops dashboard`, `devops k8s pods`)**:
  - STATUS and READY match `kubectl get pods` wherever pods are listed: the dashboard, `devops dashboard --summary`, `devops k8s pods` and `--watch`. The Kubernetes tab's banner names the context, the Ready nodes and the unhealthy pods, or the context and the real error when it cannot connect (#686).
  - Namespace and text filters survive refreshes and keep the highlighted pod on screen. Logs follow a pod's default container, `c` cycles containers, a replaced log stream is closed, and `e` opens the pod's containers and recent events. The Minikube probe is gone (#686).
- **Monitoring Stack on Grafana k8s-monitoring (`k8s/monitoring`, `devops k8s deploy-stack`)**:
  - kube-prometheus-stack is replaced by Grafana's `k8s-monitoring` chart with Alloy collectors for metrics, pod logs and events, and Prometheus keeps metrics for 30 days (#734). Loki does not yet delete logs by age, because its compactor retention is off; #550 turns it on.
  - The Prometheus server and Grafana run as their own charts again, cluster CPU metrics are restored, duplicate scrape jobs are off, and the Kubernetes views dashboards default to the homelab cluster (#738).
  - Traefik serves ingress routes for the monitoring services, and the monitoring perimeter admits it (#734).
  - The OpenTelemetry collector remote-writes devops-cli metrics to Alloy's Prometheus receiver at `/api/v1/metrics/write`, the only path it serves (#829).
  - `devops k8s deploy-stack` applies the `prometheus` Service that Alloy writes to and Grafana queries, and the Services `devops k8s port-forward` targets. No chart creates them (#912).
- **Multi-Node Ollama Profiles (`k8s/llm/profiles`)**:
  - Ollama runs as per-VRAM-tier DaemonSets behind `ollama-<n>gib` Services, and the LLM gateway routes every model group to them (#734).

### Changed
- **MCP Tool `k8s_chaos` Previews by Default**:
  - `experiment` is the positional argument, and a new `dry_run` parameter (default `true`) passes `--dry-run`, so the tool runs an experiment only when `dry_run` is false (#836).

### Removed
- **LightLLM Inference Backend (`devops_cli.ai`, `k8s/llm`)**:
  - Fully removed the unused `ghcr.io/modeltc/lightllm` inference backend, including `k8s/llm/lightllm/` manifests, `CONST_AI_BACKEND_LIGHTLLM`, `GatewayRouter.scale_lightllm()`, the `devops-cli-ai_lightllm_scale` MCP tool, and all associated CLI, configuration, and test references.
- **MCP Tools and Parameters With No Command Behind Them**:
  - The `ai_architecture` tool, which called a nonexistent `devops analyze architecture`, and the parameters `repos_sync(all_repos)`, `k8s_audit(namespace)` and `k8s_chaos(action)`, which their commands never took (#836).
- **Squid Forward Proxy (`k8s/squid`)**:
  - The Squid egress proxy, its CA bundle and its exporter are removed (#734). An existing cluster keeps the namespace until it is deleted: `kubectl delete namespace squid`.
- **vLLM Deployment Profiles (`k8s/llm/profiles`, LLM gateway)**:
  - The vLLM DaemonSets, their `vllm-<n>gib` Services and the gateway's vLLM routes are removed in favour of the Ollama profiles (#734). An existing cluster keeps the model caches until they are deleted: `kubectl -n llm delete pvc vllm-model-cache vllm-single-model-cache`. The remaining vLLM references in code are #820.
- **kube-prometheus-stack (`k8s/monitoring`)**:
  - The kube-prometheus-stack release is replaced by k8s-monitoring (#734) and the separate Prometheus and Grafana charts (#738). Its Prometheus Operator CRDs stay installed: the `prometheus-operator-crds` release now owns them (#819), so do not delete them by hand. The alias Services that kept its names working are #818.

### Fixed
- **Branch Analysis Reads the Base Revision Again (`devops analyze branch`, `devops review`)**:
  - `symbols_removed` lists the symbols a branch removed again, so a review's "cites a removed symbol" check works. Since f93231b (#738) the base file was read as a pathspec and came back empty. Enhanced branch analyses cached since then must be regenerated with `devops analyze branch --update-all` (#787).
- **Kubernetes Monitoring Stack Integration & Dashboard Metrics (`k8s/monitoring`)**:
  - Configured `kube-state-metrics` with `metricLabelsAllowlist` and extra collector `endpoints` to emit resource labels and endpoint info for Kubernetes Views dashboards (#825).
  - Expanded Alloy cAdvisor and KSM `metricsTuning.includeMetrics` to capture container CFS throttling, OOM events, network errors, and pod container status metrics (#825).
  - Permitted port 9153 (TCP) in monitoring NetworkPolicy egress, so the Prometheus server's `kubernetes-service-endpoints` job can scrape CoreDNS through the `kube-dns` Service's scrape annotations (#825).
- **Gitleaks Scans Every File of a List Target (`devops_cli.security.gitleaks`)**:
  - A list target, such as the files of a review, now runs Gitleaks once per file and merges the outcomes, keeping every finding and the worst status. Before, the binary scanned only the first file, and since #763 the built-in patterns did too (#781).
- **Board-Owned Project Status and Truthful Reconciliation (`devops gh project reconcile`, `devops gh project sync`)**:
  - The board owns Status: reconcile sets it only when unset, or when an item's state forces Done, In Review or In Progress, so manual triage is no longer reverted. Status labels match exactly, Priority only fills an unset field from its label, and Category, Value and Effort are no longer inferred (#703).
  - `devops gh project reconcile` lists every field change with its old and new value and the source that decided it, and refuses to guess a board number when no board matches the template (#703).
  - Failed reads of the board, issues or pull requests now raise instead of reading as empty, roadmap sync and release epics read every issue rather than the first 200 or 300, and each pull request is reconciled once (#703).
- **Quality Gate Within Its Five-Minute Budget (`devops ci`, `tests/`)**:
  - The secops dry-run tests enable dry-run mode instead of running trivy, kube-linter and pluto over the whole workspace until they time out (#748).
  - The test network guard now fails external DNS lookups too; tests that validate egress against a resolving hostname declare the `public_dns` fixture (#748).
  - `devops ci` warns when the workspace is on a 9p or drvfs share of a host folder, and lists pytest's slowest tests when the test step runs past the 5-minute budget (#748).
- **Structured Replies Keep Their Answer Beside Bracketed Prose (`devops_cli.ai.response_repair`)**:
  - A reply whose prose holds brackets, such as a markdown link or `items[0]`, keeps its fenced answer, so review personas keep their findings and agent replies validate against their schema (#786).
  - A lone fenced block is read exactly from its opening fence, so a fence inside one of its strings cannot cut it short and a fenced `write_file` call keeps its content's final newline (#786).
- **Harness, Constellation and Telemetry Profile Report Only What Ran (`devops ai harness`, `devops ai constellation`, `devops telemetry profile`)**:
  - `ai harness status` shows the configured provider and model with every slot `configured`, instead of a hard-coded `claude-3-7-sonnet` with every slot `attached`. `ai harness run` and `offload` report the local search they ran and what it found, without templated model "Tier 1/Tier 3" text, token estimates, or the unused `--frontier-model`/`--local-model` options (#710).
  - `ai quiesce`, `ai failover`, `ai resume` and `ai constellation` set, record and show a flag, and say so. Task registration, which nothing called, and the per-task counts, `--drain-timeout` and failover's `--force` are removed; `ai gateway failover` reroutes requests (#710).
  - `telemetry profile <command>` reads the command's trace back from Jaeger, waiting until it stops growing, and exits non-zero without a command or trace, with telemetry export off, or when no spans reach Jaeger. The `sample.*` fallback spans and the unused `--last` are removed, and the MCP tool passes the command positionally (#710).
- **The Workspace Tripwire Passes From a Linked Worktree (`tests/conftest.py`)**:
  - `uv run devops ci` no longer fails from a linked worktree. The #749 tripwire required `.git/index`, which a linked worktree lacks, so it reported every file the gate regenerates as modified by tests; git now finds the index itself (#824).
- **Deploy-Stack Installs the Prometheus Operator CRDs (`devops k8s deploy-stack`, `devops k8s teardown-stack`)**:
  - The infra stack installs `prometheus-community/prometheus-operator-crds` before k8s-monitoring and dcgm-exporter, whose ServiceMonitors need its CRDs. Since #734 removed kube-prometheus-stack, a cluster without leftover CRDs got no Alloy, and so no cluster metrics, pod logs, or gateway and GPU metrics. Teardown leaves the CRDs in place, and they carry `helm.sh/resource-policy: keep` (#819).
  - Adoption of pre-existing resources handles cluster-scoped ones such as leftover CRDs, annotates the release's namespace that Helm checks, and retries until every leftover is adopted or a retry fails unchanged (#819).
- **The Finding Detail Pane Opens Each Finding at the Top at Once (`devops dashboard`)**:
  - Highlighting another finding scrolls the detail pane to the top immediately instead of after the next screen refresh, which a slower machine had not always drawn; CI failed intermittently on it (#834).
- **Tests Never Reach Port-Forwarded Services (`tests/conftest.py`)**:
  - The test network guard refuses loopback connects to any port the test process is not listening on, and a port refuses again once its listener closes, so a workstation's port-forwards (OTLP collector, Valkey, Ollama, ArgoCD) are never reached by the suite; one run had made 5,716 such connects. The refusal is the `ConnectionRefusedError` clients already handle (#837).
  - `EmbeddingsEngine` no longer skips its Valkey probe under pytest, and `test_popeye_dry_run` no longer runs the real popeye binary (#837).
- **MCP Tools Call Commands That Exist (`devops mcp`, `devops docs check`)**:
  - Twelve MCP entry points called commands or options the CLI does not have and failed on every call. They now call real commands: `benchmark_embeddings` and `benchmark_suite` run `devops ai benchmark`; `scan_gitleaks`, `scan_semgrep` and `scan_checkov` run `devops scan secrets`, `sast` and `iac`; `resource://workspace/status` runs `devops repos list`; `scan_complexity` passes `--max-indent`; `resource://argo/fleet/status` no longer passes `--json` (#836).
  - `devops docs check` resolves every `uv run devops` argv in the MCP server against the real command tree without running it, and reports each defect at its server line (#836).
- **MCP Tools Refuse Coerced Arguments Before They Run (`devops_cli.ai.mcp`)**:
  - Tool arguments are validated against each tool's published schema before its handler runs, for listed and withheld tools alike. A boolean, string or integral float is refused where an integer is expected: `review_pr` with `{"number": true, "post": true}` had built `devops review pr 1 --post`. A refusal names each parameter once, with the expected type and the allowed parameters, and never echoes a value. Rejected inputs no longer reach FastMCP's warning log, and `jsonschema` is a runtime dependency (#862).
- **Review Self-Improvement & Verification Feedback Loop (`devops_cli.ai.review`, `devops_cli.security`)**:
  - Remediated session `20260928-160843` findings, eliminating native secret scanner false positives, tautological criteria auto-promotions, and cluster overlay networking hallucinations (#682).
  - Anchored native fallback secret patterns with `\b` word boundaries and tightened OpenAI key pattern to `\bsk-(?:proj-)?[A-Za-z0-9]{32,128}\b`, preventing `task-*.md` markdown links from falsely triggering secret detection (#682).
  - Implemented `CONST_SECRET_PLACEHOLDER_MARKERS` and `_is_placeholder_secret` to filter out documentation and illustrative placeholder tokens (#682).
  - Implemented `_is_tautological_verification_command` in `review_environment.py` to prevent text-search (`git grep`, `grep`) and reflection commands (`__code__.co_varnames`, `hasattr`, `getattr`) from falsely promoting findings to verified status (#682).
  - Broadened `HALLUCINATION-K8S-CLUSTER-OVERLAY-HTTP` in `common_hallucinations.json` and verification prompts to cover internal container-to-container and backend service HTTP communication (#682).
  - Added `HALLUCINATION-OFFLINE-PRICING-URLSPLIT` and `HALLUCINATION-MITIGATION-LEDGER-INITIAL-EMPTY` to prevent false SSRF and absent-mitigation claims on offline pricing calculators and dynamic audit ledgers (#682).
  - Added `_sanitize_api_key_header` in `gateway.py` to strip newlines and reject non-ASCII/CRLF injection characters (#682).
  - Hardened URL scheme validation in `gateway_bench.py` before `urllib.request.urlopen` (#682).
  - Enforced strict regex format `^[a-zA-Z0-9_\-\.]+$` on `run_id` in `run_store.py` rejecting `..` traversal (#682).
  - Narrowed exception handlers in `install_tools.py` and guarded git directory pointer resolution in `tracer.py` against `(OSError, RuntimeError, ValueError)` (#682).
  - Validated revisions and paths before the git invocations in `analyze.py` (#682).
  - Added `_validate_mcp_arg("session_id", ...)` in MCP `review_findings` (#682).
  - Updated `src/devops_cli/ai/tasks/verify_finding_system.md`, `src/devops_cli/ai/tasks/review.md`, and `src/devops_cli/ai/personas/devsecops/prompt.md` with explicit falsification rules against tautological criteria, documentation placeholders, and internal cluster networking (#682).
  - Added Calibration Record for session `20260928-160843` to `docs/SELF_IMPROVEMENT.md` (#682).
  - Exported refreshed feedback dataset with 1,219 findings via `devops review export-feedback` (#682).

### Security
- **`web_fetch` Vets Every Redirect Hop Before Sending It (`devops_cli.ai.common_tools`, `devops_cli.http.broker`)**:
  - A redirect chain could reach a link-local or private address: only the first URL and the final response were checked. Now each hop goes through the HTTP broker's request hook before it is sent. Only http and https are allowed, the domain lists apply with case and trailing dots ignored, and the address must be public whatever `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK` says. Both broker clients follow at most 10 redirects (#860).
  - Each fetch uses its own client, so no cookies carry over between fetches, and a request's egress policy can only add restrictions to the broker's own SSRF check (#860).

## [0.2.23] - 2026-09-28

### Added
- **GPU-Architecture Inference Placement & Gateway Routing (`devops_cli.k8s`, `devops_cli.ai`)**:
  - Scheduled inference engines dynamically by GPU compute architecture (`nvidia.com/gpu.family` and `nvidia.com/gpu.architecture`), mapping dual-GPU Ampere+ nodes to vLLM Qwen2.5-Coder-32B at tensor parallel 2 with 64K YaRN context, single-GPU Ampere nodes to vLLM Qwen2.5-Coder-14B, and legacy hardware to Ollama (#453, #654, #655, #668).
  - Adopted throughput-weighted `simple-shuffle` gateway routing across the `devops-review` model group without artificial concurrency caps, achieving ~2 req/s throughput scaling (#467, #468, #668).
  - Ephemeral debug container script pipelining via stdin to prevent Linux `MAX_ARG_STRLEN` (128KB) overflow on large prompts during gateway tuning, with concurrency recommendations and label-keyed weight matching (#470, #669, #677).
  - Consolidated the LiteLLM Gateway as the single authenticated cluster entry point with automatic route discovery and credentials enforcement (#455, #469, #471).
  - Forwarded Ollama ranged blob pulls through the Squid forward proxy unchanged, enabling large model downloads from Cloudflare R2 (#460, #461).
  - Deployed Ollama as a headless StatefulSet with per-pod DNS routing and one gateway deployment per GPU node (#463).
- **Multi-Persona Code Review Engine & Quality Hardening (`devops_cli.ai.review`)**:
  - Added construct-aware finding location validation using Python AST to relocate drifted findings to precise line spans and support removed-symbol finding exemptions (#403, #436, #593, #659).
  - Enforced finding schema verdict polarity validation (`observed_value` vs `expected_value`) and deterministic pre-verification invalidation of contradictory polarity hallucinations (#435, #635).
  - Bound verification verdicts by finding identity and normalized location rather than list position, preventing verdict misattribution (#403, #436, #660).
  - Structured error reflection for Pydantic schema validation retries, preserving field-level validation errors and actionable fix hints (#437, #656).
  - Synthetic defect corpora generation and scoring (`devops review corpus generate` / `score`) across 9 injection templates for measured defect recall tracking (#473, #476).
  - Per-stage execution profiling and telemetry recording wall time, LLM calls, prompt/completion tokens, and serving backends in `profile.json` and spend ledger (#473, #474, #661, #664).
  - Per-call token caps on review and verification replies (`limit_completion_tokens`), preventing runaway generation delays (#494, #496).
  - Project conventions resolution nearest-first from base ref or reviewer checkout to prevent PR branches suppressing findings (#524, #658).
- **Cloudflare Tunnel GitOps & Cluster Ingress Automation (`devops_cli.k8s.cloudflared`, `devops_cli.k8s.ingress`)**:
  - Added declarative `cloudflared` multi-replica deployment with non-root security context (`runAsUser: 65532`, `readOnlyRootFilesystem: true`), token secret mapping, and dedicated network policy isolation (#646, #651).
  - Deployed Traefik Ingress Controller as an internal `ClusterIP` service with wildcard `*.homelab.<domain>` routing, client host-header preservation, and pre-configured ingress routes for `open-webui`, `llm-gateway`, `kube-prometheus-grafana`, and `argocd-server` (#646, #651).
  - Hardened Cloudflare DNS client pagination, unmanaged record protection, tunnel ingress preservation, and public IP bypass policy options (#666, #676).
- **Host Sandbox & Process Group Isolation (`devops_cli.sandbox`, `devops_cli.core.process`)**:
  - Implemented guarded POSIX process group isolation (`start_new_session=True` on `Popen`) with safe hierarchical group termination guarding PID 1 and caller process group (#440, #663).
  - Added ephemeral container streaming output byte caps, bounded ring buffers (`collections.deque(maxlen=1000)`), and read-only git worktree volume mounts (#449, #663).
  - Isolated agent workspace data tier (`.data/agent/`) preventing temporary review artifacts from polluting user workspace data (#553, #616).
- **Roadmap & Milestone Scope Governance (`devops_cli.github`)**:
  - Added the Autonomous Milestone Scope Governor & Release Air-Lock Oracle deliverable and mathematical scope convergence tracking to prevent milestone horizon inflation cascades (#678).
  - Reconciled task file traceability and backlog synchronization requiring completed deliverables and issue links (#489, #492, #679).
  - Automated release-branch issue closure (`devops gh issues close-merged`) closing pull-request referenced issues across release branches (#342, #366).

### Fixed & Hardened
- **Security Sanitization (`devops_cli.security.sanitizer`)**: Bracket-balanced credential detection and attribute chain validation in code sanitizers (#662, #676).
- **Credential Masking (`devops_cli.security.sanitizer`)**: Capitalized word discrimination preventing ordinary prose being treated as credentials (#397).
- **Keyring Credentials (`devops_cli.security`)**: Keyring credential resolution hardening and host-credential gap elimination (#485).
- **Pull Request Readiness (`devops_cli.commands.pr`)**: Blocked PR readiness checks on drafts, uncompleted task specs, and failing CI checks (#398, #400).
- **DevContainer Prefix Resolution (`devops_cli.commands.devcontainer`)**: Handled URL strings gracefully when resolving SSH key prefixes from JSONC manifests (#488).
- **Background Pipes (`devops_cli.core.process`)**: Drained background shell pipes into bounded ring buffers, avoiding deadlock on large process outputs (#449).
- **Port-Forward Process Groups (`devops_cli.k8s.port_forward`)**: Isolated port-forward daemons into dedicated process groups with graceful teardown (#440).
- **Self-Agreement Confidence Stripping (`devops_cli.ai.review`)**: Removed ungrounded self-agreement confidence heuristics in favor of external tool verifications (#402).

## [0.2.22] - 2026-09-22

### Added
- **Cluster-Native Service Addressing (`devops_cli.k8s.service_proxy`, `devops_cli.k8s.service_http`)**:
  - Introduced the `k8s://namespace/service:port` scheme, resolving endpoints through the Kubernetes API server's Service proxy so the same configuration works on any cluster without a local port-forward (#369).
  - Routed dashboard, Grafana, Prometheus, Jaeger, ArgoCD and Open WebUI endpoints through cluster-native addressing, and added `devops k8s configure-urls --addressing proxy` to record them (#370).
  - Reached the Qdrant vector store through the cluster API rather than `localhost:6333`, making `devops ai rag query` work with no port-forward running (#379).
- **Native In-Process Kubernetes Engine (`devops_cli.k8s.informer`, `devops_cli.k8s.service`)**:
  - Replaced `kubectl` subprocess invocations with a dynamic informer and an in-process service client, with bounded FIFO caches and per-entry TTLs (#307, #336).
- **Docker Engine API Client (`devops_cli.docker`)**:
  - Routed every container, image, network, volume and registry operation through the Engine API socket instead of the `docker` binary (#308, #348).
- **Native Argo Custom Resource Manipulation (`devops_cli.argo`)**:
  - Manipulated Argo Workflows and ArgoCD custom resources directly via the Kubernetes API, with localized name validation (#309, #351).
- **In-Process Terraform & OpenTofu Analysis (`devops_cli.tf.analysis`)**:
  - Parsed HCL and state in-process to build dependency graphs and detect drift without invoking the Terraform binary (#310, #352).
- **Valkey Connection Pooling & Unified Cache Tiers (`devops_cli.valkey`)**:
  - Pooled connections with idle expiry, batched commands, and consolidated the separate caching tiers behind one client (#312, #356).
- **Hybrid Retrieval & Vector Quantization (`devops_cli.ai.rag`)**:
  - Fused BM25 lexical ranking with dense embeddings and quantized stored vectors, reducing index size while preserving recall (#313, #357).
- **Client-Side Prometheus Analysis (`devops_cli.prometheus`)**:
  - Validated PromQL locally before dispatch and analysed returned series client-side, removing round trips for malformed queries (#314, #358).
- **Declarative Grafana Dashboards (`devops_cli.grafana`)**:
  - Built dashboards from declarative definitions and linted them statically, catching malformed panels before upload (#315, #359).
- **Reactive TUI Dashboard (`devops_cli.ui`)**:
  - Refreshed each dashboard domain on its own worker thread and virtualized log tailing behind a bounded buffer, so a fast producer cannot outrun the terminal (#317, #361).
- **Unified SARIF Security Engine (`devops_cli.security`)**:
  - Consolidated every scanner behind a single SARIF 2.1.0 pipeline with shared normalization and suppression (#321, #363).
- **Secret Resolution & Vault Lease Lifecycle (`devops_cli.security`)**:
  - Unified credential resolution across keyring, environment and Vault, and managed lease renewal and revocation explicitly (#311, #353).
- **Structured AI Workflows, Prompt Caching & Token Governance (`devops_cli.ai`)**:
  - Implemented Pydantic AI structured workflows, a prompt cache, and a token-bucket governor that carries overdraft as debt so the long-run rate holds (#320, #341).
- **FastMCP In-Process Execution (`devops_cli.ai.mcp`)**:
  - Executed MCP tools in-process with dispatching and resource subscriptions rather than spawning a server (#318, #338).
- **GitHub GraphQL Consolidation & ETag Caching (`devops_cli.github`)**:
  - Batched GraphQL queries, cached responses by ETag, and paced requests against live quota rather than a fixed window (#316, #337).
- **Release-Branch Issue Closure & Project Automation Inspection (`devops_cli.github.issue_closure`)**:
  - Added `devops gh issues close-merged`, closing the issues a pull request declared when it merges into a release branch -- GitHub honours closing keywords only on the default branch, so those references were previously inert (#342, #366).
  - Added `devops gh project workflows list`, reporting which built-in project automations are enabled and what each should be configured to do (#343, #381).
- **Output Format Join Point & Terminal Capability Negotiation (`devops_cli.output`)**:
  - Added `emit_serialized`, rendering any payload as JSON or YAML from one place, and made YAML output portable rather than Python-tagged (#391).
  - Restored Rich's colour negotiation, so `NO_COLOR`, a non-TTY destination and `TERM=dumb` take effect (#391).
- **DevContainer Tooling (`devops_cli.commands.devcontainer`)**:
  - Added the Claude CLI and VS Code extension to the devcontainer configuration and lifecycle (#346, #347).

### Fixed & Hardened
- **Trace Context Propagation (`devops_cli.telemetry`)**: Injected W3C `traceparent` into child process environments; the return value of the injector had been discarded at both call sites, so no child ever received a parent span (#319, #362).
- **SSH Host Key Verification (`devops_cli.crypto.known_hosts`)**: Verified host keys against `known_hosts` before trusting them, including hashed entries, `@revoked` markers and `[host]:port` forms (#322, #364).
- **CI Cache Correctness (`devops_cli.ci.cache`)**: Made the workspace fingerprint content-addressed, so staging or committing a file no longer invalidates a verified tree and the pre-push gate can reuse the run that preceded it -- 3m51s to 8.7s (#375). A passing run is now recorded even when `--no-cache` skipped reading one (#389).
- **Secret Masking (`devops_cli.security.sanitizer`)**: Masked credentials rather than sentences mentioning them; the keyword rule had rewritten "unify secret resolution" to "unify `<masked-token>`", and that corruption reached published release descriptions (#392).
- **Kubernetes Context Handling (`devops_cli.k8s.context`)**: Honoured the configured cluster context when connecting, and stopped the devcontainer post-start script overwriting it.
- **Dry-Run Semantics (`devops_cli.main`)**: Honoured an exported `DEVOPS_CLI_DRY_RUN` instead of discarding it, without letting a `--dry-run` flag latch for the life of the process (#388).
- **Terminal UI (`devops_cli.ui`)**: Corrected the Docker, telemetry, Valkey and review panels (#368), and made the dashboard quit promptly instead of hanging on an open log stream (#372).
- **Template Rendering (`devops_cli.core.templating`)**: Encoded values as JSON rather than pasting them between quotes, so a value containing a quote or newline cannot produce malformed output (#378).
- **Manifest Validation (`devops_cli.k8s`)**: Validated only actual manifests, discriminating on `apiVersion` rather than `kind`, and loosened an over-strict ArgoCD probe (#376).
- **Review Loop Calibration (`devops_cli.ai.review`)**: Grounded verification in tooling rather than model agreement -- a claimed `None` dereference is now settled by `mypy --strict`, a placeholder advisory identifier invalidates a dependency finding, and a claim against an uninstallable Python is rejected against `requires-python` (#349, #350, #371, #380).
- **Review Benchmarking Honesty (`devops_cli.ai.prompt_eval`)**: `devops ai prompt-eval` had reported accuracy 1.0 and a 0.0 false positive rate on every run without invoking a model. It now replays the deterministic suppression layer against recorded verdicts and reports both directions separately (#385).
- **AI Slot Leasing (`devops_cli.ai.client`)**: Removed arbitrary defaults from network slot leasing and raised file size limits to 50 MiB (#344, #345).
- **Continuous Integration Workflows**: Dropped an invalid `--depth=0` from devcontainer change detection (#355) and rebuilt the devcontainer image when the build workflow itself changes.

### Changed & Improved
- **HTTP Connection Reuse (`devops_cli.http.pool`)**: Shared pooled clients with HTTP/2 and bounded keepalive instead of constructing one per request -- 1.5x faster on a LAN endpoint, 4.1x on a WAN endpoint, and a proxied cluster request from 34ms to 13ms (#374).
- **In-Memory Ignore Evaluation (`devops_cli.core.gitignore`)**: Evaluated git ignore rules in-process against `pathspec`, including nested `.gitignore` files and `.git/info/exclude`, rather than spawning `git check-ignore` per file -- 39.5ms to 0.73ms per file, a 54x reduction (#373).
- **Merged Pull Request Sweeps (`devops_cli.github.issue_closure`)**: Read pull request bodies and issue states in a fixed number of calls rather than one subprocess each -- 170 subprocesses to 2, and 76s to 6.4s over 100 merged pull requests (#382).
- **Quality Gate Execution (`devops_cli.ci`)**: Parallelized the gate and narrowed test selection to the sources a change touches (#354).
- **AI Prompt Efficiency (`devops_cli.ai.tasks`)**: Compressed the two hot-path review prompts from 4785 to 3244 tokens with every decision rule preserved and pinned by tests, and scoped host-specific rules so they no longer apply when reviewing other repositories (#386).
- **Agent Instructions (`AGENTS.md`)**: Recorded that hard wrapping belongs in source files rather than emitted output (#384), and stated the token and inference cost of a `devops ai` call with a one-at-a-time concurrency cap (#390).
- **Roadmap**: Scheduled AI review verification integrity work (#360), OCI container image packaging and GHCR metadata (#333), and prompt benchmarking with synthetic corpora for evaluation and fuzzing (#387).

## [0.2.21] - 2026-09-19

### Added
- **Multi-Scale Semantic Outline & Inspectional Reading Scanner (`devops_cli.ai.inspect`)**:
  - Replaced monolithic file dumping with human-like inspectional reading and hierarchical perceptual scaffolding across 3 zoom levels: Topology, Structural Outline, and Deep Focal Window (`devops ai read --inspect`).
  - Added AST symbol extraction, hotspot complexity mapping, and dynamic focal window targeting.
- **Approximate Lifetime Spend Tracking & Observability (`devops_cli.ai.cost`)**:
  - Introduced persistent ACID SQLite ledger (`spend.db`) tracking request tokens, backend server endpoints, model names, durations, and approximate USD spend without blocking execution (`devops ai spend`, `devops ai cost report`).
  - Integrated model pricing dataset (LiteLLM registry) with parameter-bracket heuristics and custom overrides (`devops ai cost set-price`).
  - Exported Prometheus metrics (`/metrics`) and dedicated Grafana observability dashboard (`k8s/monitoring/dashboards/ai-spend.json`).
- **Priority Classification for AI/LLM Inference (`devops_cli.ai.gateway`, `devops_cli.ai.models`)**:
  - Implemented dynamic request classification prioritizing interactive/chat calls (`high`), pipeline tasks (`normal`), and background jobs (`as_available`).
  - Integrated client-side token governance and capacity-aware dispatch.
- **LightLLM & Portkey AI Routing Services Integration (`devops_cli.ai.gateway`, `devops_cli.ai.models`)**:
  - Expanded DevOps CLI AI routing tier to support Portkey AI Gateway on port 8787 and LightLLM TokenAttention inference engine on port 8000.
  - Implemented zero-trust perimeter policies, dynamic model route discovery, and direct backend health probing.
- **Dynamic Slot Leasing & Context-Aware File Review (`devops_cli.ai.client`, `devops_cli.ai.review`)**:
  - Dynamic least-loaded slot leasing across candidate inference servers with condition variable notifications.
  - Multi-layered file classification (shebangs, MIME types, AST parsing, canonical names) routing documentation, config, and code files to specialized review task prompts.
- **Milestone, Release Epics & Subsystem Research Synchronization (`devops_cli.github.release_epics`, `devops_cli.github.roadmap_sync`)**:
  - Added native Release Epics management engine (`devops release epic`) and FastMCP tool `release_epic_sync`.
  - Automated 20-deliverable issue synchronization for `v0.2.22` (#307–#326) with local task file generation in `docs/agent/tasks/`.
  - Replaced fragile multi-word bag overlap heuristics with strict deterministic title and issue number matching in roadmap sync.
  - Synchronized GitHub Projects v2 custom fields with client-side quota budgeting and rate-limit safety guards.

### Fixed & Hardened
- **Reliability Hardening, Exception Sanitization & Telemetry Optimization (`devops_cli.telemetry`, `devops_cli.core.exceptions`)**:
  - Hardened exception handling across AI, Git, Security, and Core modules with explicit domain exception hierarchies.
  - Enforced bounded string length caps ($\le 256$ chars) on external exception details to prevent log bloat and CWE-209/CWE-400 leakage.
  - Optimized OTel span processors and deduplicated telemetry attributes across command invocations.
  - Resolved Bandit B608 static finding in `SpendLedger` using parameterized SQLite queries.

## [0.2.20] - 2026-09-18

### Added
- **Forward-Looking Project Management & Automated Roadmap Synchronization (`devops_cli.github.projects`, `devops_cli.github.issues`)**:
  - Implemented forward-looking project management principles in `AGENTS.md` and automated roadmap synchronization (`devops gh issues sync-roadmap`) converting uncompleted roadmap deliverables into GitHub Issues and per-task tracking files (`docs/agent/tasks/`).
  - Hardened documentation compactor (`devops docs compact`) against truncating or removing scheduled milestones.
- **Automated Pull Request Synchronization & Branch Update Integrations (`devops_cli.github.pr_update`)**:
  - Implemented native CLI command `devops pr update` (with batch `--all`, optimistic concurrency `--expected-head-sha`, and `--dry-run`), FastMCP tool `pr_update_branch`, and GitHub Actions workflow `.github/workflows/update-prs.yml`.
- **Fast CI Execution Caching & Git Pre-Commit File Change Tracking (`devops_cli.commands.ci`)**:
  - Introduced input-addressed execution caching for `devops ci` quality gates, reducing unchanged verification from ~3 minutes to sub-second execution with Git working tree change tracking and `--no-cache`/`--force` overrides.
- **Universal Subcommand Option Propagation (`devops_cli.core.command_options`)**:
  - Ensured universal trailing `--dry-run` and `--explain` options across all CLI subcommands with declarative dry-run callbacks and option inheritance.

### Performance & Optimization
- **CI Performance Acceleration, Worker Auto-Scaling & Pathological Test Mocking (`devops_cli.commands.ci`)**:
  - Accelerated `devops ci` quality gate pipeline latency by over 75% with dynamic Pytest worker auto-scaling (`min(os.cpu_count(), 8)`).
  - Mocked unmocked socket probes in Kubernetes context bootstrapping, bounded `.venv` workspace traversal in repo map generation, and bypassed whole-tree git hashing in CI tests.
  - Eliminated sequential blocking documentation passes with zero-blocking concurrent pipeline dispatch at timestamp 0.

### Fixed & Hardened
- **Review Findings Remediation & Defensive Boundary Hardening (`devops_cli.ai.rag`, `devops_cli.sandbox`, `devops_cli.core.audit`)**:
  - Enforced path traversal guards (`validate_no_path_traversal`), forbidden system root blocks, symlink rejection, and pre-flight file size caps ($\le 5\text{MB}$) across RAG chunkers, drift analysis, benchmark chunkers, and prompt evaluation.
  - Decomposed complex workspace directory validation in sandbox engine into single-responsibility helpers, enforcing cyclomatic complexity $M \le 4$.
  - Enforced atomic serialized file exports (`write_serialized_file`) in Kubernetes diagnostics.
  - Hardened None-safe severity handling in review reporting and pipeline stages.
- **Review Verification Prompts & Closed-Loop Feedback Dataset Export (`devops_cli.ai.review`)**:
  - Hardened verification prompts (`verify_finding_system.md`) with falsification rules distinguishing internal loopback services, CLI path logging, and local scope variable grounding from false-positive vulnerabilities.
  - Updated DevSecOps persona instructions and expanded the anti-hallucination catalog (`common_hallucinations.json`).
  - Closed the self-improvement loop with automated dataset export (`devops review export-feedback --status ALL`) to `.data/feedback_dataset.jsonl`.
- **Review Markdown Code Block & Asterisk Formatting (`devops_cli.ai.review`)**:
  - Implemented line-start fence delimiter detection in fix and description formatters to prevent inline backticks (e.g. `print("```")`) from creating malformed Markdown fences.
  - Hardened title and heading rendering by escaping un-backticked asterisks (`\*`) to prevent Markdown bold collisions with Python unpacking syntax (`**kwargs`).
  - Conditioned Markdown bold stripping on matched outer pairs (`^\s*\*\*(.+)\*\*\s*$`), preserving valid variable names like `**kwargs`.
- **Dynamic Package Version Loader & Pyproject Single Source of Truth (`devops_cli.core.version`)**:
  - Refactored `devops_cli.__version__` to read directly from `pyproject.toml` metadata as the single source of truth.
  - Derived generator test fixtures dynamically from `devops_cli.__version__` to prevent stale version assertions.
- **PR Copilot Timeline State Parser Robustness (`devops_cli.github.pr_monitor`)**:
  - Safely handles JSON array timeline payloads and empty responses (`[]`) from `gh api .../timeline`, preventing `AttributeError: 'list' object has no attribute 'get'` during PR monitoring.

### Changed & Improved
- **Release v0.2.20 Branch Initialization**:
  - Created `release/v0.2.20` tracking branch, bumped package version to `0.2.20`, and synchronized documentation across the repository.

## [0.2.19] - 2026-09-16

### Added
- **Adaptive Embedding Batch Sizing Circuit Breaker & Valkey L2 Chunk Caching (`devops_cli.ai.rag.embeddings`)**:
  - Implemented dynamic batch sizing starting at 32 with automatic halving (32 -> 16 -> 8 -> 4 -> 2 -> 1) on latency degradation (> 2.0s) or timeouts.
  - Added recursive sub-batch subdivision and single-chunk request fallback when multi-chunk batches fail across candidate nodes.
  - Implemented exponential backoff with bounded jitter on transient network timeouts.
  - Integrated pre-flight Valkey SHA-256 chunk cache checks before remote embedding dispatch, with automatic write-through caching and 7-day TTL.
- **Automated Draft Release PR Description Generator (`devops release pr`)**:
  - Automatically queries and lists target milestone issues and deliverables under `### Target Milestone Deliverables`.
  - Dynamically synthesizes Gated CI quality checklists, CodeQL, and PR readiness controls adapted for draft vs. ready pull requests.
  - Resolves clean, non-duplicate release notes from git commits and changelog sources, preventing previous release note duplication.
- **Git Squash Merge Commit Body Parsing & Categorization (`devops release changelog`)**:
  - Parses squash commit bodies (`%B`) to extract PR commit items into Keep-a-Changelog sections (`### Added`, `### Fixed & Hardened`, `### Changed & Improved`).

### Performance & Optimization
- **Parallel Async Branch and PR Review Worker Pool with Semaphore Concurrency (`devops_cli.ai.review`)**:
  - Implemented `ReviewWorkerPool.create()` with bounded semaphore concurrency ($1 \le C \le 8$), token-bucket rate limiting (`DEFAULT_REVIEW_RATE_LIMIT = 10.0`), and per-task timeout management.
  - Upgraded pre-analysis refresh, multi-persona segment review, findings validation, and persona loops in both `ReviewPipelineOrchestrator` and `runner.py` to use managed asynchronous worker pools.
  - Replaced legacy unbound `ThreadPoolExecutor` and sequential single-worker fallbacks with concurrent execution, accelerating multi-file and multi-persona review cycles while preventing VRAM spikes, Ollama out-of-memory errors, and rate-limit throttling.
  - Hardened error isolation with `return_exceptions=True` across parallel review stages, guaranteeing that an isolated LLM inference error or malformed payload does not fail remaining segment reviews.

### Fixed & Hardened
- **GitHub Copilot Review Completion on Resolved Threads (`devops pr monitor`, `devops pr wait`)**:
  - Automatically transitions `copilot_status` to `completed` when all recommended changes in review threads have been addressed and 0 unresolved threads remain.
  - Prevents premature failure exit code 2 when all CI checks are green and all discussion threads have been resolved.
  - Excludes bot reviews from human review approval decision evaluations in `_resolve_review_decision`.
- **Main Branch AI Review & Base Resolution (`devops ai review branch`)**:
  - Dynamically resolves comparison bases when reviewing `main` branch or when passing `main` as an argument from another branch (e.g. `release/v0.2.19`).
  - Supports diffing uncommitted working tree modifications against `HEAD`, and cleanly falls back to latest release tags or parent commits (`main~1`) when working tree is clean.
  - Automatically switches comparison targets when positional branch argument matches default base on an active topic/release branch.
- **Documentation Compactor Idempotency (`devops docs compact`)**:
  - Enhanced version range regex to parse all matching version patterns from roadmap headers and recognize canonical summary blocks, guaranteeing idempotent compaction.
- **Polyglot Tree-Sitter File Size Boundary Guard & Resource Containment (`devops_cli.ai.repomap`)**:
  - Enforced pre-flight `MAX_REPOMAP_FILE_SIZE_BYTES` checks in `_polyglot_to_file_node` for all multilingual source trees (TypeScript, Go, Rust, Java, HCL), excluding files exceeding 5MB to prevent memory spikes and OOM crashes.
  - Hardened symlink resolution with `strict=True` to trap and exclude circular symlink loops (`ELOOP`) and symlinks escaping repository workspace boundaries.
  - Added structured warning logging on oversized file exclusions and symlink containment violations.
- **Pre-Release Non-Empty Changelog Verification (`devops release check`)**:
  - Enforced strict validation ensuring changelog notes are populated prior to release certification.

### Changed & Improved
- **AI/LLM Prompt Deduplication & Token Utilization Optimization**:
  - Authoritatively centralized anti-hallucination invariants into `src/devops_cli/ai/tasks/review.md`.
  - Removed duplicate multi-paragraph blocks across all 6 personas (`architect`, `auditor`, `challenger`, `devsecops`, `pm`, `qa`) and review task prompts.
  - Slashed prompt footprint by 32% (~1,500 tokens saved per review turn).
- **High-Performance AST Context Packer with Binary Search Truncation (`devops_cli.ai.context_packer`)**:
  - Replaced O(N^2) linear statement re-unparsing loops with O(log N) binary search truncation index discovery.
  - Implemented O(1) per-statement token weight estimation with AST node memoization (`_estimate_stmt_tokens`).
  - Added tokenizer pre-warming in `ContextPacker` initialization, dropping 1,000-line AST tree pruning latency from >300ms down to <5ms.
- **Release v0.2.19 Branch Initialization**:
  - Created `release/v0.2.19` tracking branch, bumped version to `0.2.19`, and synchronized documentation across the repository.


## [0.2.18] - 2026-09-16

### Added
- **Sigstore Cosign Container Provenance & Automated Keyless Signing (`devops docker sign`, `devops docker verify`)**:
  - Cryptographic container image signing and signature verification using Sigstore Cosign with Keyring-backed ephemeral OIDC tokens.
  - Automated pre-push artifact verification, GHCR registry cleanup, and zero-trust container supply chain security.
- **Kubernetes Falco eBPF Runtime Security Streaming & Anomaly Detection (`devops k8s security-stream`)**:
  - Real-time kernel eBPF runtime security event streaming, priority filtering, and automated anomaly classification via Falco sidecar.
  - Granular severity thresholding, JSON event ingestion, and terminal alerting for unexpected process execution, filesystem writes, and privilege escalations.
- **Distributed Threat Intelligence Valkey L2 Cache & Cloudflare Radar Batching (`devops security intel package`, `devops security intel network`)**:
  - Distributed threat intelligence evaluation pipeline with Valkey L2 caching, Cloudflare Radar batching, and OSV package vulnerability analysis.
  - Configurable TTL caching, offline-first fallback, and automated domain/package reputation scoring.
- **Multi-Tier Docker Sandbox Networking Options (`devops sandbox deploy --network-mode`)**:
  - Configurable sandbox network isolation modes: `isolated` (zero egress), `egress-only` (restricted outbound), and `host`.
  - Network policy verification, automated port mapping validation, and container egress containment.
- **Native GitHub API Rate Limiting & Token-Bucket Pacing (`devops gh api`, `devops gh rate-limit`)**:
  - Native client-side token-bucket rate limiter (`run_gh`, `GitHubRateLimiter`) with adaptive request throttling, low-quota circuit breakers, and read caching.
  - Automatic quota reset monitoring and elimination of bare unmanaged `gh` CLI invocations.

### Fixed & Hardened
- **Zero Information Leakage & Secret Sanitizer Hardening**:
  - Word-boundary regex enforcement for sensitive keys and tokens, eliminating partial-word false positives.
  - Comprehensive path exclusions preventing credential leakage in log streams and exception representations.
  - Concrete RFC 1918 and internal homelab hostnames replaced with RFC 5737 documentation placeholders across code, tests, and documentation.
- **Kubernetes Ollama Memory Uncapping & DaemonSet Limit Elevation**:
  - Uncapped Ollama container memory limits in Kubernetes manifests to prevent OOM kills on high-parameter models.
  - Elevated CoreDNS and daemonset resource allocations for high-throughput cluster environments.
- **Mandatory Draft PR Policy & Pre-Push Quality Gate Enforcement**:
  - Defaulted release pull requests to draft mode (`devops release pr --draft`) to guarantee review controls.
  - Enforced mandatory pre-push local `devops ci` gate via pre-commit hooks, guaranteeing 100% test passing and >= 90% code coverage.
- **DevSecOps Review Feedback Remediation**:
  - Remediated review findings across sandbox container streaming, path traversal mitigations, and mock provider locations.

## [0.2.17] - 2026-09-14

### Added
- **Protocol-Agnostic Endpoint Readiness & Health Probing Subsystem (`devops sandbox probe`)**:
  - Multi-protocol health verification supporting HTTP/HTTPS, TCP socket handshakes, UDP datagram echoes, and TLS certificate validation.
  - Granular bounded timeouts, adaptive retry policies, and structured exit reporting for container startup orchestration.
- **Cgroup v2 Metrics Collection & Prometheus Application Scraping (`devops sandbox metrics`)**:
  - Native Linux cgroup v2 hierarchy traversal for memory limits, CPU throttle statistics, swap usage, and I/O pressure metrics (`psi/`).
  - Prometheus exposition format client scraping and real-time terminal metrics reporting.
- **W3C Traceparent Propagation & Distributed Trace Correlation (`devops sandbox traces`)**:
  - Distributed trace context injection and extraction conforming to W3C Trace Context specifications (`traceparent`, `tracestate`).
  - Terminal waterfall timeline rendering for span durations, network latencies, and child context propagation.
- **Streaming Diagnostic Log Aggregator & Panic Detector (`devops sandbox logs`)**:
  - Real-time multiplexed container log tailing with regex-driven panic, deadlock, and unhandled exception detection.
  - Color-coded severity categorizations and automated crash context diagnostics.
- **Automated GitOps Drift Detection & Argo CD Watch (`devops argo gitops watch`)**:
  - Automated continuous GitOps reconciliation and drift detection against remote Git repositories and target cluster states.
  - Rich status dashboard and automatic event notifications for out-of-sync or degraded Argo CD applications.
- **Declarative GitHub Branch Protection Ruleset Auditor & Synchronizer (`devops gh branch-protection`)**:
  - Declarative policy specification in YAML (`.github/branch-protection.yml`) for `main` and `release/*`.
  - Comprehensive drift detection across required reviews, status checks, admin enforcement, and merge restrictions, with automated sync.
- **Libsodium-Sealed Repository Secrets Synchronization (`devops gh secrets`)**:
  - Secure public-key encryption using PyNaCl libsodium sealed-boxes for GitHub Actions repository secrets.
  - Direct synchronization from OS Keyring or HashiCorp Vault with strict zero-plaintext-leakage guarantees and bounded error truncation.
- **Deterministic Async Memory & Connection Pool Profiler (`devops test profile-memory`)**:
  - Leverages Python `tracemalloc` to snapshot, measure, and analyze heap allocations and detect socket leaks across async workloads (`fastmcp`, `http-pool`, custom callables).
  - Configurable peak memory thresholds (`--max-peak-mb`), socket leak validation (`--fail-on-leak`), OpenTelemetry span profiling, and structured JSON output.
- **DevOps CLI GitHub Operations & Pull Request Governance (`devops gh`, `devops pr`)**:
  - Native Typer command groups for GitHub Projects v2, milestones, labels, issues, and PR lifecycle management.
  - Multi-tiered merge readiness gating requiring 0 merge conflicts, 0 unresolved review threads, green CI checks, and approved reviews.
  - Resilient GitHub GraphQL secondary rate limit detection and automatic REST API fallback.
  - Programmatic review thread resolution (`devops pr threads resolve-all`) and replied-thread validation (`--auto-resolve`, `--allow-replied-threads`) in merge readiness checks.
- **Mandatory Draft PRs for In-Progress Work**:
  - Enforced policy and tooling requiring in-progress work to start as draft pull requests, preventing premature reviews and merge attempts.
- **Automated CI Check & Review Thread Monitoring (`devops pr monitor`, `devops pr checks`)**:
  - Real-time polling and progress inspection of remote CI checks, Copilot code reviews, and unresolved conversation threads.

### Fixed & Hardened
- **Kubernetes & Cloud Native Hardening**:
  - Resolved Helm Server-Side Apply (SSA) field ownership conflicts, Loki validation errors, and PodSecurity compliance issues (`k8s/`).
  - Centralized Fluent Bit namespace scoping and log perimeter hardening (`k8s/logging/`).
  - Flexible Kubernetes context configuration and conditional Minikube autostart.
- **DevSecOps Review Feedback Loop & Anti-Hallucination Datasets**:
  - Closed-loop review remediation and test verification across all static analysis and security scanning rules.
  - Updated anti-hallucination datasets for AI review models.
- **Core Dependency Ecosystem Alignment**:
  - Synchronized and locked dependencies across `uv.lock` for Python 3.14+ runtime stability.

## [0.2.16] - 2026-09-12

### Added
- **Long-Running Workload Sandbox Lifecycle Engine (`devops sandbox`)**:
  - Secure ephemeral Docker container sandboxes for long-running processes, dev servers, background tasks, and isolation testing.
  - Lifecycle orchestration: `deploy`, `status`, `exec`, and `stop`.
  - Enforced memory limits, CPU bounds, read-only root filesystems, and bounded workspace mounts.
- **Automated Formatting and Linting Commands (`devops format`, `devops lint`)**:
  - Introduced top-level `devops format` and `devops lint` CLI commands with clean leaf command usage.
  - Default `--fix` enabled across `devops ci`, `devops ci format`, and `devops ci lint`, with `--check` flag for non-mutating validation.
  - Reorganized Jekyll documentation site under `docs/` for seamless GitHub Pages rendering.
- **Squid Caching Forward Proxy & SSL-Bump Cluster Enablement (`k8s/squid/`)**:
  - Deployed Squid caching forward proxy in Minikube/Kubernetes cluster with SSL-Bump decryption, local CA generation (`devops tls generate-ca`), and signed endpoint certificates (`devops tls generate-cert`).
  - Enabled proxy cluster-wide, resolving root CA trust and accelerating external LLM model downloads and container registry image pulls.
  - Comprehensive Prometheus metrics scraping and automated health failover handling.
- **Context Document Compaction Engine (`devops docs compact`)**:
  - Context-preserving document compaction CLI and engine designed for large AI prompts, runbooks, and historical task tracking archives.
  - Compaction options including token estimation, hierarchical section reduction, and technical invariant preservation.
- **AI Chat Rich Formatting & Persona Styling**:
  - Modernized interactive `devops ai chat` CLI with live Rich Markdown streaming, syntax-highlighted code blocks, and formatted thinking display blocks.
  - Integrated distinct Persona Orange visual styling for enhanced developer identity.
- **Pre-1.0 Alpha Policy & Post-1.0 SemVer Governance**:
  - Formalized Pre-1.0 Alpha lifecycle policy guaranteeing zero backwards compatibility prior to 1.0.0 and requiring ruthless elimination of legacy remnants, obsolete shims, and zombie code.
  - Defined strict Semantic Versioning 2.0.0 and enterprise change management guidelines for post-1.0 releases.
- **Roadmap Strategic Expansion**:
  - Added Core Principles 12-14 and scheduled milestones:
    - **v0.2.19**: *Autonomous Trial-and-Error Solution Discovery, MCTS Exploration & Delta-Debugging Engine*
    - **v0.2.20**: *Deep Cognitive Information Foraging, Syntopical Reading & Epistemic Research Engine*
    - **v0.2.21**: *Iterative Agentic GitHub Project Manager & Autonomous Backlog Orchestration*

### Fixed & Hardened
- **Release Notes Fallback Extraction & Fatal Changelog Check (`devops release notes`, `devops release check`)**:
  - Strictly enforce matching version in `CHANGELOG.md` during `devops release check`, failing with exit code 1 if missing or mismatched.
  - Layered fallback extraction across `CHANGELOG.md` -> `docs/RELEASE_NOTES.md` -> git commit history (`git log <prev_tag>..HEAD` or `git log -n 20`).
  - Guarded `.github/workflows/release.yml` with a defensive fallback to commit logs in the release notes extraction step.
  - Decomposed `release_check` into helper functions preserving cyclomatic complexity <= 10.
- **DevSecOps Review Findings Remediation**:
  - **Credential Leakage Defenses**: Excluded `authorization_token` from serialized model settings in diagnostics while preserving runtime provider authentication in MCP tools (`NativeTool.get_model_settings`, `_build_mcp_tool_settings`).
  - **Argument & Command Injection Mitigation**: Centralized Kubernetes RFC 1123 resource name validation in `core/validation.py` for chaos testing (`k8s/chaos.py`) and log querying (`k8s/logql.py`).
  - **Rich Markup Injection Defense**: Hardened `console.print()`, `panels.py`, `scalars.py`, and `table_builder.py` with `safe=True` markup escaping to prevent terminal escape injection.
  - **WebSocket Frame Bounding**: Enforced 1MB maximum frame size at raw UTF-8 byte level in `server/routes/stream.py`, closing oversized connections with code 1009.
  - **Error String Bounding**: Enforced strict <= 256 character limits on exception messages in `pipeline/pipeline.py` and dry-run details to prevent log injection.
  - **Offline Threat Intel Fallback**: Integrated resilient offline fallbacks into `security/reference_extractor.py` and filtered documented example domains (RFC 2606, 6761), IPs (RFC 5737, 3849, 6890), and telephone numbers.
  - **Closed-Loop Feedback**: Registered `HALLUCINATION-LOCAL-FILE-OR-COLLECTION-CWE400` in common hallucinations catalog and added falsification rules in review prompts.
- **Comprehensive Infrastructure & Homelab Sanitization**:
  - Stripped internal LAN hostnames, RFC 1918 IPs, concrete hardware mount paths, and homelab topology across codebase templates, manifests, tests, and documentation.
  - Hardened agent instructions in `AGENTS.md` and `instruction_generator.py` to enforce abstract infrastructure placeholders (`<storage-node>`, `<host>`, RFC 5737 documentation blocks).
  - Protected local user runtime `config.yaml` from automated sanitization resets.
- **Kubernetes Workload Resource Tuning & OOMKill Prevention**:
  - Eliminated container cgroup OOMKills (`ExitCode 137`) across Jaeger and Valkey workloads by adjusting memory requests/limits and bounding trace/key buffers.
- **Architectural Circular Import Decoupling**:
  - Decoupled circular module imports and streamlined convoluted import patterns across core config settings, CLI main entry points, and stack lifecycle runners.
- **Unified Embedding Configuration**:
  - Consolidated all embedding configuration under `ai.tasks.embedding` (`model`, `ollama_urls`, `timeout`), removing duplicate and conflicting keys under `ai.rag`.

## [0.2.15] - 2026-09-10

### Added
- **Centralized Kubernetes Logging Stack & LogQL Integration (`devops k8s logs`)**:
  - Loki log aggregation engine and Fluent Bit log forwarder integration with dynamic namespace scraping.
  - Invocation `devops k8s logs [--query <logql>] [--tail <n>] [--follow] [<pod_name>]` supporting LogQL expressions, label streams, stream filtering, and JSON/terminal output formatting.
  - FastMCP tools for Loki centralized log exploration.
- **Infracost FinOps Cloud Cost Engine (`devops tf cost`)**:
  - Cloud infrastructure cost estimation and breakdown across AWS, Azure, and Google Cloud with breakdown tables and diff reporting.
- **Multi-Cluster ArgoCD Fleet Sync & Rollouts (`devops argo sync --fleet`)**:
  - Multi-cluster ArgoCD orchestration, fleet synchronization across managed clusters, and automated rollback triggers on health degradation.
- **BaseSecurityScanner Registry Migration**:
  - Completed migration of all 11 built-in security scanners (Bandit, Checkov, Dive, Gitleaks, Kubeconform, Kube-linter, Pluto, Popeye, Semgrep, TFLint, Trivy) to `BaseSecurityScanner` and unified `ScannerRegistry`.
- **Target-Agnostic AI Code Review & Multi-Convention Discovery**:
  - Generalize `devops ai review` for arbitrary target repositories (Python, Go, Rust, TypeScript, monorepos, Kubernetes manifests) with automated discovery across `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.cursorrules`.
- **Modular Agent Task Architecture (`docs/agent/tasks/`)**:
  - Per-task markdown tracking eliminating git merge conflicts across feature branches.

### Fixed
- **Distributed Tracing & Jaeger Stability Optimizations**:
  - Reduced `MEMORY_MAX_TRACES` to 10,000 and increased memory limit to 1024Mi in `k8s/otel/jaeger.yaml` to prevent pod OOMKills (`Exit Code 137`).
  - Refactored `src/devops_cli/telemetry/tracer.py` to avoid recording stack trace events on handled CLI exits (`typer.Exit`).
  - Bounded embedding timeout (`DEFAULT_RAG_EMBEDDING_TIMEOUT: 15.0`) with 2.0s connect timeout in `src/devops_cli/ai/rag/embeddings.py` for rapid multi-node failover.
- **Compatibility Remnants & Zombie Code Removal**:
  - Eliminated obsolete fallback shims, proxy wrappers, and vestigial aliases project-wide.

## [0.2.14] - 2026-09-09

### Added
- **Tree-Sitter Multilingual AST Graph & Polyglot Code Intelligence Engine (`devops ai ast`, `devops ai repomap --multilingual`)**:
  - Polyglot concrete syntax tree (CST) parser and S-expression query engine supporting Python, TypeScript, Go, Rust, Java, and HCL/Terraform without requiring host C compiler toolchains.
  - Subcommands `devops ai ast parse <file> [--query <s-expr>]` and `devops ai ast graph <path> [--format json|dot]`.
  - FastMCP tools `ai_ast_parse` and `ai_ast_graph` with dynamic AST schema exports.
  - Resilient zero-crash fallback to standard library `ast` when optional tree-sitter grammars are uninstalled.
- **Library API Drift & Deprecation Usage Auditor (`devops ai audit-library-usage`)**:
  - Proactive AST call-site auditor comparing workspace code against indexed library contracts in `.data/libraries/`.
  - Categorizes and flags `REMOVED_METHOD`, `UNKNOWN_ATTRIBUTE`, `UNRECOGNIZED_KWARG`, and `DEPRECATED_CALL`.
  - Emits Rich terminal discrepancy tables and persistent JSON reports (`.data/analysis/api_drift_report.json`) with `--fail-on-breaking`.
- **AI Context Packing & Symbol-Pruned Prompt Synthesizer (`devops ai pack-context`)**:
  - AST-driven symbol extraction and usage ranking reducing prompt token consumption by 40-60% while preserving strict interface fidelity.
  - Strips unreferenced private functions, methods, and attributes (`_helper`), skeletonizes function bodies with ellipsis (`...`), and compresses docstrings.
  - Multi-snippet token budgeting (`pack_snippets`) distributing limits proportionally across files.
  - Integrated into AI review pipeline `Stage1PreAnalysis` replacing naive character slicing.
  - CLI command `devops ai pack-context <path> [--referenced <syms>] [--max-tokens <int>]` and FastMCP tool `ai_pack_context`.
- **Autonomous RAG Index Drift Detection & Auto-Reindexing Engine (`devops ai rag drift`)**:
  - Compares working tree file content hashes and git commit HEAD divergence against vector index cache (`WorkspaceIndexer._load_cache()`).
  - Tracks `stale_modified_files`, `new_unindexed_files`, `deleted_files`, and computes normalized drift score ($[0.0, 1.0]$).
  - OpenTelemetry distributed tracing span (`rag.drift_detection`) and Prometheus metrics (`devops_cli_rag_drift_detected_total`, `devops_cli_rag_drift_score`).
  - Automated index reconciliation via `--auto-sync` and exit code gating with `--fail-on-drift`.
  - FastMCP tool `rag_drift(path, auto_sync)`.
- **Import-Driven AST Prompt Grounding & Contract Invalidation**:
  - Ground-truth library contract injection into code review stages (`Stage1PreAnalysis` and `Stage3PersonaReview`), reducing third-party API hallucination rates to <1%.
- **FastMCP Library Intelligence Tools & Dynamic System Resources**:
  - 3 FastMCP tools (`ai_ingest_library`, `ai_query_library`, `ai_inspect_symbol`) and dynamic system resource `resource://libraries/indexed`.
- **Dynamic Package Introspection & Multi-Source Documentation Ingestion (`devops ai ingest`)**:
  - Automated type stub extractor indexing installed library signatures into structured Pydantic v2 contracts (`.data/libraries/<pkg>-contract.json`).
  - SSRF-guarded documentation crawler ingesting remote/local documentation with breadcrumb navigation.
  - Dedicated vector collection `devops_libraries` in Qdrant with Valkey symbol caching.
- **GitHub Pages, Issues, Projects & Views Integration with FastMCP**:
  - Complete management subsystem for GitHub Pages, Issues, Projects v2, and Views with 10 FastMCP tools and 4 dynamic system resources (`resource://gh/*`).
- **GitHub Pull Request Review Threads & Multi-Turn Conversation Management**:
  - Programmatic resolution and in-thread reply automation for GitHub Pull Request review threads via GraphQL and REST APIs.

### Changed
- **Knowledge Base & Documentation Freshness**: Introspected CLI reference and README command matrix with 117 registered FastMCP tool schemas.
- **Architectural Invariants Compliance**: Enforced strict cyclomatic complexity $\le 10$ and nesting depth $\le 5$ project-wide across all new modules and CLI commands.

## [0.2.13] - 2026-09-09

### Added
- **Sub-Agent Local Offloading Engine & Agent Harness Slots (`devops_cli.ai.harness.slots`)**:
  - Modular Harness Slots (`ModelSlot`, `SkillSlot`, `ToolSlot`, `SubAgentSlot`) offloading token-intensive AST exploration, file scouting, and symbol cataloging to local open models (Granite, Qwen2.5-Coder via Ollama).
  - "Big decides, small types, big checks" multi-tier synthesis protocol achieving 85%+ frontier token savings with automated baseline calculation.
  - Dedicated CLI command group `devops ai harness` (`status`, `offload`, `run`) with `--format json` and `--dry-run` modes.
  - 2 FastMCP tools: `ai_harness_status` and `ai_subagent_offload`.
- **Interactive Terminal UI Dashboard (`devops dashboard` / `devops tui`)**: Full-screen responsive terminal dashboard powered by `Textual` for live Kubernetes pods, Docker containers, OTel spans, Valkey cache metrics, and AI review statuses with keyboard navigation and accessible help modal.
- **Model Dependency Chaos Engineering Suite (`devops ai chaos-model`)**:
  - Automated fault injection engine (`ModelChaosInjector`) evaluating resilient fallback routing across 4 failure modes: artificial latency, HTTP 429 rate-limiting, request timeouts, and malformed JSON payloads.
  - Automated local open-model fallback routing ensuring CI quality gates pass without manual intervention.
  - OpenTelemetry spans and Prometheus counter metrics tracking chaos injections and recovery events.
  - FastMCP tool `ai_chaos_model` and CLI command `devops ai chaos-model`.
- **Agent Constellation Quiesce & Emergency Failover Controller (`devops ai quiesce`, `devops ai failover`)**:
  - Enterprise state machine managing agent constellation suspension (`quiesce`), emergency route diversion (`failover`), and state resumption (`resume`).
  - Persistent snapshot state machine in `.data/agent/quiesce.json` with active route discovery and health inspection.
  - 4 FastMCP tools: `ai_quiesce`, `ai_failover`, `ai_resume`, `ai_constellation_status` and live resource `resource://ai/constellation`.
- **Multi-Model LLM Benchmark Evaluation Harness (`devops ai benchmark --suite`)**:
  - Parallel evaluation runner executing standardized benchmark suites with quantitative scoring (precision, recall, F1, hallucination rate, throughput).
  - Rich leaderboard table output and Markdown export for offline analysis.
  - FastMCP tool `benchmark_suite`.
- **Parallel Async Multi-File Review Worker Pool & Streaming Diff Parser**:
  - Asynchronous worker pool (`ReviewWorkerPool`) leveraging Python 3.14 `asyncio.TaskGroup`, `asyncio.Semaphore`, and token bucket rate limiting.
  - Streaming generator-based unified diff chunker (`diff_stream_chunks`) for zero-copy review processing.
  - CLI flags `--concurrency` / `-c` and `--parallel / --no-parallel` across `devops review path`, `branch`, and `pr`.
- **Logfire Structured AI Observability Bridge (`logfire`)**:
  - Native integration with Pydantic Logfire (`LogfireBridge`) supporting bidirectional W3C traceparent propagation and OTel collector forwarding.
  - Context manager `logfire_agent_turn` and Rich terminal visualizers (`render_agent_turn_table`, `render_agent_turn_panel`).
  - FastMCP tool `telemetry_logfire_status` and dynamic system resource `resource://telemetry/logfire`.
- **In-Cluster Container Registry & Kubernetes Stack Lifecycle**:
  - Automated local container registry on NodePort `30500` with containerd mirror endpoints on k3s nodes.
  - PodSecurity admission label alignment across namespaces.
  - Added `--wait / --no-wait` and `--timeout` flags to `devops k8s deploy-stack` for non-blocking deployments.
- **GitHub Milestones Lifecycle Automation**: Hardened `close_repository_milestone` and `edit_milestone` with automatic title fallback and parameter signature inspection.

### Changed
- **Dependabot Active Release Tracking**: Configured `.github/dependabot.yml` to target active release branch `release/v0.2.13`.
- **Human-Readable Output Duration Formatting**: Rounded durations >= 10s to whole seconds across CLI outputs, benchmarks, and multi-stage reviews.
- **Configuration Deduplication & Child Path Rebasing**: Harmonized `append_cache` between `AIConfig` and `AICacheConfig`, and implemented table-driven child path rebasing in `DataConfig`.

### Fixed
- **Review Findings Remediation & Self-Improvement Loop Hardening**:
  - Automatically mask sensitive dictionary fields in root `DevOpsError` exception representations.
  - Hardened AI agent step persistence, durable execution serialization, prompt template sanitization against tag injection, and tool argument traversal checks.
  - Eliminated Bandit B104 hardcoded loopback binding alert and satisfied strict static type constraints in `test_gen.py`.
  - Expanded the common AI hallucinations catalog and deterministic pre-verification engine with checks for uninitialized variables above loops, Pathlib `resolve()` non-existent path behavior, health probe version disclosure, and SSE streaming event timestamps.
  - Expanded test coverage across GitHub projects, milestones, labels, and verification heuristics to exceed strict 90% quality gate.
- **DevContainer SSH Signing Key Isolation & Tooling**:
  - Isolated git commit signing to devcontainer without mutating user global configurations.
  - Installed `pre-commit` at the system level in devcontainer Dockerfile.
- **GitHub Pages Site Layout & Documentation Badges**:
  - Resolved table rendering for Kramdown, updated canonical repository links, and hardened responsive CSS layouts.
  - Addressed Copilot code review feedback with dynamic site versioning and defensive DOM helpers.

## [0.2.12] - 2026-09-07

### Added
- **Valkey Workstation Management & High-Performance Distributed Caching Tier (`devops valkey`)**:
  - Pure-Python synchronous RESP2/RESP3 wire protocol encoder (`encode_command`) and streaming parser (`parse_resp`) without native C dependencies (`src/devops_cli/valkey/protocol.py`).
  - Standard TCP socket client (`ValkeyClient`) with connection pooling, bounded timeouts, password authentication, and zero-trust SSRF destination validation (`src/devops_cli/valkey/client.py`).
  - Valkey-backed atomic sliding-window token bucket rate limiter (`ValkeyTokenBucketRateLimiter`) with fail-soft burst mitigation and embedded Lua evaluation script (`src/devops_cli/valkey/rate_limiter.py`).
  - Distributed AI embedding and review finding cache tier (`ValkeyCacheProvider`) with fail-soft availability semantics and automatic key namespace isolation (`src/devops_cli/ai/cache/valkey_cache.py`).
  - Dedicated CLI command group `devops valkey` with subcommands: `ping`, `info`, `stats`, `keys`, `get`, `set`, `flush`, `backup`, and `cli`, integrated with `@dry_run_command` and runtime duration formatting (`src/devops_cli/commands/valkey.py`).
  - 6 new FastMCP tools (`valkey_ping`, `valkey_info`, `valkey_stats`, `valkey_get`, `valkey_set`, `valkey_flush`) and live system resource `resource://valkey/status` (`src/devops_cli/ai/mcp/server.py`).
  - Configuration and Keyring integration for Valkey: host, port, DB, timeout, and secret password (`valkey.password`) in OS keyring.
- **GitHub Projects v2, Milestones & Runtime Duration Formatting**:
  - Human-readable duration formatting (`format_duration`) across all CLI command outputs, benchmarks, and multi-stage review pipelines.
  - Omitted status suffixes from milestone descriptions during automated roadmap extraction.
  - Automated project management FastMCP tools and GraphQL conversation resolution for Pull Request reviews.

### Fixed
- **OS Keyring Secret Health Auditor**:
  - Expanded audited secret keys in `devops config audit-keys` to 8 managed credentials including `valkey.password`.
- **Egress & Protocol Safety**:
  - Strict rejection of cloud metadata (`169.254.169.254`) and unauthorized non-public IPs on Valkey socket endpoints.

## [0.2.11] - 2026-09-06

### Added
- **DevSecOps Architectural Hardening & Zero-Trust Defense-in-Depth**:
  - Expanded universal secret sanitizer pattern catalog with HashiCorp Vault tokens (`s.*`, `hvs.*`, `hvb.*`), GitLab PATs (`glpat-*`), Slack webhooks, and HuggingFace API tokens (`hf_*`).
  - Injected `Authorization: Bearer <key>` into `OpenAIProvider` and `x-api-key` into `AnthropicProvider` with OS Keyring and environment variable fallbacks.
  - Implemented fail-closed SSRF DNS resolution guard in `_enforce_non_private_ssrf`, eliminating DNS-rebinding and unresolvable destination bypasses when `allow_private=False`.
  - Hardened Docker workload sandbox (`WorkloadSandboxRunner`) with default `read_only=True`, `cap_drop=["ALL"]`, `security_opt=["no-new-privileges:true"]`, `pids_limit=256`, path containment blocking `~`, `.ssh`, `.aws`, `.kube`, `.git`, and `docker.sock`, and bounded subprocess timeouts.
  - Added `ignore_tests` parameter to `run_gitleaks_scan` and review static analysis stages to eliminate false alerts from mock test credentials per `AGENTS.md` guidelines.
  - Added Pod Security Admission (`restricted` / `baseline`) labels to `k8s/namespaces.yaml` and `k8s/llm/namespace.yaml`.
  - Created `k8s/llm/networkpolicy.yaml` with default-deny perimeter, intra-namespace routing, CoreDNS (port 53), and cloud metadata (`169.254.169.254/32`) egress blocking.
  - Configured restricted `securityContext` and `podSecurityContext` in `k8s/llm/values-qdrant.yaml`.
  - Pinned `uv` to `0.12.3` in `.devcontainer/Dockerfile`.
- **GitHub Integration Subsystem (`devops gh`)**:
  - Declarative label management (`devops gh labels sync`, `devops gh labels audit`) using `.github/labels.yml`.
  - Roadmap-driven milestone synchronization (`devops gh milestones sync`, `devops gh milestones list`).
  - GitHub Projects v2 lifecycle & template provisioning (`devops gh project sync`, `devops gh views list`).
  - Registered 6 new FastMCP tools for GitHub automation.
- **Architectural & Submodule Boilerplate Consolidation**:
  - Declarative `@dry_run_command` and `@cli_command_handler` decorators across CLI command modules.
  - Unified path containment helpers (`safe_resolve_subpath`), subprocess execution (`run_json_subprocess`), and binary checking (`require_binary`).
  - Consolidated security scanner base (`BaseSecurityScanner`, `ScannerRegistry`) and unified AST cache (`ASTCache`).
  - Table rendering helper (`render_table`, `TableBuilder`).

### Changed
- **Token Efficiency & Documentation Optimization**:
  - Streamlined `AGENTS.md` by 36% (10.5KB reduction) to resolve assistant context window truncation.
  - Deduplicated AI review prompt stack across `review.md`, `guardrails_isolation.md`, and `verify_finding_system.md` (34% token reduction per review segment).
  - Clarified workspace data tier (`.data`) versus dedicated agent work product tier (`.data/agent`).

## [0.2.10] - 2026-09-05


### Added
- **Native Pydantic AI Framework Subsystem Adoption**:
  - Adopted native `pydantic_ai.toolsets` (`AbstractToolset`, `FunctionToolset`, `create_function_toolset`, combinators) with dual sync/async contracts, replacing legacy custom toolsets in `src/devops_cli/ai/toolsets/`.
  - Adopted native `pydantic_ai.tools` (`Tool`, `ToolDefinition`, `DeferredToolRequests`, `ToolApproved`, `ToolDenied`) in `src/devops_cli/ai/tools/`.
  - Adopted native `pydantic_ai.template` (`TemplateStr`, `PromptTemplate`, `PromptRunner`) in `src/devops_cli/ai/template/`.
  - Adopted native `pydantic_ai.settings` (`ModelSettings`) and model modernizations in `src/devops_cli/ai/settings/`.
  - Adopted native `pydantic_ai.run` (`format_run_summary`, `create_pending_message`, traceparent header integration) in `src/devops_cli/ai/run/`.
  - Adopted native `pydantic_ai.retries` (`RetryClient`, `create_retry_transport`) in `src/devops_cli/ai/retries/`.
  - Adopted native `pydantic_ai.result` (`Usage`, `AgentRunResult`, `CostSummary`) in `src/devops_cli/ai/result/`.
  - Adopted native `pydantic_ai.profiles` and `pydantic_ai.providers` (`create_pydantic_ai_provider`, `ThinkingStreamProcessor` dynamic delimiters) in `src/devops_cli/ai/profiles/` and `providers/`.
  - Adopted native `pydantic_ai.output` (`ToolOutput`, `NativeOutput`, `PromptedOutput`, `TextOutput`, `StructuredDict`, `CallableDict`, `OutputSpec`) in `src/devops_cli/ai/output/`.
  - Adopted native `pydantic_ai.models.ollama` (`OllamaModel`, `create_ollama_model`, `create_ollama_provider`, profile overrides) in `src/devops_cli/ai/models/ollama.py`.
  - Adopted native `pydantic_ai.mcp` (`MCPToolset`, `create_devops_mcp_toolset`, dynamic in-process FastMCP discovery) in `src/devops_cli/ai/mcp/`.
  - Adopted native `pydantic_ai.function_signature` (`FunctionSignature`, `signature_from_schema`, `signature_from_callable`, `render_tool_interface`) in `src/devops_cli/ai/function_signature.py`.
  - Adopted native `pydantic_ai.format_prompt` (`format_as_xml`, `format_context_as_xml`, `format_findings_as_xml`) in `src/devops_cli/ai/format_prompt.py`.
  - Adopted native `pydantic_ai.exceptions` and unified domain error taxonomy in `src/devops_cli/ai/exceptions.py`.
  - Adopted native `pydantic_ai.durable_exec` (`DurableWorkflowEngine`, `WorkflowStepRecord`) in `src/devops_cli/ai/durable.py`.
  - Adopted native `pydantic_ai.direct` (`direct_request`, `direct_request_stream`) in `src/devops_cli/ai/direct.py`.
  - Adopted native `pydantic_ai.concurrency` (`ConcurrencyLimitedModel`, `ConcurrencyLimiter`) in `src/devops_cli/ai/concurrency.py`.
  - Re-exported native common tools (`web_fetch_tool`, `duckduckgo_search_tool`, `tavily_search_tool`, `exa_search_tool`, `image_generation_tool`, `x_search_tool`) with SSRF guardrails in `src/devops_cli/ai/common_tools.py`.
- **Autonomous Common Hallucinations Registry & Hardened Matching Engine**:
  - Centralized declarative hallucination catalog (`.data/common_hallucinations.json` and `src/devops_cli/ai/review/common_hallucinations.json`) tracking recurring false positives.
  - Category-aligned similarity guards preventing syntax rules from over-matching security findings (path traversal, SSRF, command injection).
  - Stop-words filtering in `_FORBIDDEN_COMMON_WORDS` to prevent generic words from contaminating signature keywords.
  - Ground-truth verification (`verify_ground_truth_hallucination`) before invalidating findings.
- **Dedicated Agent Operational Task Tracking**:
  - Relocated continuous, real-time agent task tracking to `docs/agent/task.md` with `docs/agent/README.md` governance.

### Changed
- **Persona & System Review Prompts**:
  - Added Python 3.14+ PEP 758 bracketless multi-exception syntax awareness (`except Exc1, Exc2:`) and sanitization placeholder guidance (`<masked-*>`, `[REDACTED]`) to `devsecops/prompt.md`, `architect/prompt.md`, and `verify_finding_system.md`.
  - Added explicit invalidation rules disallowing false alarms on valid variable identifiers (e.g. `secret_storage_failed`).
- **Elimination of Legacy Boilerplate & Zombie Code**:
  - Cleaned up custom implementations of toolsets and tools in favor of native Pydantic AI primitives.

### Security
- **Secret Sanitizer Regex Hardening (`src/devops_cli/ai/review/sanitization.py`)**:
  - Required assignment/token context to prevent redacting standard Python identifiers like `secret_storage_failed`.
- **Codebase Security Remediations (Review Session 141532)**:
  - `src/devops_cli/ai/ext_langchain.py`: Added percent-decoding `unquote` before path traversal checks.
  - `src/devops_cli/ai/agents/media.py`: Added 64-character hex regex validation and directory containment in `DiskMediaStore`.
  - `src/devops_cli/security/vault_broker.py`: Added percent-decoding `unquote` in `parse_vault_uri`.
  - `src/devops_cli/ai/review/auto_fix.py`: Added path containment check before writing candidate remediation branches.
  - `src/devops_cli/ai/common_tools.py` & `src/devops_cli/ai/agents/capabilities.py`: Reordered `blocked_domains` check before allowlists and SSRF DNS, added case-insensitivity and strict redirect SSRF validation, and forwarded `blocked_domains` from `WebFetch`.
  - `src/devops_cli/k8s/chaos_runner.py`: Validated arguments against CLI flag injection (`-` prefix) and inserted `--` into `kubectl delete pod`.
  - `src/devops_cli/ai/diff/difftastic.py`: Validated branch and base references against leading hyphens.
  - `src/devops_cli/security/complexity.py` & `src/devops_cli/security/kubelinter.py`: Relativized target file paths to prevent system path disclosure.

## [0.2.9] - 2026-09-03

### Added
- **Deterministic Prompt Rule Transformations & Location Canonicalization (`src/devops_cli/ai/review_schema.py`, `tests/test_prompt_programmatic_functions.py`)**:
  - Added pure programmatic functions replacing fragile inline LLM prompt heuristics: `canonicalize_finding_location` (canonical `file:start-end` or `file:line` formatting, markdown reference stripping, inverted range correction), `sanitize_finding_text` (stripping criteria leakage and prompt boilerplate), and `derive_recommendation` (severity-based merge decision mapping).
  - Added comprehensive unit test suite in `tests/test_prompt_programmatic_functions.py`.
- **Review Finding Feedback Dataset Export & Self-Improvement Loop**:
  - Exported verified finding dataset to `.data/feedback_dataset.jsonl` enabling downstream agentic self-improvement and prompt evaluation.
- **Universal Multi-Stage Workflow Orchestration Pipeline (`src/devops_cli/pipeline/`, `tests/test_pipeline_engine.py`)**:
  - Introduced generic `StagePipeline[ContextT, ResultT]` and `PipelineStage` framework supporting sequential and DAG-based stage execution with scratchpad context passing.
  - Granular `@trace_span` telemetry waterfalls, error isolation, and metrics collection (`pipeline_runs_total`, `pipeline_run_duration_seconds`).
- **Unified Async HTTP/2 Connection & Security Broker (`src/devops_cli/http/broker.py`, `tests/test_http_broker.py`)**:
  - Centralized thread-safe `HttpClientBroker` managing shared `httpx2` client connection pools with HTTP/2 multiplexing, SSRF private network isolation, and traceparent propagation.
- **Local Kubernetes Chaos & Fault Injection Runner (`src/devops_cli/k8s/chaos_runner.py`, `tests/test_k8s_chaos_runner.py`)**:
  - Added `ChaosFaultRunner` supporting declarative pod disruptions, recovery time observation, and automatic rollback handling.
- **Continuous IDE File Watcher & Instant Review (`devops ai review path --watch`)**:
  - Added `--watch` / `-w` and `--debounce-ms` options to `devops review path` leveraging `DebouncedFileWatcher` to trigger instant multi-persona reviews on active file changes.
- **Automated Kubernetes Stack Credential Synchronization (`src/devops_cli/k8s/credentials.py`, `devops k8s sync-secrets`)**:
  - Added zero-plaintext credential extraction from Kubernetes Secrets (`argocd-initial-admin-secret`, `kube-prometheus-stack-grafana`, `grafana`) directly into OS Keyring (`argocd_password`, `grafana_password`).
  - Integrated automated credential synchronization into `devops k8s deploy-stack` and `devops k8s sync-secrets`.
- **Automated Dependency Vulnerability Remediation PR Engine (`src/devops_cli/security/dependency_remediator.py`, `devops scan fix`)**:
  - Added `DependencyRemediator` automating CVE patching across lockfiles (`uv lock --upgrade-package`), dry-run remediation planning, and git topic branch staging (`fix/security-<cve>`).
  - Registered `scan_fix` FastMCP tool for autonomous agent-driven dependency remediation.
- **Isolated Dockerized Workload Sandbox Environment (`src/devops_cli/docker/sandbox.py`, `devops test sandbox`, `devops docker sandbox`)**:
  - Added `WorkloadSandboxRunner` providing rootless, ephemeral container test harnesses with bound workspace directories, resource quotas (`--memory`, `--cpus`), network isolation (`--network none`), and automatic container teardown.
  - Registered `docker_sandbox` FastMCP tool.
- **Enterprise HashiCorp Vault & Cloud KMS Secret Broker (`src/devops_cli/security/vault_broker.py`, `devops vault`)**:
  - Added `VaultSecretBroker` supporting Vault KV-v2 REST engine, URI references (`vault://<path>#<key>`), zero-plaintext storage, and seamless fallback to OS Keyring.
  - Added `devops vault` subcommands (`status`, `get`, `set`, `sync`) and registered `vault_status` and `vault_get` FastMCP tools.
- **Kubernetes Background Port-Forward Daemon Management (`src/devops_cli/k8s/port_forward_daemon.py`, `devops k8s port-forward`)**:
  - Added `PortForwardDaemonManager` with managed PID lifecycle tracking (`.data/k8s/port_forwards.json`), status inspection (`devops k8s port-forward-status`), and graceful process termination (`devops k8s port-forward-stop`).

### Changed
- **Removal of Heuristic Invalidation and Validation Functions**:
  - Removed heuristic auto-invalidation functions (`_check_contextual_exemption`, `_check_kustomization_namespace_exemption`, `_check_iac_operational_outputs`, `_check_missing_symbol_hallucination`, `_check_syntax_error_hallucination`, `_check_line_boundaries`) from `src/devops_cli/ai/review/verification.py` to prevent suppressing valid security defects.
  - Fixed verification default to `verified=False` preventing unverified findings from falsely validating.
  - Removed synthetic criteria count ratio scoring in finding verification.
  - Refined adversarial debate invalidation to preserve valid findings mentioning dependencies like `httpx2`.
  - Removed blanket exclusion instructions from `guardrails_isolation.md` and `verify_finding_system.md`.
- **Legacy & Shim Code Elimination**:
  - Removed legacy sequential single-prompt embedding fallback (`_fetch_fallback_single_embeddings`) in `src/devops_cli/ai/rag/embeddings.py`.
  - Cleaned up obsolete v0.1.1 feature comments and stubs in `src/devops_cli/commands/config.py`, `src/devops_cli/config/settings.py`, and `src/devops_cli/config/options.py`.
  - Updated review CLI docstrings to eliminate vestigial version tags.

### Security
- **Defense-in-Depth Path Traversal & SSRF Hardening**:
  - Enforced `allow_traversal=False` default in `validate_path` (`src/devops_cli/core/validation.py`).
  - Added DNS rebinding resolution to `_is_private_or_loopback` in `src/devops_cli/ai/common_tools.py`.
  - Added secret and credential token redaction (`***REDACTED***`) across agent hooks in `src/devops_cli/ai/agents/persistence.py`.
  - Added directory traversal guards to SQLite step store and symlink boundary containment guards across `aibom.py`, `kubeconform.py`, `skills.py`, and `pre_analysis.py`.
  - Sanitized prompt template variables in `ManagedPrompt.render` (`src/devops_cli/ai/agents/prompt.py`).


## [0.2.8] - 2026-09-01

### Added
- **Modular Output Formatters Subpackage (`src/devops_cli/output/formatters/`, `tests/test_fast_dispatch.py`)**:
  - Deconstructed monolithic formatting engine into modular, single-responsibility submodules: `scalars.py`, `tables.py`, and `panels.py`.
  - Added dedicated polymorphic TablePayload builders and finding panel formatters exposed via `devops_cli.output`.
- **Centralized Language Messages & Badges (`src/devops_cli/lang/en/messages.py`)**:
  - Added `BadgeMessages` and `OutputMessages` dataclasses to `LanguageCatalog` for full localization of terminal badges, status indicators, and headers.
  - Localized Kubernetes node status strings (`node_ready`, `node_not_ready`) and table titles.

### Changed
- **Declarative Dispatch Tables & Cyclomatic Complexity Elimination**:
  - Refactored AST symbol streaming in `src/devops_cli/ai/ast_stream.py` to use table-driven `_NODE_HANDLERS` dictionary and recursive decorator extraction.
  - Implemented declarative `_NATIVE_TOOL_SETTINGS_BUILDERS` and `_extract_local_tools` in `src/devops_cli/ai/agents/capabilities.py`.
  - Decoupled sub-agent execution in `src/devops_cli/ai/harness/workflow.py` via `_invoke_agent_callable`.
  - Replaced procedural truncation in `src/devops_cli/ai/harness/compaction.py` with `_TRUNCATION_FORMATTERS` and `_apply_compactor`.
  - Simplified settings coercion in `src/devops_cli/config/settings.py` via `_coerce_setting_value`.
  - Extracted certificate reading in `src/devops_cli/crypto/tls_certificates.py` via `_read_cert_bytes`.
- **Documentation Alignment & DevContainer Standardization (`docs/`)**:
  - Pinned container tag examples in `docs/DEVCONTAINER_USAGE.md` to current release (`v0.2.8`).
  - Aligned `docs/PENDING_FEATURES.md` and `docs/ROADMAP.md` reflecting completed v0.2.8 milestones.

### Removed
- **Zombie Code & Legacy Shims**:
  - Removed obsolete shims: `src/devops_cli/ai/review/rendering.py`, `src/devops_cli/models/dry_run.py`, and `src/devops_cli/core/dry_run.py`.
  - Merged `SSHKeyInfo` into `src/devops_cli/models/ssh.py` and deleted redundant `src/devops_cli/models/github.py`.
  - Cleaned duplicate entries in `src/devops_cli/output/__init__.py::__all__`.

## [0.2.7] - 2026-09-01

### Added
- **AI Bill of Materials (AIBOM) Generator & Model Curation (`src/devops_cli/security/aibom.py`, `src/devops_cli/commands/scan.py`, `tests/test_aibom.py`)**:
  - CycloneDX 1.5-compliant AI Bill of Materials (`devops scan aibom`) extracting model architecture parameters, licensing models (Permissive, Open-Source, Capped, RAIL, Proprietary), safe tensor formats, and cryptographic SHA-256 weight hashes.
  - Automated `trust_remote_code` AST and config analyzer detecting risky remote execution scripts before GPU provisioning.
  - Serving hardware heuristic estimator calculating peak RAM, inference VRAM, and disk storage for dense and Mixture-of-Experts (MoE) models across quantization bit-depths.
- **Zero-Allocation AST Symbol & Token Stream Parser (`src/devops_cli/ai/ast_stream.py`, `tests/test_ast_stream.py`)**:
  - Generator-based streaming parser yielding structural classes, functions, decorators, and imports without allocating intermediate node trees.
  - Line-level token streaming identifying indentation depths, comments, and string literals.
- **Cross-Encoder Context Re-Ranker & Deep Semantic RAG (`src/devops_cli/ai/rag/reranker.py`, `tests/test_rag_reranker.py`)**:
  - `CrossEncoderReranker` evaluating full query-chunk cross-token interaction density and reciprocal positional weighting.
- **"Big Decides, Small Types, Big Checks" Multi-Agent Synthesis Protocol (`src/devops_cli/ai/agents/synthesis_protocol.py`, `tests/test_synthesis_protocol.py`)**:
  - Three-stage synthesis pipeline orchestrating frontier planning models (Big Decides), fast local drafting models (Small Types), and frontier auditor models (Big Checks).
- **High-Performance Streaming Serializers (`src/devops_cli/output/streaming_serializer.py`, `tests/test_streaming_serializer.py`)**:
  - Low-memory streaming serializers for JSON arrays (`stream_json_array`), line-delimited JSON (`stream_jsonl`), and multi-document YAML (`stream_yaml_docs`).

### Fixed
- **SSH Key Prefix Configuration & Options Across Subcommands (`src/devops_cli/commands/ssh.py`, `src/devops_cli/crypto/ssh_keys.py`, `tests/test_ssh.py`)**:
  - Enhanced `devops ssh register` with `--prefix` / `-p` option and ensured it honors configured `settings.ssh.key_prefix` when discovering keys and generating registration titles.
  - Added prefix filtering and fallback in `find_newest_key()`, `list_managed_keys()`, and `list_managed_keys_info()`.
  - Added `--prefix` / `-p` support to `devops ssh status` and `devops ssh list` / `devops ssh audit`.
  - Exported `parse_key_prefix` and `list_managed_keys_info` in `devops_cli.crypto`.

## [0.2.6] - 2026-08-31

### Added
- **Multi-Dimensional AI Model Routing & Governance (`src/devops_cli/ai/router.py`, `tests/test_ai_router.py`)**:
  - Dynamic multi-axis model routing across task complexity (`LOW`, `MEDIUM`, `HIGH`, `FRONTIER`), task freshness (`STATIC_CONTEXT`, `LIVE_MCP_LOOKUP`, `EXTERNAL_WEB_SEARCH`), and data sensitivity (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL_AIRGAP`).
  - Air-gap data egress enforcement redirecting confidential workloads to local air-gapped models (`ollama`) with local fallback chains.
  - Cost and latency tier forecasting (`sub-second`, `fast-interactive`, `multi-second`, `deep-reasoning`) for AI execution plans.
  - Knowledge Base topic manual for Model Governance, Routing & Curation (`src/devops_cli/ai/knowledge_base/it_domains/topics/model_governance_routing_and_curation.md`).
- **AST Code Complexity & SBOM Generation (`src/devops_cli/security/complexity.py`, `src/devops_cli/security/sbom.py`, `src/devops_cli/commands/scan.py`)**:
  - AST cyclomatic complexity analyzer (`devops scan complexity`) computing per-function and per-module complexity scores and identifying nested branching.
  - Software Bill of Materials generator (`devops scan sbom`) supporting CycloneDX and SPDX formats from active lockfiles and installed packages.
- **Git-Diff Aware Targeted Test Execution (`src/devops_cli/commands/test_cmd.py`, `tests/test_test_runner.py`)**:
  - Added `devops test run --diff` discovering and executing only test files affected by unstaged or branch-level git diffs.
- **Live Resource & State Watchers Across Subsystems (`src/devops_cli/watchers/live_resource.py`, `src/devops_cli/commands/`)**:
  - Added `--watch` / `-w` and `--interval` support powered by `rich.live.Live` across `devops k8s pods --watch`, `devops docker stats --watch`, `devops argo cd apps list --watch`, and `devops release status --watch`.
  - Added `devops docker stats` command with real-time CPU%, memory net usage/limit, and network RX/TX I/O statistics table.
  - Added `devops k8s pods` command with real-time pod phase, ready container counts, restart metrics, and age reporting.
- **In-Memory SHA-256 Embedding LRU Cache (`src/devops_cli/ai/rag/embeddings.py`, `tests/test_rag_embeddings.py`)**:
  - Implemented thread-safe in-memory LRU cache (`_EmbeddingLRUCache`) keyed by SHA-256 hash of text and model identifier, accelerating repeated RAG queries and semantic search.
  - Instrumented embedding cache hits, misses, and active size metrics via OpenTelemetry/Prometheus.

### Changed
- **AST Chunking, Tool Registries & Review Stage Cyclomatic Complexity Reduction (`src/devops_cli/ai/rag/chunker.py`, `src/devops_cli/ai/tools/builtin_tools.py`, `src/devops_cli/ai/review/stages/`)**:
  - Decomposed complex multi-branch functions in AST chunking, tool registries, and review stages into dedicated single-responsibility helper functions and functional pipelines.
- **DevContainer Standalone Binary Isolation & Mount Hardening (`.devcontainer/devcontainer.json`, `src/devops_cli/commands/devcontainer.py`)**:
  - Configured dynamic interpreter path (`${containerWorkspaceFolder}/.venv/bin/python`) and remote environment `PATH`.
  - Preserved native `/usr/local/bin/devops` installation without overwriting with broken workspace symlinks.
  - Standardized cross-platform SSH mount syntax (`${localEnv:HOME}${localEnv:USERPROFILE}/.ssh`).

## [0.2.5] - 2026-08-27

### Added
- **Zero-Plaintext Invariant & Keyring Egress Security Audit (`tests/test_zero_plaintext_invariants.py`, `devops_cli.exceptions.security`)**:
  - Automated continuous regression suite verifying zero unencrypted secrets, tokens, or private keys exist across configuration files, `.data/`, `.devops/`, test fixtures, or docs.
  - Added `InsecureConfigError` with canonical exit code `126` (`E_INSECURE_CONFIG`) and contextual path masking.
- **FastMCP Tool Schema Completeness & Strict Type Validation (`tests/test_fastmcp_contracts.py`, `devops_cli.ai.mcp.server`)**:
  - Registered 6 new FastMCP tools (`ai_repomap`, `ai_diagram`, `ai_test_gen`, `config_audit_keys`, `telemetry_profile`, `tf_notify_plan`), bringing total registered tools to 40.
  - Verified 100% parameter descriptions, strict type annotations, structured JSON schemas, and flag injection defenses across all tools.
- **Universal Pydantic Resource Model Catalog (`devops_cli.models`)**:
  - Standardized request and result resource models across all domain subsystems (`docker`, `k8s`, `security`, `tf`, `config`, `workspace`, `release`, `ci`, `git`, `ai`) with dynamic FastMCP resource endpoints (`resource://*`).
- **DevContainer Workspace Cache Volumes & Lifecycle Management (`devops_cli.commands.devcontainer`, `.devcontainer/devcontainer.json`)**:
  - Configured dedicated Docker named volume mounts for `.uv`, `.venv`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, and `.data` for native Linux `ext4` I/O throughput on Windows hosts.
  - Added automated `post-create` and `post-start` permission enforcement ensuring standard cache directories are created and chowned to the active container user (`vscode`).
- **Team IDE Configuration & MCP Tracking (`.gitignore`, `.vscode/mcp.json`)**:
  - Permitted version-controlled tracking of shared `.vscode/` team configurations (`mcp.json`, `settings.json`, `tasks.json`, `launch.json`) in `.gitignore` while continuing to ignore user-specific overrides.
- **Structural Diff Path Containment & Arbitrary File Read Hardening (`devops_cli.ai.diff.difftastic`, `tests/test_difftastic.py`)**:
  - Enforced strict repository boundary validation with `resolve_safe_subpath` in `get_structural_diff`, mitigating arbitrary file read and information exposure risks (CWE-200 / CWE-284).

### Changed
- **Target Path Resolution & Pre-Analysis Metadata Refinement (`devops_cli.commands.review`, `devops_cli.ai.review.pipeline`)**:
  - Enforced absolute target path resolution across review commands and stage trace spans, eliminating relative `.` path ambiguity and path segment duplication in finding locations.
- **AST Structural Standardization & Strict Indentation Budgeting**:
  - Audited project-wide control flow and refactored all functions exceeding indentation depth limits, achieving **0** functions with depth $\ge 6$ across the entire repository.
  - Refactored `_render_review_result` in `rendering.py`, `_analyze_python_ast` in `scanner.py`, `_find_plaintext_config_leaks` in `config.py`, `chunk_file` in `chunker.py`, `Finding._pre_validate_finding` in `review_schema.py`, `_from_otlp_any_value` in `tracer.py`, and `render_table` in `formatter.py` into dedicated functional pipelines and standard library helpers.
- **Cold Import Latency Optimization & Lazy Loader Consolidation**:
  - Verified CLI cold import isolation, keeping `devops_cli.main` load overhead sub-second and deferring heavy third-party packages (`kubernetes`, `fastmcp`, `boto3`, `trivy`, `pydantic_ai`) to command execution time.
- **Workspace Data Tier Standardization (`.data/scratch/`)**:
  - Consolidated temporary and exploratory scripts into `.data/scratch/` ensuring 100% data artifacts reside within the centralized `.data/` tier.

## [0.2.4] - 2026-08-27

### Added
- **Trace Waterfall Visualizer CLI (`devops telemetry profile`, `devops_cli.telemetry.tracer`)**:
  - Implemented interactive terminal waterfall breakdown and latency heatmap of OpenTelemetry spans.
  - Added subcommands for span filtering by trace ID, last recorded trace, and direct command execution profiling.
- **Keyring Token Housekeeping & Secret Health Auditor (`devops config audit-keys`, `devops_cli.commands.config`)**:
  - Implemented OS Keyring backend health auditing, token state verification, and zero-plaintext file scanning.
- **FastMCP Tool Schema Contract Regression Suite (`tests/test_fastmcp_contracts.py`)**:
  - Added regression test suite verifying tool registration, parameter descriptions, typed signatures, and flag injection defenses across all 35+ FastMCP tools.
- **Aider-Style AST Repository Map Generator (`devops ai repomap`, `devops_cli.ai.repomap`)**:
  - Compact whole-repo symbol and relationship map generator parsing AST signatures and docstrings without context window overflow.
- **Architecture & Threat Modeling Diagram Synthesis (`devops ai diagram`, `devops_cli.ai.diagram`)**:
  - Automated Mermaid architecture topology (`graph TD`) and STRIDE zero-trust threat flowcharts (`graph LR`).
- **Prompt Mutation Testing & Benchmark Guardrails (`devops ai prompt-eval`, `devops_cli.ai.prompt_eval`)**:
  - Mutation benchmark suite evaluating persona prompt variations against ground truth feedback datasets. *(Correction: shipped as a deterministic suppression benchmark under that label without prompt perturbation; see #385 and #600).*
- **Automated Unit Test Synthesizer (`devops ai test-gen`, `devops_cli.ai.test_gen`)**:
  - Synthesizes isolated pytest test suites from AST signatures and uncommitted diffs.
- **Automated PR Remediation Branch Generator (`devops ai review auto-fix`, `devops_cli.ai.review.auto_fix`)**:
  - Generates corrective topic branches (`fix/finding-<id>`) with staged patches and unit test verifications.
- **tfcmt Automated PR Plan Notifier (`devops tf notify-plan`, `devops_cli.commands.tf`)**:
  - Formats structured, collapsible OpenTofu/Terraform plan diff summaries for automated PR comments.
- **Streaming SSE / WebSocket Agent Reasoning Feed (`devops serve /stream` & `/ws`, `devops_cli.server.routes.stream`)**:
  - Server-Sent Events (SSE) and duplex WebSocket feeds streaming real-time LLM token generation and reasoning scratchpad updates.
- **Hybrid Dense-Sparse RAG Tier (BM25 + Qdrant RRF, `devops_cli.ai.rag.retriever`)**:
  - Reciprocal Rank Fusion (RRF) combining dense embeddings with sparse keyword search scores.
- **Async HTTP/2 Connection Pooling & Client Reuse (`devops_cli.http.client`)**:
  - Added `new_async_http_client` with HTTP/2 support and connection pooling.

## [0.2.3] - 2026-08-26

### Added
- **Centralized Parameter Defaults & Invariant Constants Architecture (`devops_cli.config.defaults`, `devops_cli.config.constants`)**:
  - Centralized all inline parameter default values across functions and CLI subcommands into `src/devops_cli/config/defaults.py` and `src/devops_cli/config/constants.py`.
  - Added declarative subprocess argument builders in `src/devops_cli/config/commands.py` (`build_kubectl_cmd`, `build_kustomize_build_cmd`, `build_bandit_cmd`, `build_trivy_scan_cmd`, `build_popeye_cmd`, `build_kubelinter_cmd`, `build_pluto_cmd`, `build_uv_audit_cmd`, `build_tf_cmd`, `build_tofu_cmd`, `build_gitleaks_cmd`, `build_semgrep_cmd`).
- **Declarative Output Renderable Models (`devops_cli.output.models`)**:
  - Implemented declarative Pydantic v2 schemas (`TablePayload`, `PanelPayload`, `MarkdownPayload`, `SyntaxPayload`, `RulePayload`, `KeyValuePayload`, `MessageLevel`) with encapsulated Rich console rendering in `devops_cli.output`.
- **Comprehensive Domain Exception Taxonomy (`devops_cli.exceptions`)**:
  - Standardized strongly typed exceptions under `src/devops_cli/exceptions/` (`DevOpsCLIError`, `GitOperationError`, `InvalidBranchNameError`, `InvalidURLError`, `SecurityValidationError`, `ToolExecutionError`, `AIProviderError`, `ConfigurationError`).
  - Configured explicit POSIX exit codes, canonical machine-readable error codes, and structured error contexts project-wide.
- **Fast Typer Startup & PEP 562 Lazy Loading**:
  - Optimized CLI command dispatch with Typer lazy loading and stateless PEP 562 `__getattr__` / `_get` resolution across subcommands (`repos`, `branches`, `ci`, `mcp`, `release`, `uv`, `workspace`).

## [0.2.2] - 2026-08-25

### Added
- **Checkov IaC Static Policy & Compliance Engine (`devops scan iac`, `devops scan checkov`, `devops_cli.security.checkov`)**:
  - Implemented static compliance and policy security auditing across Terraform, CloudFormation, Kubernetes, and Dockerfile manifests.
  - Added CLI subcommands `devops scan iac <target>` and `devops scan checkov <target>` with Rich table and JSON exports.
  - Registered `scan_iac` native persona tool and bundled Knowledge Base manual: `it_domains/tools/checkov.md`.
- **TFLint Cloud Provider Linter (`devops tf lint`, `devops_cli.security.tflint`)**:
  - Implemented deep static Terraform/OpenTofu validation against cloud provider rules, deprecated syntax, and module variable constraints.
  - Added CLI subcommand `devops tf lint <dir> [--config FILE] [--json]`.
  - Registered `tf_lint` native persona tool and bundled Knowledge Base manual: `it_domains/tools/tflint.md`.
- **Dive Docker Layer Efficiency Analyzer (`devops docker analyze-layers`, `devops_cli.security.dive`)**:
  - Container image layer exploration and wasted space analysis computing efficiency scores and layer breakdowns.
  - Added CLI subcommand `devops docker analyze-layers <image> [--json]`.
  - Registered `docker_analyze_layers` native persona tool and bundled Knowledge Base manual: `it_domains/tools/dive.md`.
- **Kubeconform Fast OpenAPI Schema Validator (`devops k8s validate`, `devops_cli.security.kubeconform`)**:
  - Fast offline Kubernetes manifest validation against OpenAPI JSON schemas supporting arbitrary target Kubernetes versions and strict validation.
  - Added CLI subcommand `devops k8s validate <target> [--kubernetes-version STR] [--strict] [--json]`.
  - Registered `k8s_validate_manifests` native persona tool and bundled Knowledge Base manual: `it_domains/tools/kubeconform.md`.
- **Dynamic Cost- & Latency-Aware LLM Router (`devops ai route`, `devops_cli.ai.router`)**:
  - Task complexity classification and intelligent query steering between local Ollama models and frontier cloud models with estimated cost tracking.
  - Added CLI subcommand `devops ai route <task> [--tokens INT] [--frontier] [--json]`.
- **Automated Workspace & Data Tier Housekeeping Engine (`devops workspace clean`, `devops_cli.core.cleanup`)**:
  - Added retention policy pruning for stale review runs, temporary analysis caches, and trace logs under `.data/`.
  - Added CLI subcommand `devops workspace clean [--older-than INT] [--dry-run]` with top-level alias `devops clean`.

## [0.2.1] - 2026-08-25

### Added
- **Local Context Budgeting & Token Counting Engine (`devops ai token-count`, `devops_cli.ai.context_budget`)**:
  - Implemented Byte-Pair Encoding (BPE) token counting using `tiktoken` with model-family encoding resolution (`o-series`, `gpt-4o`, and character-ratio fallback).
  - Added semantic prefix-preserving truncation (`truncate_to_token_limit`) and hunk-aware git diff budgeting (`budget_diff_chunks`) to prevent context window overflow (HTTP 400).
  - Added CLI command `devops ai token-count <target> [--budget INT] [--model STR] [--json]` with Rich breakdown tables.
  - Bundled Knowledge Base tool manual: `it_domains/tools/tiktoken.md`.
- **Gitleaks Sub-Millisecond Secret Pre-Filter (`devops scan secrets`, `devops scan gitleaks`, `devops_cli.security.gitleaks`)**:
  - Subprocess runner with native regex fallback pattern scanning AWS access keys, GitHub PATs, OpenAI API keys, RSA/EC private key blocks, and Stripe tokens.
  - Integrated into Stage 2 code review pipeline (`devops_cli.ai.review.pipeline`) to scrub uncommitted secrets before LLM prompt dispatch.
  - Added CLI subcommands `devops scan secrets <target>` and `devops scan gitleaks <target>` with Rich table and JSON exports.
  - Registered `scan_gitleaks` native persona tool and bundled Knowledge Base manual: `it_domains/tools/gitleaks.md`.
- **Semgrep Static AST Pattern Matcher (`devops scan semgrep`, `devops scan sast`, `devops_cli.security.semgrep`)**:
  - Polyglot static AST pattern matching runner (`p/default`) with structured finding normalization (`Finding` models).
  - Integrated into Stage 2 code review pipeline for multi-language AST vulnerability scanning.
  - Added CLI subcommands `devops scan semgrep <target>` and `devops scan sast <target>`.
  - Registered `scan_semgrep` native persona tool and bundled Knowledge Base manual: `it_domains/tools/semgrep.md`.
- **PydanticAI Standardized Agent Framework (`devops_cli.ai.pydantic_ai_bridge`)**:
  - Standardized PydanticAI Agent bridge adapter (`create_pydantic_ai_agent`, `get_persona_pydantic_agent`) supporting strongly typed output models, dynamic parameter inspection, and persona workflows (`devsecops`, `architect`, `qa`, `pm`).
  - Bundled Knowledge Base manual: `it_domains/tools/pydantic_ai.md`.
- **Modular AI Review Pipeline Stages (`devops_cli.ai.review.stages`)**:
  - Decomposed the multi-stage review orchestrator into dedicated single-responsibility stage modules (`pre_analysis.py`, `static_scan.py`, `persona_review.py`, `verification.py`, `reranking.py`, `reporting.py`) with `@trace_span` telemetry instrumentation.
- **LLM Provider Abstraction Layer (`devops_cli.ai.providers`)**:
  - Modular provider protocol architecture (`BaseLLMProvider`) with dedicated provider implementations for `ollama`, `openai`, `claude`, `copilot`, and `mock` for deterministic test isolation.
- **Standardized Domain Exception Taxonomy (`devops_cli.exceptions`)**:
  - Strongly typed exception hierarchy (`DevOpsCLIError`, `SecurityError`, `SSRFBlockedError`, `KeyringUnavailableError`, `SecretExposureError`, `LLMInferenceError`, `ContextBudgetExceededError`, `ModelUnavailableError`, `PersonaExecutionError`) with explicit POSIX exit codes and canonical error codes.
- **In-Memory Prometheus Metrics Collector & Context Propagation (`devops_cli.telemetry.metrics`, `devops_cli.telemetry.context`)**:
  - Thread-safe in-memory metric registry (`GLOBAL_METRICS`, `InMemoryMetricsRegistry`) tracking counters, gauges, and histograms with Prometheus text exposition format and W3C traceparent header propagation (`inject_traceparent_headers`, `extract_traceparent`).
- **Strategic Roadmap Grooming & Industry Tool Integrations (`docs/ROADMAP.md`)**:
  - Extended and groomed the strategic roadmap through v0.3.0 incorporating advanced AI research (Multi-Agent Adversarial Debate, Spec-Driven Development, Dynamic Cost/Latency Router, Automated Test Synthesizer, Hybrid BM25+Qdrant Search, Cross-Encoder Re-Ranking) and open-source DevOps tooling (TFLint, Dive, Kubeconform, Stern, Helm-diff, Difftastic, tfcmt, Falco).

### Fixed
- **CodeQL Security Hardening**:
  - Resolved `py/stack-trace-exposure` on `/api/v1/telemetry` by sanitizing OTLP probe error returns and logging internal exception details via `logger.debug`.
  - Resolved `py/clear-text-storage-sensitive-data` in `file_writer.py` by allocating file descriptors using `os.open` with restrictive POSIX file creation modes (`0o644` / `0o600`) and upfront `os.chmod` on atomic temporary files.

## [0.2.0] - 2026-08-25

### Added
- **Published DevContainer Image Scaffolding Engine (`devops devcontainer init`, `devops_cli.commands.devcontainer`)**:
  - `devops devcontainer init` now defaults to the pre-built, published container image `ghcr.io/dan-petty/devops-cli/devcontainer:latest`.
  - Streamlined `devcontainer.json` generation omitting redundant feature blocks when using the published image, eliminating unnecessary tool builds in child repositories.
  - Added `--home-volume` option to configure custom persistent `/home/vscode` named volumes.
  - Added `--force` (`-f`) flag for in-place re-scaffolding of `.devcontainer/` and `.vscode/mcp.json`.
- **Pre-baked DevContainer Dockerfile & uv Integration**:
  - Created `.devcontainer/Dockerfile` pre-baking standalone `uv` and `uvx` binaries from `ghcr.io/astral-sh/uv:latest` and installing `devops-cli` globally.
  - Added self-bootstrapping lifecycle hooks in `postCreateCommand` for seamless container startup across all target repositories.
- **Pull Request DevContainer Image Publishing (`.github/workflows/ci.yml`)**:
  - Added automated GitHub Container Registry (GHCR) image builds for Pull Requests tagged with `pr-<number>` (without the `latest` tag) to enable pre-merge devcontainer validation.
- **Fault-Tolerant Code Review Pipeline (`devops_cli.ai.review.pipeline`)**:
  - Graceful per-file error isolation across all 6 review pipeline stages (pre-analysis, payload initialization, multi-persona review, verification, re-ranking, and report generation).
  - Skips failing files without crashing multi-file reviews and outputs dedicated Rich console tables and a Markdown `## Skipped / Errored Files` section in `review.md`.
- **Comprehensive Distributed Tracing & Subcommand Hierarchy (`devops_cli.telemetry`)**:
  - Unified command proxy delegation in `main.py` nesting all child commands, subprocess executions, and multi-agent pipeline stages under the root `cli.<subcommand>` span.
  - Instrumented OpenTelemetry spans across workspace RAG indexing (`ai.rag.index_workspace`, `ai.rag.upsert_chunk_batch`, `ai.rag.embed_texts`, `ai.rag.ollama_embed_batch`, `qdrant.upsert_points`).
  - Added `BaseException` handling in `trace_span` to capture `KeyboardInterrupt` and `SIGINT` cancellations with error tags and status attributes.

### Changed
- **Zero Hardcoded Scoring Policy & Agent Instruction Standards**:
  - Eliminated synthetic confidence floats, fallback weights, and static scoring defaults project-wide.
  - All review findings and quality ratings originate strictly from native external security scanners (Bandit, Trivy, OSV, Pluto) or structured LLM responses.
- **RAG Collection Isolation**:
  - Separated workspace indexing and knowledge base indexing into distinct Qdrant collections (`devops_code`, `devops_docs` vs `kb_code`, `kb_docs`) to prevent point deletion collisions.
- **Performance Optimizations & In-Memory Caching**:
  - Optimized repository file discovery in `runner.py` by eliminating redundant `git check-ignore` subprocesses for files already sourced from `git ls-files --exclude-standard`.
  - Cached compiled `.gitignore` pattern matching using `@functools.lru_cache` on `pathspec.PathSpec`.
  - Added RAG investigation memoization (`_INVESTIGATION_CACHE`) with a 60-second TTL and client reuse.
  - Cached `QdrantClient.is_alive()` status (15-second TTL) to eliminate repetitive HTTP collection probes.
  - Added robust integer coercion for `offset` and `max_bytes` in the `read_file` agent tool.
- **Default Git Configuration**:
  - Automatically configured default branch `main` and `push.autoSetupRemote true` across DevContainer post-start lifecycles.
- **Pure uv Toolchain Standardization**:
  - Replaced legacy pip invocations across all Dockerfile builds and devcontainer templates with pure `uv` commands (`uv tool install` and `uv pip install --system`).

## [0.1.13] - 2026-08-24

### Added
- **Embedding Model Benchmark Suite (`devops ai benchmark --type embedding`, `devops_cli.ai.benchmark`)**:
  - Dedicated vector embedding benchmark engine (`EmbeddingBenchmarkRunner`, `EmbeddingBenchmarkResult`, `EmbeddingBenchmarkReport`) evaluating dense vector embedding models (`qwen3-embedding`, `nomic-embed-text`, `all-minilm`, `bge-*`, `text-embedding-3-*`).
  - Automatic model classification and CLI routing in `devops ai benchmark` when embedding models are provided.
  - Evaluation corpus of 15 domain-specific query-passage pairs across 5 DevOps domains (Security, Kubernetes, Architecture, CI/CD, Infrastructure) and 10 distractor passages.
  - Evaluates semantic retrieval quality (Recall@1, Recall@3, Mean Reciprocal Rank (MRR), and Cosine Margin), single-query latency (p50/p95 ms), batch throughput (items/sec and chars/sec), and vector health ($L_2$ norm and dimension verification).
  - Rich interactive terminal leaderboard tables, JSON export to `.data/benchmarks/`, and Markdown summary rendering.
- **Local & Homelab TLS Certificate Management (`devops tls`, `devops cert`, `devops_cli.crypto`)**:
  - X.509 Certificate Authority and TLS server/client certificate generation using `cryptography.x509`.
  - Subject Alternative Name (SAN) auto-generation supporting IP addresses, hostnames, localhost, homelab `.lan` / `.local` domains, and Kubernetes service FQDNs.
  - Automated Kubernetes TLS secret provisioning (`devops tls inject-k8s-secret`, `devops k8s enable-tls`) and cert-manager ClusterIssuer integration for homelab/k3s/minikube environments.
- **Universal OpenTelemetry Integration (`devops telemetry`, `devops otel`, `devops_cli.telemetry`)**:
  - End-to-end telemetry configuration, status inspection, and OTLP trace export across all CLI operations and AI multi-agent pipelines.
  - Jaeger Query UI and OTLP collector deployment configurations in `k8s/otel/jaeger.yaml`.

- **OpenTelemetry Universal Command Tracing & Span Instrumentation (`devops_cli.telemetry.tracer`)**:
  - Full end-to-end command tracing spanning CLI subcommands (`branches`, `devcontainer`, `docker`, `github`, `install_tools`, `k8s`, `kustomize`, `mcp`, `pr`, `release`, `scan`, `tf`, `tls`, `tofu`, `uv`, `workspace`).
  - Trace span lifecycle attributes, sanitized arguments, duration tracking, error status recording, and custom OTLP header authentication support.

### Changed
- **Review Schema & Finding Deduplication Hardening (`devops_cli.ai.review_schema`)**:
  - Eliminated fragile literal collections, ad-hoc string lists, and keyword regex heuristics in favor of clean structural schema validation and standard path parsing.
  - Robust set-based token similarity with universal token length filtering and configurable line-range overlap tolerance for duplicate finding consolidation.
  - Hardened location parser handling POSIX URIs, GitHub-style anchors (`#L10-L20`), line ranges (`:10-20`), and Windows path conventions.
- **Standard Library & PEP 508 Code Hygiene Refactoring (`devops_cli.security.reference_extractor`)**:
  - Eliminated ad-hoc keyword lists and custom regex string splitting in favor of standard libraries (`ast`, `tokenize`, `packaging.requirements.Requirement`, `tomllib`, `json`, `yaml`, `urllib.parse`, `ipaddress`, `mimetypes`, `tldextract`).
  - Implemented PEP 508 requirement parsing for PyPI dependencies, PEP 621 `pyproject.toml` dependencies, optional dependency groups, and PEP 735 dependency groups.
  - Implemented AST string literal and comment tokenization for Python source code to eliminate false-positive domain matches on function calls, attributes, and variables.
  - Implemented RFC 2606 reserved domain exclusions (`.example`, `.test`, `.invalid`, `.localhost`) and strict public IP routability checks via `ipaddress.ip_address.is_global`.
- **Review Pipeline Linked File Context Optimization (`devops_cli.ai.review.pipeline`)**:
  - Added universal standard library filtering (`_UNIVERSAL_MODULES`) to prevent connecting all repository files via universal imports like `typing` or `pathlib`.
  - Bounded linked dependency files context to the top 10 relevant modules.
- **AI Review Tasks & Finding Verification Prompt Hardening**:
  - Hardened `src/devops_cli/ai/tasks/review.md` and `verify_finding.md` to prevent false positive detections and enforce actionable verification criteria.


## [0.1.12] - 2026-08-20

### Added
- **Universal Retrieval-Augmented Generation (RAG) Architecture (`devops ai rag`, `devops_cli.ai.rag`)**:
  - Polyglot syntax-aware AST chunker for Python, Go, Rust, TypeScript, JavaScript, Java, C/C++, Terraform/HCL, SQL, and Kubernetes YAML manifests.
  - Hierarchical technical documentation chunker preserving Markdown, AsciiDoc, and RST heading depth with breadcrumb hierarchy tracking.
  - Multi-project workspace autodetection (`Cargo.toml`, `go.mod`, `package.json`, `pyproject.toml`) and faceted semantic filtering (`--project`, `--language`, `--category`).
  - Native Qdrant vector database integration and Ollama dense embeddings generation (`all-minilm`).
- **Official `qdrant-client` SDK Adoption & Modernization**:
  - Replaced manual HTTP REST JSON calls with the official `qdrant-client` Python SDK with connection pooling, typed models, batch upserts, and payload filtering.
- **Hierarchical Configuration Modernization (`pydantic-settings`)**:
  - Upgraded `Settings` to inherit from `pydantic_settings.BaseSettings` with `SettingsConfigDict` supporting automatic environment variable binding (`DEVOPS_CLI_*`), schema validation, and secret masking while preserving OS Keyring security.
- **Multi-Context & Remote Cluster Kubernetes Support (`devops k8s`)**:
  - Added dynamic cluster reachability verification (`_cluster_reachable`) supporting remote k3s, EKS, and GKE cluster contexts via `kubectl cluster-info`.
  - Added `--context` (`-c`) option support across `deploy-stack`, `teardown-stack`, `port-forward`, and `configure-urls`.
  - Added automated iterative pre-existing Helm resource adoption (`_adopt_helm_resource_if_conflict`).
- **Multi-GPU Native Ollama DaemonSet Deployment**:
  - Integrated `k8s/llm/ollama-daemonset.yaml` with multi-GPU access (`NVIDIA_VISIBLE_DEVICES: "all"`), `runtimeClassName: nvidia`, hostPort 11434, and shared NFS model cache.
- **Structural Metadata Extraction Engine (`src/devops_cli/ai/rag/metadata.py`)**:
  - Polyglot dependency and import parsing across 8+ programming languages.
  - Automated security sensitivity classification tagging code chunks into `crypto`, `network`, `auth`, `secrets`, `db`, `fs`, and `iam`.
  - Document frontmatter metadata parser extracting YAML/TOML metadata and heading hierarchy metrics.
- **Multi-Signal Search Re-Ranking Engine (`src/devops_cli/ai/rag/reranker.py`)**:
  - Hybrid scoring fusion engine combining dense vector cosine similarity (0.60), lexical token overlap (0.25), exact symbol match bonuses (+0.15), query intent classification (+0.10 for docs/code), and security alignment (+0.10).
  - Attached transparent `rerank_score` and individual `rank_factors` to every retrieved chunk.
- **Universal AI Subcommand RAG Integration**:
  - `devops ai chat`: Per-turn conversational semantic retrieval (`--rag/--no-rag`).
  - `devops ai pipeline`: Seeds multi-agent review and reasoning pipelines with relevant codebase context.
  - `devops ai agents`: Retrieves architectural context and CLI conventions when generating canonical agent instructions.
  - `devops ai analyze`: Injects related architectural context during metadata analysis and pseudocode extraction.
  - `devops ai review`: Injects re-ranked cross-file context with symbol and security tags into multi-persona code reviews.
- **End-to-End OpenTelemetry Tracing & Observability Stack**:
  - Integrated OpenTelemetry trace lifecycle spans across LLM dispatches, pipeline stages, and CLI operations (`devops_cli.telemetry`).
  - Jaeger Query UI and OTLP collector deployment manifests (`k8s/otel/jaeger.yaml`).
  - Customized Grafana dashboards for AI inference latency, token metrics, and Kubernetes cluster health (`k8s/monitoring/dashboards/`).
- **DevContainer Background Git Daemon**:
  - Native automated background Git daemon with `--export-all` across `k8s` and `repos` during container post-start lifecycle.
- **GitHub PR Governance & Remote CI Inspection (`devops pr`)**:
  - Pull request lifecycle management (`create`, `status`, `checks`, `view`, `diff`) with automated release branch base targeting and CI check monitoring.
- **AI Review Subsystem Modularization & Decoupling**:
  - Refactored monolithic `commands/review.py` into cohesive domain modules under `src/devops_cli/ai/review/` (`runner.py`, `chunker.py`, `patching.py`, `exporter.py`, `verification.py`, `pipeline.py`).
- **Atomic AI Tasks, Finding Verification/Invalidation Criteria & Reportability Scoring**:
  - Decomposed AI review tasks into discrete, single-responsibility micro-steps to prevent prompt degradation.
  - Added explicit `verification_criteria` and `invalidation_criteria` to `Finding` data models.
  - Implemented criterion-based verification, deterministic confidence scoring, and `reportable: bool` assessment in review pipelines.
- **External Dependency Vulnerability Scanning & Network Reputation Auditing (`devops_cli.security.intelligence`)**:
  - Automated dependency extraction across Python (`pyproject.toml`, `requirements.txt`), JavaScript/TypeScript (`package.json`), Rust (`Cargo.toml`), and Go (`go.mod`) with live OSV.dev and NVD (NIST) vulnerability CVE lookups.
  - Automated extraction of external network references (public IPs, FQDNs, URLs in docs and source code) with Shodan InternetDB port/vulnerability and Cloudflare Radar threat reputation auditing.
  - Added formatted dependency and network intelligence tables to Markdown review reports and structured findings JSON payloads.
- **Universal AI Agent Memory & Automatic Summarization Engine (`devops_cli.ai.agents.memory`)**:
  - Incorporated structured `AgentMemory` with `MemoryEntry` tracking across all `PydanticAgent` instances, `MultiAgentPipeline` execution stages, and `devops ai chat` sessions.
  - Implemented automatic size-triggered context summarization (`auto_summarize_if_needed`) when interaction histories exceed message count or character limits, preserving critical technical decisions while consolidating older context.
- **Universal AI/LLM Response Fixer & JSON Recovery (`devops_cli.ai.fixer`)**:
  - Integrated `json-repair` library for resilient recovery and structural parsing of corrupted, truncated, or markdown-wrapped JSON payloads across all LLM inference streams.
  - Implemented thought-scratchpad filtering and dedicated natural language synthesis turns to guarantee clean user-facing outputs without leaked reasoning scratchpads.
- **Native Dependency Audit Tool (`scan_uv_audit`, `audit_dependencies`)**:
  - Integrated `uvx pip-audit` tools in native CLI tool registry (`devops_cli.ai.tools.native`) and FastMCP server (`devops_cli.ai.mcp.server`) for auditing Python dependencies in `pyproject.toml`, `uv.lock`, and `requirements.txt`.
- **Parallel Multi-Node LLM Prewarming (`devops ai chat --prewarm`)**:
  - Added parallel model prewarming and VRAM memory pinning (`keep_alive: "1h"`) across all configured Ollama cluster nodes at chat startup.
- **Architectural Separation of Constants and Defaults (`devops_cli.config`)**:
  - Decoupled immutable system invariants (`CONST_*` in `config/constants.py`) from configurable optional parameter defaults (`DEFAULT_*` in `config/defaults.py`).
  - Removed all `DEFAULT` prefixes and substrings from `CONST_` symbol definitions across the entire codebase.

### Changed
- **AI Agent Tool Execution & Anti-Repetition Loop Guardrails**:
  - Enforced parameter validation against tool schemas to eliminate stop-word argument hallucination.
  - Added duplicate tool call detection and autonomous natural language report synthesis in `PydanticAgent`.
- **Review Prompt & Verification Rule Hardening**:
  - Refined `src/devops_cli/ai/tasks/review.md` and `src/devops_cli/ai/tasks/verify_finding.md` to prevent speculative vulnerability reports on hypothetical helper behavior and eliminate false-positive syntax error hallucinations on standard Python 3 tuple exception handlers (`except (Err1, Err2):`).
  - Streamlined feedback dataset exporter (`devops ai review export-feedback`) to export complete review findings into `.data/feedback.jsonl` for continuous improvement benchmarks.

### Security
- **Path Traversal & Injection Defenses**:
  - Added strict path traversal defenses in `load_custom_repo_persona` (`src/devops_cli/ai/personas/__init__.py`).
  - Added tool description sanitization in `PydanticAgent` prompt construction (`src/devops_cli/ai/agents/pydantic_agent.py`) to prevent indirect prompt injection.
  - Added semantic version regex validation in `devops install-tools` binary downloads.
  - Added label format validation in `devops release prepare` before GitHub CLI invocation.
  - Switched Valkey deployment in `k8s/llm/valkey.yaml` from NodePort to `ClusterIP` and removed `--protected-mode no`.

### Fixed
- **API Boundary & Pipeline Invariants**:
  - Removed internal helper functions `_run_mcp_cmd` and `_validate_mcp_arg` from public `__all__` in `src/devops_cli/ai/mcp/__init__.py`.
  - Added positive integer validation for `max_turns_per_agent` and hoisted imports in `MultiAgentPipeline` (`src/devops_cli/ai/agents/pipeline.py`).
  - Added bounds enforcement on `top_k` and `score_threshold` and query masking in telemetry traces (`src/devops_cli/ai/rag/retriever.py`).

## [0.1.11] - 2026-08-18

### Added
- **Git & GitHub Project Best Practice Guardrails (`AGENTS.md`, `CONTRIBUTING.md`, `docs/ROUTINE_TASKS.md`)**: Comprehensive AI agent and developer operational guardrails for branch hierarchy (zero direct commits to `main`, base branch targeting `release/vX.Y.Z`, fresh topic branches), commit hygiene (Conventional Commits, atomicity, pre-commit validation, zero leaked secrets), PR governance (no autonomous merging by agents, in-place topic branch updates, active CI monitoring, and issue linking), and targeted unit testing during iterative feature development before full final-stage test runs.
- **Published Dev Container User Guide & CLI Scaffolding (`docs/DEVCONTAINER_USAGE.md`)**: Comprehensive user guide for consuming the published multi-tool GHCR DevContainer image (`ghcr.io/dan-petty/devops-cli/devcontainer:latest`) across VS Code, Cursor, and GitHub Codespaces, along with `--published` (`-p`) and `--image` (`-i`) flag support in `devops devcontainer init`.
- **Automated DevContainer Pre-Commit Installation**: Integrated automated `uv run pre-commit install` into the container startup lifecycle hook (`devops devcontainer run-lifecycle --post-start`) and added `.gitattributes` to enforce consistent LF line endings.

### Changed
- **Single Source of Truth Project Metadata Architecture**: Centralized metadata loading in `src/devops_cli/config/metadata.py` dynamically reading package version, description, and Python requirements directly from `pyproject.toml` and standard package distribution metadata (`importlib.metadata`), eliminating hardcoded version and configuration duplication across commands and defaults.
- **AI / LLM Prompt & Token Density Optimization**: Optimized persona domain prompts (`devsecops`, `architect`, `auditor`, `pm`, `qa`) and core review task prompts (`review.md`, `analyze_pseudocode.md`, `verify_finding.md`, `compose.md`, `metadata.md`, `chat.md`), eliminating cross-prompt rule duplication and reducing prompt token consumption.
- **CI Workflow Optimization & Duplicate PR Check Elimination**: Refactored `.github/workflows/ci.yml` to restrict `push` triggers strictly to `main` while maintaining `pull_request` triggers on `main` and `release/**`, eliminating duplicate CI runs on pull requests, and added workflow concurrency management to cancel superseded in-flight builds.
- **Evergreen Validation Nomenclature**: Standardized validation terminology across GitHub Actions workflows, CLI tooling, and documentation from numbered gates to evergreen `validate` / `Validation`.

### Fixed
- **DevContainer MCP & Minikube Initialization Resilience**: Enhanced `devops devcontainer post-start` to automatically scaffold and sync `.vscode/mcp.json` with explicit `env: { PATH: ... }` to `~/.gemini/config/mcp_config.json` and `.agents/mcp_config.json`. Hardened Minikube initialization with GPU detection (`nvidia-smi`), automatic fallback to CPU driver (`--driver=docker`), Docker daemon readiness verification, and automatic `minikube update-context` kubeconfig synchronization.
- **DevContainer GHCR Image Publishing Resilience**: Hardened `.github/workflows/release.yml` with lowercase GHCR repository naming and streamlined tag publication (`vX.Y.Z,latest`) to prevent 403 / `unknown blob` upload errors.

## [0.1.10] - 2026-08-18

### Added
- **Routine Tasks, Order & Methodology Guide (`docs/ROUTINE_TASKS.md`)**: Comprehensive operational manual outlining inner development loops, PR lifecycles, release orchestrations, security audit schedules, and workspace synchronization with explicit sequence ordering, frequencies, and troubleshooting matrices.
- **Strict Python 3.14 Environment Gate (`devops ci python-version`)**: Enforced standard Python 3.14+ runtime requirement across all CI quality checks and dev container configurations.
- **Actionlint & Pre-Commit Hook Integration**: Integrated [actionlint](https://github.com/rhysd/actionlint) (`actionlint-py`) into `devops ci actionlint`, `.github/workflows/ci.yml` validation pipeline, and root `.pre-commit-config.yaml` to detect GitHub Actions workflow schema discrepancies and parameter mismatches before triggering remote jobs.
- **DevContainer Pre-Build Smoke Test & Manifest Validation**: Added `devops devcontainer validate` command with JSONC comment-stripping and schema/mount/feature validation, and integrated pre-build smoke testing into `.github/workflows/ci.yml` and `.github/workflows/release.yml` prior to GHCR container registry publishing.
- **AI Review Feedback Dataset Exporter (`devops ai review export-feedback`)**: Added status-filtered JSONL dataset export (`--status INVALIDATED|VERIFIED|MITIGATED|ALL`) with rich finding metadata for prompt calibration, DPO alignment, and model fine-tuning.
- **FastAPI Service Roadmap Integration**: Defined native async FastAPI REST and OpenAPI service engine (`devops serve`) in `docs/ROADMAP.md` for remote CLI execution, AI reviews, and webhook integrations.
- **Parallel Test Execution & Worker Optimization**: Configured `--maxprocesses=4` for pytest-xdist in `pyproject.toml` and `devops ci`, reducing test suite execution time by ~4x.

### Security & Hardening
- **Path Traversal & Boundary Protection**: Enforced path containment checks across AI cache metadata (`cache.py`), outline timestamps (`outlines.py`), symlink tree walking (`repo.py`), and audit log destination paths (`audit.py`).
- **Data Confidentiality & Masking**: Redacted sensitive tokens, GitHub PATs, and PEM private keys in outline analysis and multi-agent scratchpad reasoning context.
- **SSH Key Permissions**: Implemented atomic creation of `.pub` files with restricted `0644` permissions and sanitized comment control characters.

### Changed
- **Codebase Modernization & Cleanup**: Streamlined developer and agent instruction documents (`AGENTS.md`, `CONTRIBUTING.md`, `RELEASE_CYCLE.md`), simplified branch protection and PR merge guidelines, and cleaned documentation artifacts.

## [0.1.9] - 2026-08-18

### Added
- **OpenTofu CLI Integration (`devops tofu` / `devops tf`)**: Infrastructure-as-Code command suite automating OpenTofu initialization, planning, application, outputs, and state validation with dual `tofu`/`terraform` binary discovery.
- **Multi-Cloud Cloud Resource Modules (`tf/`)**: Production OpenTofu manifests for provisioning Kubernetes clusters and networking across AWS (EKS), Azure (AKS), and Google Cloud (GKE) tailored for deployment of project `k8s/` resources.
- **Reusable Dev Container Package Publication (GHCR)**: Integrated automated Docker Dev Container image build and publication to GitHub Container Registry (`ghcr.io/dan-petty/devops-cli/devcontainer:<version>`) on release.
- **FastMCP OpenTofu Tools & Agent Bridge**: Exposed `tf_plan`, `tf_apply`, and `tf_output` (with `tofu_*` aliases) over Model Context Protocol and bridged tools for autonomous agent execution.
- **AI Prompt Optimization & Token Density Reduction**: Optimized task directives (`review.md`, `verify_finding.md`, `chat.md`, `compose.md`, `metadata.md`) and persona domain prompts, reducing prompt overhead by ~30% while preserving strict schema invariants.
- **Roadmap & Open-Source Tooling Refresh (`docs/ROADMAP.md`)**: Chronologically ordered all release milestones and defined integrations for OpenTelemetry, Prometheus, PydanticAI, Sigstore Cosign, Semgrep, Infracost, and FastAPI.

### Changed
- **Canonical Command References**: Standardized all legacy `devops review` documentation, tests, and configuration references to `devops ai review`.
- **Python 3 Exception Tuple Invariants**: Refactored multi-exception handling to parenthesized tuples `except (Err1, Err2):` across all codebase modules.
- **Pydantic Mutable Defaults**: Enforced `Field(default_factory=...)` on all Pydantic model mutable collection defaults.

### Governance
- **Agent Branch Isolation Guidelines**: Added strict rules forbidding commits to merged or unrelated branches in `AGENTS.md`, `CONTRIBUTING.md`, and `RELEASE_CYCLE.md`.

## [0.1.8] - 2026-08-17

### Added
- **Automated Release Cycle Suite (`devops release`)**: Native release management commands (`status`, `prepare`, `check`, `notes`, `tag`) automating semver bumping, changelog entries, docs synchronization, and pre-release verification.
- **FastMCP Release Tools**: Added `release_status` MCP tool allowing autonomous AI agents to query version consistency, git tags, and documentation freshness over Model Context Protocol.
- **Automated Documentation Engine (`devops docs`)**: Dynamic CLI and FastMCP introspection engine generating markdown manuals (`CLI_REFERENCE.md`, `MCP_TOOLS.md`, `ENV_VARS.md`) and synchronizing the `README.md` Command Matrix.
- **System Architecture & SRE Governance**: Enterprise system blueprints (`ARCHITECTURE.md`), open-source governance (`LICENSE`, `CONTRIBUTING.md`), defense-in-depth threat model (`SECURITY.md`), and GitHub Actions CI/CD quality gates (`.github/workflows/ci.yml`, `.github/workflows/release.yml`).
- **Configuration & Constant Centralization**: Unified all static paths, timeouts, regex patterns, and user-facing messages in `config/constants.py`, `config/defaults.py`, and `lang/en.py`.

## [0.1.7] - 2026-08-17

### Added
- **Native DevContainer Lifecycle Engine (`devops devcontainer run-lifecycle`)**: Implemented type-safe, cross-platform Python lifecycle hooks (`--post-create`, `--post-start`, `--all`) replacing legacy shell scripts (`postCreate.sh`, `postStart.sh`).
- **Enhanced AI Reasoning Scratchpad (`ScratchpadBuffer`)**: Multi-turn reasoning scratchpad context preserving intermediate chain-of-thought, persona notes, and verification hypotheses across multi-agent review stages.
- **Prompt Token & Latency Optimization**: Compact JSON serialization (`separators=(",", ":")`), structured prompt context formatting, and reduced prompt token overhead across local Ollama and remote LLM providers.
- **Robust Worker Error Recovery**: Exception resilience in multi-agent review workers and top-level workspace `.data` directory persistence for all review sessions and metadata.
- **Dry-Run State Isolation**: Added automated test lifecycle fixture resetting dry-run state across test worker processes.

## [0.1.6] - 2026-08-12

### Added
- **SecOps Static Vulnerability Engine (`devops scan`)**: Aqua Trivy integration for vulnerability, secret, and IaC scanning with automated finding injection into `devsecops` persona reviews.
- **Kubernetes Manifest Auditor (`devops k8s lint`)**: Red Hat Kube-linter static analysis for Kubernetes manifests and Helm chart security best practices.
- **Popeye Cluster Health Sanitizer (`devops k8s audit`)**: Active Minikube and Kubernetes cluster scanning for resource limits, probe configurations, and cluster anomalies.
- **Pluto Deprecated API Scanner (`devops k8s check-deprecated`)**: Fairwinds Pluto static scanner detecting deprecated and removed Kubernetes API versions.

## [0.1.5] - 2026-08-12

### Added
- **Minikube Endpoint Auto-Detection (`devops k8s configure-urls`)**: Auto-detects Minikube NodePort service endpoints (`argocd-server`, `kube-prometheus-grafana`, `kube-prometheus-kube-prome-prometheus`) and updates `config.yaml`.
- **Validation Pipeline Integration**: Automated quality gate enforcing sequential checks (`test`, `coverage`, `lint`, `format`, `typecheck`, `audit`, `security`).
- **Active Model Display**: Explicit model backend and provider visibility for all AI review file requests.

## [0.1.4] - 2026-08-12

### Added
- **Default AI Metadata Analysis (`devops ai analyze`)**: Made `--enhanced` mode the default execution behavior across all analysis commands (`path`, `branch`, `pr`), generating 6-10 line minimalist pseudocode outlines, complexity scoring, and ISO timestamps (`last_analyzed`).
- **Incremental Analysis Caching**: Intelligent skipping of unchanged files based on `st_mtime` vs `last_analyzed` timestamps, with `--update-all` (`-u`) flag to force full metadata regeneration.
- **Submodule-Aware Dependency Scanner**: Preserved full module/submodule imports (`pydantic.v2`, `rich.console`, `devops_cli.models.ai`) in Python AST and package analysis.
- **Clean Pseudocode Generation**: Eliminated generic boilerplate language and strictly excluded import statements and package directives from pseudocode output to ensure clean separation from extracted dependencies.
- **Code Dry-Run & Core Helper Refactoring**: Added `render_dry_run_result()` in `dry_run/state.py`, `get_repo_origin_name()` in `core/repo.py`, and `get_llm_client()` in `config/settings.py`.

## [0.1.3] - 2026-08-11

### Added
- **Interactive Patch Staging (`devops ai review apply-patch --interactive`)**: Interactive unified diff rendering and confirmation before applying suggested LLM fixes.
- **Air-Gapped Ollama Model Bundler (`devops ai bundle-models`)**: Export and package local Ollama model weight manifests for air-gapped DevContainer environments.
- **Kubernetes RBAC Audit Policy Scanner (`devops k8s rbac-audit`)**: Security audit scanner evaluating RoleBindings and ServiceAccount privileges across namespaces.
- **SIEM Live Audit Streamer (`devops config audit-stream`)**: Streaming structured JSON audit trail records to Syslog or HTTP collectors.

## [0.1.2] - 2026-08-11

### Added
- **Multi-Cluster Kubeconfig Management (`devops k8s switch-context`)**: Added context switching and cluster namespace controls.
- **SIEM Audit Trail Logger (`devops_cli.core.audit`)**: Structured JSON audit trail logging (`AuditLogger`) streaming execution events to `.data/logs/audit.jsonl` or `DEVOPS_CLI_AUDIT_LOG_DEST`.
- **Automated Fix Patch Application (`devops ai review apply-patch`)**: Interactively staging suggested LLM code fixes (`finding.fix`) to target workspace source files.
- **Subcommand Dry-Run Pydantic Expansion**: Standardized `CommandDryRunResult` Pydantic models across `argo`, `grafana`, `prometheus`, `devcontainer` subcommands.

## [0.1.1] - 2026-08-11

### Added
- **Human Invalidation Feedback Exporter (`devops ai review export-feedback`)**: Export invalidated review findings (`status == "INVALIDATED"`) into JSONL benchmark datasets for prompt tuning.
- **Repository-Level Custom Team Personas (`.devops/personas/<name>.md`)**: Dynamic loading of custom reviewer persona prompts defined in `.devops/personas/` under target repositories.
- **Headless CI Ephemeral Auth (`devops config auth-headless`)**: Memory secret storage fallback for DBus-less headless Linux CI environments.
- **Line-Level GitHub PR Inline Comments (`create_pr_review_comment`)**: Line-level inline comment posting capabilities in `GitHubClient`.
- **v0.1.1 Feature Flag Configuration**: Added `FEATURE_PR_INLINE_COMMENTS`, `FEATURE_CUSTOM_PERSONAS`, and `FEATURE_HEADLESS_AUTH` canonical option constants.

## [0.1.0] - 2026-08-11

### Added
- **Codebase Metadata Analysis (`devops ai analyze`)**: Subcommand generating structured `.data/analysis/<type>-<sanitized-ref>-metadata.json` files containing project structure, dependency graphs, key symbols, and file type classification.
- **Pydantic Model Dry-Run Responses**: All subcommands in `--dry-run` mode (`review`, `analyze`, `k8s`, `docker`, `repos`, `ssh`) construct and output structured Pydantic model JSON representations (`ReviewResult`, `AnalysisMetadata`, `CommandDryRunResult`).
- **`dry_run` Submodule Package (`devops_cli.dry_run`)**: Modular package structure (`state.py`, `models.py`, `__init__.py`) providing environment-backed dry-run state tracking and response schemas.
- **Package Security Audit (`devops ci audit`)**: Added `uv audit` command and integrated dependency vulnerability scans into the standard `devops ci` quality gate pipeline.
- **`UV_MALWARE_CHECK=1` Integration**: Enabled malware scanning for `uv` package operations in `.devcontainer/devcontainer.json` and `.devcontainer/postCreate.sh`.
- **Finding Verification Pipeline**: Step 3 verification (`_validate_segment_findings`) automatically cross-references reported findings against visible source code with `VERIFIED`, `UNVERIFIED`, and `MITIGATED` status tracking.

### Changed
- **Python 3.14 Compatibility**: Standardized all exception handling clauses to parenthesized tuples `except (Err1, Err2):`.
- **Target-Agnostic Heuristics**: Refactored AI reviewer persona prompts, static analysis heuristics, and review task templates to evaluate target repositories based on their own documented conventions rather than `devops-cli` specific paths.
- **Literal Centralization**: Centralized user-facing messages, command outputs, error responses, and configuration constants in `src/devops_cli/lang/en.py` (`LanguageCatalog`) and `src/devops_cli/config/constants.py`.

### Security & Hardening
- **Path Traversal & Injection Protections**: Enforced workspace boundary checks (`_is_safe_workspace_path`, `_resolve_from_project_root`) and input sanitization against argument injection (`-` prefix validation).
- **OS Keyring Isolation**: Sensitive tokens (`github.token`, `grafana.token`, `argocd.token`, `ai.api_key`) stored exclusively in OS keyring via `keyring`.
