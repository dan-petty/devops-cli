# Routine Tasks, Order, Frequency & Methodology — devops-cli

This document serves as the authoritative operational manual for developers, maintainers, and AI agents contributing to `devops-cli`. It defines the exact **order of operations**, **execution frequency**, and **engineering methodology** across all routine maintenance, development and security workflows. The workflow `release-merge.yml` merges the release pull request, or a person merges it: [`RELEASE_CYCLE.md`](../RELEASE_CYCLE.md) tells how.

---

## 1. Engineering Principles & Methodology

All routine operations in `devops-cli` adhere to six core engineering tenets:
1. **Deterministic Execution**: Workflows run through standardized CLI commands (`devops ci`, `devops docs`, `uv`) to guarantee reproducible outcomes across local DevContainers and GitHub Actions CI.
2. **Zero-Plaintext Credentials**: No token is stored in git, configuration or logs. Tokens (GitHub, OpenAI, Claude, Grafana, ArgoCD) come from a secret store. Examples are the OS Keyring (`devops config set`, Python `keyring`), the credential store of the owning tool and a Kubernetes Secret in the cluster.
3. **Strict Quality Assurance**: Changes must pass every check that `devops ci` runs before merging ([`SDLC.md`](SDLC.md), Phase 4, lists them).
4. **Target Branch & Non-Merge Policy**: Every topic PR targets `main`, and nobody pushes to `main`. Only a person merges a pull request ([`AGENTS.md`](../AGENTS.md)).
5. **Dynamic Documentation Freshness**: Command matrices, CLI reference guides, and FastMCP schemas are generated dynamically through code introspection (`devops docs generate`) and verified in CI (`devops docs check`).
6. **Mandatory Defect Incident Tracking (Zero Unrecorded CLI Errors/Warnings)**: Whenever a CLI command produces an unhandled error, subcommand failure, crash, diagnostic warning, or unexpected behavior, agents and maintainers must first search the open issues (`devops gh api "search/issues?q=repo:<owner>/<repo>+is:issue+is:open+<check or error text>"`) and, when one covers the defect, comment there with the new evidence and file nothing. Else they must promptly file it as a candidate (`devops roadmap intake --title "fix(<scope>): …" --body-file <file> --confirm`), in the shape of the standardized bug report template. Intake checks it for a duplicate, labels its type, Status, Value, Effort and Priority, and puts it in the backlog; nobody sets a milestone or priority on the new issue by hand. [`SDLC.md`](SDLC.md), Phase 1, Roadmap & Backlog Synchronization, gives the rules of a filed candidate.


---

## 2. Master Routine Tasks Matrix

The following matrix categorizes all project routine tasks by operational layer, defining their exact sequence, cadence, and verification criteria:

| Operational Cadence | Routine Task | Sequence Order | Primary Command(s) | Methodology & Scope | Success Verification Gate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Inner Loop (Daily / Per Edit)** | Task Grounding | Step 1 | `devops gh issues triage` && `devops roadmap intake` | Verify the labels of the issue, or file the work through intake | Task grounded in an open issue with a `priority/*` label |
| **Inner Loop (Daily / Per Edit)** | Dependency Synchronization | Step 2 | `uv sync` | Synchronizes virtual environment with `uv.lock` | Clean exit; all dependencies resolved |
| **Inner Loop (Daily / Per Edit)** | Constant & Config Placement | Step 3 | Manual / Refactor | Put each table beside its one owner, and in `config/` once a second package imports it; put messages in `lang/en/` | No hardcoded string literals in command code |
| **Inner Loop (Daily / Per Edit)** | Targeted Linting & Formatting | Step 4 | `uv run ruff check --fix <file>` | Fast focused linting on modified files | `ruff check` reports 0 errors |
| **Inner Loop (Daily / Per Edit)** | Targeted Type Checking | Step 5 | `uv run mypy --strict <file>` | Strict type validation on modified modules | 0 type errors across modified files |
| **Inner Loop (Daily / Per Edit)** | Targeted Unit Testing | Step 6 | `uv run devops ci test <test-file>` | Fast isolated testing of active features/fixes, with xdist workers sized to the selection | Targeted tests pass |
| **Inner Loop (Daily / Per Edit)** | Telemetry, Log & CLI Output Review | Step 7 | `devops telemetry status` / log inspection | Inspect CLI command outputs, `.data/logs/`, metrics, and tracing spans for performance bottlenecks, misconfigurations, and warnings | Clean logs, no warnings, nominal latencies |
| **Final Pre-Commit / Pre-PR** | Documentation & README Sync | Step 1 | `uv run devops docs generate --sync-readme` | CLI introspection & README Command Matrix update | `uv run devops docs check` passes |
| **Final Pre-Commit / Pre-PR** | Full Parallel Test Suite | Step 2 | `uv run pytest` | Complete parallel test run (`addopts`' `-n logical --dist worksteal`) | All tests pass |
| **Final Pre-Commit / Pre-PR** | Full CI Validation Suite | Step 3 | `uv run devops ci` | Runs the full automated verification suite by hand, when you want it before the push. The required checks of CI gate the merge | All checks show `✓ pass` |
| **Final Pre-Commit / Pre-PR** | Observability, Log & Trace Audit | Step 4 | `devops telemetry status` / `.data/logs/` | Audit CLI command outputs, application logs, metrics, and OpenTelemetry tracing data for performance issues and misconfigurations | Zero unhandled exceptions or warnings in logs/spans |
| **Feature / PR Lifecycle** | Branch Creation | Step 1 | `devops repos worktrees add <issue> --type <type> --slug <slug>` | Dedicated worktree and topic branch off the fetched `origin/main`, named as [CONTRIBUTING.md](../CONTRIBUTING.md#5-naming) says; the command takes over a staged branch that the App pushed for the issue, and refuses an issue that a worktree or any other pushed branch already holds | Clean worktree based on `origin/main` |
| **Feature / PR Lifecycle** | PR Submission | Step 2 | `devops pr create --title "<type>(<scope>): <summary>"` | Opens a draft PR into `main`; the title becomes the changelog line | Draft PR opened with Conventional Commit title |
| **Feature / PR Lifecycle** | Taxonomy Linking | Step 3 | `devops gh labels audit` | Audits open PRs for mandatory `type/*` and `scope/*` labels | Zero taxonomy audit findings |
| **Feature / PR Lifecycle** | PR Monitoring & Review Resolution | Step 4 | `devops pr monitor <pr_number>`, then `devops pr ready <pr_number>` | Actively monitors checks and any review a person requested, remediates in-thread, then marks the draft ready | All checks green, requested reviews settled, 0 unresolved threads |
| **Feature / PR Lifecycle** | AI Code Review | Step 5 | `devops ai review branch <name> --dry-run` | Automated review and group analysis | Findings inspected in `.data/reviews/` |
| **Feature / PR Lifecycle** | Human Squash Merge | Step 6 | GitHub web UI (a person) | Maintainer squash-merges the approved PR into `main` | PR merged and topic branch deleted |
| **Feature / PR Lifecycle** | Remote Branch Audit & Pruning | Step 7 | `git fetch --prune origin` | Prunes merged, closed, or superseded remote tracking branches | Zero orphan remote branches on origin |
| **Release (scheduled)** | Release Pull Request Merge | Every 6 hours | `release-merge.yml`, or a person in the GitHub web UI | The workflow merges the release-please pull request when it passes the guards; a person can merge it at any time or hold it with the label `hold-release`. `release.yml` then publishes. Agents have no step ([`RELEASE_CYCLE.md`](../RELEASE_CYCLE.md)) | GitHub release, tag, packages and images published |
| **Security & Audits** | Dependency Security Audit | Weekly | `uv run devops ci audit` (`uv audit`, `npm audit`) | Scans installed packages and the lockfile of each Node tool in `tools.lock` for known vulnerabilities | 0 known vulnerabilities |
| **Security & Audits** | Ignore Entry Renewal | Daily / Pre-PR | `git grep -n 'exp:' .trivyignore` | Renews or drops each ignore entry before its `exp:` date, as [SECURITY.md](../SECURITY.md#a-finding-with-no-fix) says | No entry is past its date; the image scans pass |
| **Security & Audits** | Static Security Scan (SAST) | Weekly | `uv run devops ci security` (`bandit`) | Static security scan for code vulnerabilities | 0 issues in `src/`; 0 high/medium issues in `tests/` |
| **Security & Audits** | Kubernetes Manifest Scans | Per Manifest Change | `devops k8s lint` / `devops k8s check-deprecated` / `devops scan trivy <dir> --type config` | Validates manifests against K8s security best practices (cluster health: `devops k8s audit`) | Zero deprecated APIs or misconfigurations |
| **Security & Audits** | Codebase Deduplication & Invariant Audit | Weekly / Pre-PR | `uv run ruff check --config pyproject.toml .` && `uv run devops ci test tests/invariants/test_architectural_invariants.py tests/commands/test_ruff_complexity_cap.py` | Ruff `C901` caps complexity at 10 and `PLR1702` caps nesting at 4 blocks; the tests hold their configuration, the `C901` marker ceiling and shared helper adoption | Zero invariant violations |
| **Observability & Diagnostics** | Command Output, Logs, Metrics & Trace Audit | Continuous / On Execution | `devops telemetry status` / `devops telemetry logfire` | Comprehensive review of command outputs, application logs (`.data/logs/`), metrics, and tracing spans for latency, misconfigurations, and warnings | Nominal latencies, zero unhandled errors/warnings |
| **Workspace & Sync** | DevContainer Lifecycle Hooks | Daily / On Start | `devops devcontainer run-lifecycle --post-start` | Cross-platform container initialization tasks | All lifecycle tasks complete successfully |
| **Workspace & Sync** | Multi-Repo Synchronization | Daily / On Demand | `devops repos sync` / `devops repos list` | Pulls upstream changes across all managed repos | All repositories up to date |
| **Workspace & Sync** | GitHub Pages Publishing & Readiness Audit | Pre-PR | `devops gh pages status` / `devops gh pages verify` | Inspects live publishing health, HTTPS enforcement, and validates `docs/_config.yml`, the site settings that the Pages build reads, and `docs/` | Clean verification; HTTPS strictly enforced |
| **Workspace & Sync** | GitHub Issues Lifecycle & Triage Audit | Daily / Pre-PR | `devops gh issues triage` / `devops gh issues status` | Audits open issues for mandatory taxonomy labels (`type/*`, `scope/*`) and a `priority/*` label, and reports those with no `priority/*` label as awaiting intake | Zero untriaged open issues; `devops roadmap intake` clears those awaiting intake |
| **Workspace & Sync** | GitHub Projects & Issues Views Sync & Audit | On Demand | `devops gh project sync` / `devops gh project audit` / `devops gh views audit` | Provisions and links the board, reconciles card fields, and audits the 4 declarative project views | All projects and views populated with zero drift or empty state (`projects` & `issues/views`) |
| **Workspace & Sync** | SSH Keys & Host Audit | On Demand | `devops ssh status` / `devops ssh audit` | Validates ED25519 keys, permissions, and GitHub keys | No keys past rotation_days |
| **Workspace & Sync** | Roadmap Implement Job (Service) | Every 7 minutes (row `implement`) | `kubectl -n devops get jobs -l implement-repo` / `devops roadmap implement --repo <owner/name> --item <number> --confirm` | The Service makes one runner Job per repository at a time for a Staged or Planned item, reports each Job that ended on its item, and sets Blocked on an item whose Job left it eligible, then clears that stop on a retry, on a continuation of a Job with no result, or on a new runner image | No Job ends without a comment on its item; no item runs twice after a failed Job until a person comments `implement: retry`, the Service continues a Job with no result (at most `roadmap.implement.continuations_per_item` times), or one new runner image rolls out |
| **Process** | Standards Pass | After a batch of decided workflow changes | `devops pr create` (one documents pull request) | Put each rule that people and agents can follow now in its owning document ([`AGENTS.md`](../AGENTS.md), Where to look). Text about a feature that is not built goes into the pull request of that feature. Each tracker gets one comment that lists the documents that its children must change | Each rule is in one document, and no document states a feature that `main` does not have |


---

## 3. Detailed Workflow Methodologies

### Cadence A: Inner Loop (Test-First Iterative Feature Development)

The Inner Development Loop follows a strict **Test-First Development (TDD)** methodology. Author tests first as living specifications of intended functionality before writing implementation code. Run targeted tests and linters for immediate feedback; do NOT run the full test suite during this inner loop.

```mermaid
flowchart TD
    A[Requirement / Feature Goal] --> B[1. Project Planning & Task State Setup]
    B --> C[2. uv sync Dependencies]
    C --> D[3. Place Constants & Defaults]
    D --> E[4. Write Tests First in tests/test_*.py]
    E --> F[5. Implement Feature Code in src/]
    F --> G[6. ruff check & format modified files]
    G --> H[7. mypy target files]
    H --> I[8. pytest target test file]
```

#### Step-by-Step Order:
1. **GitHub Project Bootstrap, Issue Grounding & Task State Setup**:
   - **Inspect the Triage Queue**: Read the triage queue with `devops gh issues triage` (or FastMCP `gh_issues_triage`). The labels of each issue hold its state, so this step does not read the project board.
   - **Ground Requirement in a GitHub Issue**: Every feature, bug fix, or refactor must map to an open issue that is a roadmap item: it holds a `priority/*` label.
     - If a matching issue exists: link the task to it and verify its taxonomy labels.
     - Without a matching issue: **FILE THE TASK AS A CANDIDATE** (`devops roadmap intake --title "<conventional title>" --body-file <file> --confirm` or FastMCP `roadmap_intake` with `mode="confirm"`). Intake files it (a possible duplicate too, which its reason comment names for a person to close), labels its type, Status, Priority, Value and Effort, and puts it in the backlog; set no milestone or priority on it yourself.
   - Plan the item as an OpenSpec change, `openspec/changes/<issue>-<slug>/` ([`openspec/config.yaml`](../openspec/config.yaml)). The labels of the issue hold the Status of the item, and the change folder holds none.
2. **Sync Dependencies (`uv sync`)**: Always ensure `.venv` is aligned with `uv.lock` before starting work.
3. **Place Constants, Config & Defaults**:
   - Put configuration options and environment variable schemas in [`src/devops_cli/config/settings.py`](../src/devops_cli/config/settings.py).
   - Put a constant, regex, protocol string, timeout or numeric default beside its one owner. Move it to [`src/devops_cli/config/constants.py`](../src/devops_cli/config/constants.py) or [`src/devops_cli/config/defaults.py`](../src/devops_cli/config/defaults.py) only when a second package imports it ([CONTRIBUTING.md](../CONTRIBUTING.md), "Closed Lists and Standard Parsers").
   - Put user-facing messages, summaries, and error logs in [`src/devops_cli/lang/en/`](../src/devops_cli/lang/en/).
4. **Leverage Shared Domain Helpers & Declarative Frameworks**:
   - Before writing ad-hoc subprocess calls, path containment checks, binary verification, or secret sanitization, always leverage the shared helper ecosystem:
     - `devops_cli.core.binaries.check_binary` / `require_binary` for external tool checks.
     - `devops_cli.core.paths.safe_resolve_subpath` for filesystem containment and traversal prevention.
     - `devops_cli.core.process.run_json_subprocess` and `devops_cli.core.serialization.extract_json_block` for robust JSON subprocess handling.
     - `devops_cli.security.sanitizer.mask_secrets` for credential masking.
     - `devops_cli.dry_run.decorator.dry_run_command` for state-mutating command dry-runs.
     - `devops_cli.security.base.BaseSecurityScanner` for security linters.
5. **Write Tests First (Living Functional Specification)**:
   - Write the tests that state the intended behaviour, edge cases and error conditions before the code, following [`docs/TESTING.md`](TESTING.md) for where they go, what they may double and what they assert.
6. **Implement Feature Logic**:
   - Author clean, concise, domain-driven implementation code in `src/` specifically to satisfy the pre-written tests with zero extraneous boilerplate.
7. **Format & Lint Target Files**:
   ```bash
   uv run ruff check --fix <modified_paths>
   uv run ruff format <modified_paths>
   ```
8. **Verify Static Types for Target Files**:
   ```bash
   uv run mypy --strict <modified_paths>
   ```
9. **Run Targeted Unit Tests**:
   ```bash
   uv run devops ci test tests/test_<feature>.py -k <test_name>
   ```
10. **Review CLI Command Outputs, Application Logs, Metrics & Tracing Data**:
   - Actively inspect terminal command outputs, application logs (under `.data/logs/`), metrics, and distributed tracing spans (`@trace_span` / Logfire / OpenTelemetry) emitted during execution.
   - Check for performance regressions, latency bottlenecks, misconfigurations, unhandled exceptions, and deprecation or diagnostic warnings.
   - If any error or warning is discovered, immediately file a tracking issue per Tenet 6 and resolve before proceeding.

---

### Cadence A (final stage): Pre-Commit / Pre-PR Validation

Executed at the final stage of work after all iterative feature modifications and targeted tests pass:

1. **Regenerate Documentation & Check Freshness**:
   ```bash
   uv run devops docs generate --sync-readme
   uv run devops docs check
   ```
2. **Optional: Run the Full Local CI Validation Suite by Hand**: The pre-push hook runs only the fast static checks, and the required checks of CI gate the merge ([`docs/SDLC.md`](SDLC.md), Phase 4).
   ```bash
   uv run devops ci
   ```
3. **Audit Observability, Telemetry & Application Logs**:
   - Review execution durations, OpenTelemetry spans, metric gauges, and application log output generated during test runs and CLI executions.
   - Verify absence of performance bottlenecks, resource leaks, configuration warnings, or suppressed exceptions.
4. **Validate GitHub Governance, Pages Readiness & Issues Triage**:
   - Verify the syntax and the required keys of `docs/_config.yml`, the one file of site settings that the Pages build reads, and the `docs/` publishing root, with `devops gh pages verify`.
   - Audit open issues for mandatory taxonomy labels (`type/*`, `scope/*`) and a `priority/*` label via `devops gh issues triage`, and run `devops roadmap intake` for those it reports as awaiting intake.
   - Inspect issue portfolio distribution via `devops gh issues status`.


---

### Cadence B: Feature & Pull Request Lifecycle

Executed for every new feature, bug fix, refactor, or documentation update.

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer / Agent
    participant Git as Git Repo
    participant Hub as GitHub (main)
    participant CI as GitHub Actions
    actor Maintainer as Human Maintainer

    Dev->>Git: devops repos worktrees add <issue> --type <type> --slug <slug>
    Dev->>Git: Code, Test, Format, devops ci
    Dev->>Hub: git push -u origin <branch>
    Dev->>Hub: devops pr create (opens a draft into main)
    Hub->>CI: Trigger CI Validation
    CI-->>Hub: CI Checks Pass (Green)
    Dev->>Hub: Push additional fixes if needed (git push)
    Dev->>Hub: devops pr ready <pr_number>
    Maintainer->>Hub: Review & squash-merge in the web UI
```

#### Rules & Methodology:
[`docs/SDLC.md`](SDLC.md), Phase 6, holds the rules of a pull request from the branch to the merge: the push rule, the draft, the order of work, the watch, the review threads and the branch deletion. [`CONTRIBUTING.md`](../CONTRIBUTING.md), sections 4 and 5, holds the title, the body, the commits and the names. This cadence does not repeat them.

---

### Cadence C: Releases (a Scheduled Merge)

release-please opens and updates the release pull request, and the workflow `release-merge.yml` merges it every 6 hours unless a person holds it. [`RELEASE_CYCLE.md`](../RELEASE_CYCLE.md) is the procedure, and this cadence does not repeat it.

---

### Cadence D: Security, Vulnerability & Dependency Audits

Executed weekly, or when dependencies are updated.

#### 1. Dependency Vulnerability Audit (`uv audit`, `npm audit`)
- **Frequency**: Weekly & in every CI run.
- **Methodology**: Scans packages in `uv.lock` against Open Source Vulnerabilities (OSV) database, and the `package-lock.json` of each Node tool in `tools.lock` against npm's advisory database, without installing it.
- **Command**: `uv run devops ci audit`, or `uv audit` and `npm audit --package-lock-only --json --prefix src/devops_cli/tools_lock/<tool>`.
- **Ignore entries**: An entry in `.trivyignore` expires by itself, and the scan fails after its `exp:` date. Before the date, renew or drop the entry as [SECURITY.md](../SECURITY.md#a-finding-with-no-fix) says. This document does not repeat that rule.

#### 2. Static Application Security Testing (SAST - `bandit`)
- **Frequency**: Pre-commit / CI gate.
- **Methodology**: Analyzes AST for common security pitfalls (unsafe subshell calls, hardcoded passwords, weak crypto).
- **Scope**: `src/` at low severity and above, and `tests/` at medium and above: the targets `.bandit` names, with the four low rules it skips (B404, B603, B110, B112) and the reasons it gives. A `# nosec` in `src/` names its rules and, after a second `#`, the reason.
- **Command**: `uv run devops ci security`, or `uv run bandit -r src --ini .bandit --severity-level low` and `uv run bandit -r tests --ini .bandit --severity-level medium`.

#### 3. Kubernetes & IaC Security Scans
- **Frequency**: Whenever `k8s/` or `tf/` manifests are modified.
- **Methodology**: Uses Kube-linter, Pluto (deprecated API versions), Popeye (cluster sanitization), and Trivy (misconfigurations and vulnerabilities).
- **Commands**:
  ```bash
  devops k8s lint k8s/
  devops k8s check-deprecated k8s/
  devops scan trivy k8s/ --type config
  ```

#### 4. SSRF Guardrails & OS Keyring Audit
- **Methodology**: Every HTTP client is built by `devops_cli.http.entry` and checked at the connect: untrusted URLs at the public level, configured services at loopback (private once `ai.allow_private_network` is set), internal infrastructure at private. Kept pre-flight checks (Qdrant, kubectl manifest apply, container engine endpoint, config init wizard) call `vet_addresses` directly at their level. Cloud metadata endpoints are always rejected; other link-local addresses only at the public and loopback levels.

#### 5. AI Code Review Verification, Feedback Export & Self-Improvement Loop
- **Frequency**: After running AI code reviews or before PR approval.
- **Methodology**:
  1. Inspect structured review findings across sessions:
     ```bash
     devops ai review findings --session <session-id>
     ```
  2. Record a person's verdict:
     - No model verifies a finding; a person verifies or invalidates each with specific rationale:
     ```bash
     devops ai review verify <session-id> --index 1 --status INVALIDATED --reason "False positive on valid exception tuple"
     ```
  3. Append the verdicts to the feedback dataset for prompt tuning, DPO alignment, and model calibration:
     ```bash
     devops ai review export-feedback --status ALL
     ```
  4. Continuous Self-Improvement Loop:
     - Regularly analyze the feedback dataset, `.data/feedback_dataset.jsonl` (`data.feedback_dataset_path`), to identify recurring false positives; record each as a `[[suppressions]]` entry in `.devops/review.toml` with a reason and an expiry, or refine the persona domain prompts (`devsecops`, `architect`, `auditor`, `pm`, `qa`).

---

### Cadence E: Workspace & Infrastructure Synchronization

Executed on workspace initialization (DevContainer startup) or on-demand.

#### 1. DevContainer Lifecycle Hooks
- **Frequency**: On container creation (`postCreateCommand`) and container startup (`postStartCommand`).
- **Methodology**: Runs the Python lifecycle engine: bootstraps missing tools and the keyring, configures shell history/completion, git defaults and SSH commit signing, kubeconfig, and pre-commit hooks.
- **Commands**:
  ```bash
  devops devcontainer run-lifecycle --post-create
  devops devcontainer run-lifecycle --post-start
  ```

#### 2. Multi-Repository Synchronization
- **Frequency**: Daily or before multi-repo reviews.
- **Methodology**: Discovers all configured git repositories in workspace, pulls latest commits from tracked remotes, and reports branch statuses.
- **Commands**:
  ```bash
  devops repos sync
  devops repos list
  ```

#### 3. SSH Key & Host Security Audit
- **Frequency**: On-demand / Monthly.
- **Methodology**: Lists the managed SSH keys of the project prefix with age and rotation status (`devops ssh audit`/`list`, or `--all` for the keys of all projects) and shows the active key and days until rotation (`devops ssh status`).
- **Commands**:
  ```bash
  devops ssh status
  devops ssh audit
  ```

#### 4. GitHub Governance, Pages, Issues & Views Auditing
- **Frequency**: Pre-PR or On-Demand.
- **Methodology**:
  - Validates GitHub Pages deployment health and verifies local publishing assets (`docs/_config.yml` and `docs/`).
  - Audits live open issues for missing taxonomy labels (`type/*`, `scope/*`) or a missing `priority/*` label.
  - On demand only: audits remote GitHub Projects v2 boards and views against `.github/project-template.json` to prevent configuration drift. See [`SDLC.md`](SDLC.md), Phase 1, Status Lives on GitHub.
- **Commands**:
  ```bash
  devops gh pages status
  devops gh pages verify
  devops gh issues triage
  devops gh issues status
  devops gh project audit
  devops gh views audit
  ```

#### 5. Roadmap Implement Job (Runner)
- **Frequency**: Continuous. The Service's row `implement` is due every 7 minutes ([k8s/README.md](../k8s/README.md), Roadmap service step 16).
- **Methodology**: The Service makes one runner Job for the first Staged or Planned item of a repository, and makes no second Job while one runs. [k8s/README.md](../k8s/README.md), Runner Jobs, gives the image, the size, the deadline, the Role and the guarantees. [ROADMAP_WORKFLOW.md](ROADMAP_WORKFLOW.md), The stop and retry path, gives the stops and the retries.
- **Commands**:
  ```bash
  kubectl -n devops get jobs -l implement-repo
  kubectl -n devops logs job/<name>
  devops roadmap implement --repo <owner/name> --item <number> --dry-run
  devops roadmap implement --repo <owner/name> --item <number> --confirm
  ```
  The last command makes the same Job by hand with the code of `devops k8s run-job --template runner`, follows its log, and refuses a claimed item, an item that is neither Ready nor Planned, and a repository that has a runner Job that has not ended.

---

## 4. Failure Recovery & Troubleshooting Matrix

| Failure Scenario | Root Cause | Remediation Procedure |
| :--- | :--- | :--- |
| `devops ci` fails at `format` | Unformatted code or non-compliant line lengths | Run `uv run ruff format .` and re-run `devops ci`. |
| `devops ci` fails at `lint` | Unused imports, bad syntax, or sorting violations | Run `uv run ruff check --fix .` and resolve manual warnings. |
| `devops ci` fails at `typecheck` | Missing type annotations or strict type mismatch | Run `uv run mypy --strict src` to pinpoint offending line and type. |
| `devops ci` fails at `docs` | CLI commands or flags changed without updating docs | Run `uv run devops docs generate --sync-readme` and verify with `devops docs check`. |
| `pytest` intermittent test failures | Non-deterministic test ordering in multi-threaded code | Ensure assertions use order-independent checks (`any(...)` or sets) rather than fixed array indices. |
| `uv audit` reports vulnerability | A dependency has a known security advisory | Run `uv lock --upgrade-package <name>` and verify compatibility. |
| `npm audit` reports vulnerability | A package in a Node tool's `package-lock.json` has a known security advisory | Bump the tool with the runbook in the header of `src/devops_cli/tools_lock/tools.lock`. |
| `devops ci audit` says an audit could not run | The registry is unreachable or serves no advisories endpoint; npm exits 1 for this as for a finding, uv exits 2 | Read the output above the verdict, restore the network or registry configuration and re-run. |
| Agent PR targeting error | Topic PR opened against a base other than `main` | Update PR base branch via `devops pr edit <id> --base main`. |
