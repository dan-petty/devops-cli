# AGENTS.md — AI Agent Instructions & Engineering Best Practices

This document provides context, architectural principles, and best practices for AI coding assistants (GitHub Copilot, Claude, Cursor, Codex) working on this codebase or reviewing target repositories.

> **Canonical Source**: This file is the single source of truth for AI agent instructions. [CLAUDE.md](./CLAUDE.md), [GEMINI.md](./GEMINI.md) and [.github/copilot-instructions.md](./.github/copilot-instructions.md) are thin pointers to this file.

---

## 1. Core Engineering Philosophy & Objectives

- **High Reliability & Quality First**: Build resilient workstation automation and developer tooling with defensive error handling, bounded timeouts, and zero tolerance for flaky tests.
- **Poetic Conciseness, Expressive Integration & Zero Boilerplate**:
  - The codebase must read as an expressive, poetically concise integration of tools, libraries, docs, AI, and automation rather than a sprawl of procedural loops or boilerplate.
  - **Complexity and Nesting Caps**: Ruff caps cyclomatic complexity at 10 (`C901`) in `pyproject.toml`. `uv run devops ci` and the pre-commit `ruff-check` hook run it with `--config pyproject.toml`. Decompose a breach. Do not suppress it. `tests/test_ruff_complexity_cap.py` checks the Ruff settings and every `ruff check` command. `test_suppressions_stay_under_their_ceilings` ([`tests/test_architectural_invariants.py`](tests/test_architectural_invariants.py)) lets the `# noqa: C901` markers that remain only fall. The `structural-invariants` pre-commit hook and `test_the_source_tree_keeps_its_structural_invariants` enforce nesting depth $\le 5$ (< 6 indentation levels). They read `devops_cli.core.code_metrics`.
  - Split a multi-step task into helper functions, pure predicates and pipelines. For a closed set, use `match` with `assert_never` or a table, not an `if/elif` chain. Prefer the standard library (`functools`, `itertools`, `pathlib`, `collections`, `ipaddress`, `urllib.parse`) and Pydantic v2 models to hand-written code.
- **Strict Prohibition of Brittle Pattern Subsets & Mandatory Constants/Defaults Placement**:
  - Matching against a list of strings or regular expressions is **ONLY acceptable if it covers 100% of possible scenarios** (mathematically bounded, closed domains defined by official RFCs or language grammars).
  - Matching against a limited or arbitrary subset of a larger or unknown list of possible values is strictly prohibited. Use mature solutions such as programming language symbol parsers (Python AST visitors, tokenizer pipelines) or official registries (Mozilla Public Suffix List via `tldextract`).
  - Any string list, tuple, or frozen set for matching, classification, or filtering **MUST be declared in `src/devops_cli/config/constants.py` or `src/devops_cli/config/defaults.py`**, never scattered across functional modules.
- **Modern Python Ecosystem**: Track Python 3.14+ and prefer established libraries. The tools in `pyproject.toml` are choices, not requirements.
- **Open Tools Before Internal Code**: Before building a capability, name the open tool or library that covers it. Building instead needs a written cost in the issue or PR: tokens to implement, maintain and fix until it matches the tool, plus elapsed time. A plan that prescribes a build is a proposal. A convention is never a reason to keep or write custom code. This rule outranks every convention here.
- **Write in ASD-STE100 Simplified Technical English**: Write all prose in ASD-STE100: chat replies, PR, issue and commit text, documents, task files, `devops ai` output, and new or edited output strings. Code, commands, file names, identifiers and quoted text stay as they are.
  - Put one instruction in each sentence. Use at most 20 words in a procedure sentence and 25 in a description. Use at most six sentences in a paragraph.
  - Use the active voice and simple tenses. Do not use contractions. Keep the articles. Use one word for one meaning.
- **Zero-Trust Security & Egress Safety**:
  - Never store a secret in code, configuration files, logs or git. Read each secret from a secret store, such as the OS keyring, HashiCorp Vault, a Kubernetes Secret or the credential store of the owning tool.
  - **Zero Information Leakage & Environment Sanitization**:
    - Never leak, extract, or expose confidential, private, hidden, or `.gitignored` files (`.env*`, `.ssh/`, `.data/`, `~/.gemini/`, credentials, private keys) into any documents, changelogs, review findings, public commits, or code artifacts. Enforced by `.gitignore`, `detect-private-key`, and `bandit`.
    - **Strict Prohibition of Internal Systems & Real Infrastructure Data**: Never record, publish, or leak concrete internal hostnames (`*.lan`, `*.local`, physical machine names, private server hostnames), private RFC 1918 IP addresses (`192.168.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`), private container registries, non-standard local NodePort services (`:30500`), physical block devices/mount paths (`/mnt/nvme*`, `/dev/sd*`), or private cluster topology details into task tracking (`docs/agent/tasks/`), documentation, roadmaps, code comments, tests, manifests (`k8s/`), or configuration templates (`config.yaml`).
    - **Mandatory Abstract Roles & Documentation Placeholders**: Replace concrete environments with abstractions:
      - Hostnames: `<storage-node>`, `<gpu-node>`, `<worker-node>`, `<host>`, `node1.example.internal`, `localhost`.
      - IP Addresses: RFC 5737 documentation blocks (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) or loopback (`127.0.0.1` / `localhost`).
      - Registry Endpoints: `ghcr.io/<org>/<image>:<tag>` or `<registry-host>:<port>/<image>:<tag>`.
      - Storage Mount Paths: `<storage-mount-path>`, `<fast-storage>`, standard Kubernetes PersistentVolumeClaims.
      - **Mandatory Mock Test Hostname Standardization**: Use the exact same hostname with no subdomain (`example.com`) for all mock/dummy test values across all tests, fixtures, mocks, and examples. Never introduce subdomains (such as `api.example.com` or `vault.example.com`) for mock test endpoints.
    - **Configuration Template Hygiene vs User Runtime Config**:
      - Committed templates (`config.example.yaml`) and documentation must strictly use generic documentation or localhost endpoints (`http://localhost:11434`, `http://localhost:6333`, `http://localhost:8080`), never private LAN hostnames or internal IPs.
      - **Protection of User Runtime Config (`config.yaml`)**: Local `config.yaml` is uncommitted, gitignored, and belongs exclusively to the user's active runtime environment. AI agents and workflows MUST NEVER overwrite, sanitize, or reset the user's `ollama_urls`, inference hostnames, or custom ports in `config.yaml` to localhost.
  - Bounded string truncation on error details: Cap external inputs propagated into exception `details` dictionaries or structured error logs at $\le 256$ chars to prevent log bloat and injection (CWE-209 / CWE-400).
  - Mitigate Server-Side Request Forgery (SSRF) and network egress risks by validating destination endpoints.
  - **Defensive Subprocess Management & Process Group Isolation**:
    - When invoking external commands or background workers via `subprocess.Popen`, never terminate processes using simple `proc.kill()`, which leaves spawned subshells as zombies adopted by PID 1.
    - Isolate execution into a dedicated POSIX process group (`start_new_session=True` on `subprocess.Popen`) and terminate the entire hierarchy by signalling the group by its id (`os.killpg(proc.pid, signal.SIGTERM)`). See `_terminate_process_group` in `src/devops_cli/sandbox/host.py`.
    - **Protection Against Container Starvation & Killing**:
      - **Prohibition of `RLIMIT_NPROC`**: In Linux, `setrlimit(RLIMIT_NPROC, ...)` applies per-real-UID across the entire container, NOT per-process tree. Setting `RLIMIT_NPROC` inside child hooks or tests starves ambient container processes (VS Code Server, shells), causing `os.fork()` to fail with `EAGAIN`. Never enforce process caps via `RLIMIT_NPROC` or execute fork bombs in tests.
      - **Terminal File Descriptor Safety**: Never call `os.set_blocking(fd, False)` or set `O_NONBLOCK` on standard descriptors `{0, 1, 2}`. Setting non-blocking mode on STDOUT/PTY corrupts terminal I/O for VS Code Server.
      - **Guarded Process Group Termination**: When killing process groups via `os.killpg(pgid, sig)`, guard against killing PID 1 (container init), PID 0, negative PIDs, self PID (`os.getpid()`), or caller process group (`os.getpgrp()`). Enforce: `if not isinstance(pid, int) or pid <= 1: return` and `if pgid <= 1 or pgid == os.getpgrp(): return`.
  - **Defensive Filesystem & Symlink Containment**:
    - Enforce pre-flight file size caps (`MAX_REPOMAP_FILE_SIZE_BYTES` $\le 50$MB) before ingesting or packing files into memory to prevent OOM crashes.
    - Defensively resolve symlinks (`path.resolve()`) and verify that target paths stay strictly confined to the intended root workspace (`resolved_path.is_relative_to(base_root)`), catching `(OSError, RuntimeError)`.
  - **Mandatory Telemetry Opt-Outs**:
    - Always disable third-party telemetry, phone-home mechanisms, anonymous usage reporting, crash analytics, and background update checks across all tools, services, workloads, containers, and CLI configurations whenever doing so does not impact functional user experience (Grafana, Alloy, Loki, Traefik, Open WebUI, LiteLLM, devcontainer opt-outs `DO_NOT_TRACK=1`, `GOTELEMETRY=off`, `PIP_DISABLE_PIP_VERSION_CHECK=1`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `HF_HUB_DISABLE_TELEMETRY=1`, `OPENSPEC_TELEMETRY=0`).
    - For web integrations that provide tangible user-facing functionality or dynamic content (IDE plugin update notifications, community news feeds, remote marketplace catalogs), confirm with user before disabling.
- **Mandatory Comprehensive Kubernetes Stack Deployment (`devops k8s deploy-stack --stack all`)**:
  - Every Kubernetes manifest, service, workload, ConfigMap, CronJob, NetworkPolicy, or Helm chart running in the cluster MUST be integrated into and deployed by `devops k8s deploy-stack`.
  - Executing `devops k8s deploy-stack --stack all` MUST deploy, synchronize, and update all cluster resources across all stacks (`infra`, `llm`, `logging`, and in-cluster `devops` services under `k8s/devops/`). Registered under `_MANIFESTS_BY_STACK`, `_HELM_RELEASES_BY_STACK`, or `_POST_HELM_BY_STACK` in `stack_lifecycle.py`.
- **Never Lower Security Standards or Quality Thresholds**: Never lower, relax, disable or bypass a security standard or quality threshold (90% coverage, strict typing, lint rules, compliance checks). Only the user can allow this. Every change meets the project standards. Replacing a check with a standard tool that enforces at least the same property on this repository is not lowering it. Run both checks once. Show both results in the PR.
- **Strict Pre-Push Quality Gate Mandate (Zero Pushes Without Passing `devops ci`)**:
  - The pre-push hook's `uv run devops ci` is the gate run. A manual run counts only when nothing changes before the push. Run it, if at all, after the last rebase, amend or edit, in the worktree you push from, with no `--check`, `--no-fix`, `--only` or `--skip`.
  - AI agents, workflows, and developers **MUST NEVER PUSH COMMITS (`git push`)** to any remote branch unless `uv run devops ci` has completed locally with 100% passing status (every check `devops ci` runs, coverage $\ge 90.0\%$, zero failed tests, zero unhandled deprecation warnings) in the active session.
  - Enforced locally via git hooks (`.pre-commit-config.yaml` pre-push stage running `uv run devops ci`). Bypassing pre-push hooks (`--no-verify`) is strictly forbidden.
  - When the hook's docs pre-fix rewrites files, regenerate and commit the docs, then push again. Do not repeat the push unchanged.
- **Strict Prohibition of Direct Commits to `main` (Pull Requests Required)**:
  - AI agents, workflows, and developers **MUST NEVER COMMIT OR PUSH DIRECTLY TO `main`**.
  - Every change goes on a topic branch (`fix/<description>`, `feat/<description>`, `docs/<description>`, `refactor/<description>`) and reaches `main` only through a GitHub pull request.
  - The pre-commit hook `no-commit-to-branch` (`args: [--branch, main]`) blocks a commit on `main`.
- **Proactive GitHub Project Tracking & Workflow Grounding**: Every engineering action, planned deliverable, active WIP implementation, review remediation, and defect investigation MUST be grounded in GitHub Projects v2 (`https://github.com/dan-petty/devops-cli/projects`) and GitHub Issues. Work without an active project card is strictly prohibited. Bootstrap tasks into issues, maintain real-time card state transitions, and reconcile custom fields on every lifecycle event.
- **Author All Code, Documentation, Status & Wording as Merged/Committed (Zero Administrative Tracking PRs)**:
  - Status and wording of all code, documentation, checklists, deliverable descriptions, and task tracking files (`docs/agent/tasks/`) **MUST BE AUTHORED FROM THE OUTSET EXACTLY AS THEY WILL READ ONCE COMMITTED AND MERGED**.
  - **Strict Prohibition of Standalone Tracking Commits & Follow-Up Status PRs**: Never create commits or pull requests solely to update tracking after a PR has merged. Such PRs are pointless administrative clutter. The deliverable is described in its final completed state within the functional deliverable PR itself (`- [x]`). Work not done is a plain bullet naming its follow-up issue; checks only a person can run are plain bullets starting `Pending a person:`.
- **API Rate Limit Honor, Resilient Backoff & Quota Budgeting**:
  - Respect API rate limits, complexity budgets, and resource quotas across external services (GitHub REST/GraphQL, AI LLM/embedding inference, package registries, cloud providers).
  - Inspect remaining rate limits proactively (`devops gh rate-limit`, `x-ratelimit-remaining`, `Retry-After`).
  - **Strict Prohibition of Bare `gh` CLI Invocations**: All GitHub operations must be routed through native rate-managed commands (`devops gh`, `devops pr`) or FastMCP tools, using `GitHubRateLimiter` (`run_gh`) for client-side token-bucket pacing, quota safety thresholds, and read caching.
  - Apply bounded exponential backoff with jitter on HTTP 429 / rate limits. Cache idempotent queries locally (`.data/` or Valkey L2 cache).
- **Negative Tool Schema Invariants & Prescriptive Error Feedback**: FastMCP tools and agent schemas MUST enforce strict parameter boundaries (`extra="forbid"` in Pydantic v2 or `additionalProperties: false` in JSON Schema). Validation handlers synthesize structured, prescriptive error prompts detailing allowable arguments.
- **Pre-1.0 Alpha Lifecycle & Zero Backwards Compatibility Guarantee**:
  - `devops-cli` is **alpha software** before `1.0.0` with **no intention of maintaining backwards compatibility**. Breaking changes, interface evolutions, and schema redesigns may land in any release without legacy shims.
  - The codebase MUST remain clean of legacy references, obsolete shims, deprecated aliases, and compatibility remnants at all times.
- **Post-1.0 Semantic Versioning & Enterprise Change Management**: Releases after `1.0.0` adhere strictly to Semantic Versioning 2.0.0 (`MAJOR.MINOR.PATCH`) with runtime feature flags, multi-release deprecation warnings, and migration tooling.
- **Clean Solutions Over Legacy Remnants (Zero Zombie Code)**: When modifying, refactoring, or replacing features or schemas, implement clean, complete solutions and remove obsolete code, variables, aliases, fallback shims, and legacy workarounds.
- **Dedicated Agent Workspace Data Isolation**: The workspace data directory is configured via `DEVOPS_CLI_DATA_DIR` (or `data.dir`, defaulting to `./.data`). Isolate agent work products under subfolder `<data_dir>/agent` (e.g. `./.data/agent`) to separate agent artifacts from user workspace data.
- **Scratch Work Stays Untracked**: Keep ad-hoc scripts and reproductions in `<data_dir>/agent/scratch/` or `$TMPDIR`. Never put them in the project root or in `src/`. A reproduction that stays becomes a test in `tests/`. `test_no_stray_scripts_in_project_root` ([`tests/test_architectural_invariants.py`](tests/test_architectural_invariants.py)) fails on a `.py` or `.sh` file in the project root. Put a committed helper script in `scripts/` as a PEP 723 file. Ruff checks it with the rest of the tree. The pull request that adds the first script adds `scripts` to the mypy and Bandit targets.
- **Mandatory Backup for Files Outside Workspace**: When modifying files outside workspace (`~/.ssh/`, `~/.bashrc`, `/etc/`), create a timestamped backup `<original-filepath>.bak-<YYYYMMDD-HHMMSS>` before edits.
- **Mandatory Defect Filing on CLI Errors & Warnings**: When encountering unhandled errors, subcommand failures, crashes, or diagnostic warnings executing `devops` CLI commands, file a bug candidate with `devops roadmap intake --title "fix(<scope>): <description>" --body-file <file> --confirm`. Never suppress or bypass errors silently.
- **Mandatory Root-Cause Remediation**: Investigate and fix the cause at the source. If an external constraint blocks the fix, add a check that fails when the problem returns, and link the incident. Add prose here only when no check is possible.
- **Proactive Deprecation Remediation & Zero-Warning Mandate**: When encountering deprecation warnings (`DeprecationWarning`, Python 3.14+, Pydantic v2, Typer, Click), investigate and resolve them at the source immediately. Enforced by `uv run devops ci`.
- **Continuous Roadmap Synthesis, Field Observations & Self-Improvement**:
  - File candidates with `devops roadmap intake --title "<conventional title>" --body-file <file> --confirm` (or FastMCP `roadmap_intake` with `mode="confirm"`). The body states friction, evidence, and proposed remedy. Intake checks duplicates, labels `source/agent`, assigns type, Priority, Value, Effort, and puts the item in the backlog.
  - Never set milestone or priority on a new issue. A person plans milestones on the board ([ADR 0013](docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md)).
- **Continuous Interaction & Collaborative Value Improvement**: Suggest ways to improve ergonomics, speed, resilience, docs, test coverage, and tooling efficiency.

---

## 2. Development Workflow & Progressive Verification

All work follows a test-first progressive verification strategy:

### Feasibility Check (Before Any Code or Tests)
- **Confirm Premise Against Real System**: Confirm premise against upstream documentation, library source, live cluster state, or CLI runtime. Record verification method in task file's `**Feasibility**` field.
- **Stop Rather Than Add Compensating Code**: When an item cannot be built as specified or requires refactoring beyond its scope, write no compensating code (no dummy mocks, no swallowed exceptions). Comment on the issue with evidence, ask a person to return the item to `New` (`devops roadmap return <issue-number> --comment "<evidence>" --confirm`), and stop. See [#1348](https://github.com/dan-petty/devops-cli/issues/1348).
- **Signals to Stop**: Swallowing an error (`except Exception: pass`, unread `check=False`); product code detecting tests; a second fix on top of a fix in the same area within one release; review loop repeatedly finding new defects in the same feature.

### Test-First Development Cycle (TDD as Living Contract)
1. **Define Specification via Tests First**: Author unit and integration tests defining behavior, boundaries, and errors in `tests/` before implementation. Where a test goes, what it may double, how it is named and what it asserts: [`docs/TESTING.md`](docs/TESTING.md). Defect and fix PRs cite the `fail-to-pass` check run (`devops ci fail-to-pass --base <ref>` / `.github/workflows/fail-to-pass.yml`) instead of typing failure counts by hand. The check fails any PR whose replay pytest could not run on base: pytest was interrupted, stopped with an internal or usage error, or wrote no complete JUnit report, as when the overlaid `tests/` import support the base lacks or the PR changes dependencies or the test harness. Such a PR declares `Fail-to-pass: not applicable: <reason>` in its body. A changed test that only fails to collect on base is reported as errored.
2. **Implement Feature Logic**: Write clean, concise code in `src/devops_cli/` to satisfy tests.
3. **Verify Locally**: Run targeted tests (`uv run devops ci test tests/test_<feature>.py`), which sizes its xdist workers to the selection.
4. **Comprehensive Quality Gate**: Execute `devops ci` (or `uv run devops ci`) validating all gates and enforcing $\ge 90\%$ coverage.
5. **Zero Deprecation Warnings**: Remediate all deprecation warnings before concluding work.
6. **Tests Pass Bandit Too**: Run `.bandit` security checks over `tests/` (`devops ci security`). Bind sockets to `127.0.0.1` or `::1`, use `tmp_path`. Use `# nosec BXXX` only for literals deliberately under test. Test conventions are detailed in [`docs/TESTING.md`](docs/TESTING.md).

### Project Planning & Task Tracking
- **Task Files Written by Delivering PR**: A task file is authored only in the pull request that delivers the item (never before implementation), describing completed work and feasibility.
- **GitHub Projects v2 Bootstrap**: Ground every task in an issue card on the board (`https://github.com/dan-petty/devops-cli/projects`). Move cards to `In Progress` before editing `src/`.
- **Modular Per-Task Tracking Architecture (`docs/agent/tasks/`)**:
  - Task tracking lives exclusively in isolated per-task files (`docs/agent/tasks/task-<issue>-<slug>.md`). Topic branches create/modify only their own task file.
  - **Changelog**: The PR title is the changelog line. Never edit `CHANGELOG.md`, `.release-please-manifest.json` or a version line: release-please writes them in its own pull request.
  - **Issue-Only Linking & No Metadata Fields**: Task files link only their issue (`**Issue**: [#<issue>](...)`). Never carry `**PR**`, `**Status**`, `**Milestone**`, or `**Priority**` lines (status, milestone, and priority live exclusively on GitHub per ADR 0001). Enforced by [`tests/test_agent_task_files.py`](tests/test_agent_task_files.py).
  - **Mandatory Author-as-Merged Rule**: Deliverable PR authors the task file in the deliverable commit with ticked boxes (`- [x]`) only for completed work. Once merged, the issue closes and cards move to Done without administrative commits. Work not done is a plain bullet naming its follow-up issue.
  - Reconcile board fields (`Status`, `Priority`) using `devops gh project sync` (sets Status from issue labels; adds no cards).

### Knowledge Base & Routine Operations
- Consult **DevOps CLI Knowledge Base** under [`src/devops_cli/ai/knowledge_base/README.md`](src/devops_cli/ai/knowledge_base/README.md) for internals (`devops_cli/tasks/`) and IT domain guides (`it_domains/`).
- Execute routine tasks following sequence and cadence in [`docs/ROUTINE_TASKS.md`](docs/ROUTINE_TASKS.md).
- Synchronize CLI documentation (`devops docs generate --sync-readme`) to keep it fresh (verified by `devops docs check`).
- Maintain review and self-improvement loop following [`docs/SELF_IMPROVEMENT.md`](docs/SELF_IMPROVEMENT.md).

### Build, Lint & Test Commands
| Operation | Command | Purpose |
| :--- | :--- | :--- |
| **Dependency Sync** | `uv sync` | Synchronize virtual environment with lockfile. |
| **Full CI Suite (Primary Gate)** | `devops ci` / `uv run devops ci` | Quality gate (python_version, test, coverage $\ge 90\%$, lint, format, typecheck, audit, security, build, actionlint, docs, deps, openspec). |
| **Targeted Test** | `uv run devops ci test tests/test_<feature>.py` | Fast, isolated unit test execution, serial for a few test files. |
| **Targeted Lint** | `uv run ruff check path/to/file.py` | Fast lint inspection on modified files. |
| **Targeted Typecheck** | `uv run mypy path/to/file.py` | Strict static type validation on modified modules. |
| **Documentation Sync** | `devops docs generate --sync-readme` | Synchronize markdown CLI references and README matrix. |
| **Milestones** | `devops gh milestones list` | Inspect the progress of the planning milestones. |
| **Project Sync** | `devops gh project sync` | Reconcile Status and Priority on cards already on the board. |

---

## 3. Git Hygiene, Pull Requests & GitHub Integration

### Branches & Releases
- **Branch Targeting**: Topic PRs target `main`. The PR title is a Conventional Commit (`type(scope): summary`). Before `1.0.0` nothing is a breaking change, so a title has no `!` and a body has no `BREAKING CHANGE:` footer. The `Semantic PR title` check enforces it. The squash commit takes the title, and the title becomes the changelog line.
- **Agents Take No Part in Releases**: release-please makes every release, and a person merges its pull request ([`RELEASE_CYCLE.md`](RELEASE_CYCLE.md)).
  - Agents do not open, edit, update, review, comment on or merge the release-please pull request.
  - Agents do not create tags or GitHub releases. Agents do not edit `CHANGELOG.md`, `.release-please-manifest.json` or version lines.
  - Agents do not run release-please, and do not change its settings to steer a version. Agents never write a `Release-As:` line.
- **`roadmap-service` Is Suspended ([#1562](https://github.com/dan-petty/devops-cli/issues/1562))**:
  - GitHub suspended the Service's machine account. `deployment/roadmap-service` is held at 0 replicas in git. Rules describing the running Service do not apply until #1562's revert merges.
  - Nobody scales up, restarts, or re-pushes secrets for `roadmap-service`.
  - An agent files its own new candidate with `intake --title`, `--body-file` and `--confirm`. Only a person runs any other mutating `devops roadmap` command, from their own account: `return --confirm`, `refine`, `run --confirm`, and `intake` over existing issues. For these, an agent uses `--plan` and `--dry-run` only.
  - Items labelled `status/blocked` pointing to #1562 stay blocked until reinstated.
- **In-Cluster Service & Concurrency Avoidance**: When `roadmap-service` is active, avoid concurrent manual mutations (`intake --confirm`). Read-only inspection (`--plan`, `--dry-run`) is permitted. For service architecture, job cycles, telemetry, and diagnostics, see `k8s/README.md` and [`docs/SDLC.md`](docs/SDLC.md) Phase 6.
- **Remote Branch Lifecycle**: Every remote branch must have an open PR, which `devops pr create` opens as a draft. Merged or superseded branches must be deleted immediately (`git push origin --delete <branch>` and `git fetch --prune origin`). Orphan remote branches are strictly prohibited.
- **Commit Standards**: Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`). Concise, effect-driven messages. Never include internal session timestamps (`164259`), review IDs, or prompt phase numbers. Zero standalone tracking commits.

### Pull Request Lifecycle & Review Remediation
- **Sequential PR Processing (FIFO)**: When multiple open PRs exist, process and advance them in strict chronological order (lowest PR number / earliest creation date first). Addressing feedback, fixing CI, and resolving conflicts on older PRs strictly takes precedence over newer PRs. Process only your own PRs. Skip the release-please PR: agents do not touch it.
- **Two-Stage PR Lifecycle**:
  - **Stage 1 (Draft PR)**: Open every PR with `devops pr create`, which always opens a draft. Monitor remote CI checks on push.
  - **Stage 2 (Ready for Review)**: After the checks pass, convert the PR with `devops pr ready <pr_number>` (GraphQL `markPullRequestReadyForReview`; REST API ignores `draft: false`). It is the only path to ready.
- **Mandatory PR Monitoring Gate (`devops pr monitor`)**:
  - Run `devops pr monitor <pr_number>` immediately after opening or updating PRs. Allow at least 5 minutes (300s) for remote CI checks. Wait at least 60s between polls. Copilot reviews a PR only when a person requests it.
  - **Remediate Check Failures Immediately**: Inspect failed logs (`devops gh runs view <run_id> --log-failed`), apply test-first fixes, push, and re-monitor.
  - **In-Thread Review Replies & Resolution**: When review comments are submitted (exit code 2), inspect open threads (`devops pr threads list <pr_number> --unresolved-only`), apply test-first fixes, reply **directly within each review thread** (`devops pr threads reply <thread_id> "<body>"`), and resolve threads (`devops pr threads resolve <thread_id>`). Top-level summary comments alone do not satisfy this requirement.
  - **Merge Readiness Guarantee**: A PR is ready for merging ONLY when `devops pr monitor` exits 0 (all checks green, 0 unresolved threads). Maintainers approve and squash-merge; agents never merge autonomously. See [`docs/SDLC.md`](docs/SDLC.md) Phase 6.

### GitHub Projects, Issues, Views, Milestones & Pages
- **Issue Templates & Milestones**: Intake files new issues in the shape of the templates (`.github/ISSUE_TEMPLATE/`: `bug_report.yml`, `feature_request.yml`), with Conventional Commit titles and taxonomy labels (`type/*`, `scope/*`, `priority/*`). A milestone is a planning bucket that a person sets. It never names a version.
- **PR Closing Keywords**: The PR body closes exactly one open issue with a closing keyword (`Fixes #<id>`, `Closes #<id>`, `Resolves #<id>`). GitHub closes the issue when the PR merges into `main`. The PR changes that issue's task file. `devops pr check-readiness` blocks a body that closes no issue or several.
- **Four Canonical Project Views**: Ground work in `.github/project-template.json` views (*Sprint Kanban*, *Roadmap Timeline*, *Triage & Quality Table*, *Value vs Effort Priority Matrix*). Link board via `devops gh project link <number>`.
- **Triage Auditing**: Regularly run `devops gh issues triage` to detect untriaged issues.
- **GitHub Pages Verification**: Run `devops gh pages verify` to validate Jekyll config (`docs/github-pages.config.yaml`) and docs publishing root.
- **Rate-Managed Tooling**: Always use native CLI commands (`devops pr`, `devops gh`) or FastMCP tools (`pr_monitor`, `gh_rate_limit`, `run_gh`). Bare `gh` invocations are strictly prohibited.

---

## 4. Code Quality & Architectural Standards

- **Separation of Concerns**: Separate configuration, domain logic, data models, network I/O, and user interface layers. Avoid monolithic modules.
- **Purpose-Driven Naming**: Name files, modules, classes and functions for their responsibility (`reference_extractor.py`). Do not use a placeholder (`temp_util.py`, `data`). Do not duplicate or shadow a name across scopes. Ruff `N` checks the form.
- **Config & Defaults Separation**: Distinguish immutable constants (`src/devops_cli/config/constants.py`) from user-configurable defaults (`src/devops_cli/config/defaults.py`).
- **Strict Typing & Modern Idioms**: Enforce type annotations (`mypy --strict`), Python 3.14+ union syntax (`A | B`), standard collections, and Pydantic v2 models with `Field(default_factory=...)`.
- **Test Conventions**: Tests follow [`docs/TESTING.md`](docs/TESTING.md): they double only process edges, each through one shared fake ([ADR 0007](docs/adr/0007-tests-double-only-process-edges.md)), and never hardcode live credentials or endpoints.
- **Standard Parsers Over Brittle Literals**: Never rely on partial collections of string literals or ad-hoc file extensions. Use standard library parsers (`ast`, `tokenize`, `json`, `tomllib`, `yaml`, `urllib.parse`, `ipaddress`) and official specifications (Public Suffix List via `tldextract`, PEP 508 `packaging.requirements`).
- **Pure Markdown Prompt Tasks**: All LLM system prompts and task instructions MUST reside in dedicated Markdown files under `src/devops_cli/ai/tasks/` loaded via `load_task_prompt()`. Inline multi-line prompt strings in Python code are strictly prohibited.
- **Line Breaks Belong to Source Files, Not Output**: Hard-wrap text only where line length limits apply (Python source files, Markdown documents). Never hand-wrap emitted text: terminal messages, Rich renderables, log records, commit bodies, PR descriptions, or `lang/en/` strings. Compose emitted text as continuous paragraphs, splitting source strings via implicit string concatenation across lines rather than inserting embedded `\n`.
- **Canonical Location Formatting**: Terminal output, Rich tables, reports, and findings must format locations as `filename.ext:line` or `filename.ext:n-n`.
- **Zero Hardcoded Scoring**: Never hardcode arbitrary numerical scores or confidence weights. Scoring must originate directly from external tools or structured AI responses; otherwise fields remain `None` or 0.0.
- **Standardized Domain Exception Taxonomy**: All domain error states must raise typed exceptions inheriting from `DevOpsCLIError` under `src/devops_cli/exceptions/`, specifying POSIX exit codes, machine-readable error codes (`CONST_ERROR_CODE_*`), and structured context dictionaries. Bare Python exceptions (`ValueError`, `RuntimeError`) in domain logic are strictly prohibited.
- **Telemetry & Metrics by Default**: Instrument new subcommands, background tasks, and AI pipeline stages with OpenTelemetry distributed spans (`@trace_span`) and Prometheus metrics (`GLOBAL_METRICS`).

---

## 5. Agentic AI & Review System Guidelines

- **Responsible Use of `devops ai` (Token Cost & Local Inference Capacity)**:
  - Every `devops ai` command spends tokens and occupies GPU VRAM and inference slots. These commands are permitted where they are the right tool, not as a default reflex. A question answerable by reading a file or running deterministic checks must be answered that way.
  - **Narrow the request**: Pass the most specific parameters (single file or path, explicit model, bounded result count).
  - **One at a time**: Run **at most one `devops ai` call concurrently**. Never fan out parallel invocations. Concurrent calls queue against finite slots.
  - **Justify the call**: Verify whether the command performs inference before invoking (`devops ai token-count` and `repomap` do not call models).
- **Automated Code Review & Group Analysis**: `devops review` runs tool-anchored inspection across target files, branches, or pull requests using deterministic static analyzers, dependency vulnerability audits, and secret scanning, with bounded model analysis for admitted finding groups.
- **Knowledge Base Grounding**: Ground explanations and remediations against target project conventions and the DevOps CLI Knowledge Base (`src/devops_cli/ai/knowledge_base/`).
- **Review Guards**: The file `.devops/review.md` lists what a review of this repository must not flag. `nearest_review_conventions` loads it.
- **Zero Hallucinated CVEs & Synthetic IDs**: Never synthesize fictitious CVE numbers. Cite advisories only from static scanner outputs (`scan_trivy`, `scan_uv_audit`) or public databases (OSV, NVD). Never call a verified dependency such as `httpx2` malicious without scanner output.
- **Internal Infrastructure vs External SSRF Distinction**: Internal service connectors (Valkey, Vault broker, Kubernetes API, Prometheus, Grafana Loki, Ollama, LiteLLM gateway) reach private networks by design as workstation tooling. Reviewers and analysis stages MUST NOT flag internal service connectors as SSRF vulnerabilities. SSRF applies to untrusted external fetches dialled outside the client factory (`devops_cli.http.client`).
- **Closed-Loop Review & Self-Improvement Cycle**:
  - Agents record no verdicts on review findings: a person records verdicts (`VERIFIED`, `INVALIDATED`, `MITIGATED`, `UNVERIFIED`) with `devops review verify <session> --index <n> --status <STATUS> --reason "..."`.
  - Export verdicts via `devops review export-feedback --status ALL` to `.data/feedback_dataset.jsonl`, read by `devops ai prompt-eval`.
  - Recurring false positives are suppressed via reviewed `[[suppressions]]` in `.devops/review.toml` with a reason and expiry, or via prompt refinements in `src/devops_cli/ai/tasks/`. See [`docs/SELF_IMPROVEMENT.md`](docs/SELF_IMPROVEMENT.md).
- **AI Inference Rate Limit & Token Budget Management**:
  - LLM review stages must budget token consumption and honor provider rate limits (TPM and RPM).
  - Bound concurrency with semaphores (`asyncio.Semaphore(5)` for 4–8 concurrent workers) to prevent overloading inference endpoints.
  - Implement exponential backoff with jitter on HTTP 429 or provider overload errors.
