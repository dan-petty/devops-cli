# Pending Features & Design Proposals — devops-cli

> [!NOTE]
> This document has been consolidated into the comprehensive [Strategic Roadmap (`docs/ROADMAP.md`)](ROADMAP.md).
> Please consult [`ROADMAP.md`](ROADMAP.md) for the active release roadmap, technical specifications, and ROI prioritization matrix.

---

## 🎯 Active Release Focus

### Current Milestone: `v0.2.11` (Active Development)
1. **Workstation Infrastructure Valkey Migration**: Replaced all Redis components in the Kubernetes stack (ArgoCD and LLM stack) with Valkey 8.0-alpine under the BSD-3-Clause open-source license.
2. **Codebase Stylistic & Structural Drift Remediation & Parameter Establishment**:
   - Zero functions exceeding nesting depth 5 (<6 indentations) project-wide across `src/devops_cli`.
   - Reduced cyclomatic complexity $\le 10$ across tool factory closures (`FileSystem.get_tools`).
   - Standardized domain exception taxonomy inheriting from `DevOpsCLIError`, completely eradicating bare `ValueError`/`RuntimeError` across domain logic.
   - Clean test collection hygiene (`__test__ = False` on mock models) and unawaited coroutine prevention.
   - Automated architectural invariant quality gates in CI (`tests/test_architectural_invariants.py`).
3. **FastMCP Server Tool Expansion & Antigravity Schema Integration**:
   - Expanded FastMCP server from 53 to 72 registered tools achieving 1:1 parity with CLI subcommands (Kubernetes chaos/audit/lint/validate/diff, Trivy, Gitleaks, Semgrep, Checkov, AIBOM, SBOM, Vault, benchmark, git branch/PR).
   - Introduced 4 FastMCP prompt templates and 6 dynamic system resources.
   - Added `devops mcp export-schemas` subcommand.
   - Synchronized lazy tool schemas directly to Antigravity IDE (`/home/vscode/.gemini/antigravity-ide/mcp/devops-cli/`).

### Previous Milestones
- **`v0.2.10` (Completed)**: Native Pydantic AI Framework Subsystem Adoption, Autonomous Common Hallucinations Registry & Hardened Matching Engine, Secret Sanitizer Regex Hardening, Codebase Hygiene & Zombie Code Elimination.
- **`v0.2.9` (Completed)**: Universal Multi-Stage Workflow Orchestration Pipeline (`src/devops_cli/pipeline/`), Unified Async HTTP/2 Connection Broker (`src/devops_cli/http/broker.py`), Local Kubernetes Chaos & Fault Injection Engine (`src/devops_cli/k8s/chaos_runner.py`), Continuous IDE File Watcher (`devops ai review path --watch`), Automated Dependency Vulnerability Remediation PR Engine (`devops scan fix`), Isolated Dockerized Workload Sandbox (`devops docker sandbox`), Enterprise Vault & Cloud KMS Secret Broker (`devops vault`), Kubernetes Background Port-Forward Daemon (`devops k8s port-forward`).
- **`v0.2.8` (Completed)**: Output Subsystem Modularization (`src/devops_cli/output/formatters/`), Language Message Catalog & Badge Localization (`src/devops_cli/lang/en/messages.py`), Declarative Dispatch Registries, Zombie Code Elimination.

### Upcoming Milestones

#### Milestone: `v0.2.12` (Scheduled)
1. **Valkey Workstation CLI Subsystem (`devops valkey`)**: Dedicated command group providing `ping`, `info`, `stats`, `keys`, `get`, `set`, `flush`, `cli`, and snapshot `backup`/`restore` managing local and remote Valkey instances.
2. **Valkey High-Performance Distributed AI & Embedding Cache (`ai.cache.backend=valkey`)**: Distributed SHA-256 keyed embedding and review finding cache tier slashing duplicate LLM inference by up to 85%.
3. **Distributed LLM Token Bucket & Concurrency Rate Limiter**: Valkey-backed atomic sliding-window rate limiter preventing GPU memory exhaustion on local Ollama endpoints and HTTP 429 throttling against cloud AI APIs.
4. **FastMCP Valkey Toolset & Live System Resource**: 6 FastMCP tools (`valkey_ping`, `valkey_info`, `valkey_get`, `valkey_set`, `valkey_keys`, `valkey_flush`) and dynamic system resource `resource://valkey/status`.
5. **Ephemeral Testcontainers Valkey Testing Harness**: Rootless container fixture for offline unit and integration test suites without requiring live Minikube cluster dependencies.
6. **Valkey IT Domain Knowledge Base Manual (`it_domains/tools/valkey.md`)**: Comprehensive technical guide covering Valkey 8.0 architecture, RESP3 wire protocol, memory optimization, eviction policies, and cluster topologies.

#### Milestone: `v0.2.13` (Scheduled)
1. **Dynamic Package Introspection & Type Stub Parser (`devops ai ingest library`)**: Automated AST and type stub (`.pyi`) extractor indexing installed library classes, method signatures, parameter types, defaults, and docstrings.
2. **Multi-Source Documentation & Standards Ingester (`devops ai ingest docs`)**: SSRF-guarded crawler ingesting local and remote documentation sets (Sphinx, MkDocs, DevDocs, PEPs, CIS benchmarks).
3. **Dedicated Library Vector Tier (`devops_libraries`) & Valkey Symbol Store**: Segregated Qdrant collection and Valkey cache tier providing sub-millisecond API signature lookups and hybrid dense-sparse search.
4. **Import-Driven AST Prompt Grounding**: Automatic detection of third-party imports across review diffs and on-the-fly injection of verified library API contracts into LLM prompts.
5. **FastMCP Library Ingestion & Symbol Tools**: Exposing `ai_ingest_library`, `ai_query_library`, and dynamic resource `resource://libraries/indexed` to IDE AI coding assistants.
6. **Library API Drift & Deprecation Auditor (`devops ai audit-library-usage`)**: Static AST analyzer comparing workspace calls against library contracts to detect deprecated parameters and removed APIs.

#### Milestone: `v0.2.14` (Scheduled)
1. **GitHub Issue Triage & Management Engine (`devops gh issues`)**: Automated issue classification, duplicate detection, sentiment/urgency analysis, and automated milestone/label assignment.
2. **GitHub Projects v2 Bi-Directional Synchronization (`devops gh project`)**: Two-way synchronization between local task tracking (`docs/agent/task.md`) and GitHub Projects v2 Kanban boards and roadmap views.
3. **Declarative Branch Protection & Repository Rule Auditor (`devops gh branch-protection`)**: Automated auditing and policy enforcement for repository branch protection rules, required reviews, and status check gates.
4. **Workstation Secret to GitHub Actions Secret Sync (`devops gh secrets`)**: Secure synchronization of developer workstation credentials (OS Keyring / Vault) to GitHub repository and environment secrets via libsodium public-key encryption.
5. **Declarative GitHub Label Schema Provisioner (`devops gh labels`)**: Automated reconciliation of repository labels and colors defined in `.github/labels.yml`.
6. **FastMCP GitHub Tools & Project Resources**: 4 FastMCP tools (`gh_issue_list`, `gh_issue_create`, `gh_project_status`, `gh_branch_protect_audit`) and live resource `resource://github/issues/open`.

#### Milestone: `v0.3.0` (Scheduled)
1. **Multi-Region Workstation Mesh & Cluster Federation**: Cross-cluster service discovery and state sync.
2. **Autonomous Self-Healing Agent Pipeline**: Self-diagnostic remediation loops.
3. **Cloud-Native Ephemeral Test Environment Engine**: Dynamic Minikube/Helm ephemeral environments.

---

## 📖 Related Strategic Documents
- **Master Strategic Roadmap**: [`docs/ROADMAP.md`](ROADMAP.md)
- **Active Working Log**: [`docs/LOG.md`](LOG.md)
- **System Architecture**: [`ARCHITECTURE.md`](../ARCHITECTURE.md)
- **Knowledge Base Task Manuals**: [`src/devops_cli/ai/knowledge_base/`](../src/devops_cli/ai/knowledge_base/README.md)
