# Strategic Roadmap — devops-cli

High-density product roadmap, engineering milestones, and open-source integration strategy for `devops-cli`.

## Core Vision & Design Principles

1. **Workstation-Native DevContainer First**: Native to local Dev Container workstation environments with Python 3.14+ runtime, `uv` virtual environments, and reproducible toolchains.
2. **Zero-Plaintext Secret Isolation**: Mandatory OS Keyring integration (`keyring`) for tokens and credentials (`github`, `grafana`, `argocd`, `ai`), eliminating plaintext storage across files, logs, and artifacts.
3. **SSRF-Defended AI Integrations**: Multi-provider LLM client (`ollama`, `claude`, `copilot`, `openai`) with private-network egress guards (`DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true`) and strict destination endpoint validation.
4. **Adaptive Workflow & Model Routing ("Own the Sensitive, Rent the Frontier")**: Decouple static single-model dependence. Dynamically route across two decision axes (Complexity and Freshness) to retain sensitive internal code on air-gapped/local open models (Granite, Qwen, DeepSeek) while renting frontier reasoning engines for high-complexity architectural design.
5. **Agent Harness Slots & Sub-Agent Local Offloading**: Partition multi-agent execution into swappable slots (Model, Skills, Tools, Sub-Agents). Offload token-intensive sub-agent tasks (code exploration, AST symbol mapping) to local open-weight models ("Big decides, small types, big checks") to achieve 85%+ token savings.
6. **Model Curation Pipeline & AI Bill of Materials (AIBOM)**: Fast, automated model supply-chain governance gating `trust_remote_code=True` via static AST/Semgrep inspection before GPU provisioning, preventing Shadow AI breaches and compiling verifiable AIBOM records.
7. **Model Dependency Chaos Engineering & Slow-Zone Resilience**: Deliberately test fallback models ("Chaos Monkey for Models") against tool suites and keep documentation/CLI `--help` 100% synchronized so lesser models can pilot automation without human coaching.
8. **Auditable Multi-Persona Code Reviews**: Domain-specialized personas (`devsecops`, `architect`, `pm`, `auditor`, `qa`) with deterministic static metadata extraction (`SegmentMeta`), prompt boundary isolation, and closed-loop finding verification.
9. **Zero Boilerplate & Standard Library Leverage**: Expressive integration of modern standard library utilities (`pathlib`, `ast`, `collections`, `itertools`, `functools`), Pydantic v2 schemas, and strict indentation budgets (<6 levels).
10. **Complete Observability Triad & Centralized Kubernetes Logging**: Unified telemetry integrating Prometheus client metrics, Jaeger/OTel distributed tracing, and Grafana Loki centralized log aggregation with LogQL CLI querying and agentic incident diagnosis.
11. **Pre-1.0 Alpha Velocity & Post-1.0 SemVer Change Management**: Until at least release `1.0.0`, `devops-cli` is active alpha software with no intention of maintaining backwards compatibility. The codebase must remain clean of legacy references and obsolete shims at all times so that it can reach maturity at a reasonable rate. Any version after `1.0.0` will follow strict semantic versioning conventions, and use all change management best practices including feature flags, deprecations, and migration functionality.
12. **Hypothesis-Driven Trial-and-Error & Counterexample-Guided Synthesis (CEGIS)**: Never rely on fragile single-shot generation for complex defects, performance bottlenecks, or refactorings. Formulate falsifiable hypotheses, explore solution trees (Tree-of-Thought / MCTS) in ephemeral shadow worktrees, accumulate failing counterexamples as formal negative constraints (CEGIS), enforce cascading fast-fail verification gates, and minimize discovered patches to atomic, Pareto-optimal diffs.
13. **Cognitive Information Foraging & Syntopical Epistemic Hygiene**: Agents must read, research, and gather information with human-like cognitive discipline—prioritizing inspectional multi-scale outlines over monolithic token dumps, traversing information scent cues with backtracking, maintaining active marginalia, triangulating claims against ground-truth primary sources, and synthesizing syntopical mental models that resolve dialectical contradictions.
14. **Autonomous Agentic Project Governance & Grounded Lifecycle Orchestration**: Software delivery must be autonomously governed through closed-loop, agentic project management. Work items, review remediations, and architectural epics must be decomposed into atomic, traceable issues with grounded taxonomy, real-time board transitions across lifecycle states, explicit dependency tracking, and dynamic WIP budgeting to eliminate ungrounded development and project drift.
15. **Reactive Terminal Ergonomics & Unified Workstation Command Center**: The developer terminal is the primary operational canvas. Complex multi-cloud, container, AI, and project lifecycle telemetry must be synthesized into a reactive, high-density terminal user interface (TUI) with non-blocking async workers, master-detail split screens, live log streaming, and sub-second fuzzy command dispatch, eliminating context switching to fragmented web dashboards.
16. **Stochastic Language Bound by Deterministic Mechanical Oracles & Feedback Inversion**: Autonomous engineering velocity relies on pairing probabilistic LLM token generation with deterministic mechanical oracles (AST complexity parsers, structural tuple assertion consolidation, negative JSON schema validation, POSIX process group containment, and pre-flight boundary limits). As quality gates reach 100% pass rates, feedback loops dynamically invert from reactive defect remediation to proactive architectural headroom optimization.

---

## Release Milestones (Chronological Order)

### Workstation Foundation, SecOps, Multi-Cloud IaC & Core Architecture (v0.0.1 – v0.1.9 - Completed)
- [x] **Runtime, Packaging & Workstation Core**: Python 3.14+ runtime with `uv` virtual environment management, cross-platform DevContainer Python lifecycle hooks (`devops devcontainer run-lifecycle`), OS Keyring zero-plaintext secret storage, SIEM audit logging (`AuditLogger`), and automated GHCR DevContainer container publishing.
- [x] **Multi-Persona Code Review Engine**: Domain-specialized personas (`devsecops`, `architect`, `pm`, `auditor`, `qa`), diff pagination, line-level GitHub PR inline comments, human invalidation feedback dataset exporter (`devops ai review export-feedback`), structured scratchpad reasoning buffer (`ScratchpadBuffer`), and XML prompt boundary isolation.
- [x] **Static SecOps & Kubernetes Auditing**: Static security scanner integrations (Aqua Trivy vulnerability & IaC scans, Red Hat Kube-linter manifest audits, Derailed Popeye cluster health sanitizer, Fairwinds Pluto API deprecations, and Kubernetes RBAC policy scanner).
- [x] **Local Kubernetes & Minikube Infrastructure**: Multi-cluster Kubeconfig context switching, automated Minikube NodePort endpoint discovery (`devops k8s configure-urls`), and multi-stack lifecycle (`infra`, `llm`, `all`).
- [x] **OpenTofu Multi-Cloud Infrastructure as Code**: Full IaC command suite (`devops tf`) with production OpenTofu modules for AWS (EKS), Azure (AKS), and GCP (GKE), and FastMCP IaC tools (`tf_plan`, `tf_apply`, `tf_output`).
- [x] **Automated Quality Gates & Dynamic Documentation**: Gated CI quality suite (`test`, `coverage`, `lint`, `format`, `typecheck`, `audit`, `security`), dynamic Click/Typer docs introspection engine (`CLI_REFERENCE.md`, `ENV_VARS.md`, `MCP_TOOLS.md`), and automated release management suite (`devops release`).

### Distributed Observability, AI Agent Harness, Workload Sandboxing & Hardened SecOps (v0.2.0 – v0.2.19 - Completed)
- [x] **Distributed Observability & Telemetry**: Prometheus client metrics, Jaeger distributed tracing waterfalls, Loki LogQL live log streaming, and OpenTelemetry traceparent propagation.
- [x] **Next-Gen PydanticAI Agent Architecture**: PydanticAI native subsystems, multi-turn reasoning buffers, prompt mutation testing, and human-in-the-loop feedback dataset export.
- [x] **Valkey Distributed Caching & Rate Limiting**: Pure-Python RESP3 wire protocol client, token-bucket rate limiter, and vector cache slashing LLM latency.
- [x] **Code Intelligence, Tree-Sitter & Ingestion Engine**: Polyglot CST parser, library contract introspector, API drift auditor, AST context packing, and file-size/symlink resource containment boundaries.
- [x] **Workload Sandboxing & Dynamic Runtime Security**: Rootless container sandbox, endpoint health probing, dynamic fuzzing, and base security scanner consolidation.
- [x] **High-Throughput LLM Gateway & Distributed Model Router (`#142`)**: Centralized OpenAI-compatible LiteLLM proxy in `llm` namespace with virtual model tiering (`devops-chat`, `devops-coder`, `devops-reasoning`, `devops-embedding`), vLLM Tensor Parallelism ($TP=2$) serving 70B models, least-latency routing, and circuit-breaking.

### Autonomous Trial-and-Error Solution Discovery, MCTS Exploration & Delta-Debugging Engine (v0.2.20 - Current Release / Active Development)
- [ ] **MCTS & Tree-of-Thought Solution Exploration Engine (`devops ai explore`) (P0 - Critical)**:
  - *Context & Rationale*: Replaces linear retry loops with structured graph/tree search over solution spaces. When addressing complex defects, test failures, or refactoring objectives, the engine synthesizes $K$ diverse, orthogonal root hypotheses across algorithmic, concurrency, configuration, and interface domains rather than greedily iterating on a single path.
  - *Search Dynamics & Heuristics*:
    - **Monte Carlo Tree Search (MCTS) & Upper Confidence Bound for Trees (UCT)**: Balances exploration of novel hypothesis branches with exploitation of partially passing candidates.
    - **State ($S_t$) & Action ($A_t$)**: Nodes encapsulate git AST snapshots, configuration state, and execution history; edges represent discrete AST mutations or configuration edits.
    - **Dynamic Pruning & Backtracking**: Detects circular diffs, regression dead-ends, and divergent search paths, pruning subtrees and immediately backtracking to the highest-scoring common ancestor node.
  - *Acceptance Criteria*: 100% detection of cyclic/divergent mutations; sub-50ms node state transitions; configurable exploration parameters (`--max-depth 4`, `--max-trials 10`, `--beam-width 3`).
- [ ] **Ephemeral Shadow Worktrees & CoW State Snapshots (`devops sandbox worktree`) (P0 - Critical)**:
  - *Context & Rationale*: Guarantees zero working tree contamination during exploratory trial-and-error runs. Automatically provisions isolated git worktrees under `.data/sandbox/worktrees/<trial_id>` linked to ephemeral branches.
  - *Sub-Second Checkpointing & Rollback*: Utilizes Copy-on-Write (CoW) filesystem features and git index staging to checkpoint state in $<50\text{ms}$ before applying speculative mutations, enabling instant micro-rollback upon failure without residual disk clutter.
  - *Containerized Shadow Environments*: Seamlessly links shadow worktrees with rootless Docker sandboxes (`devops sandbox deploy`) or ephemeral Kubernetes namespaces (`sandbox-<app>-<trial>`) for runtime executions requiring network ports, databases, or microservice dependencies.
- [ ] **Counterexample-Guided Inductive Synthesis (CEGIS) & Negative Constraint Accumulator (P0 - Critical)**:
  - *Context & Rationale*: Turns failed trial executions into authoritative learning signals rather than wasted compute.
  - *Diagnostic Failure Mining*: Parses failing trial runs to extract structured counterexamples: exact failing test inputs, assertion diffs (expected vs. actual), AST call stacks, exception types, and violated architectural invariants.
  - *Negative Constraint Synthesis*: Converts counterexamples into formal negative constraints injected into subsequent prompt turns (e.g. `[NEGATIVE_CONSTRAINT] Mutation must NOT alter parameter types of function F; caused AttributeError at caller C`).
  - *Regression Lock Engine*: Freezes previously passing assertions (`IterationState.passing_assertions`); automatically rejects any mutation that breaks an existing green check.
- [ ] **Hierarchical Delta-Debugging & Patch Minimization Engine (`devops ai patch-minimize`) (P1 - High)**:
  - *Context & Rationale*: Discovered trial-and-error solutions frequently contain superfluous code, exploratory debug statements, unnecessary variable renames, and speculative refactorings.
  - *Minimal Sufficient Patch (MSP)*: Implements hierarchical delta-debugging on the AST diff, systematically pruning individual AST nodes and diff hunks while re-running targeted tests.
  - *Occam's Razor Guarantee*: Outputs the absolute minimal atomic diff that completely satisfies all failing tests and architectural invariants, reducing review burden and PR noise.
- [ ] **Multi-Objective Pareto Solution Ranker (`devops ai rank-solutions`) (P1 - High)**:
  - *Context & Rationale*: When multiple exploratory branches yield passing solutions, evaluates candidates across a multi-dimensional Pareto frontier rather than picking an arbitrary winner.
  - *Evaluation Vectors*:
    1. **Correctness & Robustness**: 100% passing test suites, zero regressions, and resilience under fuzzing.
    2. **Structural Complexity**: Cyclomatic complexity $\le 10$, nesting depth $\le 5$, and minimal indentation churn.
    3. **Diff Minimality**: Minimal lines of code modified, minimal files touched.
    4. **Runtime Performance**: Execution latency delta and memory allocation delta.
    5. **Idiom & Style Conformity**: Leverage of standard library primitives (`pathlib`, `itertools`, `functools`) and conformity with project guidelines (`AGENTS.md`).
- [ ] **Valkey L2 Trial Invalidation Cache & Experience Replay (`trial:invalidation:*`) (P1 - High)**:
  - *Context & Rationale*: Distributed experience replay tier caching failed hypothesis fingerprints, counterexamples, and AST mutation signatures in Valkey L2.
  - *Collaborative Deduplication*: Prevents parallel subagents or future CLI sessions from repeating identical failing trials or exploring proven blind alleys across similar codebase patterns.
  - *Feedback Dataset Ingestion*: Automatically exports verified successful trial trajectories and minimized patches into `.data/feedback_dataset.jsonl` for offline prompt tuning and model distillation.
- [ ] **Canary Resilience & Chaos Fault-Injection Verifier (`devops ai verify-resilience`) (P1 - High)**:
  - *Context & Rationale*: Validates that the discovered solution is robust and generalizable rather than an overfitted workaround.
  - *Synthetic Adversarial Verification*: Subjects candidate patches to automated chaos experiments using `devops k8s chaos run` and dynamic API fuzzing (`devops sandbox fuzz`), testing pod disruption, injected network latency ($200\text{ms}$), packet loss, and boundary payload fuzzing.
- [ ] **Cascading Fast-Fail Verification Battery & Token Governor (P1 - High)**:
  - *Context & Rationale*: Hierarchical execution pipeline minimizing compute and latency during deep tree search:
    - *Tier 0 (Syntax AST Check, $<20\text{ms}$)*: Validates AST parseability and imports before spawning any processes.
    - *Tier 1 (Targeted Assertion, $<500\text{ms}$)*: Evaluates only the primary failing test case.
    - *Tier 2 (Submodule Regression, $<5\text{s}$)*: Runs targeted domain test suites.
    - *Tier 3 (CI & Invariant Gates, $<30\text{s}$)*: Executes full lint, typecheck, complexity, and security scans.
    - *Tier 4 (Chaos & Fuzzing, $<60\text{s}$)*: Adversarial canary stress test.
  - *Token & Wall-Clock Governor*: Tracks exploratory token spend and search depth, terminating unpromising branches before quota exhaustion.
- [ ] **FastMCP Solution Discovery Tools & Trial System Resources (P1 - High)**:
  - *Context & Rationale*: Exposes native FastMCP tools (`ai_explore`, `ai_patch_minimize`, `ai_rank_solutions`, `ai_verify_resilience`, `sandbox_worktree_create`, `sandbox_worktree_rollback`) and dynamic system resources (`resource://ai/exploration/tree`, `resource://ai/exploration/pareto`) enabling IDE coding assistants to trigger, inspect, and guide trial-and-error exploration interactively.
- [x] **Consolidated AI Review Report Markdown Sanitization & Code Block Hardening (P1 - High, Issue #250, PR #251)**:
  - *Context & Rationale*: Systemic normalization of `review.md` report artifacts across `.data/reviews`—automatic balancing of unclosed code fences (`format_markdown_fix`), safe rendering of pre-fenced markdown fixes without double-fencing, sanitized theme extraction resilient to scanner tags (`[DRY-RUN]`, `[GITLEAKS]`), and backtick/bold syntax collision prevention.
- [x] **Universal Subcommand Option Propagation (`--dry-run` & `--explain`) (P1 - High, Issue #252, PR #253)**:
  - *Context & Rationale*: Universal propagation of trailing `--dry-run` and `--explain` options across all CLI subcommands. Audited and verified all 369 registered subcommands have `--help` and verified declarative dry-run callbacks across all mutating commands.
- [x] **Forward-Looking Project Management, Roadmap Evolution & Issue/Task Synchronization (P0 - Critical, Issue #254, PR #255)**:
  - *Context & Rationale*: Mandates that project management across agent instructions, persona prompts, and automated tooling is forward-looking—continuously formulating ideas, suggestions, useful features, and meaningful integrations for `docs/ROADMAP.md`. Hardens documentation compaction against deleting scheduled milestones and builds automated roadmap-to-issue and task tracking synchronization.
- [x] **Fast CI Execution Caching & Pre-Commit File Change Tracking Integration (P1 - High, Issue #256, PR #257)**:
  - *Context & Rationale*: Introduces persistent, deterministic execution caching for `devops ci` quality gates, bypassing expensive test and validation runs (reducing execution latency from ~3 minutes to < 0.05s) when the workspace is unchanged since the last passing run. Integrates with Git pre-commit file change tracking (`pass_filenames: true`) and working tree/index change detection, with `--no-cache`/`--force` overrides.
- [ ] **Automated Parameter, Schema & CLI Interface Parity Oracle (P1 - High)**:
  - *Context & Rationale*: Static AST analyzer and runtime validator detecting missing or unpropagated CLI options, asymmetric parameter signatures, and schema discrepancies across Typer commands, FastMCP tools, and orchestrator APIs.
- [x] **Automated GitHub Pull Request Synchronization & Branch Update Integrations (P1 - High, Issue #258, PR #259)**:
  - *Context & Rationale*: End-to-end automated integrations and developer tooling to keep pull requests continuously synchronized with target base branches (`main`, `release/**`). Includes native CLI command `devops pr update` (with batch `--all`, optimistic concurrency `--expected-head-sha`, and `--dry-run`), FastMCP tool `pr_update_branch`, and GitHub Actions workflow `.github/workflows/update-prs.yml` supporting push-triggered sync, manual `workflow_dispatch`, and `/update` / `/sync` PR comment slash-commands.
- [x] **CI Performance Acceleration, Worker Auto-Scaling & Pathological Test Mocking (P0 - Critical, Issue #260, PR #261)**:
  - *Context & Rationale*: Reduces `devops ci` quality gate latency by 75%+ (from ~3m 15s to under 45s) across local workstations and CI runners.
  - *Worker Auto-Scaling & Dynamic Topology*: Dynamically scales Pytest xdist workers based on available hardware (`min(os.cpu_count(), 16)`), removing the hardcoded `--maxprocesses=4` bottleneck.
  - *Pathological Test Mocking*: Remediates unmocked socket probes in `test_k8s_bootstrap_success` (saving 78s), bounds workspace crawling in `test_repomap_cli` (saving 70s), and isolates git repository hashing in `test_ci.py` (saving 46s).
  - *Fine-Grained Gate Caching*: Implements input-addressed caching per quality gate (e.g. `actionlint` keyed to `.github/**`, `bandit`/`mypy` keyed to `src/**`), enabling instant sub-second verification for isolated docs, workflow, or dependency changes.
  - *Zero-Blocking Pipeline Dispatch*: Launches Pytest immediately at timestamp 0 without waiting for synchronous sequential docs validation passes.
- [x] **Review Findings Remediation, Defensive Boundary Hardening & Self-Improvement Feedback Loop (P0 - Critical, Issue #262, PR #263)**:
  - *Context & Rationale*: Remediates session findings across defensive boundaries (directory traversal containment, symlink rejection, pre-flight file size caps $\le 5\text{MB}$, None-safe severity handling, atomic serialized file exports).
  - *Anti-Hallucination & Evidence-Based Verification*: Hardens review verification prompts (`verify_finding_system.md`), persona instructions (`devsecops/prompt.md`), and common hallucination catalog (`common_hallucinations.json`) with rules distinguishing intentional internal infrastructure connectors (`allow_private_network=True`) from SSRF, CLI console path printing from information leaks, and scope-local AST symbol grounding before claiming `NameError`.
  - *Closed-Loop Feedback Replay*: Reconciles review findings in `.data/reviews/` and exports clean benchmark datasets (`devops review export-feedback --status ALL`) to `.data/feedback_dataset.jsonl` for continuous RAG retrieval and model distillation.
  - *AST Verification Oracle & Criteria Inversion Prevention*: Formalizes semantic alignment between verification and invalidation criteria, preventing verifiers from misinterpreting passing assertions or invalidation conditions as defect confirmations.

### Deep Cognitive Information Foraging, Syntopical Reading & Epistemic Research Engine (v0.2.21 - Scheduled)
- [x] **Multi-Scale Semantic Outline & Inspectional Scanner (`devops ai read --inspect`) (P0 - Critical)**:
  - *Context & Rationale*: Replaces naive monolithic file dumping with human-like inspectional reading and hierarchical perceptual scaffolding. Allows agents to navigate code and documentation across 3 discrete focal zoom levels:
    - **Level 0 (Topology)**: AST class/method hierarchies, exported symbols, docstring summaries, and cyclomatic hotspots without function bodies (< 200 tokens/file).
    - **Level 1 (Structural Outline)**: Function signatures, parameter types, return contracts, and control-flow sketches.
    - **Level 2 (Deep Focal Window)**: Line-bounded targeted code slices with surrounding breadcrumb context.
  - *Acceptance Criteria*: Sub-10ms AST outline generation; 85%+ token reduction compared to full-file ingestion; seamless integration with `Stage1PreAnalysis`.
- [ ] **Syntopical Dialectical Synthesis Engine (`devops ai research syntopical`) (P0 - Critical)**:
  - *Context & Rationale*: Implements Mortimer Adler's syntopical reading methodology for AI agents. Ingests heterogeneous sources on a complex topic (source code, PR review threads, git commit logs, markdown documentation, RFC specifications, and upstream issue discussions) to conduct comparative analysis.
  - *Lexicon Alignment & Dialectical Matrix*: Automatically reconciles divergent terminology across documents, identifies areas of consensus and contradiction, and outputs structured dialectical comparison matrices (`.data/research/syntopical_<topic>.json`).
  - *Acceptance Criteria*: Autonomous detection of conflicting statements across code and docs; structured JSON and Rich terminal output with source citations.
- [ ] **Agentic Information Foraging & Scent Tracker (`devops ai research forage`) (P0 - Critical)**:
  - *Context & Rationale*: Implements Pirolli & Card's Information Foraging Theory. Rather than executing disjointed keyword grep searches, the agent follows relational "information scent" across codebases and repositories.
  - *Breadcrumb Relational Crawler*: Traverses outbound cues from a starting anchor (error traceback, failing test, or feature keyword) across symbol imports, call hierarchies, git blame history, PR discussions, and markdown references.
  - *Heuristic Scent Scoring & Backtracking*: Scores edges based on semantic relevance to the inquiry; maintains an explicit traversal ledger that detects circular paths and systematically backtracks when an information trail grows cold.
- [ ] **Active Marginalia & Epistemic Scratchpad (`devops ai read annotate`) (P1 - High)**:
  - *Context & Rationale*: Emulates human active reading ("reading with a pencil"). Provides a persistent, file-anchored note and hypothesis tier (`.data/marginalia/<file_hash>.jsonl`).
  - *Structured Marginalia Schema*: Records typed annotations attached to file paths, AST nodes, or line ranges: `[ASSUMPTION]`, `[HYPOTHESIS]`, `[CONTRADICTION]`, `[QUESTION]`, `[TODO]`.
  - *Context Injection*: Automatically surfaces relevant prior marginalia into subsequent inspection passes, ensuring the agent remembers prior observations across turns and sessions without redundant re-reading.
- [ ] **Ground-Truth Source Triangulator & Provenance Auditor (`devops ai research verify-claim`) (P1 - High)**:
  - *Context & Rationale*: Implements epistemic hygiene by evaluating documentation claims, comments, and tutorials against authoritative ground-truth sources.
  - *Empirical Verification*: Tests claims against live AST call contracts, active configuration schemas (`config.yaml`), and sandboxed test execution outputs.
  - *Epistemic Confidence Scoring*: Classifies claims into *Empirically Verified* (concurs with primary code/runtime), *Documented Stale* (contradicted by code), or *Unverified Speculation* (hallucinated or unsubstantiated).
- [ ] **Socratic Inquiry & Knowledge Gap Formulator (`devops ai research socratic`) (P1 - High)**:
  - *Context & Rationale*: Emulates metacognitive awareness ("knowing what you don't know"). Proactively analyzes the agent's current state of knowledge for a task to identify gaps, ambiguities, and underspecified contracts.
  - *Minimal Diagnostic Probing*: Formulates concise, highly targeted clarifying questions or targeted code lookup instructions that eliminate maximum uncertainty with minimal token expenditure.
- [ ] **Cross-Domain Analogical Pattern Retriever (`devops ai research analogies`) (P1 - High)**:
  - *Context & Rationale*: Facilitates creative problem solving and lateral thinking by detecting structural pattern isomorphisms across disparate software modules and IT domains in the DevOps CLI Knowledge Base.
  - *Analogical Matching*: Uses multi-vector topological clustering to surface cross-domain analogies (e.g. comparing network backoff to retry loops in K8s reconcilers, or database write-ahead logs to event-sourcing pipelines).
- [ ] **Living Mental Model Synthesizer & Causal Graph Distiller (`devops ai research model`) (P1 - High)**:
  - *Context & Rationale*: Progressively compacts sprawling research observations into a concise, living mental model (`.data/research/mental_model_<topic>.yaml`).
  - *Causal & State Machine Modeling*: Distills raw text findings into explicit state transitions, causal DAGs, and invariant rules that serve as working theories during complex refactorings and defect investigations.
- [ ] **FastMCP Cognitive Research Tools & Epistemic System Resources (P1 - High)**:
  - *Context & Rationale*: Exposes native FastMCP tools (`ai_read_inspect`, `ai_research_syntopical`, `ai_research_forage`, `ai_read_annotate`, `ai_verify_claim`, `ai_research_socratic`, `ai_research_model`) and dynamic system resources (`resource://ai/research/marginalia`, `resource://ai/research/mental_model`) enabling IDE coding assistants to perform human-like research interactively.

### Iterative Agentic GitHub Project Manager & Autonomous Backlog Orchestration (v0.2.22 - Scheduled)
- [ ] **Multi-Repository Fleet Coordination & Portfolio Management (`devops gh pm fleet`) (P0 - Critical)**:
  - *Context & Rationale*: Connects across an arbitrary fleet or list of repositories (`--repos-file`, `--repos-dir`, or configured in `config.yaml`) to coordinate multi-repo project portfolios under a unified GitHub Projects v2 board.
  - *Cross-Repo Dependency Graphs*: Tracks dependencies across repositories (e.g. backend API issue in repo A blocking frontend feature in repo B), ensuring synchronized release staging.
  - *Federated Milestones & Label Alignment*: Reconciles taxonomy labels and milestone cadences across all fleet repositories simultaneously.
- [ ] **Background Project Watcher Daemon & Event Streamer (`devops gh pm daemon`, `devops gh pm watch`) (P0 - Critical)**:
  - *Context & Rationale*: Persistent, non-blocking background daemon that continuously monitors GitHub Projects v2 boards, pull requests, and issues across the repository fleet via webhooks or bounded polling with proactive rate-limit pacing (`GitHubRateLimiter`).
  - *Autonomous Event Loop*: Reactively processes issue creation, PR lifecycle events, reviewer assignments, and CI status updates without requiring manual CLI invocations.
  - *Stateful Event Journal*: Maintains an append-only event log (`.data/pm/events.jsonl`) to guarantee idempotent, zero-duplicate state transitions.
- [ ] **Cognitive Feature Research & Roadmap Prioritization Engine (`devops gh pm research`) (P0 - Critical)**:
  - *Context & Rationale*: Autonomous strategic product manager engine that continuously investigates, analyzes, and prioritizes new feature opportunities for the roadmap.
  - *Multi-Signal Synthesis*: Ingests user feedback, issue triage trends, recurring review findings, and competitive open-source ecosystem developments.
  - *Value vs. Effort Scoring & Matrix Maintenance*: Evaluates candidate features against a structured Value vs. Effort scoring rubric (quantifying business impact, user friction, token budget, and architectural complexity) and iteratively updates `docs/ROADMAP.md` proposals.
- [ ] **In-Flight Work, PR Stagnation & Blocker Radar (`devops gh pm inflight`) (P1 - High)**:
  - *Context & Rationale*: Continuous surveillance of active in-flight work across the repository fleet to eliminate PR starvation, review stagnation, and merge conflict decay.
  - *FIFO PR Queue Surveillance*: Enforces strict chronological (oldest to newest / FIFO) PR processing and surfaces older open PRs that are being starved or blocked by newer work.
  - *Stagnation & Bottleneck Detection*: Flags PRs with unresolved Copilot/peer review threads, failing CI checks, or unassigned reviewers exceeding configurable latency thresholds (e.g. >24h); emits actionable remediation nudges.
- [ ] **Autonomous Epic Decomposition & Backlog Synthesizer (`devops gh pm plan`) (P0 - Critical)**:
  - *Context & Rationale*: Takes high-level features, PR review findings, or architectural roadmaps and autonomously decomposes them into atomic, executable GitHub Issues.
  - *Automated Story Sizing & Acceptance Contracts*: Generates user stories with standardized Gherkin/Markdown acceptance criteria, domain scopes, test specifications, and effort estimation (T-shirt / Fibonacci sizing).
  - *Declarative Taxonomy Enrichment*: Automatically attaches standardized taxonomy labels matching `.github/labels.yml` (`type/*`, `scope/*`, `priority/*`) and maps issues to active release milestones.
  - *Duplicate & Overlap Detection*: Vector-similarity pre-check against existing issues and backlog items to prevent duplicate tickets.
- [ ] **Continuous State Machine Reconciler & Card Daemon (`devops gh pm reconcile`) (P0 - Critical)**:
  - *Context & Rationale*: Autonomous background reconciler (or event-driven webhook listener) synchronizing real-world git, PR, and CI events with GitHub Projects v2 board columns across 5 standardized lifecycle states (`Backlog`, `Ready`, `In Progress`, `In Review`, `Done`).
  - *Automated State Transitions*: Detects branch checkout $\to$ `In Progress`, PR creation $\to$ `In Review`, CI failures $\to$ `status/blocked` label with diagnostic comments, and PR squash-merge $\to$ `Done` with issue closure and milestone burn-up updates.
  - *Two-Way File Synchronization*: Keeps local per-task tracking files (`docs/agent/tasks/task-<issue>-<slug>.md`) and project board fields 100% in sync without merge conflicts.
- [ ] **DAG Dependency Engine & Critical Path Unblocker (`devops gh pm deps`) (P0 - Critical)**:
  - *Context & Rationale*: Models issue dependencies (`blocked-by #123`, `depends-on #456`) as a topological Directed Acyclic Graph (DAG).
  - *Critical Path Computation*: Identifies the critical path through milestone deliverables, calculating dependency depth and bottleneck issues.
  - *Autonomous Unblock Trigger*: When a blocking issue/PR is merged, immediately promotes downstream dependent cards from `Blocked` to `Ready` and notifies available subagents.
- [ ] **WIP Limit Governor & Workload Dispatcher (P1 - High)**:
  - *Context & Rationale*: Enforces Kanban Work-In-Progress (WIP) caps per developer or subagent constellation to prevent context thrashing, unbounded parallel branches, and stale review queues.
  - *Pull-Based Dispatching*: Prevents new cards from being pulled into `In Progress` until existing `In Review` items are reviewed, remediated, or merged.
  - *Token Quota Budgeting*: Allocates token budgets dynamically across active cards based on issue priority and estimated effort.
- [ ] **Agentic Sprint Cadence & Velocity Engine (`devops gh pm sprint`) (P1 - High)**:
  - *Context & Rationale*: Orchestrates sprint and release milestone cadences. Automates milestone creation, deadline monitoring, sprint rollover, and scope change management.
  - *Predictive Burndown & Velocity Analytics*: Analyzes historical issue throughput, cycle time, and review turnaround latency to forecast release completion dates and detect sprint drift early.
- [ ] **Automated Triage & Sandbox Repro Validator (`devops gh pm triage`) (P1 - High)**:
  - *Context & Rationale*: Monitors newly created issues, bug reports, and CI failures.
  - *Intelligent Classification*: Evaluates issue descriptions with PydanticAI to categorize priority (`priority/p0-critical` through `priority/p3-low`), component scope, and security sensitivity.
  - *Automated Repro Validator*: Ingests issue reproduction steps, provisions an isolated sandbox (`devops sandbox deploy`), and verifies whether the defect is reproducible before assigning to developers.
- [ ] **Standup & Executive Velocity Reporter (`devops gh pm report`) (P1 - High)**:
  - *Context & Rationale*: Generates high-density executive progress summaries, daily standup digests, and sprint retrospective reports in Markdown and Slack/terminal formats.
  - *Metrics Triad*: Reports velocity deltas, open blocker heatmaps, PR review latency, and milestone completion percentages with zero manual tracking overhead.
- [ ] **FastMCP Agentic Project Management Tools & Epistemic Resources (P1 - High)**:
  - *Context & Rationale*: Exposes native FastMCP tools (`gh_pm_fleet`, `gh_pm_daemon`, `gh_pm_research`, `gh_pm_inflight`, `gh_pm_plan`, `gh_pm_reconcile`, `gh_pm_deps`, `gh_pm_triage`, `gh_pm_sprint`, `gh_pm_report`) and dynamic system resources (`resource://gh/pm/kanban`, `resource://gh/pm/velocity`, `resource://gh/pm/critical-path`, `resource://gh/pm/fleet`, `resource://gh/pm/inflight`) enabling IDE-hosted AI coding assistants to manage projects, unblock dependencies, and transition cards autonomously.
- [ ] **GitHub Models Zero-Setup Inference Provider (`devops ai models github`) (P0 - Critical)**:
  - *Context & Rationale*: Ingests and routes inference through the GitHub Models catalog (`models.inference.ai.azure.com`), utilizing developer `GITHUB_TOKEN` or Copilot enterprise credentials. Eliminates the friction of configuring separate third-party API keys or maintaining local GPU infrastructure for CI runners and cloud workstations.
  - *Virtual Model Tiering*: Maps GitHub Models endpoints directly to DevOps CLI model tiers: `devops-reasoning` -> `o3-mini` / `DeepSeek-R1`, `devops-coder` -> `gpt-4o` / `claude-3.5-sonnet`, `devops-chat` -> `gpt-4o-mini`.
  - *Token Rate & Quota Limiter*: Integrates client-side rate limit tracking and token-bucket pacing aligned with GitHub Models service tiers, with automatic fallback failover to local Ollama or OpenAI endpoints.
- [ ] **Autonomous GitHub Actions Self-Healing & PR Triage Workflows (`devops-action`) (P0 - Critical)**:
  - *Context & Rationale*: Reusable, autonomous GitHub Actions workflows executing closed-loop diagnosis and self-healing across pull requests and issues.
  - *Autonomous Issue Triage Action*: Reacts on `issues: opened`, parses reproduction steps, provisions an isolated container sandbox (`devops sandbox deploy`), executes reproduction attempts with `devops ai explore`, and labels the issue with verified diagnostic logs.
  - *CI Gate Auto-Remediation Action*: Reacts on `workflow_run: failure`, downloads failing step logs, isolates failing unit test or lint assertions, invokes `devops ai patch-minimize` to formulate an atomic fix, validates all 10 local CI quality checks, and commits a remediation patch directly to the PR branch.
- [ ] **GitHub Copilot Extension & Web Agent (`@devops-cli` on GitHub.com) (P1 - High)**:
  - *Context & Rationale*: Exposes `devops-cli` as a first-class GitHub Copilot Extension / GitHub App on the GitHub Marketplace.
  - *Web Chat Participant*: Allows engineering teams to invoke `@devops-cli` directly inside GitHub.com web PRs, Issues, and Discussions: `@devops-cli /review` (runs multi-persona code review and posts consolidated findings), `@devops-cli /k8s` (returns sanitized cluster deployment health), and `@devops-cli /explain` (diagnoses failing CI logs and security scanner CVEs with suggested patches).
  - *Zero-Egress Security*: Runs in isolated, containerized workers with OS Keyring token authorization and SSRF-defended egress boundaries.

### Reactive Workstation Command Center, Interactive TUI & Unified Operations Hub (v0.2.23 - Scheduled)
- [ ] **Reactive Multi-Workspace Textual TUI Architecture & Master-Detail Navigation (`devops dashboard`, `devops tui`) (P0 - Critical)**:
  - *Context & Rationale*: Modernizes the basic Textual dashboard from static read-only tables into a reactive, multi-workspace workstation command center with non-blocking async workers (`work()`), real-time push events, and master-detail ergonomic split screens (navigation tree/list on left, contextual detail inspector with YAML/logs/markdown on right).
  - *Unified Workspaces*: Seamlessly tabs between 7 domain workspaces: (1) `PR & Git Lifecycle`, (2) `K8s & Minikube`, (3) `Docker & Sandboxes`, (4) `SecOps & Vault`, (5) `GitOps & ArgoCD`, (6) `AI Constellation & Memory`, and (7) `Telemetry & Loki Logs`.
  - *Stateful Navigation*: Preserves active table selections, scroll positions, and filter queries across tab switches with URL-like hash routing.
- [ ] **Interactive GitHub Lifecycle, PR Monitor & Projects v2 Kanban Hub (`tab-github`) (P0 - Critical)**:
  - *Context & Rationale*: Embeds full GitHub engineering workflow visibility directly inside the terminal.
  - *Chronological FIFO PR Queue*: Live pull request queue prioritized from oldest to newest with status badges (CI check conclusion, Copilot review settling indicator, unresolved review threads counter). Selecting a PR opens an inspector pane with commit diff summary and failing check logs.
  - *Interactive Actions*: Instant keybinding triggers to run readiness checks (`p` -> `devops pr check-readiness`), view failing run logs (`v` -> `devops gh runs view`), or open PR in browser (`o`).
  - *Projects v2 Mini-Kanban*: Responsive columnar view showing active milestone issues across `Backlog`, `Ready`, `In Progress`, `In Review`, and `Done` with taxonomy labels.
  - *API Quota Gauge*: Live visual token-bucket meter displaying remaining GitHub REST/GraphQL rate limits and reset countdown (`devops gh rate-limit`).
- [ ] **Cloud-Native Cluster Runtime, Pod Inspector & Live Log Streamer (`tab-k8s`) (P0 - Critical)**:
  - *Context & Rationale*: Transforms the primitive 10-pod table into a live, interactive Kubernetes console.
  - *Multi-Namespace Filtering*: Namespace selector dropdown, search query bar (`/`), and status filters (`Running`, `Pending`, `CrashLoopBackOff`, `Failed`).
  - *Integrated Log Streamer Drawer*: Embedded `RichLog` drawer streaming live container logs with auto-scroll and follow mode (`l`), backed by non-blocking Stern/Kubernetes log tailing.
  - *Cluster Health & Minikube Overview*: Node resource allocation (CPU/Memory gauges), Minikube GPU status badge (`Active` / `Fallback`), and service ingress URL table (`devops k8s configure-urls`).
  - *Port-Forward Daemon Manager*: Real-time list of active background port forwards (`devops k8s port-forward --status`) with one-key start and terminate controls.
  - *Interactive Pod Actions*: Restart pod (`r`), stream logs (`l`), view manifest YAML (`y`), or inspect pod events (`e`).
- [ ] **Docker Containers & Multi-Tier Workload Sandbox Console (`tab-docker`) (P1 - High)**:
  - *Context & Rationale*: Comprehensive workstation container and sandbox observability hub.
  - *Multi-Tier Sandbox Inspector*: Dedicated view of running Docker and Kubernetes sandboxes (`devops sandbox status`) showing active network modes (`isolated`, `sandbox_namespace`, `public_whitelist`, `local_whitelist`), cgroup resource limits, and health probe states.
  - *Container Performance Metrics*: Live CPU %, memory RSS vs limit, block I/O, and network throughput sparklines.
  - *Interactive Sandbox Controls*: Terminate sandbox (`k`), stream sandbox diagnostic logs (`l`), trigger dynamic health probe (`p`), or prune dangling volumes and images.
- [ ] **Unified SecOps, Compliance & HashiCorp Vault Command Center (`tab-secops`) (P1 - High)**:
  - *Context & Rationale*: Consolidates all static and dynamic security scanners into an actionable vulnerability triage center.
  - *Scanner Severity Dashboard*: Aggregated threat summary cards (Trivy CVEs by severity, Gitleaks detected secrets, Semgrep SAST alerts, Checkov IaC failed checks). Selecting an alert displays CVE details, affected line numbers, CVSS scores, and remediation hints.
  - *Automated Remediation Queue*: Highlights vulnerabilities resolvable via `devops scan fix` with one-key preview of auto-remediation patches.
  - *HashiCorp Vault Secret Broker Status*: Visual broker health indicator, seal state, token lease TTL progress bar, and OS Keyring synchronization status (`devops vault status`).
- [ ] **GitOps Fleet, ArgoCD Rollouts & Cloud Cost Monitor (`tab-gitops`) (P1 - High)**:
  - *Context & Rationale*: Brings continuous deployment and cloud infrastructure FinOps into situational awareness.
  - *ArgoCD Application Fleet*: Tree view of deployed GitOps applications showing sync status (`Synced`, `OutOfSync`) and health status (`Healthy`, `Progressing`, `Degraded`). One-key app synchronization trigger (`s` -> `devops argo cd apps sync`).
  - *Argo Rollout Canary Visualizer*: Live step-by-step rollout progression with canary traffic weight and automated metric analysis results.
  - *IaC Drift & Infracost Spend Tracker*: OpenTofu workspace state overview, drift status badge, and monthly cloud cost forecast summary (`devops tf cost`).
- [ ] **AI Constellation Topology, RAG Health & Review Findings Studio (`tab-ai`) (P1 - High)**:
  - *Context & Rationale*: Deep inspection of local and distributed AI inference tiers and knowledge bases.
  - *Ollama Constellation Topology*: Node health matrix, active model weights, GPU VRAM allocation gauges, and failover circuit breaker status.
  - *RAG Vector Tier Health*: Qdrant collection size, indexed document count, semantic drift score, and Valkey L2 embedding cache hit ratio sparkline.
  - *Review Findings Studio*: Interactive hierarchical tree of AI code review findings with severity badges, collapsible rationale scratchpads, file diff snippet previews, and one-key finding status transitions (`MITIGATED`, `INVALIDATED`).
- [ ] **Centralized Loki LogQL Streamer, Prometheus Sparklines & Trace Waterfalls (`tab-telemetry`) (P1 - High)**:
  - *Context & Rationale*: Unifies the complete observability triad directly within the terminal UI.
  - *Loki Centralized LogQL Query Console*: Embedded LogQL query input bar with syntax highlighting and live streaming log console, querying cluster-wide Fluent Bit / Loki logs without leaving the TUI.
  - *Prometheus Performance Sparklines*: Terminal ASCII sparklines and gauges rendering real-time command execution latencies, LLM token throughput (tokens/sec), and cache hit ratios.
  - *Trace Waterfall Modal*: Visual breakdown of recent OpenTelemetry distributed traces and multi-persona review spans with service latency waterfalls.
- [ ] **Comprehensive DevOps CLI Grafana Observability Dashboard Suite & GitOps Provisioner (`devops grafana dashboards sync`) (P0 - Critical)**:
  - *Context & Rationale*: While the Textual TUI provides immediate interactive terminal visibility, long-term trend analysis, multi-workstation telemetry aggregation, and cluster-wide observability require enterprise-grade Grafana dashboards backed by Prometheus, Loki, and Tempo/Jaeger.
  - *Unified Observability Dashboard Portfolio*:
    - **DevOps Workstation CLI & Agent Telemetry (`dashboards/devops-cli.json`)**: Subcommand invocation frequency, p50/p95/p99 execution latency histograms, exit code distributions, subagent task durations, and OpenTelemetry span waterfalls.
    - **AI Constellation & Priority Slot Leasing (`dashboards/ai-constellation.json`)**: Multi-node Ollama slot leasing concurrency, active leases vs. parallel limits, token generation throughput (tokens/sec), time-to-first-token (TTFT), vector cache hit ratios, and priority queue lengths (`high`, `normal`, `as_available`).
    - **Multi-Persona Code Review & Findings Quality (`dashboards/ai-review.json`)**: Review volume segmented by classification context (`documentation`, `configuration`, `code`), persona finding distributions (`devsecops`, `architect`, `qa`, `pm`, `auditor`), severity heatmaps, finding mitigation latency, and false-positive invalidation rates.
    - **GitHub Projects v2, PR Queue & API Quota (`dashboards/github-agentic.json`)**: FIFO pull request queue depth, PR readiness turnaround, Copilot review settling latency, and real-time REST/GraphQL token-bucket consumption gauges.
    - **Centralized Logging & Incident Triage (`dashboards/loki-incident-triage.json`)**: Loki LogQL error stream panels, trace-to-log correlation via trace ID exemplars, and SIEM audit logs.
  - *Automated K8s Sidecar & ConfigMap GitOps Provisioning*: Packages bundled dashboards into Kubernetes ConfigMaps labeled with `grafana_dashboard: "1"`, enabling automatic, zero-restart discovery and live reloads via the Grafana dashboard sidecar (`k8s/monitoring/prometheus-values.yaml`).
  - *Declarative Dashboard Linter & Exporter (`devops grafana dashboards validate`) (P1 - High)*: Automated schema validator and exporter verifying Grafana 10+ panel schema compliance, datasource parameterization (`${DS_PROMETHEUS}`, `${DS_LOKI}`), and uid idempotency across all committed dashboard definitions.
- [ ] **Universal Terminal Command Palette & Fuzzy Action Launcher (P1 - High)**:
  - *Context & Rationale*: High-velocity keyboard workflow allowing developers to execute any DevOps CLI command without exiting the TUI.
  - *Modal Launcher (`Ctrl+P` / `:`)*: Fast fuzzy-search command palette listing all CLI subcommands (`ci run`, `scan trivy`, `release status`, `argo sync`, `vault sync`, `sandbox iterate`).
  - *Non-Blocking Command Output Drawer*: Executes commands in a non-blocking background thread, streaming output directly into an ephemeral sliding terminal drawer.
- [ ] **FastMCP TUI Management Tools & Dynamic Dashboard Resources (P2 - Medium)**:
  - *Context & Rationale*: Exposes FastMCP tools (`dashboard_launch`, `dashboard_status`, `dashboard_switch_tab`) and dynamic system resources (`resource://dashboard/status`, `resource://dashboard/k8s`, `resource://dashboard/github`, `resource://dashboard/secops`) enabling AI assistants to query dashboard state, monitor workstation telemetry, and trigger UI focus programmatically.

### Architectural Alignment & Vibes Showcase Porting (v0.2.24 - Scheduled)
- [ ] **POSIX Process Group Sandbox Enforcement (P0 - Critical)**:
  - *Context & Rationale*: Unbounded `subprocess.Popen` invocations in `k8s/networking.py`, `ai/gateway.py`, and `sandbox/metrics.py` currently lack `start_new_session=True`, risking zombie process leaks if the CLI terminates unexpectedly (violating vibes Obs 05).
  - *Implementation*: Refactor all background subprocess dispatchers to enforce POSIX process group containment and ensure clean termination via `os.killpg`.
- [ ] **Structural Pre-Commit Hook Inversion (P0 - Critical)**:
  - *Context & Rationale*: `devops-cli` relies on a monolithic `devops ci` pre-commit hook that omits the AST invariant sentinel (complexity/depth gates) and documentation structural validation, violating the mechanical enforcement mandate (vibes Systems Obs 08).
  - *Implementation*: Port the standalone `ast-invariant-sentinel.py` and `docs_validator.py` from the `vibes` repository into `devops-cli`. Wire them natively into `.pre-commit-config.yaml` as fast, independent `<200ms` quality gates preventing non-compliant commits locally.
- [ ] **Anti-Brittle Constant Elimination (P1 - High)**:
  - *Context & Rationale*: `src/devops_cli/config/constants.py` contains hardcoded prefix matchers (e.g., `CONST_BRANCH_PREFIXES`) which are open-domain sets. This induces heuristic brittleness (vibes Obs 06).
  - *Implementation*: Eliminate arbitrary string list subsets. Replace branch parsing and config prefix matching with structural git invariants or explicit functional routing logic.
- [ ] **Semantic Validator Deprecation & Structural Positional Oracles (P1 - High)**:
  - *Context & Rationale*: Ensure internal `devops-cli` AI review schemas and validators use structural/positional enumeration rather than semantic keyword matching (vibes Obs 17).
  - *Implementation*: Audit `ai/analyze/outlines.py` and `ai/review_schema.py` to strip out keyword assertions and enforce strict structural schema boundaries.
- [ ] **Lazy Domain-Gated MCP Tool Schema Hydration (P0 - Critical)**:
  - *Context & Rationale*: `devops-cli` exposes 100+ FastMCP tools. At ~80 tokens per schema, eager hydration consumes ~8,000 tokens (25% of a 32K window) before any task reasoning begins. Above ~40 tools, models exhibit selection precision collapse — vacillating between semantically adjacent tools like `scan_trivy` vs `scan_semgrep` (vibes Obs 18). The `SkillSlot` cap of 20 (`slots.py:150`) correctly bounds skills but leaves the tool surface unbounded.
  - *Implementation*: Partition tools into a core eager set (~15 high-frequency tools: `view_file`, `grep_search`, `run_command`, etc.) and lazy domain sets (`k8s_*`, `scan_*`, `gh_*`, `tf_*`, `docker_*`, `vault_*`) hydrated on-demand when the agent's reasoning trajectory enters that namespace. Inject namespace disambiguation preambles for same-prefix tool families. Apply schema compression (strip descriptions, keep skeleton) after the model's first exposure.
- [ ] **Pipeline Stage Context Budgeting & Invariant Pinning (P0 - Critical)**:
  - *Context & Rationale*: The sequential `MultiAgentPipeline` (`pipeline.py:196-199`) accumulates context linearly without truncation — a 5-stage pipeline generates ~20K tokens of bloat. `AgentMemory` auto-summarization at 96K chars (`memory.py:26-28`) is lossy, discarding verbatim invariant constraint wording. System instructions (AGENTS.md rules, complexity caps) are progressively evicted from model attention as tool outputs and conversation history accumulate (vibes Obs 19).
  - *Implementation*: Apply `ContextPacker` binary search truncation to inter-stage pipeline context with per-stage budgets (~4K tokens). Partition `AgentMemory` into a volatile conversation buffer (subject to auto-summarization) and an invariant constraint store (never summarized, re-injected verbatim at head of each turn). Inject a compressed invariant reminder block every N turns.
- [ ] **Lossless Structured Error Reflection for Schema Retries (P1 - High)**:
  - *Context & Rationale*: `structured.py` truncates Pydantic validation errors to 256 characters (`CONST_MAX_ERROR_DETAIL_LENGTH`), cutting off field locators and type mismatch descriptions. This forces multi-turn retry loops instead of single-turn correction. Complex nested validation errors (e.g. a list of invalid items with field paths) are unrecoverable with truncated feedback (vibes Obs 19).
  - *Implementation*: Replace the 256-char truncation with a structured error summary preserving up to 5 field paths with type violations and prescriptive fix hints. Budget ~400 chars for structured errors to achieve single-turn convergence on nested schema failures.
- [ ] **Capability-Gated Model Failover & AIMD Batch Recovery (P0 - Critical)**:
  - *Context & Rationale*: The gateway failover cascade (`gateway.py:67-73`) routes `devops-reasoning` (70B) to `devops-coder` (14B) — a capability cliff, not a graceful degradation. A 32K reasoning task that succeeds at 70B produces categorically different failure modes at 14B (hallucinated tool params, broken JSON syntax). The embedding engine's batch adaptation (`embeddings.py:266-279`) only halves batch size on latency spikes but never recovers — a single transient spike permanently collapses throughput 32× (vibes Obs 20).
  - *Implementation*: Classify task minimum capability requirements (reasoning $\ge$ 30B, coding $\ge$ 7B, chat = any). Reject failover to tiers below the task's minimum, returning an explicit error instead of silent degradation. Replace the one-way embedding batch ratchet with AIMD (Additive Increase / Multiplicative Decrease): halve on spike, increment by 1 on sustained low latency, with cooldown windows between recovery attempts.
- [ ] **Background Shell Pipe Deadlock Fix & Output Contract (P1 - High)**:
  - *Context & Rationale*: `shell.py:188-211` spawns background commands with `stdout=subprocess.PIPE, stderr=subprocess.PIPE` but `check_command` only calls `proc.poll()` — pipes are never drained. Any background subprocess producing $> 64$KB output (the OS pipe buffer) deadlocks indefinitely. The output contract ("Report status and accumulated output") silently breaks (vibes Systems Obs 09).
  - *Implementation*: Add daemon reader threads that drain `stdout`/`stderr` into bounded ring buffers (`collections.deque(maxlen=1000)` lines). Wire `check_command` to return actual accumulated output. Add a maximum output cap to prevent memory exhaustion on verbose commands.
- [ ] **Structured Constraint Propagation Across Subagent Delegation (P1 - High)**:
  - *Context & Rationale*: Each agent delegation boundary loses ~15% constraint fidelity through prompt decomposition. Three layers of delegation retain only $0.85^3 \approx 61\%$ of the original intent. `SubAgents.delegate_task` (`workflow.py:262-365`) constructs child prompts from flat text without structured constraint annotations. The `execute_tiered` protocol (`slots.py:775-831`) is structurally correct but executes stubs — fabricating tier responses via string templates without contacting model APIs (vibes Systems Obs 09).
  - *Implementation*: Annotate delegation prompts with typed constraint blocks (`invariants`, `budget`, `security`) that must propagate verbatim to all descendants. Replace free-text subagent results with `SubagentResult` schemas containing `status`, `warnings`, `constraints_verified`, and `constraints_violated`. Implement real LLM calls in `execute_tiered` to validate the delegation hierarchy under production workloads.
- [ ] **MCP Resource-First Data Access & Tool Output Sandboxing (P1 - High)**:
  - *Context & Rationale*: MCP Resources (`resource://`) provide URI-addressable, cacheable, subscription-capable data endpoints — 3× cheaper than Tool calls for read-heavy patterns. Yet the `devops-cli` MCP server relies almost exclusively on Tools for all data access. Additionally, MCP tool return strings are untyped — an attacker controlling tool output (via compromised repos, malicious web content, or poisoned dependencies) can inject instructions interpreted as system directives (vibes Systems Obs 10).
  - *Implementation*: Convert read-heavy, stable-state inspection endpoints (`k8s_status`, `argo_status`, `docker_stats`, `vault_status`, `telemetry_status`, `gh_rate_limit`) from Tools to MCP Resources with URI subscriptions. Apply sanitization pipeline to all tool return strings — strip potential instruction injections, validate against expected output schemas, and cap output length.

### GitHub Copilot & VS Code Agentic Ecosystem, Language Model Tools & IDE Companion (v0.2.25 - Scheduled)
- [ ] **Native VS Code Language Model Tools API Provider (`vscode.lm.tools`) (P0 - Critical)**:
  - *Context & Rationale*: Exposes DevOps CLI's core inspection, AST outline, complexity analysis, and cluster querying tools as native VS Code Language Model Tools via the `vscode.lm.tools` API contribution point. Enables any VS Code agent or chat participant (e.g. `@workspace`, Copilot Agent mode) to invoke DevOps CLI tools seamlessly without spawning external subshells or parsing plaintext console output.
  - *Implementation*: Implement native language model tool definitions (`devops_inspect_symbol`, `devops_scan_complexity`, `devops_k8s_pods`, `devops_pr_status`, `devops_secops_summary`) returning typed JSON schemas and structured Markdown results.
- [ ] **VS Code Copilot Chat Custom Participant (`@devops`) & Slash Command Suite (P0 - Critical)**:
  - *Context & Rationale*: Embeds a dedicated `@devops` chat participant directly in the VS Code Copilot Chat panel, providing developers with immediate workstation and cluster operations without context switching to external terminals or web consoles.
  - *Implementation*: Support specialized slash commands: `@devops /review` (multi-persona code review on active editor or staged diff), `@devops /explore` (MCTS solution exploration for active test failures), `@devops /k8s` (pod inspection and live log tailing), `@devops /secops` (vulnerability triage and fix suggestions), and `@devops /tui` (launches or focuses the Textual TUI in an integrated terminal). Provide interactive chat response controls ("Open Diff", "Apply Patch", "View Loki Logs").
- [ ] **Multi-Document Proposed Edits & Native Side-by-Side Diff Integration (P1 - High)**:
  - *Context & Rationale*: Bridges CLI solution synthesis (`devops ai patch-minimize`, `devops ai explore`) with VS Code's native `LanguageModelProposedEdit` API, replacing terminal unified diff dumps with interactive, side-by-side graphical diff reviews.
  - *Implementation*: Stream multi-file modifications directly into VS Code's native diff review editor with per-hunk "Accept / Reject" controls, syntax highlighting, and immediate post-edit syntax validation before persisting changes to disk.
- [ ] **Automated Multi-IDE MCP Scaffolder & Health Watchdog (`devops ide configure`) (P1 - High)**:
  - *Context & Rationale*: Developers frequently switch across modern AI-assisted IDEs (VS Code, Cursor, Windsurf, Claude Desktop, Antigravity). Manually managing `.vscode/mcp.json` or global config paths across IDE updates and container rebuilds is prone to path mismatch and environment drift.
  - *Implementation*: Provide a unified `devops ide configure [--ide vscode|cursor|windsurf|claude|all]` command that auto-detects installed IDE configurations and writes standardized, hardened MCP server entries. Include a background watchdog detecting hanging stdio subshells and automatically restarting the FastMCP server when deadlocks or high-memory leaks occur.
- [ ] **Path-Specific Copilot Instructions & Executable Prompt Scaffolder (`devops ai instructions scaffold`) (P1 - High)**:
  - *Context & Rationale*: Modern GitHub Copilot and VS Code Agent mode support hierarchical path-specific instructions (`.github/instructions/**/*.md`) and executable prompt templates (`.github/prompts/*.prompt.md`). Monolithic instruction files (`AGENTS.md`) can overwhelm model attention with irrelevant rules when editing specialized subtrees.
  - *Implementation*: Generate scoped instruction files matching file globs (e.g. `.github/instructions/k8s.md` for Kubernetes manifests, `.github/instructions/tests.md` for structural tuple assertions and complexity caps, `.github/instructions/security.md` for zero-trust egress and POSIX isolation). Provide pre-packaged prompt templates: `.github/prompts/k8s-triage.prompt.md`, `.github/prompts/pr-review.prompt.md`, `.github/prompts/adr-generate.prompt.md`.
- [ ] **DevOps CLI VS Code Companion Extension (`devops-vscode`) (P1 - High)**:
  - *Context & Rationale*: A lightweight, open-source companion VS Code extension packaging all VS Code agentic integrations, status bar indicators, and editor gutter annotations into a turnkey developer experience.
  - *Implementation*: Status bar items displaying active K8s cluster context/namespace, active PR readiness status, rate limit meter, and Ollama server health. Gutter decorations highlighting code review findings (`CRITICAL`, `HIGH`, `MEDIUM`) with inline quick fixes ("Mitigate Finding", "Mark Invalid", "Explain Rationale"). Webview canvas hosting the reactive Textual TUI inside an editor tab.

### Multi-Cloud Mesh & Production Ecosystem (v0.3.0 - Future Vision)
- [ ] **Multi-Region Workstation Mesh & Cluster Federation**: Distributed cluster management across hybrid on-premise and multi-cloud Kubernetes clusters with automatic service mesh routing.
- [ ] **Autonomous Self-Healing Agent Pipeline**: Closed-loop diagnostic engine capable of discovering cluster incidents, generating corrective patches, running CI gates, and executing rollback.
- [ ] **Cloud-Native Ephemeral Test Environment Provisioner (`devops env ephemeral up/down`)**: Automated provisioning of isolated namespace staging environments with seeded mock databases, synthetic datasets, and TLS ingresses on minikube or cloud clusters.
- [ ] **Zero-Trust Git Commit & Tag Cryptographic Verification (`devops release verify-signatures`)**: Automated verification of SSH/GPG and Sigstore keyless commit signatures across repository history and pull requests.
- [ ] **Distributed Multi-Cluster Telemetry & OTel Egress Mesh**: Global trace and metric federation across hybrid workstation topologies with automated anomaly alerting.
- [ ] **Distributed Cache & Shared Semantic Embeddings Sync (`devops ai cache sync`)**: S3 / OCI-backed shared LLM response and vector embedding cache for remote engineering teams.
- [ ] **JIT Python 3.14 Tail-Call & Bytecode Optimization Benchmarking**: Comprehensive runtime benchmarks utilizing Python 3.14+ specialization and JIT compiler tiers.
- [ ] **Universal `--json` CLI Output Flag Alias Pipeline (`devops * --json`)**: First-class `--json` alias for `--format json` across all inspection and diagnostic subcommands.
- [ ] **Mutation-Driven GitHub Cache Invalidation Hooks**: Automatic invalidation of cached GitHub REST and GraphQL responses on edit, patch, and reconcile operations.
- [ ] **Proportional API Rate Budgeting & GraphQL Circuit Breaker Guard**: Proportional budget allocation per CLI command and automated circuit breaking when external API quota drops below 20%, preventing rapid quota exhaustion.
- [ ] **Native Process Hierarchy Inspector & POSIX Process Group Terminator (`devops ps`)**: Active inspection and cleanup of orphaned background subprocesses and container workers via POSIX process groups (`os.killpg`), eliminating zombie leaks adopted by PID 1 (derived from empirical shell history telemetry).
- [ ] **Automated Pre-Rebase Merge Conflict Dry-Runner (`devops pr check-readiness --dry-rebase`)**: In-memory git three-way tree merge analysis (`git merge-tree`) to proactively detect conflicting hunks before initiating PR rebases or merges.
- [ ] **Ephemeral Sandboxed Evaluation Harness (`devops scratch eval`)**: Secure, isolated in-memory Python runtime evaluator replacing repetitive one-line ad-hoc terminal probing with structured telemetry and complexity enforcement.
- [ ] **IDE Host Health & Submodule Scan Boundary Auditor (`devops ide audit`)**: Automated diagnostic inspection of Antigravity/VS Code server extensions, language servers, and repository ignore boundaries (`git.repositoryScanIgnoredFolders`) to prevent memory exhaustion in deep monorepo workspaces.

---

## Value vs. Effort Prioritization Matrix

> [!NOTE]
> This matrix prioritizes forward-looking, active, scheduled, and future roadmap deliverables across Value and Effort dimensions. Completed items are recorded in milestone history and release changelogs, keeping this prioritization backlog strictly focused on in-flight and upcoming work.

| Priority Category | Feature / Focus | Primary Open Source Resource | Value | Effort | Target Release | Status |
|---|---|---|---|---|---|---|
| **Quick Wins** | In-Flight Work, PR Stagnation & Blocker Radar (`devops gh pm inflight`) | GitHub API / FIFO / Metrics | High | Low | v0.2.22 | 📋 Scheduled (P1) |
|  | Universal Command Palette & Fuzzy Action Launcher | Textual CommandPalette | High | Low | v0.2.23 | 📋 Scheduled (P1) |
|  | Zero-Trust Git Commit & Tag Signature Verifier | `git`, GPG, Sigstore | High | Low | v0.3.0 | 💡 Future Vision |
|  | JIT Python 3.14 Bytecode Optimization Benchmarking | `pytest-benchmark` / JIT | Medium | Low | v0.3.0 | 💡 Future Vision |
|  | Universal `--json` CLI Output Flag Alias Pipeline | Typer / Rich | Medium | Low | v0.3.0 | 💡 Future Vision |
|  | Mutation-Driven GitHub Cache Invalidation Hooks | Disk Cache / SQLite | High | Low | v0.3.0 | 💡 Future Vision |
|  | Native Process Group Inspector & Terminator | POSIX / `os.killpg` | High | Low | v0.3.0 | 💡 Future Vision |
|  | Automated Pre-Rebase Merge Conflict Dry-Runner | `git merge-tree` / libgit2 | High | Low | v0.3.0 | 💡 Future Vision |
|  | Ephemeral Sandboxed Evaluation Harness | Python AST / Safe Eval | Medium | Low | v0.3.0 | 💡 Future Vision |
|  | IDE Host Health & Submodule Scan Auditor | VS Code Server / JSON | Medium | Low | v0.3.0 | 💡 Future Vision |
| **Major Projects** | MCTS & Tree-of-Thought Solution Exploration Engine (`devops ai explore`) | MCTS / UCT / Beam Search | High | High | v0.2.20 | 📋 Scheduled (P0) |
|  | Ephemeral Shadow Worktrees & CoW State Snapshots | Git / CoW / Docker | High | High | v0.2.20 | 📋 Scheduled (P0) |
|  | Syntopical Dialectical Synthesis Engine (`devops ai research syntopical`) | PydanticAI / Multi-Source | High | High | v0.2.21 | 📋 Scheduled (P0) |
|  | Agentic Information Foraging & Scent Tracker (`devops ai research forage`) | Graph Search / Scent | High | High | v0.2.21 | 📋 Scheduled (P0) |
|  | Continuous State Machine Reconciler & Card Daemon (`devops gh pm reconcile`) | GitHub API / Watcher | High | High | v0.2.22 | 📋 Scheduled (P0) |
|  | GitHub Models Zero-Setup Inference Provider (`devops ai models github`) | Azure AI / `models.github.ai` | High | High | v0.2.22 | 📋 Scheduled (P0) |
|  | Autonomous GitHub Actions Self-Healing & PR Triage Workflows | GitHub Actions / Runner | High | High | v0.2.22 | 📋 Scheduled (P0) |
|  | Comprehensive DevOps CLI Grafana Observability Dashboard Suite | Grafana 10+ / Prometheus / Loki | High | High | v0.2.23 | 📋 Scheduled (P0) |
|  | Native VS Code Language Model Tools API Provider (`vscode.lm.tools`) | VS Code API / JSON Schema | High | High | v0.2.25 | 📋 Scheduled (P0) |
|  | VS Code Copilot Chat Custom Participant (`@devops`) & Slash Commands | VS Code Chat API / Slash | High | High | v0.2.25 | 📋 Scheduled (P0) |
|  | Multi-Region Workstation Mesh & Cluster Federation | Kubernetes / Fleet | High | High | v0.3.0 | 💡 Future Vision |
|  | Autonomous Self-Healing Agent Pipeline | PydanticAI / Diagnostic | High | High | v0.3.0 | 💡 Future Vision |
|  | Distributed Multi-Cluster Telemetry & OTel Egress Mesh | OTel Collector / Prometheus | High | High | v0.3.0 | 💡 Future Vision |
| **Strategic Investments** | Counterexample-Guided Inductive Synthesis (CEGIS) Loop | AST / Pytest / Negative Constraints | High | Medium | v0.2.20 | 📋 Scheduled (P0) |
|  | Hierarchical Delta-Debugging & Patch Minimization Engine | Delta-AST / Delta-Debugging | High | Medium | v0.2.20 | 📋 Scheduled (P1) |
|  | Multi-Objective Pareto Solution Ranker (`devops ai rank-solutions`) | Pydantic / AST / Profiler | High | Medium | v0.2.20 | 📋 Scheduled (P1) |
|  | Valkey L2 Trial Invalidation Cache & Experience Replay | Valkey L2 / Hashing | High | Medium | v0.2.20 | 📋 Scheduled (P1) |
|  | Canary Resilience & Chaos Fault-Injection Verifier | Chaos Mesh / k6 / Subprocess | High | Medium | v0.2.20 | 📋 Scheduled (P1) |
|  | Automated Parameter & Interface Parity Oracle | Python AST / Typer / FastMCP | High | Medium | v0.2.20 | 📋 Scheduled (P1) |
|  | Ground-Truth Source Triangulator & Provenance Auditor | AST / Config / Pytest | High | Medium | v0.2.21 | 📋 Scheduled (P1) |
|  | Living Mental Model Synthesizer & Causal Graph Distiller | YAML / Causal DAG | High | Medium | v0.2.21 | 📋 Scheduled (P1) |
|  | Cross-Domain Analogical Pattern Retriever | Qdrant / Multi-Vector | High | Medium | v0.2.21 | 📋 Scheduled (P1) |
|  | Multi-Repository Fleet Coordination & Portfolio Management (`devops gh pm fleet`) | GitHub REST/GraphQL / DAG | High | Medium | v0.2.22 | 📋 Scheduled (P0) |
|  | Background Project Watcher Daemon & Event Streamer (`devops gh pm daemon`) | Asyncio / Webhooks / Rate Limiter | High | Medium | v0.2.22 | 📋 Scheduled (P0) |
|  | Cognitive Feature Research & Roadmap Prioritization Engine (`devops gh pm research`) | PydanticAI / Multi-Source | High | Medium | v0.2.22 | 📋 Scheduled (P0) |
|  | Autonomous Epic Decomposition & Backlog Synthesizer (`devops gh pm plan`) | PydanticAI / Stories / Labels | High | Medium | v0.2.22 | 📋 Scheduled (P0) |
|  | DAG Dependency Engine & Critical Path Unblocker (`devops gh pm deps`) | NetworkX / DAG / AST | High | Medium | v0.2.22 | 📋 Scheduled (P0) |
|  | WIP Limit Governor & Workload Dispatcher | Pydantic / Token Budget | High | Medium | v0.2.22 | 📋 Scheduled (P1) |
|  | Agentic Sprint Cadence & Velocity Engine (`devops gh pm sprint`) | GitHub Projects v2 / Velocity | High | Medium | v0.2.22 | 📋 Scheduled (P1) |
|  | GitHub Copilot Extension & Web Agent (`@devops-cli`) | Copilot Extensions API | High | Medium | v0.2.22 | 📋 Scheduled (P1) |
|  | Reactive Multi-Workspace Textual TUI Architecture | Textual / Async Workers | High | Medium | v0.2.23 | 📋 Scheduled (P0) |
|  | Interactive GitHub Lifecycle, PR Monitor & Kanban Hub | Textual / GitHub REST | High | Medium | v0.2.23 | 📋 Scheduled (P0) |
|  | Cloud-Native Cluster Runtime & Pod Log Streamer | Textual / Kubernetes / Stern | High | Medium | v0.2.23 | 📋 Scheduled (P0) |
|  | Docker Containers & Multi-Tier Sandbox Console | Textual / Docker SDK / cgroups | High | Medium | v0.2.23 | 📋 Scheduled (P1) |
|  | Unified SecOps, Compliance & Vault Command Center | Textual / Trivy / Semgrep / Vault | High | Medium | v0.2.23 | 📋 Scheduled (P1) |
|  | GitOps Fleet, Argo Rollouts & Cloud Cost Monitor | Textual / ArgoCD / Infracost | High | Medium | v0.2.23 | 📋 Scheduled (P1) |
|  | AI Constellation Topology & Review Findings Studio | Textual / Ollama / Qdrant | High | Medium | v0.2.23 | 📋 Scheduled (P1) |
|  | Centralized Loki LogQL Streamer & Trace Waterfalls | Textual / Loki / Prometheus | High | Medium | v0.2.23 | 📋 Scheduled (P1) |
|  | Declarative Dashboard Linter & K8s Sidecar GitOps Provisioner | Kubernetes / ConfigMap / Helm | High | Medium | v0.2.23 | 📋 Scheduled (P1) |
|  | POSIX Process Group Sandbox Enforcement | Subprocess / OS | High | Low | v0.2.24 | 📋 Scheduled (P0) |
|  | Structural Pre-Commit Hook Inversion | Pre-commit / Pytest | High | Medium | v0.2.24 | 📋 Scheduled (P0) |
|  | Anti-Brittle Constant Elimination | Standard Library / AST | High | Medium | v0.2.24 | 📋 Scheduled (P1) |
|  | Semantic Validator Deprecation & Structural Positional Oracles | AST / Pydantic | High | Medium | v0.2.24 | 📋 Scheduled (P1) |
|  | Lazy Domain-Gated MCP Tool Schema Hydration | FastMCP / MCP Protocol | High | Medium | v0.2.24 | 📋 Scheduled (P0) |
|  | Pipeline Stage Context Budgeting & Invariant Pinning | ContextPacker / AgentMemory | High | Medium | v0.2.24 | 📋 Scheduled (P0) |
|  | Capability-Gated Model Failover & AIMD Batch Recovery | Gateway / AIMD / Embeddings | High | Medium | v0.2.24 | 📋 Scheduled (P0) |
|  | Lossless Structured Error Reflection for Schema Retries | Pydantic / Structured Output | High | Low | v0.2.24 | 📋 Scheduled (P1) |
|  | Background Shell Pipe Deadlock Fix & Output Contract | Subprocess / Threading | High | Low | v0.2.24 | 📋 Scheduled (P1) |
|  | Structured Constraint Propagation Across Subagent Delegation | PydanticAI / Workflow | High | Medium | v0.2.24 | 📋 Scheduled (P1) |
|  | MCP Resource-First Data Access & Tool Output Sandboxing | FastMCP / MCP Resources | High | Medium | v0.2.24 | 📋 Scheduled (P1) |
|  | Multi-Document Proposed Edits & Native Side-by-Side Diff Review | VS Code Proposed Edits | High | Medium | v0.2.25 | 📋 Scheduled (P1) |
|  | Automated Multi-IDE MCP Scaffolder & Health Watchdog (`devops ide configure`) | FastMCP / Stdio / Watchdog | High | Medium | v0.2.25 | 📋 Scheduled (P1) |
|  | Path-Specific Copilot Instructions & Executable Prompt Scaffolder | Copilot Prompts / AST | High | Medium | v0.2.25 | 📋 Scheduled (P1) |
|  | DevOps CLI VS Code Companion Extension (`devops-vscode`) | VS Code Extension / Webview | High | Medium | v0.2.25 | 📋 Scheduled (P1) |
|  | Cloud-Native Ephemeral Test Environment Engine | Minikube / Helm / Ingress | High | Medium | v0.3.0 | 💡 Future Vision |
|  | Distributed Cache & Shared Semantic Embeddings Sync | S3 / OCI / SQLite | High | Medium | v0.3.0 | 💡 Future Vision |
|  | Proportional API Rate Budgeting & GraphQL Circuit Breaker Guard | Standard Library / SQLite | High | Medium | v0.3.0 | 💡 Future Vision |
| **Tactical Additions** | Cascading Fast-Fail Verification Battery & Token Governor | AST / Pytest / Token Bucket | High | Low | v0.2.20 | 📋 Scheduled (P1) |
|  | FastMCP Solution Discovery Tools & Dynamic Resources | FastMCP / PydanticAI | High | Low | v0.2.20 | 📋 Scheduled (P1) |
|  | Socratic Inquiry & Knowledge Gap Formulator (`devops ai research socratic`) | Pydantic / Metacognition | High | Low | v0.2.21 | 📋 Scheduled (P1) |
|  | Active Marginalia & Epistemic Scratchpad (`devops ai read annotate`) | JSONL / Marginalia | High | Low | v0.2.21 | 📋 Scheduled (P1) |
|  | FastMCP Cognitive Research Tools & Epistemic Resources | FastMCP / PydanticAI | High | Low | v0.2.21 | 📋 Scheduled (P1) |
|  | Automated Triage & Sandbox Repro Validator (`devops gh pm triage`) | PydanticAI / Docker | High | Low | v0.2.22 | 📋 Scheduled (P1) |
|  | Standup & Executive Velocity Reporter (`devops gh pm report`) | Pydantic / Markdown / Rich | High | Low | v0.2.22 | 📋 Scheduled (P1) |
|  | FastMCP Agentic PM Tools & System Resources | FastMCP / PydanticAI | High | Low | v0.2.22 | 📋 Scheduled (P1) |
|  | FastMCP TUI Management Tools & Dynamic Resources | FastMCP / PydanticAI | Medium | Low | v0.2.23 | 📋 Scheduled (P2) |
|  | Reusable DevOps Task Prompt File Catalog | GitHub Prompts / Markdown | Medium | Low | v0.2.25 | 📋 Scheduled (P2) |
| **Fill-Ins** | Multi-Scale Semantic Outline Scanner (`devops ai read --inspect`) | Python AST / Tree-Sitter | High | Low | v0.2.21 | ✅ Completed (P0) |
|  | Information Scent Trail Visualizer & Breadcrumb Tree | Rich Trees / Graphviz | Medium | Low | v0.2.21 | 📋 Scheduled (P2) |
|  | Dependency DAG Visualizer & Critical Path Graph | Mermaid / Rich Trees | Medium | Low | v0.2.22 | 📋 Scheduled (P2) |
| **De-prioritized** | Bare-Metal OS Installers | Shell scripts | Low | High | — | ❌ Rejected (DevContainer native) |
|  | Heavyweight Monolithic Orchestrators | Full LangChain | Low | High | — | ❌ Rejected (FastMCP + PydanticAI) |
